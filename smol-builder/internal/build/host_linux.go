package build

import (
	"os"
	"strconv"
	"strings"
)

func (systemHost) BootID() string {
	data, err := os.ReadFile("/proc/sys/kernel/random/boot_id")
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(data))
}

func (systemHost) Self() Process {
	pid := os.Getpid()
	start, _ := procStat(pid)
	return Process{PID: pid, Start: start}
}

// Running reads /proc. Within one boot, a process ID and start time name
// exactly one process, so a reused ID is not mistaken for the build. A
// zombie has exited.
func (systemHost) Running(p Process) bool {
	start, state := procStat(p.PID)
	if start == "" || state == "Z" || state == "X" {
		return false
	}
	return p.Start == "" || p.Start == start
}

// procStat returns a process's start time, in clock ticks since boot, and
// its state, or "" when there is no such process.
func procStat(pid int) (start, state string) {
	if pid <= 0 {
		return "", ""
	}
	data, err := os.ReadFile("/proc/" + strconv.Itoa(pid) + "/stat")
	if err != nil {
		return "", ""
	}
	// The command name, field 2, is in parentheses and may hold spaces.
	i := strings.LastIndexByte(string(data), ')')
	if i < 0 {
		return "", ""
	}
	// After it: field 3 (state) onward; field 22 is the start time.
	fields := strings.Fields(string(data[i+1:]))
	if len(fields) < 20 {
		return "", ""
	}
	return fields[19], fields[0]
}
