package build

// Process identifies a running build: its process ID and, where the host can
// tell, its start time, which tells a reused process ID from the original.
type Process struct {
	PID   int
	Start string
}

// Host answers which builds still run on this host.
type Host interface {
	// BootID identifies the host's current boot, or is "" when unknown.
	BootID() string
	// Self is this process.
	Self() Process
	// Running reports whether p still runs. When p has a start time, a
	// process with the same ID but another start time is not p.
	Running(p Process) bool
}

// systemHost is the Host of the machine smol-builder runs on. Its methods
// are in host_<os>.go.
type systemHost struct{}
