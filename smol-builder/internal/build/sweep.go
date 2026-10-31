package build

import (
	"context"
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
)

// Labels that tie a builder machine to the build that created it.
const (
	LabelPID   = "smol-builder.pid"
	LabelStart = "smol-builder.start"
	LabelBoot  = "smol-builder.boot"
)

// builderLabels are the --label arguments of a builder machine.
func (b *Builder) builderLabels() []string {
	self := b.Host.Self()
	args := []string{"--label", BuilderLabel, "--label", LabelPID + "=" + strconv.Itoa(self.PID)}
	if self.Start != "" {
		args = append(args, "--label", LabelStart+"="+self.Start)
	}
	if boot := b.Host.BootID(); boot != "" {
		args = append(args, "--label", LabelBoot+"="+boot)
	}
	return args
}

type listedMachine struct {
	Name   string            `json:"name"`
	Labels map[string]string `json:"labels"`
}

// sweep deletes every builder machine an earlier run left behind: one whose
// boot ID is not the current boot's, or whose build no longer runs. It keeps
// every machine without BuilderLabel, and every builder machine without a
// process ID, which only an older smol-builder creates.
func (b *Builder) sweep(ctx context.Context) error {
	out, err := b.Run.Output(ctx, "smolvm", "machine", "ls", "--json")
	if err != nil {
		return fmt.Errorf("listing machines: %w", err)
	}
	var machines []listedMachine
	if err := json.Unmarshal(out, &machines); err != nil {
		return fmt.Errorf("smolvm machine ls --json: %w", err)
	}
	key, value, _ := strings.Cut(BuilderLabel, "=")
	boot := b.Host.BootID()
	for _, m := range machines {
		if m.Labels[key] != value {
			continue
		}
		reason, ok := leftBehind(m.Labels, boot, b.Host)
		if reason == "" {
			continue
		}
		if !ok {
			b.logf("keeping builder machine %s: %s", m.Name, reason)
			continue
		}
		b.logf("builder machine %s was left behind: %s", m.Name, reason)
		if err := b.deleteMachine(ctx, m.Name); err != nil {
			return err
		}
	}
	return nil
}

// leftBehind returns why a builder machine with labels is left behind, with
// ok set; or, with ok unset, why it is kept although its build cannot be
// told; or "" for a live build's machine.
func leftBehind(labels map[string]string, boot string, host Host) (reason string, ok bool) {
	pid, err := strconv.Atoi(labels[LabelPID])
	if err != nil || pid <= 0 {
		return "it has no " + LabelPID + " label, so an older smol-builder made it and its build may still run", false
	}
	if theirs := labels[LabelBoot]; theirs != "" && boot != "" && theirs != boot {
		return "it was created before the host last started", true
	}
	if !host.Running(Process{PID: pid, Start: labels[LabelStart]}) {
		return "its build, process " + strconv.Itoa(pid) + ", no longer runs", true
	}
	return "", false
}
