package build

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strconv"
)

// ownerFile, in each temporary directory a build makes, records the build
// the way a builder machine's labels do, so a later build can tell whether
// the directory was left behind.
const ownerFile = ".smol-builder-owner"

// ownedTempDir makes a temporary directory, as os.MkdirTemp does, and
// records this build as its owner.
func (b *Builder) ownedTempDir(parent, pattern string) (string, error) {
	dir, err := os.MkdirTemp(parent, pattern)
	if err != nil {
		return "", err
	}
	self := b.Host.Self()
	owner := map[string]string{LabelPID: strconv.Itoa(self.PID)}
	if self.Start != "" {
		owner[LabelStart] = self.Start
	}
	if boot := b.Host.BootID(); boot != "" {
		owner[LabelBoot] = boot
	}
	data, err := json.Marshal(owner)
	if err == nil {
		err = os.WriteFile(filepath.Join(dir, ownerFile), data, 0o600)
	}
	if err != nil {
		_ = os.RemoveAll(dir)
		return "", err
	}
	return dir, nil
}

// sweepDirs removes the directories matching pattern in parent that an
// earlier build left behind. A directory without a readable owner file is
// not one of ours and stays. Failures are logged: a leftover directory
// costs space, not correctness.
func (b *Builder) sweepDirs(parent, pattern string) {
	if parent == "" {
		parent = os.TempDir()
	}
	matches, err := filepath.Glob(filepath.Join(parent, pattern))
	if err != nil {
		return
	}
	boot := b.Host.BootID()
	for _, dir := range matches {
		data, err := os.ReadFile(filepath.Join(dir, ownerFile)) //nolint:gosec // a directory name this tool chose
		if err != nil {
			continue
		}
		var owner map[string]string
		if json.Unmarshal(data, &owner) != nil {
			continue
		}
		reason, ok := leftBehind(owner, boot, b.Host)
		if !ok {
			continue
		}
		b.logf("removing %s, left behind: %s", dir, reason)
		if err := os.RemoveAll(dir); err != nil {
			b.logf("removing %s: %v", dir, err)
		}
	}
}
