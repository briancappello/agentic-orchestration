package broker

import (
	"encoding/json"
	"sync"
	"time"
)

// Floor names who may start turns in the session.
type Floor string

const (
	// FloorDriver means the driving client starts turns. Viewers may watch
	// and steer.
	FloorDriver Floor = "driver"

	// FloorHuman means a viewer interrupted the session. The driver's turn
	// is held open until a viewer hands the session back.
	FloorHuman Floor = "human"
)

// Command is one request a viewer sends to the broker.
type Command struct {
	// Op is one of "steer", "interrupt" (also accepted as "takeover" and
	// "cancel"), "prompt", "handback", "permit", or "state".
	Op   string `json:"op"`
	Text string `json:"text,omitempty"`

	// ID and Option answer a permission request for op "permit": ID is the
	// request's ID as the permission event showed it, and Option is an
	// option ID or an option kind such as "allow_once" or "reject_once".
	// Option "cancel" answers with the cancelled outcome.
	ID     string `json:"id,omitempty"`
	Option string `json:"option,omitempty"`
}

// Event is one message the broker sends to a viewer.
type Event struct {
	// Seq numbers the session's events, rising by one per event. It is 0
	// on a state snapshot and on a reply sent to one viewer, which are not
	// part of the event log.
	Seq int64 `json:"seq"`

	// Time is when the broker produced the event.
	Time time.Time `json:"time"`

	// Type is "state", "update", "result", "error", "permission", or
	// "permission_resolved".
	Type string `json:"type"`

	// ID and Request carry a permission request the agent sent: ID is the
	// request's ID and Request its params object.
	ID      string          `json:"id,omitempty"`
	Request json.RawMessage `json:"request,omitempty"`

	Floor      Floor  `json:"floor,omitempty"`
	SessionID  string `json:"sessionId,omitempty"`
	DriverTurn string `json:"driverTurn,omitempty"`
	Steering   *bool  `json:"steering,omitempty"`

	// SteersQueued counts the steers that have not landed yet: queued, or
	// awaiting the agent's native steering outcome.
	SteersQueued int `json:"steersQueued,omitempty"`

	// Update is the params object of a session/update notification.
	Update json.RawMessage `json:"update,omitempty"`

	Op      string          `json:"op,omitempty"`
	Result  json.RawMessage `json:"result,omitempty"`
	Error   json.RawMessage `json:"error,omitempty"`
	Message string          `json:"message,omitempty"`
}

// viewerBuffer bounds the live events a viewer may fall behind by before
// the broker disconnects it. A viewer's channel also holds its replay.
const viewerBuffer = 1024

// Viewer is one attached human client as a transport sees it. The broker
// sends it records on Lines and never blocks on it: a viewer that falls
// behind is disconnected, which closes Lines.
type Viewer struct {
	b    *Broker
	out  chan Record
	once sync.Once
}

// Attach registers a new viewer. The viewer first receives the current
// state, then every buffered event in order, then live events. When older
// events were already evicted, an error event saying so precedes the
// buffered ones.
func (b *Broker) Attach() *Viewer { return b.attach(false, 0) }

// Resume registers a viewer that already received the events up to and
// including after. It receives only the buffered events after that one,
// preceded by an error event when some of them were evicted, then live
// events.
func (b *Broker) Resume(after int64) *Viewer { return b.attach(true, after) }

func (b *Broker) attach(resume bool, after int64) *Viewer {
	v := &Viewer{b: b}
	ready := make(chan struct{})
	select {
	case b.events <- event{kind: evViewerJoined, viewer: v, resume: resume, after: after, ready: ready}:
		select {
		case <-ready:
			return v
		case <-b.done:
		}
	case <-b.done:
	}
	if v.out == nil {
		v.out = make(chan Record)
		close(v.out)
	}
	return v
}

// Lines returns the viewer's outgoing records. It is closed when the
// viewer is disconnected or the session ends.
func (v *Viewer) Lines() <-chan Record { return v.out }

// Command hands cmd to the broker. An error it causes goes to this
// viewer's Lines.
func (v *Viewer) Command(cmd Command) {
	v.b.post(event{kind: evViewerCommand, viewer: v, command: cmd})
}

// CommandLine decodes one JSON command line and hands it to the broker,
// which answers a line that does not decode with an error event.
func (v *Viewer) CommandLine(line []byte) {
	var cmd Command
	if err := json.Unmarshal(line, &cmd); err != nil {
		v.b.post(event{kind: evViewerCommand, viewer: v, badCommand: err.Error()})
		return
	}
	v.Command(cmd)
}

// Close detaches the viewer. It is safe to call more than once.
func (v *Viewer) Close() {
	v.once.Do(func() {
		v.b.post(event{kind: evViewerLeft, viewer: v})
	})
}

// Do runs cmd and returns its immediate result: an error event when the
// broker refused it, and otherwise the state after it was applied.
func (b *Broker) Do(cmd Command) Event {
	reply := make(chan Event, 1)
	select {
	case b.events <- event{kind: evViewerCommand, command: cmd, reply: reply}:
	case <-b.done:
		return Event{Type: "error", Op: cmd.Op, Message: "the session has ended"}
	}
	select {
	case ev := <-reply:
		return ev
	case <-b.done:
		return Event{Type: "error", Op: cmd.Op, Message: "the session has ended"}
	}
}

// State returns the current state.
func (b *Broker) State() Event { return b.Do(Command{Op: "state"}) }

func encodeEvent(ev Event) []byte {
	out, err := json.Marshal(ev)
	if err != nil {
		panic("broker: encode event: " + err.Error())
	}
	return append(out, '\n')
}
