// Package stack reads a repository's stack definition and resolves it into
// an ordered chain of image builds over a layer library.
package stack

import (
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"sort"
)

// BaseLayer is the library layer every chain starts from. It is always
// applied and cannot be listed in a stack definition.
const BaseLayer = "base"

// Library is a directory of layers, one subdirectory per layer, each holding
// a Dockerfile.
type Library struct {
	dir   string
	names map[string]bool
}

// OpenLibrary reads the layer names under dir. It fails when dir has no base
// layer.
func OpenLibrary(dir string) (*Library, error) {
	abs, err := filepath.Abs(dir)
	if err != nil {
		return nil, fmt.Errorf("layer library %q: %w", dir, err)
	}
	entries, err := os.ReadDir(abs)
	if err != nil {
		return nil, fmt.Errorf("layer library %q: %w", dir, err)
	}
	lib := &Library{dir: abs, names: map[string]bool{}}
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		info, err := os.Stat(filepath.Join(abs, e.Name(), "Dockerfile"))
		if err != nil || !info.Mode().IsRegular() {
			continue
		}
		lib.names[e.Name()] = true
	}
	if !lib.names[BaseLayer] {
		return nil, fmt.Errorf("layer library %q: no %q layer (want %s)", dir, BaseLayer,
			filepath.Join(dir, BaseLayer, "Dockerfile"))
	}
	return lib, nil
}

// Dir is the library's absolute directory.
func (l *Library) Dir() string { return l.dir }

// Has reports whether name is a layer that a stack definition may list.
func (l *Library) Has(name string) bool { return name != BaseLayer && l.names[name] }

// Names lists the selectable layers, sorted. The base layer is not included.
func (l *Library) Names() []string {
	var out []string
	for n := range l.names {
		if n != BaseLayer {
			out = append(out, n)
		}
	}
	sort.Strings(out)
	return out
}

// LayerDir is the directory of the named layer.
func (l *Library) LayerDir(name string) string { return filepath.Join(l.dir, name) }

// ExtractLibrary copies a layer library from fsys into dir, which must exist.
// It is how the library embedded in the binary becomes a build context.
func ExtractLibrary(fsys fs.FS, dir string) error {
	return fs.WalkDir(fsys, ".", func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		target := filepath.Join(dir, filepath.FromSlash(path))
		switch {
		case d.IsDir():
			// Layer files are world-readable like a git checkout, so a COPY
			// in a layer yields the same file mode as building from a clone.
			return os.MkdirAll(target, 0o755) //nolint:gosec // build context, no secrets

		case d.Type().IsRegular():
			data, err := fs.ReadFile(fsys, path)
			if err != nil {
				return err
			}
			return os.WriteFile(target, data, 0o644) //nolint:gosec // build context, no secrets
		default:
			return errors.New("layer library: unsupported file type at " + path)
		}
	})
}
