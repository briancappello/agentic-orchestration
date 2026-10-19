package broker

import "fmt"

// Default bounds of the replay buffer.
const (
	DefaultReplayEvents = 5000
	DefaultReplayBytes  = 16 << 20
)

// Record is one encoded event as a transport sends it. Seq is 0 for a
// snapshot or a reply to one viewer, which is not part of the event log.
type Record struct {
	Seq  int64
	Data []byte // one JSON object followed by a newline
}

// eventLog numbers outgoing events and keeps the most recent ones, bounded
// by count and by bytes, for viewers that attach late. Owned by the loop.
type eventLog struct {
	maxEvents int
	maxBytes  int

	entries []Record
	bytes   int
	last    int64
}

func newEventLog(maxEvents, maxBytes int) *eventLog {
	if maxEvents <= 0 {
		maxEvents = DefaultReplayEvents
	}
	if maxBytes <= 0 {
		maxBytes = DefaultReplayBytes
	}
	return &eventLog{maxEvents: maxEvents, maxBytes: maxBytes}
}

// next returns the sequence number the next appended event takes.
func (l *eventLog) next() int64 { return l.last + 1 }

// append stores rec, whose Seq must be next(), and evicts the oldest
// events until both bounds hold. The newest event is always kept.
func (l *eventLog) append(rec Record) {
	l.last = rec.Seq
	l.entries = append(l.entries, rec)
	l.bytes += len(rec.Data)
	drop := 0
	for len(l.entries)-drop > 1 && (len(l.entries)-drop > l.maxEvents || l.bytes > l.maxBytes) {
		l.bytes -= len(l.entries[drop].Data)
		drop++
	}
	if drop > 0 {
		// Copy rather than reslice, so the backing array of evicted events
		// can be freed.
		l.entries = append([]Record(nil), l.entries[drop:]...)
	}
}

// oldest returns the sequence number of the oldest buffered event, or
// next() when the buffer is empty.
func (l *eventLog) oldest() int64 {
	if len(l.entries) == 0 {
		return l.next()
	}
	return l.entries[0].Seq
}

// since returns the buffered events with a sequence number above after,
// in order, and the number of events after it that are no longer
// buffered.
func (l *eventLog) since(after int64) (records []Record, dropped int64) {
	if first := l.oldest(); first > after+1 {
		dropped = first - after - 1
	}
	for _, r := range l.entries {
		if r.Seq > after {
			records = append(records, r)
		}
	}
	return records, dropped
}

// droppedEvent tells a viewer that events it would otherwise receive are
// no longer buffered.
func droppedEvent(after, dropped int64) Event {
	return Event{
		Type:    "error",
		Op:      "replay",
		Message: fmt.Sprintf("events %d to %d are no longer buffered", after+1, after+dropped),
	}
}
