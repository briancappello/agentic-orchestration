package runner

import (
	"bytes"
	"context"
	"errors"
	"strings"
	"testing"
	"time"
)

func TestOutput(t *testing.T) {
	var log bytes.Buffer
	out, err := Exec{Log: &log}.Output(context.Background(), "sh", "-c", "echo out; echo diag >&2")
	if err != nil {
		t.Fatal(err)
	}
	if string(out) != "out\n" || log.String() != "diag\n" {
		t.Fatalf("stdout %q log %q", out, log.String())
	}
}

func TestRunSendsStdoutToLog(t *testing.T) {
	var log bytes.Buffer
	if err := (Exec{Log: &log}).Run(context.Background(), "sh", "-c", "echo out"); err != nil {
		t.Fatal(err)
	}
	if log.String() != "out\n" {
		t.Fatalf("log %q", log.String())
	}
}

func TestErrorCarriesExitCodeAndStderrTail(t *testing.T) {
	big := strings.Repeat("x", 2*stderrTail)
	_, err := Exec{}.Output(context.Background(), "sh", "-c", "printf %s "+big+" >&2; echo END >&2; exit 3")
	var e *Error
	if !errors.As(err, &e) {
		t.Fatalf("err = %v, want *Error", err)
	}
	if e.ExitCode != 3 || ExitCode(err) != 3 {
		t.Fatalf("exit code %d", e.ExitCode)
	}
	if len(e.Stderr) != stderrTail || !strings.HasSuffix(e.Stderr, "END\n") {
		t.Fatalf("stderr tail has %d bytes, ends %q", len(e.Stderr), e.Stderr[len(e.Stderr)-8:])
	}
	if !strings.HasPrefix(e.Error(), "sh -c") {
		t.Fatalf("error %q does not name the command", e.Error())
	}
}

func TestMissingProgram(t *testing.T) {
	err := Exec{}.Run(context.Background(), "smol-builder-no-such-program")
	if err == nil || ExitCode(err) != -1 || !strings.Contains(err.Error(), "smol-builder-no-such-program") {
		t.Fatalf("err = %v", err)
	}
}

func TestCancelInterrupts(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 200*time.Millisecond)
	defer cancel()
	start := time.Now()
	err := Exec{}.Run(ctx, "sleep", "30")
	if err == nil || !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("err = %v, want deadline exceeded", err)
	}
	if time.Since(start) > 10*time.Second {
		t.Fatal("cancel did not stop the program")
	}
}
