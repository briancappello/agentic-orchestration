// Package sortieclient tells Sortie about an ACP broker's session: that
// humans hold the run, that they released it, and that the agent needs a
// person. Calls authenticate with the run's scoped session token and
// never block the caller: one worker brings Sortie to the desired state,
// retrying with capped backoff.
package sortieclient

import (
	"bytes"
	"cmp"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"
)

// Holder is the holder name the broker gives Sortie.
const Holder = "acp-broker"

// Defaults for the retry and request bounds.
const (
	DefaultMinBackoff     = 500 * time.Millisecond
	DefaultMaxBackoff     = 30 * time.Second
	DefaultRequestTimeout = 10 * time.Second
	maxQueuedEscalations  = 32
)

// Config names the Sortie run a client reports on.
type Config struct {
	// BaseURL is Sortie's HTTP server, as SORTIE_API_URL gives it.
	BaseURL string

	// Identifier is the issue the run serves, SORTIE_ISSUE_IDENTIFIER.
	Identifier string

	// Token is the run's session token, SORTIE_SESSION_TOKEN.
	Token string

	HTTP           *http.Client
	Logger         *slog.Logger
	MinBackoff     time.Duration
	MaxBackoff     time.Duration
	RequestTimeout time.Duration
}

// Escalation asks Sortie to call people about the run.
type Escalation struct {
	Message string `json:"message"`
	Kind    string `json:"kind"`
	URL     string `json:"url,omitempty"`
}

// Client reconciles Sortie's hold state with the broker's and delivers
// escalations. Construct with New and start with Run.
type Client struct {
	cfg Config
	log *slog.Logger

	mu          sync.Mutex
	wantHeld    bool
	wantReason  string
	isHeld      bool
	everHeld    bool
	escalations []Escalation
	wake        chan struct{}
	stopped     chan struct{}
}

// New returns a client for cfg.
func New(cfg Config) *Client {
	if cfg.HTTP == nil {
		cfg.HTTP = &http.Client{}
	}
	if cfg.MinBackoff <= 0 {
		cfg.MinBackoff = DefaultMinBackoff
	}
	if cfg.MaxBackoff <= 0 {
		cfg.MaxBackoff = DefaultMaxBackoff
	}
	if cfg.RequestTimeout <= 0 {
		cfg.RequestTimeout = DefaultRequestTimeout
	}
	log := cfg.Logger
	if log == nil {
		log = slog.Default()
	}
	return &Client{cfg: cfg, log: log, wake: make(chan struct{}, 1), stopped: make(chan struct{})}
}

// SetHold sets the desired hold state: held with reason when reason is
// non-empty, released otherwise. It returns at once.
func (c *Client) SetHold(reason string) {
	c.mu.Lock()
	c.wantHeld = reason != ""
	if c.wantHeld {
		c.wantReason = reason
	}
	c.mu.Unlock()
	c.signal()
}

// Escalate queues an escalation. It returns at once; when too many are
// queued, the oldest is dropped.
func (c *Client) Escalate(e Escalation) {
	c.mu.Lock()
	if len(c.escalations) >= maxQueuedEscalations {
		c.log.Warn("dropping a queued escalation", slog.String("kind", c.escalations[0].Kind))
		c.escalations = c.escalations[1:]
	}
	c.escalations = append(c.escalations, e)
	c.mu.Unlock()
	c.signal()
}

func (c *Client) signal() {
	select {
	case c.wake <- struct{}{}:
	default:
	}
}

// Run delivers the desired state until ctx ends.
func (c *Client) Run(ctx context.Context) {
	defer close(c.stopped)
	backoff := time.Duration(0)
	for {
		switch {
		case backoff > 0:
			timer := time.NewTimer(backoff)
			select {
			case <-ctx.Done():
				timer.Stop()
				return
			case <-timer.C:
			}
		case !c.pending():
			select {
			case <-ctx.Done():
				return
			case <-c.wake:
			}
		}
		if ctx.Err() != nil {
			return
		}
		if c.step(ctx) {
			backoff = 0
		} else {
			backoff = c.nextBackoff(backoff)
		}
	}
}

func (c *Client) nextBackoff(current time.Duration) time.Duration {
	if current <= 0 {
		return c.cfg.MinBackoff
	}
	return min(2*current, c.cfg.MaxBackoff)
}

// pending reports whether anything is left to deliver.
func (c *Client) pending() bool {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.wantHeld != c.isHeld || len(c.escalations) > 0
}

// step delivers one piece of the desired state and reports whether it
// succeeded or had nothing to do.
func (c *Client) step(ctx context.Context) bool {
	c.mu.Lock()
	wantHeld, reason, isHeld := c.wantHeld, c.wantReason, c.isHeld
	var esc *Escalation
	if wantHeld == isHeld && len(c.escalations) > 0 {
		esc = &c.escalations[0]
	}
	c.mu.Unlock()

	switch {
	case wantHeld != isHeld:
		var err error
		if wantHeld {
			err = c.post(ctx, "hold", map[string]string{"reason": reason, "holder": Holder})
		} else {
			err = c.post(ctx, "release", nil)
		}
		if err != nil {
			c.log.Warn("sortie hold update failed; retrying", slog.Bool("held", wantHeld), slog.Any("error", err))
			return false
		}
		c.mu.Lock()
		c.isHeld = wantHeld
		c.everHeld = c.everHeld || wantHeld
		c.mu.Unlock()
		c.log.Info("sortie hold updated", slog.Bool("held", wantHeld), slog.String("reason", reason))
		return true
	case esc != nil:
		err := c.post(ctx, "escalate", *esc)
		if err != nil && retryable(err) {
			c.log.Warn("sortie escalation failed; retrying", slog.String("kind", esc.Kind), slog.Any("error", err))
			return false
		}
		c.mu.Lock()
		c.escalations = c.escalations[1:]
		c.mu.Unlock()
		if err != nil {
			c.log.Warn("sortie refused an escalation", slog.String("kind", esc.Kind), slog.Any("error", err))
		} else {
			c.log.Info("escalated to sortie", slog.String("kind", esc.Kind))
		}
		return true
	}
	return true
}

// Close stops Run, waiting for it to return, and then makes one final
// release attempt bounded by ctx when Sortie may still hold the run.
func (c *Client) Close(ctx context.Context, stopRun context.CancelFunc) {
	stopRun()
	select {
	case <-c.stopped:
	case <-ctx.Done():
	}
	c.mu.Lock()
	release := c.isHeld || c.everHeld || c.wantHeld
	c.mu.Unlock()
	if !release {
		return
	}
	if err := c.post(ctx, "release", nil); err != nil {
		c.log.Warn("final sortie release failed", slog.Any("error", err))
		return
	}
	c.log.Info("final sortie release sent")
}

// statusError is a response Sortie answered with a status other than 2xx.
type statusError struct {
	status int
	body   string
}

func (e *statusError) Error() string {
	return fmt.Sprintf("sortie answered %d: %s", e.status, e.body)
}

// retryable reports whether a failed call may succeed later: a transport
// failure or a 5xx answer. A 4xx answer is final.
func retryable(err error) bool {
	if se, ok := errors.AsType[*statusError](err); ok {
		return se.status >= 500
	}
	return true
}

func (c *Client) post(ctx context.Context, action string, body any) error {
	ctx, cancel := context.WithTimeout(ctx, c.cfg.RequestTimeout)
	defer cancel()
	var payload io.Reader = http.NoBody
	if body != nil {
		data, err := json.Marshal(body)
		if err != nil {
			return err
		}
		payload = bytes.NewReader(data)
	}
	endpoint := strings.TrimRight(c.cfg.BaseURL, "/") + "/api/v1/" + url.PathEscape(c.cfg.Identifier) + "/" + action
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, payload)
	if err != nil {
		return err
	}
	req.Header.Set("Authorization", "Bearer "+c.cfg.Token)
	req.Header.Set("Content-Type", "application/json")
	resp, err := c.cfg.HTTP.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close() //nolint:errcheck // the body is read below; a close error changes nothing
	if resp.StatusCode/100 == 2 {
		_, _ = io.Copy(io.Discard, resp.Body)
		return nil
	}
	data, _ := io.ReadAll(io.LimitReader(resp.Body, 512))
	return &statusError{status: resp.StatusCode, body: strings.TrimSpace(string(data))}
}

// brokerReportMaxDelay caps the backoff between broker report attempts.
const brokerReportMaxDelay = 30 * time.Second

// brokerReportFirstDelay is the first backoff delay of a broker report
// when the configuration sets no MinBackoff.
const brokerReportFirstDelay = time.Second

// ReportBroker tells Sortie the broker's HTTP viewer address and token,
// so clients can find the session through Sortie. It retries a transport
// failure or a 5xx answer with backoff, capped at 30 s, until it succeeds,
// a 4xx answer makes it final, or ctx ends. A failure never affects the
// session: it is only logged.
func (c *Client) ReportBroker(ctx context.Context, httpURL, viewerToken string) {
	delay := cmp.Or(c.cfg.MinBackoff, brokerReportFirstDelay)
	for {
		err := c.post(ctx, "broker", map[string]string{"http_url": httpURL, "viewer_token": viewerToken})
		switch {
		case err == nil:
			c.log.Info("broker address reported to sortie", slog.String("http_url", httpURL))
			return
		case !retryable(err):
			c.log.Warn("sortie refused the broker address", slog.Any("error", err))
			return
		case ctx.Err() != nil:
			return
		}
		c.log.Warn("broker address report failed, retrying", slog.Any("error", err), slog.Duration("retry_in", delay))
		select {
		case <-ctx.Done():
			return
		case <-time.After(delay):
		}
		delay = min(delay*2, brokerReportMaxDelay)
	}
}
