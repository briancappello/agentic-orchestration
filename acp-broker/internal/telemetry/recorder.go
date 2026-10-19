package telemetry

import (
	"encoding/json"
	"strings"
	"time"
)

// Defaults for the recorder's limits.
const (
	// DefaultContentMax is how many bytes of each transcript value are
	// exported when content is enabled.
	DefaultContentMax = 4096

	// MaxToolsPerTurn bounds the tool call spans one turn records. Calls
	// past it are only counted on the turn.
	MaxToolsPerTurn = 1024

	// contentSlack is how far past ContentMax the recorder keeps text, so
	// that masking still sees a secret that straddles the export limit.
	contentSlack = 512
)

// Options configure a Recorder.
type Options struct {
	// Labels are the session labels every span carries.
	Labels Labels

	// Content records transcript content: prompt text, agent messages,
	// and tool input and output. ContentMax bounds each value in bytes;
	// zero selects DefaultContentMax.
	Content    bool
	ContentMax int

	// Emit receives each span as it ends. It is called from the
	// recorder's caller and must return at once.
	Emit func(Span)

	// Now returns the current time; nil selects time.Now.
	Now func() time.Time
}

// Recorder turns the events of a broker session into spans. Its methods
// must all be called from one goroutine. A nil *Recorder records
// nothing, so a broker without telemetry calls it unconditionally.
type Recorder struct {
	opts    Options
	session Session
	model   string

	turns   map[string]*Span
	current *Span // the open turn session updates belong to
	tools   map[string]*Span
	toolsIn int // tool calls the current turn has seen

	outside int
}

// NewRecorder returns a recorder for opts.
func NewRecorder(opts Options) *Recorder {
	if opts.Now == nil {
		opts.Now = time.Now
	}
	if opts.ContentMax <= 0 {
		opts.ContentMax = DefaultContentMax
	}
	if opts.Emit == nil {
		opts.Emit = func(Span) {}
	}
	return &Recorder{
		opts:    opts,
		session: Session{Labels: opts.Labels},
		turns:   map[string]*Span{},
		tools:   map[string]*Span{},
	}
}

// ContentMax returns the export limit for each transcript value.
func (r *Recorder) ContentMax() int {
	if r == nil {
		return DefaultContentMax
	}
	return r.opts.ContentMax
}

// SetSession records the session ID and the agent's name and version.
func (r *Recorder) SetSession(id, agentName, agentVersion string) {
	if r == nil {
		return
	}
	r.session.ID, r.session.AgentName, r.session.AgentVersion = id, agentName, agentVersion
}

// SetModel records the session's current model; turns take the model
// current when they start.
func (r *Recorder) SetModel(model string) {
	if r == nil {
		return
	}
	r.model = model
}

// TurnStarted opens a turn for the prompt with key, sent with params, the
// session/prompt params object. steers is how many steers a steer turn
// delivers.
func (r *Recorder) TurnStarted(key string, origin Origin, params json.RawMessage, steers int) {
	if r == nil {
		return
	}
	sp := &Span{
		Kind: KindTurn, TraceID: newTraceID(), SpanID: newSpanID(), Start: r.opts.Now(),
		Origin: origin, Model: r.model, SteerCount: steers,
	}
	if r.opts.Content {
		sp.Input, sp.InputCut = r.keep("", false, promptText(params))
	}
	r.turns[key] = sp
	r.current = sp
	r.tools = map[string]*Span{}
	r.toolsIn = 0
}

// TurnInterrupted marks the running turn as cancelled by an interrupt.
func (r *Recorder) TurnInterrupted() {
	if r == nil || r.current == nil {
		return
	}
	r.current.CancelledFor = CancelledForInterrupt
}

// TurnEnded closes the turn for the prompt with key, which the agent
// answered with result or rpcErr.
func (r *Recorder) TurnEnded(key string, result, rpcErr json.RawMessage) {
	if r == nil {
		return
	}
	sp, ok := r.turns[key]
	if !ok {
		return
	}
	delete(r.turns, key)
	var res struct {
		StopReason string `json:"stopReason"`
		Usage      *struct {
			Input       *int64 `json:"inputTokens"`
			Output      *int64 `json:"outputTokens"`
			CachedRead  *int64 `json:"cachedReadTokens"`
			CachedWrite *int64 `json:"cachedWriteTokens"`
			Total       *int64 `json:"totalTokens"`
			Reasoning   *int64 `json:"thoughtTokens"`
		} `json:"usage"`
	}
	_ = json.Unmarshal(result, &res)
	sp.StopReason = res.StopReason
	if u := res.Usage; u != nil && (u.Input != nil || u.Output != nil || u.CachedRead != nil || u.CachedWrite != nil || u.Total != nil || u.Reasoning != nil) {
		sp.Usage = &Usage{Input: u.Input, Output: u.Output, CachedRead: u.CachedRead, CachedWrite: u.CachedWrite, Total: u.Total, Reasoning: u.Reasoning}
	}
	sp.Error = errorMessage(rpcErr)
	r.end(sp, false)
}

// SteerAnswered records the agent's answer to a native steering request
// that delivered count steers, as an event on the running turn.
func (r *Recorder) SteerAnswered(count int, result, rpcErr json.RawMessage) {
	if r == nil || r.current == nil {
		return
	}
	var res struct {
		Outcome string `json:"outcome"`
	}
	_ = json.Unmarshal(result, &res)
	r.current.SteerEvents = append(r.current.SteerEvents, SteerEvent{
		Time: r.opts.Now(), Outcome: res.Outcome, Error: errorMessage(rpcErr), Count: count,
	})
}

// Update applies a session update, the update object of a session/update
// notification: tool calls and, with content enabled, agent messages.
func (r *Recorder) Update(update json.RawMessage) {
	if r == nil {
		return
	}
	var u struct {
		Kind    string `json:"sessionUpdate"`
		Content struct {
			Type string `json:"type"`
			Text string `json:"text"`
		} `json:"content"`
	}
	if json.Unmarshal(update, &u) != nil {
		return
	}
	switch u.Kind {
	case "tool_call", "tool_call_update":
		if r.current == nil {
			r.outside++
			return
		}
		r.toolUpdate(update)
	case "agent_message_chunk":
		if r.current == nil {
			r.outside++
			return
		}
		if r.opts.Content && u.Content.Type == "text" {
			r.current.Output, r.current.OutputCut = r.keep(r.current.Output, r.current.OutputCut, u.Content.Text)
		}
	}
}

// OutsideTurn returns how many tool call and message updates arrived with
// no turn running and were not recorded.
func (r *Recorder) OutsideTurn() int {
	if r == nil {
		return 0
	}
	return r.outside
}

// Stop ends every open span as unfinished, as the broker stops.
func (r *Recorder) Stop() {
	if r == nil {
		return
	}
	for key, sp := range r.turns {
		delete(r.turns, key)
		r.end(sp, true)
	}
}

func (r *Recorder) toolUpdate(update json.RawMessage) {
	var t struct {
		ID        string          `json:"toolCallId"`
		Title     *string         `json:"title"`
		Kind      *string         `json:"kind"`
		Status    *string         `json:"status"`
		RawInput  json.RawMessage `json:"rawInput"`
		RawOutput json.RawMessage `json:"rawOutput"`
		Content   []struct {
			Content struct {
				Type string `json:"type"`
				Text string `json:"text"`
			} `json:"content"`
		} `json:"content"`
	}
	if json.Unmarshal(update, &t) != nil || t.ID == "" {
		return
	}
	turn := r.current
	sp, ok := r.tools[t.ID]
	if !ok {
		if r.toolsIn >= MaxToolsPerTurn {
			turn.ToolsDropped++
			return
		}
		r.toolsIn++
		sp = &Span{Kind: KindTool, TraceID: turn.TraceID, ParentID: turn.SpanID, SpanID: newSpanID(), Start: r.opts.Now(), CallID: t.ID, Origin: turn.Origin}
		r.tools[t.ID] = sp
	}
	if t.Title != nil {
		sp.Title = *t.Title
	}
	if t.Kind != nil {
		sp.ToolKind = *t.Kind
	}
	if t.Status != nil {
		sp.Status = *t.Status
	}
	if r.opts.Content {
		if len(t.RawInput) > 0 {
			sp.Input, sp.InputCut = r.keep("", false, string(t.RawInput))
		}
		switch {
		case len(t.RawOutput) > 0:
			sp.Output, sp.OutputCut = r.keep("", false, string(t.RawOutput))
		case len(t.Content) > 0:
			var parts []string
			for _, c := range t.Content {
				if c.Content.Type == "text" {
					parts = append(parts, c.Content.Text)
				}
			}
			sp.Output, sp.OutputCut = r.keep("", false, strings.Join(parts, "\n"))
		}
	}
	if sp.Status == "completed" || sp.Status == "failed" {
		delete(r.tools, t.ID)
		if sp.Status == "failed" && sp.Error == "" {
			sp.Error = "tool call failed"
		}
		r.emit(sp)
	}
}

// end closes a turn, first ending its open tool calls as unfinished.
func (r *Recorder) end(sp *Span, unfinished bool) {
	if sp == r.current {
		for id, tool := range r.tools {
			delete(r.tools, id)
			tool.Unfinished = true
			r.emit(tool)
		}
		r.current = nil
	}
	sp.Unfinished = unfinished
	r.emit(sp)
}

func (r *Recorder) emit(sp *Span) {
	sp.End = r.opts.Now()
	sp.Session = r.session
	r.opts.Emit(*sp)
}

// keep appends add to text, keeping at most ContentMax plus a margin, and
// reports whether anything was left out.
func (r *Recorder) keep(text string, cut bool, add string) (string, bool) {
	if cut {
		return text, true
	}
	room := r.opts.ContentMax + contentSlack - len(text)
	if len(add) <= room {
		return text + add, false
	}
	return text + add[:max(room, 0)], true
}

// promptText joins the text blocks of a session/prompt params object.
func promptText(params json.RawMessage) string {
	var p struct {
		Prompt []struct {
			Type string `json:"type"`
			Text string `json:"text"`
		} `json:"prompt"`
	}
	_ = json.Unmarshal(params, &p)
	parts := make([]string, 0, len(p.Prompt))
	for _, block := range p.Prompt {
		if block.Type == "text" {
			parts = append(parts, block.Text)
		} else {
			parts = append(parts, "["+block.Type+"]")
		}
	}
	return strings.Join(parts, "\n\n")
}

// errorMessage returns the message of a JSON-RPC error object, or the
// raw error when it has none.
func errorMessage(rpcErr json.RawMessage) string {
	if len(rpcErr) == 0 || string(rpcErr) == "null" {
		return ""
	}
	var e struct {
		Message string `json:"message"`
	}
	if json.Unmarshal(rpcErr, &e) == nil && e.Message != "" {
		return e.Message
	}
	return string(rpcErr)
}
