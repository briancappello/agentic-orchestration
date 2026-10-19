//go:build !unix

package agentproc

import (
	"os"
	"os/exec"
)

// newGroup does nothing: without process groups, only the agent itself
// is stopped.
func newGroup(*exec.Cmd) {}

// signalGroup kills the agent. There is no graceful stop to ask for.
func signalGroup(proc *os.Process, _ bool) error {
	return proc.Kill()
}
