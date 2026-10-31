// Package latest holds the version test of acp-broker's Go modules. It has
// no code of its own; smol-builder keeps the same go list check, since the
// two modules do not import each other.
package latest

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"os"
	"os/exec"
	"strings"
	"testing"
	"time"
)

// TestLatestGoModules fails for every module acp-broker requires that has a
// newer release. It runs go list outside the workspace, so it checks this
// module's own build list.
func TestLatestGoModules(t *testing.T) {
	if os.Getenv("ACP_BROKER_LATEST_TEST") != "1" {
		t.Skip("set ACP_BROKER_LATEST_TEST=1 to compare the Go modules with their latest releases")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()
	const source = "go list -m -u -json all"
	cmd := exec.CommandContext(ctx, "go", "list", "-m", "-u", "-json", "all")
	cmd.Env = append(os.Environ(), "GOWORK=off")
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	out, err := cmd.Output()
	if err != nil {
		t.Fatalf("%s: %v: %s", source, err, strings.TrimSpace(stderr.String()))
	}
	dec := json.NewDecoder(bytes.NewReader(out))
	for {
		var m struct {
			Path    string
			Version string
			Main    bool
			Update  *struct{ Version string }
			Error   *struct{ Err string }
		}
		if err := dec.Decode(&m); errors.Is(err, io.EOF) {
			return
		} else if err != nil {
			t.Fatalf("%s: parsing: %v", source, err)
		}
		switch {
		case m.Error != nil:
			t.Errorf("%s: %s: %s", source, m.Path, m.Error.Err)
		case m.Main:
			t.Logf("module %s", m.Path)
		case m.Update != nil:
			t.Errorf("Go module %s: using %s, latest is %s", m.Path, m.Version, m.Update.Version)
		default:
			t.Logf("Go module %s: using %s, the latest", m.Path, m.Version)
		}
	}
}
