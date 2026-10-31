package latest

import (
	"context"
	"os"
	"testing"
	"time"
)

// TestLatestGoModules fails for every module smol-builder requires that has
// a newer release.
func TestLatestGoModules(t *testing.T) {
	if os.Getenv("SMOL_BUILDER_LATEST_TEST") != "1" {
		t.Skip("set SMOL_BUILDER_LATEST_TEST=1 to compare the Go modules with their latest releases")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()
	updates, err := GoModules(ctx, ".")
	if err != nil {
		t.Fatal(err)
	}
	for _, u := range updates {
		t.Errorf("Go module %s: using %s, latest is %s", u.Path, u.Version, u.Latest)
	}
}
