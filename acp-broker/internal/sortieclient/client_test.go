package sortieclient

import (
	"context"
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

type request struct {
	path, auth string
	body       map[string]any
}

type fakeSortie struct {
	mu       sync.Mutex
	requests []request
	failures atomic.Int64 // answer 503 this many more times
	hang     chan struct{}
}

func (f *fakeSortie) handler(w http.ResponseWriter, r *http.Request) {
	if f.hang != nil {
		select {
		case <-f.hang:
		case <-r.Context().Done():
			return
		}
	}
	data, _ := io.ReadAll(r.Body)
	var body map[string]any
	_ = json.Unmarshal(data, &body)
	f.mu.Lock()
	f.requests = append(f.requests, request{path: r.URL.Path, auth: r.Header.Get("Authorization"), body: body})
	f.mu.Unlock()
	if f.failures.Load() > 0 {
		f.failures.Add(-1)
		w.WriteHeader(http.StatusServiceUnavailable)
		return
	}
	w.WriteHeader(http.StatusOK)
}

func (f *fakeSortie) recorded() []request {
	f.mu.Lock()
	defer f.mu.Unlock()
	return append([]request(nil), f.requests...)
}

func (f *fakeSortie) waitFor(t *testing.T, n int) []request {
	t.Helper()
	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		if got := f.recorded(); len(got) >= n {
			return got
		}
		time.Sleep(5 * time.Millisecond)
	}
	t.Fatalf("sortie got %d requests, want %d: %+v", len(f.recorded()), n, f.recorded())
	return nil
}

func newTestClient(t *testing.T, f *fakeSortie) (*Client, context.CancelFunc) {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(f.handler))
	t.Cleanup(srv.Close)
	c := New(Config{
		BaseURL: srv.URL, Identifier: "LIVE-1", Token: "session-token-x",
		Logger: slog.New(slog.DiscardHandler), MinBackoff: 10 * time.Millisecond, MaxBackoff: 40 * time.Millisecond,
		RequestTimeout: 2 * time.Second,
	})
	ctx, cancel := context.WithCancel(context.Background())
	go c.Run(ctx)
	t.Cleanup(cancel)
	return c, cancel
}

func TestClient_HoldAndReleaseCarryTheSessionToken(t *testing.T) {
	t.Parallel()

	f := &fakeSortie{}
	c, _ := newTestClient(t, f)
	c.SetHold("takeover")
	f.waitFor(t, 1)
	c.SetHold("")
	got := f.waitFor(t, 2)

	if got[0].path != "/api/v1/LIVE-1/hold" || got[0].auth != "Bearer session-token-x" || got[0].body["holder"] != Holder || got[0].body["reason"] != "takeover" {
		t.Errorf("hold request = %+v, want a bearer hold for LIVE-1 by acp-broker for takeover", got[0])
	}
	if got[1].path != "/api/v1/LIVE-1/release" || got[1].auth != "Bearer session-token-x" {
		t.Errorf("release request = %+v, want a bearer release for LIVE-1", got[1])
	}
}

func TestClient_RetriesUntilSortieAnswers(t *testing.T) {
	t.Parallel()

	f := &fakeSortie{}
	f.failures.Store(3)
	c, _ := newTestClient(t, f)
	c.SetHold("permission request")

	got := f.waitFor(t, 4)
	for i, r := range got[:4] {
		if r.path != "/api/v1/LIVE-1/hold" {
			t.Errorf("request %d = %s, want the hold retried", i, r.path)
		}
	}
	time.Sleep(100 * time.Millisecond)
	if n := len(f.recorded()); n != 4 {
		t.Errorf("sortie got %d requests, want no more once the hold succeeded", n)
	}
}

func TestClient_DesiredStateCollapsesFlips(t *testing.T) {
	t.Parallel()

	f := &fakeSortie{hang: make(chan struct{})}
	c, _ := newTestClient(t, f)
	c.SetHold("takeover")
	time.Sleep(50 * time.Millisecond) // the hold call is now hanging
	c.SetHold("")
	c.SetHold("steer")
	c.SetHold("")
	close(f.hang)

	f.waitFor(t, 2)
	time.Sleep(100 * time.Millisecond)
	got := f.recorded()
	if len(got) != 2 || got[0].path != "/api/v1/LIVE-1/hold" || got[1].path != "/api/v1/LIVE-1/release" {
		t.Errorf("requests = %+v, want one hold then one release", got)
	}
}

func TestClient_CallsNeverBlockWhileSortieHangs(t *testing.T) {
	t.Parallel()

	f := &fakeSortie{hang: make(chan struct{})}
	defer close(f.hang)
	c, _ := newTestClient(t, f)

	start := time.Now()
	for i := range 100 {
		if i%2 == 0 {
			c.SetHold("takeover")
		} else {
			c.SetHold("")
		}
		c.Escalate(Escalation{Message: "q", Kind: "question"})
	}
	if elapsed := time.Since(start); elapsed > 100*time.Millisecond {
		t.Errorf("200 calls took %v while sortie hung, want them to return at once", elapsed)
	}
}

func TestClient_EscalationsAreDeliveredAndAFinalReleaseIsSent(t *testing.T) {
	t.Parallel()

	f := &fakeSortie{}
	c, cancel := newTestClient(t, f)
	c.SetHold("permission request")
	c.Escalate(Escalation{Message: "Allow Write progress.txt?", Kind: "permission", URL: "https://v.example/LIVE-1"})
	got := f.waitFor(t, 2)
	if got[1].path != "/api/v1/LIVE-1/escalate" || got[1].body["kind"] != "permission" || got[1].body["message"] != "Allow Write progress.txt?" || got[1].auth != "Bearer session-token-x" {
		t.Errorf("escalation request = %+v", got[1])
	}

	closeCtx, closeCancel := context.WithTimeout(context.Background(), time.Second)
	defer closeCancel()
	c.Close(closeCtx, cancel)
	got = f.recorded()
	if last := got[len(got)-1]; last.path != "/api/v1/LIVE-1/release" {
		t.Errorf("last request = %s, want the final release", last.path)
	}
}

func TestClient_CloseIsBoundedWhenSortieHangs(t *testing.T) {
	t.Parallel()

	f := &fakeSortie{}
	c, cancel := newTestClient(t, f)
	c.SetHold("takeover")
	f.waitFor(t, 1)
	f.hang = make(chan struct{})
	defer close(f.hang)

	closeCtx, closeCancel := context.WithTimeout(context.Background(), 200*time.Millisecond)
	defer closeCancel()
	start := time.Now()
	c.Close(closeCtx, cancel)
	if elapsed := time.Since(start); elapsed > time.Second {
		t.Errorf("Close took %v against a hanging sortie, want it bounded by its context", elapsed)
	}
}

func TestClient_ReportBrokerRetriesThenStops(t *testing.T) {
	t.Parallel()
	f := &fakeSortie{}
	f.failures.Store(2)
	c, _ := newTestClient(t, f)

	done := make(chan struct{})
	go func() {
		c.ReportBroker(context.Background(), "http://127.0.0.1:41001", "viewer-token")
		close(done)
	}()
	select {
	case <-done:
	case <-time.After(5 * time.Second):
		t.Fatal("ReportBroker did not finish after the failures cleared")
	}
	got := f.waitFor(t, 3)
	last := got[len(got)-1]
	if last.path != "/api/v1/LIVE-1/broker" || last.auth != "Bearer session-token-x" ||
		last.body["http_url"] != "http://127.0.0.1:41001" || last.body["viewer_token"] != "viewer-token" {
		t.Errorf("last request = %+v", last)
	}
	if len(got) != 3 {
		t.Errorf("requests = %d, want 2 failures and 1 success", len(got))
	}
}

func TestClient_ReportBrokerStopsWithItsContext(t *testing.T) {
	t.Parallel()
	f := &fakeSortie{}
	f.failures.Store(1 << 30)
	c, _ := newTestClient(t, f)
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan struct{})
	go func() {
		c.ReportBroker(ctx, "http://127.0.0.1:41001", "viewer-token")
		close(done)
	}()
	f.waitFor(t, 2)
	cancel()
	select {
	case <-done:
	case <-time.After(5 * time.Second):
		t.Fatal("ReportBroker kept retrying after its context ended")
	}
}
