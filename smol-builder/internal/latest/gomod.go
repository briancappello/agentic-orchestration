package latest

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"strings"
)

// ModuleUpdate is a Go module required at an older version than its latest.
type ModuleUpdate struct {
	Path, Version, Latest string
}

// goListCommand is the source GoModules names in its errors.
const goListCommand = "go list -m -u -json all"

// GoModules returns every module in the build list of the Go module in dir
// that has a newer release. It runs go list outside any workspace, so the
// answer is for that module alone.
func GoModules(ctx context.Context, dir string) ([]ModuleUpdate, error) {
	cmd := exec.CommandContext(ctx, "go", "list", "-m", "-u", "-json", "all")
	cmd.Dir = dir
	cmd.Env = append(os.Environ(), "GOWORK=off")
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	out, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("%s: %w: %s", goListCommand, err, strings.TrimSpace(stderr.String()))
	}
	return parseModules(bytes.NewReader(out))
}

// parseModules reads the stream of JSON objects go list -m -u -json prints.
func parseModules(r io.Reader) ([]ModuleUpdate, error) {
	var updates []ModuleUpdate
	dec := json.NewDecoder(r)
	for {
		var m struct {
			Path    string
			Version string
			Main    bool
			Update  *struct{ Version string }
			Error   *struct{ Err string }
		}
		if err := dec.Decode(&m); errors.Is(err, io.EOF) {
			return updates, nil
		} else if err != nil {
			return nil, fmt.Errorf("%s: parsing: %w", goListCommand, err)
		}
		if m.Error != nil {
			return nil, fmt.Errorf("%s: %s: %s", goListCommand, m.Path, m.Error.Err)
		}
		if !m.Main && m.Update != nil {
			updates = append(updates, ModuleUpdate{Path: m.Path, Version: m.Version, Latest: m.Update.Version})
		}
	}
}
