package broker

import (
	"strings"
	"testing"
)

func record(seq int64, size int) Record {
	return Record{Seq: seq, Data: []byte(strings.Repeat("x", size))}
}

func TestEventLog_EvictsAtTheCountLimit(t *testing.T) {
	t.Parallel()

	l := newEventLog(3, 1<<20)
	for i := int64(1); i <= 5; i++ {
		l.append(record(l.next(), 10))
		if l.last != i {
			t.Fatalf("last = %d after %d appends", l.last, i)
		}
	}
	got, dropped := l.since(0)
	if len(got) != 3 || got[0].Seq != 3 || got[2].Seq != 5 || dropped != 2 {
		t.Errorf("since(0) = %d records from %d, dropped %d; want events 3 to 5 and 2 dropped", len(got), got[0].Seq, dropped)
	}
}

func TestEventLog_EvictsAtTheByteLimit(t *testing.T) {
	t.Parallel()

	l := newEventLog(100, 25)
	for range 4 {
		l.append(record(l.next(), 10))
	}
	got, dropped := l.since(0)
	if len(got) != 2 || got[0].Seq != 3 || l.bytes != 20 || dropped != 2 {
		t.Errorf("since(0) = %d records from %d, bytes %d, dropped %d; want events 3 and 4, 20 bytes, 2 dropped", len(got), got[0].Seq, l.bytes, dropped)
	}

	// An event larger than the whole bound is still kept, alone.
	l.append(record(l.next(), 100))
	got, _ = l.since(0)
	if len(got) != 1 || got[0].Seq != 5 {
		t.Errorf("after an oversized event the buffer holds %d records from %d, want only event 5", len(got), got[0].Seq)
	}
}

func TestEventLog_SinceResumesAfterASequenceNumber(t *testing.T) {
	t.Parallel()

	l := newEventLog(300, 1<<20)
	for range 300 {
		l.append(record(l.next(), 1))
	}
	got, dropped := l.since(280)
	if len(got) != 20 || got[0].Seq != 281 || dropped != 0 {
		t.Errorf("since(280) = %d records from %d, dropped %d; want events 281 to 300", len(got), got[0].Seq, dropped)
	}
	got, dropped = l.since(300)
	if len(got) != 0 || dropped != 0 {
		t.Errorf("since(300) = %d records, dropped %d; want none", len(got), dropped)
	}
}
