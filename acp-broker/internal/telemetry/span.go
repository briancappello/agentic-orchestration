// Package telemetry records the turns of a broker session as trace spans
// and exports them over OTLP/HTTP.
package telemetry

import (
	"crypto/rand"
	"time"
)

// Origin names who started a turn.
type Origin string

// Turn origins.
const (
	// OriginDriver is a prompt from the driving client.
	OriginDriver Origin = "driver"

	// OriginHuman is a prompt a viewer sent.
	OriginHuman Origin = "human"

	// OriginSteer is a turn the broker ran to deliver steers.
	OriginSteer Origin = "steer"
)

// SpanKind tells a turn span from a tool call span.
type SpanKind int

// Span kinds.
const (
	KindTurn SpanKind = iota
	KindTool
)

// CancelledForInterrupt marks a turn a viewer interrupt cancelled.
const CancelledForInterrupt = "interrupt"

// Labels are the session labels the broker's supervisor gives it in its
// environment. An empty field is a label that is not set.
type Labels struct {
	Issue      string
	Rule       string
	ChainID    string
	DispatchID string
	Attempt    string
}

// Session is what every span says about the session it belongs to.
type Session struct {
	ID           string
	AgentName    string
	AgentVersion string
	Labels       Labels
}

// Usage holds the token counts an agent reported for a turn. A nil field
// is a count the agent did not report.
type Usage struct {
	Input       *int64
	Output      *int64
	CachedRead  *int64
	CachedWrite *int64
	Total       *int64
	Reasoning   *int64
}

// SteerEvent is a native steering request the agent answered while a turn
// ran.
type SteerEvent struct {
	Time    time.Time
	Outcome string
	Error   string
	Count   int
}

// Span is one finished span: a turn, or a tool call within a turn.
type Span struct {
	Kind     SpanKind
	TraceID  [16]byte
	SpanID   [8]byte
	ParentID [8]byte // zero for a turn, which roots its own trace
	Start    time.Time
	End      time.Time
	Session  Session

	// Unfinished marks a span that ended because its turn or the broker
	// stopped, not because the agent finished it.
	Unfinished bool

	// Error is the failure the agent reported, empty when it reported
	// none.
	Error string

	// Input and Output are transcript content, recorded only when the
	// operator enables content. A Cut flag marks text that was longer
	// than the recorder keeps.
	Input     string
	InputCut  bool
	Output    string
	OutputCut bool

	// Origin is the turn's origin; a tool call carries its turn's.
	Origin Origin

	// Turn fields.
	StopReason   string
	CancelledFor string
	Model        string
	Usage        *Usage // nil when the agent reported no usage
	SteerCount   int    // steers a steer turn delivered
	SteerEvents  []SteerEvent
	ToolsDropped int // tool calls past the per-turn cap

	// Tool call fields.
	CallID   string
	ToolKind string
	Title    string
	Status   string
}

func newTraceID() (id [16]byte) {
	_, _ = rand.Read(id[:])
	return id
}

func newSpanID() (id [8]byte) {
	_, _ = rand.Read(id[:])
	return id
}
