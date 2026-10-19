// Package agentproc runs the agent the broker relays to: in a process
// group of its own, so that stopping it also stops every process it
// started.
package agentproc

import (
	"context"
	"errors"
	"io"
	"os"
	"os/exec"
	"sync"
	"time"
)

// DrainGrace is how long to wait, once the agent has exited, for its
// remaining output to be read.
const DrainGrace = 5 * time.Second

// Process is a started agent.
type Process struct {
	PID int
	// Stdin is the agent's standard input.
	Stdin io.WriteCloser
	// Stdout and Stderr are the read ends of the agent's output. The
	// process never closes them itself: a reader may still be reading
	// after the agent exits. Close them with Close.
	Stdout, Stderr *os.File

	cmd  *exec.Cmd
	done chan struct{}
	err  error

	// mu orders every signal to the group before the release: once the
	// agent is reaped and released, its group number may be reused.
	mu       sync.Mutex
	released bool
}

// Start launches argv with env in a new process group. Cancelling ctx
// asks the group to stop, and kills it stopGrace later.
func Start(ctx context.Context, argv, env []string, stopGrace time.Duration) (*Process, error) {
	if len(argv) == 0 {
		return nil, errors.New("agentproc: no command")
	}
	cmd := exec.CommandContext(ctx, argv[0], argv[1:]...) //nolint:gosec // the operator names the agent command
	cmd.Env = env
	p := &Process{cmd: cmd, done: make(chan struct{})}
	newGroup(cmd)
	cmd.Cancel = func() error {
		err := p.signal(false)
		time.AfterFunc(stopGrace, func() { _ = p.signal(true) })
		return err
	}
	// If the group ignores the stop, Wait kills the agent itself.
	cmd.WaitDelay = stopGrace + time.Second

	stdin, err := cmd.StdinPipe()
	if err != nil {
		return nil, err
	}
	outR, outW, err := os.Pipe()
	if err != nil {
		return nil, err
	}
	errR, errW, err := os.Pipe()
	if err != nil {
		closeAll(outR, outW)
		return nil, err
	}
	cmd.Stdout, cmd.Stderr = outW, errW
	if err := cmd.Start(); err != nil {
		closeAll(outR, outW, errR, errW)
		return nil, err
	}
	// The agent has its own copies of the write ends. Closing ours lets the
	// readers see end of file once the agent and its children are gone.
	closeAll(outW, errW)

	p.PID, p.Stdin, p.Stdout, p.Stderr = cmd.Process.Pid, stdin, outR, errR
	go p.reap()
	return p, nil
}

// reap waits for the agent, then kills whatever is left of its group,
// such as a background child that would otherwise hold its output open.
func (p *Process) reap() {
	p.err = p.cmd.Wait()
	_ = p.signal(true)
	p.mu.Lock()
	p.released = true
	p.mu.Unlock()
	close(p.done)
}

// signal stops (kill false) or kills the agent's process group, unless
// the agent has already been reaped.
func (p *Process) signal(kill bool) error {
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.released {
		return os.ErrProcessDone
	}
	return signalGroup(p.cmd.Process, kill)
}

// Done is closed once the agent has exited and its group has been killed.
func (p *Process) Done() <-chan struct{} { return p.done }

// Err is what waiting for the agent returned. Call it after Done.
func (p *Process) Err() error { return p.err }

// ExitCode is the agent's exit status: its own code, 1 for any other
// failure, 0 for success. Call it after Done.
func (p *Process) ExitCode() int {
	if exitErr, ok := errors.AsType[*exec.ExitError](p.err); ok {
		return exitErr.ExitCode()
	}
	if p.err != nil {
		return 1
	}
	return 0
}

// Close closes the read ends of the agent's output.
func (p *Process) Close() error {
	return errors.Join(p.Stdout.Close(), p.Stderr.Close())
}

func closeAll(files ...*os.File) {
	for _, f := range files {
		_ = f.Close()
	}
}
