//go:build unix && !linux

package build

import (
	"errors"
	"os"
	"syscall"
)

// Without /proc there is no boot ID and no start time, so a builder machine
// is left behind only when no process has its ID. A reused ID keeps the
// machine: the sweep errs toward keeping one, never toward deleting a live
// build's.
func (systemHost) BootID() string { return "" }

func (systemHost) Self() Process { return Process{PID: os.Getpid()} }

func (systemHost) Running(p Process) bool {
	if p.PID <= 0 {
		return false
	}
	err := syscall.Kill(p.PID, 0)
	return err == nil || !errors.Is(err, syscall.ESRCH)
}
