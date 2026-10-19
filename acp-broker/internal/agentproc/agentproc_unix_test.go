//go:build unix

package agentproc

import (
	"bufio"
	"context"
	"errors"
	"io"
	"os"
	"strconv"
	"strings"
	"syscall"
	"testing"
	"time"
)

// failAfter bounds a wait that only a broken implementation exceeds.
const failAfter = 10 * time.Second

func start(t *testing.T, ctx context.Context, script string, grace time.Duration) *Process {
	t.Helper()
	p, err := Start(ctx, []string{"sh", "-c", script}, os.Environ(), grace)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = p.Close() })
	return p
}

func waitDone(t *testing.T, p *Process) {
	t.Helper()
	select {
	case <-p.Done():
	case <-time.After(failAfter):
		t.Fatal("the agent was not reaped")
	}
}

// firstLine reads the line a script prints first: the PID of its child.
func firstLine(t *testing.T, r io.Reader) int {
	t.Helper()
	line, err := bufio.NewReader(r).ReadString('\n')
	if err != nil {
		t.Fatal(err)
	}
	pid, err := strconv.Atoi(strings.TrimSpace(line))
	if err != nil {
		t.Fatal(err)
	}
	return pid
}

// gone reports whether pid has died. A killed child of the agent is
// reparented and stays a zombie until its new parent reaps it, which
// happens outside this process, so poll until it is gone or a zombie.
func gone(pid int) bool {
	deadline := time.Now().Add(failAfter)
	for time.Now().Before(deadline) {
		if errors.Is(syscall.Kill(pid, 0), syscall.ESRCH) || zombie(pid) {
			return true
		}
		time.Sleep(10 * time.Millisecond)
	}
	return false
}

// zombie reports whether /proc shows pid as exited but not yet reaped.
// Without /proc it reports false, and gone waits for the reap instead.
func zombie(pid int) bool {
	stat, err := os.ReadFile("/proc/" + strconv.Itoa(pid) + "/stat")
	if err != nil {
		return false
	}
	// The state follows the command name, which is in parentheses.
	_, rest, ok := strings.Cut(string(stat), ") ")
	return ok && strings.HasPrefix(rest, "Z")
}

func TestExitCodeAndOutput(t *testing.T) {
	p := start(t, context.Background(), "echo out; echo err >&2; exit 3", time.Second)
	out, _ := io.ReadAll(p.Stdout)
	errOut, _ := io.ReadAll(p.Stderr)
	waitDone(t, p)
	if string(out) != "out\n" || string(errOut) != "err\n" {
		t.Fatalf("stdout %q, stderr %q", out, errOut)
	}
	if p.ExitCode() != 3 {
		t.Fatalf("ExitCode = %d, want 3", p.ExitCode())
	}
}

func TestStdinReachesTheAgent(t *testing.T) {
	p := start(t, context.Background(), "read line; echo got $line", time.Second)
	_, _ = io.WriteString(p.Stdin, "hello\n")
	out, _ := io.ReadAll(p.Stdout)
	waitDone(t, p)
	if string(out) != "got hello\n" || p.ExitCode() != 0 {
		t.Fatalf("stdout %q, exit %d", out, p.ExitCode())
	}
}

func TestCancelStopsTheWholeGroup(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	p := start(t, ctx, "sleep 60 & echo $!; wait", time.Second)
	child := firstLine(t, p.Stdout)
	cancel()
	waitDone(t, p)
	if !gone(child) {
		t.Fatalf("the agent's child %d survived the stop", child)
	}
}

func TestAChildLeftBehindIsKilledAndOutputEnds(t *testing.T) {
	// The agent exits at once; its background child keeps the output open.
	p := start(t, context.Background(), "sleep 60 & echo $!", time.Second)
	r := bufio.NewReader(p.Stdout)
	child := firstLine(t, r)
	waitDone(t, p)
	eof := make(chan error, 1)
	go func() { _, err := r.ReadString('\n'); eof <- err }()
	select {
	case err := <-eof:
		if !errors.Is(err, io.EOF) {
			t.Fatalf("read after exit: %v", err)
		}
	case <-time.After(failAfter):
		t.Fatal("the output stayed open after the agent exited")
	}
	if !gone(child) {
		t.Fatalf("the child %d left behind is still running", child)
	}
}

func TestAnAgentThatIgnoresTheStopIsKilledAfterTheGrace(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	p := start(t, ctx, `trap "" TERM; echo $$; while :; do sleep 1; done`, 200*time.Millisecond)
	firstLine(t, p.Stdout)
	cancel()
	waitDone(t, p)
	if code := p.ExitCode(); code == 0 {
		t.Fatalf("ExitCode = 0 for a killed agent")
	}
}

func TestStartRefusesAnEmptyCommand(t *testing.T) {
	if _, err := Start(context.Background(), nil, nil, time.Second); err == nil {
		t.Fatal("Start(nil) did not fail")
	}
}
