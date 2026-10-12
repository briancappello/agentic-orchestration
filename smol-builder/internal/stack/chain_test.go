package stack

import (
	"os"
	"path/filepath"
	"regexp"
	"testing"
)

func resolve(t *testing.T, lib *Library, repo, toml string) []Step {
	t.Helper()
	def, err := Parse([]byte(toml), repo, lib)
	if err != nil {
		t.Fatal(err)
	}
	steps, err := Resolve(lib, def)
	if err != nil {
		t.Fatal(err)
	}
	return steps
}

func stepNames(steps []Step) []string {
	out := make([]string, len(steps))
	for i, s := range steps {
		out[i] = s.Name
	}
	return out
}

func TestResolveOrderIgnoresListing(t *testing.T) {
	lib := testLibrary(t)
	repo := t.TempDir()
	a := resolve(t, lib, repo, `layers = ["node", "go"]`)
	b := resolve(t, lib, repo, `layers = ["go", "node"]`)
	if got := stepNames(a); len(got) != 3 || got[0] != "base" || got[1] != "go" || got[2] != "node" {
		t.Fatalf("steps = %v, want [base go node]", got)
	}
	for i := range a {
		if a[i].Tag != b[i].Tag {
			t.Errorf("step %d: tag %s != %s", i, a[i].Tag, b[i].Tag)
		}
	}
	tagRE := regexp.MustCompile(`^localhost/smol-builder/chain:[0-9a-f]{16}$`)
	for _, s := range a {
		if !tagRE.MatchString(s.Tag) {
			t.Errorf("tag %q does not match %s", s.Tag, tagRE)
		}
	}
}

func TestResolveSharedPrefix(t *testing.T) {
	lib := testLibrary(t)
	repo := t.TempDir()
	goOnly := resolve(t, lib, repo, `layers = ["go"]`)
	goNode := resolve(t, lib, repo, `layers = ["go", "node"]`)
	if goOnly[0].Tag != goNode[0].Tag || goOnly[1].Tag != goNode[1].Tag {
		t.Fatal("a chain prefix must keep its tags when layers are added after it")
	}
	nodeOnly := resolve(t, lib, repo, `layers = ["node"]`)
	if nodeOnly[1].Tag == goNode[2].Tag {
		t.Fatal("node on base and node on go must differ")
	}
}

func TestResolveChangedLayerFile(t *testing.T) {
	lib := testLibrary(t)
	repo := t.TempDir()
	const toml = `layers = ["go", "node", "python"]`
	before := resolve(t, lib, repo, toml)

	// A new file in the node layer changes node and every later step only.
	writeFiles(t, lib.LayerDir("node"), map[string]string{"extra.txt": "x"})
	after := resolve(t, lib, repo, toml)
	changedFrom := 2 // base, go, [node, python]
	for i := range before {
		same := before[i].Tag == after[i].Tag
		if i < changedFrom && !same {
			t.Errorf("step %s changed, want unchanged", before[i].Name)
		}
		if i >= changedFrom && same {
			t.Errorf("step %s unchanged, want changed", before[i].Name)
		}
	}

	// Editing an existing file and the executable bit both count.
	writeFiles(t, lib.LayerDir("node"), map[string]string{"extra.txt": "y"})
	edited := resolve(t, lib, repo, toml)
	if edited[2].Tag == after[2].Tag {
		t.Error("editing a file did not change the tag")
	}
	if err := os.Chmod(filepath.Join(lib.LayerDir("node"), "extra.txt"), 0o755); err != nil {
		t.Fatal(err)
	}
	if chmodded := resolve(t, lib, repo, toml); chmodded[2].Tag == edited[2].Tag {
		t.Error("making a file executable did not change the tag")
	}
}

func TestResolveProjectLayerLast(t *testing.T) {
	lib := testLibrary(t)
	repo := t.TempDir()
	writeFiles(t, repo, map[string]string{
		"ci/agent.Dockerfile": goodHeader,
		"ci/packages.txt":     "libpq-dev\n",
		".git/HEAD":           "ref: refs/heads/main\n",
		"src/main.go":         "package main\n",
	})
	const toml = "layers = [\"python\", \"go\"]\nproject_layer = \"ci/agent.Dockerfile\""
	steps := resolve(t, lib, repo, toml)
	if got := stepNames(steps); len(got) != 4 || got[3] != ProjectStep || got[1] != "go" || got[2] != "python" {
		t.Fatalf("steps = %v, want [base go python project]", got)
	}
	project := steps[3]
	if project.Context != filepath.Dir(project.Dockerfile) || filepath.Base(project.Dockerfile) != "agent.Dockerfile" {
		t.Fatalf("project step context %q dockerfile %q", project.Context, project.Dockerfile)
	}

	// Files outside the project layer's directory are not its context.
	writeFiles(t, repo, map[string]string{"src/main.go": "package main // edited\n"})
	if again := resolve(t, lib, repo, toml); again[3].Tag != project.Tag {
		t.Error("a file outside the project layer's context changed its tag")
	}
	writeFiles(t, repo, map[string]string{"ci/packages.txt": "libpq-dev\ncurl\n"})
	again := resolve(t, lib, repo, toml)
	if again[3].Tag == project.Tag {
		t.Error("a file in the project layer's context did not change its tag")
	}
	if again[2].Tag != steps[2].Tag {
		t.Error("a project file changed a library step's tag")
	}
}

func TestResolveSkipsGitDirectory(t *testing.T) {
	lib := testLibrary(t)
	repo := t.TempDir()
	writeFiles(t, repo, map[string]string{"Dockerfile": goodHeader, ".git/HEAD": "a"})
	const toml = `project_layer = "Dockerfile"`
	before := resolve(t, lib, repo, toml)
	writeFiles(t, repo, map[string]string{".git/HEAD": "b", ".git/objects/x": "y"})
	if after := resolve(t, lib, repo, toml); after[1].Tag != before[1].Tag {
		t.Error("a change under .git changed the project tag")
	}
}

func TestResolveProjectDockerfileName(t *testing.T) {
	lib := testLibrary(t)
	repo := t.TempDir()
	writeFiles(t, repo, map[string]string{"a.Dockerfile": goodHeader, "b.Dockerfile": goodHeader})
	a := resolve(t, lib, repo, `project_layer = "a.Dockerfile"`)
	b := resolve(t, lib, repo, `project_layer = "b.Dockerfile"`)
	if a[1].Tag == b[1].Tag {
		t.Error("two Dockerfiles in one context must give different tags")
	}
}
