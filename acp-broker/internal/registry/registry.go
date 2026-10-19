// Package registry lets human clients find live ACP broker sessions by
// key without knowing broker process IDs.
package registry

import (
	"context"
	"net"
	"os"
	"path/filepath"
	"time"
)

// Dir returns the registry directory: $XDG_RUNTIME_DIR/acp-broker, or
// acp-broker under the temporary directory when XDG_RUNTIME_DIR is unset.
func Dir() string {
	dir := os.Getenv("XDG_RUNTIME_DIR")
	if dir == "" {
		dir = os.TempDir()
	}
	return filepath.Join(dir, "acp-broker")
}

// dialTimeout bounds the liveness probe of one socket.
const dialTimeout = 200 * time.Millisecond

// SocketAccepts reports whether the Unix socket at path accepts a
// connection.
func SocketAccepts(path string) bool {
	ctx, cancel := context.WithTimeout(context.Background(), dialTimeout)
	defer cancel()
	conn, err := (&net.Dialer{}).DialContext(ctx, "unix", path)
	if err != nil {
		return false
	}
	_ = conn.Close()
	return true
}
