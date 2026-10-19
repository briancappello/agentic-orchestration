//go:build unix

package agentproc

import (
	"errors"
	"os"
	"os/exec"
	"syscall"
)

// newGroup makes the command the leader of a new process group.
func newGroup(cmd *exec.Cmd) {
	if cmd.SysProcAttr == nil {
		cmd.SysProcAttr = &syscall.SysProcAttr{}
	}
	cmd.SysProcAttr.Setpgid = true
}

// signalGroup sends SIGTERM, or SIGKILL when kill is set, to the group
// that proc leads. A group with no process left is not an error.
func signalGroup(proc *os.Process, kill bool) error {
	sig := syscall.SIGTERM
	if kill {
		sig = syscall.SIGKILL
	}
	if err := syscall.Kill(-proc.Pid, sig); err != nil && !errors.Is(err, syscall.ESRCH) {
		return err
	}
	return nil
}
