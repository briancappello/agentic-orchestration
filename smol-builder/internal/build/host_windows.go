package build

import "os"

// On Windows smol-builder cannot tell whether a build still runs, so it
// treats every labeled builder machine as live and deletes none.
func (systemHost) BootID() string { return "" }

func (systemHost) Self() Process { return Process{PID: os.Getpid()} }

func (systemHost) Running(Process) bool { return true }
