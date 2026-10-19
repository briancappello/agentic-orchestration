package secrets

import (
	"bytes"
	"errors"
	"log/slog"
	"strings"
	"testing"
)

// reset forgets every registered value. The registry is global, so each
// test starts from an empty one.
func reset(t *testing.T) {
	t.Helper()
	mu.Lock()
	known.Store(nil)
	warned = map[string]bool{}
	mu.Unlock()
}

func TestMaskReplacesEveryOccurrence(t *testing.T) {
	reset(t)
	Add("token", "s3cret-token-1")
	got := Mask("a s3cret-token-1 b s3cret-token-1")
	if want := "a " + Marker + " b " + Marker; got != want {
		t.Fatalf("Mask = %q, want %q", got, want)
	}
	if got := Mask("nothing to hide"); got != "nothing to hide" {
		t.Fatalf("Mask changed clean text: %q", got)
	}
}

func TestAddRegistersEachLineAndTheCredentialOfASchemeValue(t *testing.T) {
	reset(t)
	Add("header", "Bearer abcdefgh123\r\nsecond-line-value")
	for _, s := range []string{"abcdefgh123", "second-line-value", "Bearer abcdefgh123"} {
		if got := Mask(s); got != Marker {
			t.Errorf("Mask(%q) = %q, want the marker", s, got)
		}
	}
}

func TestShortValuesStayReadableAndWarnOnce(t *testing.T) {
	reset(t)
	var logs bytes.Buffer
	prev := slog.Default()
	slog.SetDefault(slog.New(slog.NewTextHandler(&logs, nil)))
	t.Cleanup(func() { slog.SetDefault(prev) })

	Add("pin", "1234")
	Add("pin", "5678")
	if got := Mask("pin 1234"); got != "pin 1234" {
		t.Fatalf("a value under MinLen was masked: %q", got)
	}
	if n := strings.Count(logs.String(), "too short to mask"); n != 1 {
		t.Fatalf("got %d warnings, want 1:\n%s", n, logs.String())
	}
	Add("blank", "   ")
	if strings.Contains(logs.String(), "name=blank") {
		t.Fatal("a blank value warned")
	}
}

func TestOverlappingMatchesBecomeOneMarker(t *testing.T) {
	reset(t)
	Add("a", "abcdefgh")
	Add("b", "efghijkl")
	if got, want := Mask("xx abcdefghijkl yy"), "xx "+Marker+" yy"; got != want {
		t.Fatalf("Mask = %q, want %q", got, want)
	}
}

func TestMaskTruncatedDropsAValueCutAtTheEnd(t *testing.T) {
	reset(t)
	Add("token", "tok-0123456789")
	if got, want := MaskTruncated("the key is tok-01234"), "the key is "; got != want {
		t.Fatalf("MaskTruncated = %q, want %q", got, want)
	}
	if got, want := MaskTruncated("whole tok-0123456789 then tok-0"), "whole "+Marker+" then "; got != want {
		t.Fatalf("MaskTruncated = %q, want %q", got, want)
	}
	if got := MaskTruncated("clean words."); got != "clean words." {
		t.Fatalf("MaskTruncated changed clean text: %q", got)
	}
	// Even one byte can be the start of a value the cut split.
	if got, want := MaskTruncated("ends with t"), "ends with "; got != want {
		t.Fatalf("MaskTruncated = %q, want %q", got, want)
	}
}

func TestAddEnvironRegistersSecretNamesAndURLCredentials(t *testing.T) {
	reset(t)
	AddEnviron([]string{
		"OPENROUTER_API_KEY=sk-or-0123456789",
		"DATABASE_URL=postgres://app:hunter2hunter2@db:5432/x",
		"HOME=/home/someone-long",
		"NOT_AN_ENTRY",
	})
	for _, s := range []string{"sk-or-0123456789", "app:hunter2hunter2", "hunter2hunter2"} {
		if got := Mask(s); got != Marker {
			t.Errorf("Mask(%q) = %q, want the marker", s, got)
		}
	}
	if got := Mask("/home/someone-long"); got != "/home/someone-long" {
		t.Errorf("an ordinary value was masked: %q", got)
	}
}

func TestIsSecretName(t *testing.T) {
	for name, want := range map[string]bool{
		"OPENAI_API_KEY": true, "github-token": true, "DB_PASSWORD": true, "PG_CONNECTION_STRING": true,
		"HOME": false, "KEYBOARD_LAYOUT": false, "PATH": false,
	} {
		if got := IsSecretName(name); got != want {
			t.Errorf("IsSecretName(%q) = %v, want %v", name, got, want)
		}
	}
}

func TestReplaceAttrMasksLogValues(t *testing.T) {
	reset(t)
	Add("token", "viewer-token-xyz")
	var out bytes.Buffer
	log := slog.New(slog.NewTextHandler(&out, &slog.HandlerOptions{ReplaceAttr: ReplaceAttr}))
	log.Info("start", slog.String("t", "viewer-token-xyz"), slog.Any("err", errors.New("bad viewer-token-xyz")),
		slog.Any("argv", []string{"agent", "--token", "viewer-token-xyz"}), slog.Int("n", 3))
	if strings.Contains(out.String(), "viewer-token-xyz") {
		t.Fatalf("the token reached the log: %s", out.String())
	}
	if !strings.Contains(out.String(), "n=3") {
		t.Fatalf("an int attribute was lost: %s", out.String())
	}
}
