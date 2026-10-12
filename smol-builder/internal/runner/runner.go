// Package runner runs external programs: the container engine and smolvm.
package runner

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"strings"
	"time"
)

// Runner runs a program to completion.
type Runner interface {
	// Output runs name with args and returns its standard output.
	Output(ctx context.Context, name string, args ...string) ([]byte, error)
	// Run runs name with args, sending its standard output to the
	// diagnostic stream.
	Run(ctx context.Context, name string, args ...string) error
}

// stderrTail is how much of a failed program's standard error an Error keeps.
const stderrTail = 4 << 10

// Error is a program that ran and exited non-zero.
type Error struct {
	Command  string
	ExitCode int
	Stderr   string
	Err      error
}

func (e *Error) Error() string {
	msg := fmt.Sprintf("%s: %v", e.Command, e.Err)
	if s := strings.TrimSpace(e.Stderr); s != "" {
		msg += ": " + s
	}
	return msg
}

func (e *Error) Unwrap() error { return e.Err }

// ExitCode returns the exit code of the program behind err, or -1 when err
// is not a program's non-zero exit.
func ExitCode(err error) int {
	if e, ok := errors.AsType[*Error](err); ok {
		return e.ExitCode
	}
	return -1
}

// Exec runs programs as host subprocesses. Their standard error, and the
// standard output of Run, are copied to Log.
type Exec struct {
	Log io.Writer
}

// Output implements Runner.
func (x Exec) Output(ctx context.Context, name string, args ...string) ([]byte, error) {
	var stdout bytes.Buffer
	err := x.run(ctx, &stdout, name, args)
	return stdout.Bytes(), err
}

// Run implements Runner.
func (x Exec) Run(ctx context.Context, name string, args ...string) error {
	return x.run(ctx, x.log(), name, args)
}

func (x Exec) log() io.Writer {
	if x.Log == nil {
		return io.Discard
	}
	return x.Log
}

func (x Exec) run(ctx context.Context, stdout io.Writer, name string, args []string) error {
	cmd := exec.CommandContext(ctx, name, args...) //nolint:gosec // callers name fixed programs: the engine and smolvm
	// Interrupt first so the program can clean up, then kill.
	cmd.Cancel = func() error { return cmd.Process.Signal(os.Interrupt) }
	cmd.WaitDelay = 30 * time.Second
	tail := &tailBuffer{max: stderrTail}
	cmd.Stdout = stdout
	cmd.Stderr = io.MultiWriter(x.log(), tail)
	err := cmd.Run()
	if err == nil {
		return nil
	}
	code := -1
	if exitErr, ok := errors.AsType[*exec.ExitError](err); ok {
		code = exitErr.ExitCode()
	}
	if ctxErr := ctx.Err(); ctxErr != nil {
		err = fmt.Errorf("%w (%w)", ctxErr, err)
	}
	return &Error{
		Command:  strings.Join(append([]string{name}, args...), " "),
		ExitCode: code,
		Stderr:   tail.String(),
		Err:      err,
	}
}

// tailBuffer keeps the last max bytes written to it.
type tailBuffer struct {
	max int
	buf []byte
}

func (t *tailBuffer) Write(p []byte) (int, error) {
	t.buf = append(t.buf, p...)
	if over := len(t.buf) - t.max; over > 0 {
		t.buf = t.buf[over:]
	}
	return len(p), nil
}

func (t *tailBuffer) String() string { return string(t.buf) }
