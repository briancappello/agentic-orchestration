package stack

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"hash"
	"io"
	"io/fs"
	"os"
	"path/filepath"
	"sort"
	"strconv"
)

// ProjectStep names the project layer's step in a chain and in reports.
const ProjectStep = "project"

// TagRepository is the image repository every chain step is tagged in.
const TagRepository = "localhost/smol-builder/chain"

// Step is one image build in a chain.
type Step struct {
	// Name is the library layer's name, or ProjectStep.
	Name string
	// Context is the build context directory.
	Context string
	// Dockerfile is the Dockerfile's absolute path inside Context.
	Dockerfile string
	// Hash identifies the step: the previous step's hash, this step's name,
	// and the contents of its build context.
	Hash string
	// Tag is the image tag derived from Hash.
	Tag string
}

// Resolve orders def into a chain: the base, the library layers in sorted
// order, then the project layer. Each step's hash covers every step before
// it, so equal hashes mean equal inputs all the way down to the base.
func Resolve(lib *Library, def *Definition) ([]Step, error) {
	names := append([]string{BaseLayer}, def.Layers...)
	sort.Strings(names[1:])

	var steps []Step
	prev := "smol-builder chain v1"
	add := func(name, context, dockerfile string) error {
		rel, err := filepath.Rel(context, dockerfile)
		if err != nil {
			return err
		}
		content, err := dirHash(context)
		if err != nil {
			return fmt.Errorf("layer %s: %w", name, err)
		}
		h := sha256.New()
		for _, part := range []string{prev, name, filepath.ToSlash(rel), content} {
			h.Write([]byte(part))
			h.Write([]byte{0})
		}
		sum := hex.EncodeToString(h.Sum(nil))
		steps = append(steps, Step{
			Name:       name,
			Context:    context,
			Dockerfile: dockerfile,
			Hash:       sum,
			Tag:        TagRepository + ":" + sum[:16],
		})
		prev = sum
		return nil
	}
	for _, name := range names {
		dir := lib.LayerDir(name)
		if err := add(name, dir, filepath.Join(dir, "Dockerfile")); err != nil {
			return nil, err
		}
	}
	if def.ProjectDockerfile != "" {
		if err := add(ProjectStep, filepath.Dir(def.ProjectDockerfile), def.ProjectDockerfile); err != nil {
			return nil, err
		}
	}
	return steps, nil
}

// dirHash hashes a build context: every file's slash-separated relative
// path, its type (regular, executable, or symlink), and its bytes or link
// target, in sorted path order. Directories named .git are skipped.
func dirHash(root string) (string, error) {
	var paths []string
	err := filepath.WalkDir(root, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			if d.Name() == ".git" && path != root {
				return filepath.SkipDir
			}
			return nil
		}
		paths = append(paths, path)
		return nil
	})
	if err != nil {
		return "", err
	}
	sort.Strings(paths)

	h := sha256.New()
	for _, path := range paths {
		if err := hashEntry(h, root, path); err != nil {
			return "", err
		}
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

func hashEntry(h hash.Hash, root, path string) error {
	rel, err := filepath.Rel(root, path)
	if err != nil {
		return err
	}
	info, err := os.Lstat(path)
	if err != nil {
		return err
	}
	field := func(s string) {
		h.Write([]byte(s))
		h.Write([]byte{0})
	}
	field(filepath.ToSlash(rel))
	switch {
	case info.Mode()&fs.ModeSymlink != 0:
		target, err := os.Readlink(path)
		if err != nil {
			return err
		}
		field("symlink")
		field(target)
	case info.Mode().IsRegular():
		kind := "file"
		if info.Mode().Perm()&0o111 != 0 {
			kind = "exec"
		}
		field(kind)
		field(strconv.FormatInt(info.Size(), 10))
		f, err := os.Open(path) //nolint:gosec // path comes from walking the build context
		if err != nil {
			return err
		}
		defer f.Close() //nolint:errcheck // read-only
		n, err := io.Copy(h, f)
		if err != nil {
			return err
		}
		if n != info.Size() {
			return fmt.Errorf("%s changed while hashing", path)
		}
	default:
		field("other")
	}
	return nil
}
