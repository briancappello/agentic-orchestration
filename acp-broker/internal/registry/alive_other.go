//go:build !unix

package registry

import "os"

// processAlive reports whether a process with pid exists. Without a
// signal to probe with, finding the process is the best evidence.
func processAlive(pid int) bool {
	p, err := os.FindProcess(pid)
	if err != nil {
		return false
	}
	_ = p.Release()
	return true
}
