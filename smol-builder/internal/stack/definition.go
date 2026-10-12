package stack

import (
	"bufio"
	"bytes"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/BurntSushi/toml"
)

// FileName is the stack definition's name at the repository root.
const FileName = "smol-builder.toml"

// Definition is a validated stack definition.
type Definition struct {
	// Layers are the library layers to apply on top of the base, sorted.
	Layers []string
	// ProjectLayer is the declared project_layer path, relative to the
	// repository root, or empty when there is none.
	ProjectLayer string
	// ProjectDockerfile is the project layer's absolute path with symlinks
	// resolved. Its directory is the project layer's build context.
	ProjectDockerfile string
}

type rawDefinition struct {
	Layers       []string `toml:"layers"`
	ProjectLayer *string  `toml:"project_layer"`
}

// Load reads and validates FileName at the root of repo against lib.
func Load(repo string, lib *Library) (*Definition, error) {
	path := filepath.Join(repo, FileName)
	data, err := os.ReadFile(path) //nolint:gosec // the repository is the user's input
	if err != nil {
		return nil, fmt.Errorf("stack definition: %w", err)
	}
	def, err := Parse(data, repo, lib)
	if err != nil {
		return nil, fmt.Errorf("%s: %w", path, err)
	}
	return def, nil
}

// Parse validates a stack definition whose repository root is repo. Every
// error names the offending key, layer, or path.
func Parse(data []byte, repo string, lib *Library) (*Definition, error) {
	var raw rawDefinition
	md, err := toml.Decode(string(data), &raw)
	if err != nil {
		return nil, err
	}
	if undecoded := md.Undecoded(); len(undecoded) > 0 {
		keys := make([]string, len(undecoded))
		for i, k := range undecoded {
			keys[i] = fmt.Sprintf("%q", k.String())
		}
		return nil, fmt.Errorf("unknown key %s (allowed: layers, project_layer)", strings.Join(keys, ", "))
	}

	def := &Definition{}
	seen := map[string]bool{}
	for _, name := range raw.Layers {
		switch {
		case name == BaseLayer:
			return nil, fmt.Errorf("layers: %q is always applied and cannot be listed", name)
		case !lib.Has(name):
			return nil, fmt.Errorf("layers: unknown layer %q (library has: %s)", name, strings.Join(lib.Names(), ", "))
		case seen[name]:
			return nil, fmt.Errorf("layers: duplicate layer %q", name)
		}
		seen[name] = true
		def.Layers = append(def.Layers, name)
	}
	sort.Strings(def.Layers)

	if raw.ProjectLayer != nil {
		rel := *raw.ProjectLayer
		abs, err := resolveInRepo(repo, rel)
		if err != nil {
			return nil, fmt.Errorf("project_layer %q: %w", rel, err)
		}
		if err := checkProjectHeader(abs); err != nil {
			return nil, fmt.Errorf("project_layer %q: %w", rel, err)
		}
		def.ProjectLayer = rel
		def.ProjectDockerfile = abs
	}
	return def, nil
}

var errOutsideRepo = errors.New("path leaves the repository")

// resolveInRepo resolves rel against repo and returns the real path of the
// regular file it names. Absolute paths, ".." segments, and symlinks that
// lead outside the repository are refused.
func resolveInRepo(repo, rel string) (string, error) {
	if rel == "" {
		return "", errors.New("path is empty")
	}
	if filepath.IsAbs(rel) || !filepath.IsLocal(rel) {
		return "", errOutsideRepo
	}
	root, err := filepath.EvalSymlinks(repo)
	if err != nil {
		return "", fmt.Errorf("repository: %w", err)
	}
	root, err = filepath.Abs(root)
	if err != nil {
		return "", err
	}
	real, err := filepath.EvalSymlinks(filepath.Join(root, rel))
	if errors.Is(err, fs.ErrNotExist) {
		return "", errors.New("file does not exist")
	}
	if err != nil {
		return "", err
	}
	inside, err := filepath.Rel(root, real)
	if err != nil || !filepath.IsLocal(inside) {
		return "", errOutsideRepo
	}
	info, err := os.Stat(real)
	if err != nil {
		return "", err
	}
	if !info.Mode().IsRegular() {
		return "", errors.New("not a regular file")
	}
	return real, nil
}

// checkProjectHeader requires the Dockerfile's first two instructions to be
// ARG BASE and FROM ${BASE}, optionally naming the stage. That is what lets
// the project layer go on top of any chain.
func checkProjectHeader(path string) error {
	data, err := os.ReadFile(path) //nolint:gosec // path was resolved inside the repository
	if err != nil {
		return err
	}
	instrs := firstInstructions(data, 2)
	want := "first instructions must be \"ARG BASE\" then \"FROM ${BASE}\""
	if len(instrs) < 1 || !isArgBase(instrs[0]) {
		return fmt.Errorf("%s; found %s", want, describe(instrs, 0))
	}
	if len(instrs) < 2 || !isFromBase(instrs[1]) {
		return fmt.Errorf("%s; found %s", want, describe(instrs, 1))
	}
	return nil
}

func describe(instrs [][]string, i int) string {
	if i >= len(instrs) {
		return "end of file"
	}
	return fmt.Sprintf("%q", strings.Join(instrs[i], " "))
}

func isArgBase(f []string) bool {
	return len(f) == 2 && strings.EqualFold(f[0], "ARG") && f[1] == "BASE"
}

func isFromBase(f []string) bool {
	if len(f) < 2 || !strings.EqualFold(f[0], "FROM") || f[1] != "${BASE}" {
		return false
	}
	return len(f) == 2 || (len(f) == 4 && strings.EqualFold(f[2], "AS"))
}

// firstInstructions returns up to n instructions as whitespace-separated
// fields. Blank lines and comments, parser directives included, are skipped;
// a trailing backslash continues an instruction on the next line.
func firstInstructions(data []byte, n int) [][]string {
	var out [][]string
	var cur strings.Builder
	sc := bufio.NewScanner(bytes.NewReader(data))
	for sc.Scan() && len(out) < n {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		if cont, ok := strings.CutSuffix(line, `\`); ok {
			cur.WriteString(cont)
			cur.WriteByte(' ')
			continue
		}
		cur.WriteString(line)
		out = append(out, strings.Fields(cur.String()))
		cur.Reset()
	}
	if cur.Len() > 0 && len(out) < n {
		out = append(out, strings.Fields(cur.String()))
	}
	return out
}
