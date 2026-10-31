package latest

import (
	"context"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"testing"
)

// fixtures serves canned bodies by request path and records each request's
// headers.
type fixtures struct {
	t       *testing.T
	routes  map[string]route
	headers map[string]http.Header
}

type route struct {
	contentType string
	header      map[string]string
	body        string
}

func serve(t *testing.T, routes map[string]route) (*Client, *fixtures) {
	t.Helper()
	f := &fixtures{t: t, routes: routes, headers: map[string]http.Header{}}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		f.headers[r.URL.Path] = r.Header.Clone()
		rt, ok := f.routes[r.URL.Path]
		if !ok {
			http.NotFound(w, r)
			return
		}
		if rt.contentType != "" {
			w.Header().Set("Content-Type", rt.contentType)
		}
		for k, v := range rt.header {
			w.Header().Set(k, v)
		}
		_, _ = w.Write([]byte(rt.body))
	}))
	t.Cleanup(srv.Close)
	c := &Client{
		HTTP:           srv.Client(),
		GitHubAPI:      srv.URL + "/gh",
		GoReleases:     srv.URL + "/go",
		NodeReleases:   srv.URL + "/node",
		PythonReleases: srv.URL + "/python",
		RustChannel:    srv.URL + "/rust",
		RustupChannel:  srv.URL + "/rustup",
		RegistryAuth:   srv.URL + "/token",
		Registry:       srv.URL + "/registry",
	}
	return c, f
}

func mustVersion(t *testing.T, got Version, err error, want string) {
	t.Helper()
	if err != nil {
		t.Fatal(err)
	}
	if got.String() != want {
		t.Errorf("got %s, want %s", got, want)
	}
}

func TestParseVersion(t *testing.T) {
	for _, tc := range []struct {
		in   string
		want Version
		ok   bool
	}{
		{"1.2.3", Version{1, 2, 3}, true},
		{"v24.22.2", Version{24, 22, 2}, true},
		{"1.10.0", Version{1, 10, 0}, true},
		{"1.2", Version{}, false},
		{"1.2.3-rc1", Version{}, false},
		{"3.15.0b2", Version{}, false},
		{"go1.27.3", Version{}, false},
		{"", Version{}, false},
	} {
		got, ok := ParseVersion(tc.in)
		if got != tc.want || ok != tc.ok {
			t.Errorf("ParseVersion(%q) = %v, %v; want %v, %v", tc.in, got, ok, tc.want, tc.ok)
		}
	}
	if !(Version{1, 9, 9}).Less(Version{1, 10, 0}) || (Version{1, 10, 0}).Less(Version{1, 10, 0}) {
		t.Error("Less does not order numerically")
	}
}

func TestGitHubReleaseSkipsPrereleasesAndDrafts(t *testing.T) {
	c, f := serve(t, map[string]route{"/gh/repos/o/r/releases": {body: `[
		{"tag_name":"v3.0.0","prerelease":true,"draft":false},
		{"tag_name":"v2.9.0","prerelease":false,"draft":true},
		{"tag_name":"v2.1.0-rc1","prerelease":false,"draft":false},
		{"tag_name":"v2.0.10","prerelease":false,"draft":false},
		{"tag_name":"v2.0.9","prerelease":false,"draft":false}
	]`}})
	c.GitHubToken = "secret"
	v, err := c.GitHubRelease(context.Background(), "o/r")
	mustVersion(t, v, err, "2.0.10")
	if got := f.headers["/gh/repos/o/r/releases"].Get("Authorization"); got != "Bearer secret" {
		t.Errorf("Authorization = %q, want the bearer token", got)
	}
}

func TestGitHubReleaseWithoutToken(t *testing.T) {
	c, f := serve(t, map[string]route{"/gh/repos/o/r/releases": {body: `[{"tag_name":"0.13.6"}]`}})
	v, err := c.GitHubRelease(context.Background(), "o/r")
	mustVersion(t, v, err, "0.13.6")
	if got := f.headers["/gh/repos/o/r/releases"].Get("Authorization"); got != "" {
		t.Errorf("Authorization = %q, want none", got)
	}
}

func TestGoStable(t *testing.T) {
	c, _ := serve(t, map[string]route{"/go": {body: `[
		{"version":"go1.28rc1","stable":false},
		{"version":"go1.27.3","stable":true},
		{"version":"go1.26.10","stable":true}
	]`}})
	v, err := c.GoStable(context.Background())
	mustVersion(t, v, err, "1.27.3")
}

func TestNodeLTS(t *testing.T) {
	c, _ := serve(t, map[string]route{"/node": {body: `[
		{"version":"v27.1.0","lts":false},
		{"version":"v26.13.0","lts":"Lithium"},
		{"version":"v24.22.2","lts":"Krypton"}
	]`}})
	v, err := c.NodeLTS(context.Background())
	mustVersion(t, v, err, "26.13.0")
}

func TestCPythonFinalOnly(t *testing.T) {
	c, _ := serve(t, map[string]route{"/python": {body: `[
		{"name":"Python 3.16.0a1","pre_release":true},
		{"name":"Python install manager 26.4","pre_release":false},
		{"name":"Python 3.14.10","pre_release":false},
		{"name":"Python 3.15.2","pre_release":false},
		{"name":"Python 3.15.3","pre_release":true}
	]`}})
	v, err := c.CPython(context.Background())
	mustVersion(t, v, err, "3.15.2")
}

func TestRustStable(t *testing.T) {
	c, _ := serve(t, map[string]route{"/rust": {body: `manifest-version = "2"
date = "2026-10-13"
[pkg.cargo]
version = "0.100.1 (abc 2026-10-01)"
[pkg.rust]
version = "1.99.1 (58cf8f9c3 2026-10-13)"
[pkg.rust.target.x86_64-unknown-linux-gnu]
available = true
`}})
	v, err := c.RustStable(context.Background())
	mustVersion(t, v, err, "1.99.1")
}

func TestRustupStable(t *testing.T) {
	c, _ := serve(t, map[string]route{"/rustup": {body: "schema-version = '1'\nversion = '1.29.2'\n"}})
	v, err := c.RustupStable(context.Background())
	mustVersion(t, v, err, "1.29.2")
}

const indexBody = `{"mediaType":"application/vnd.oci.image.index.v1+json","manifests":[
	{"digest":"sha256:arm","platform":{"architecture":"arm","os":"linux","variant":"v7"}},
	{"digest":"sha256:att","platform":{"architecture":"unknown","os":"unknown"}},
	{"digest":"sha256:amd","platform":{"architecture":"amd64","os":"linux"}}
]}`

func TestImageDigestPicksThePlatformFromAnIndex(t *testing.T) {
	c, f := serve(t, map[string]route{
		"/token": {body: `{"token":"anon"}`},
		"/registry/v2/library/debian/manifests/trixie-slim": {
			contentType: "application/vnd.oci.image.index.v1+json",
			header:      map[string]string{"Docker-Content-Digest": "sha256:index"},
			body:        indexBody,
		},
	})
	d, err := c.ImageDigest(context.Background(), "library/debian", "trixie-slim", Platform{OS: "linux", Architecture: "amd64"})
	if err != nil {
		t.Fatal(err)
	}
	if d != "sha256:amd" {
		t.Errorf("digest = %s, want the linux/amd64 manifest", d)
	}
	if got := f.headers["/registry/v2/library/debian/manifests/trixie-slim"].Get("Authorization"); got != "Bearer anon" {
		t.Errorf("Authorization = %q", got)
	}
}

func TestImageDigestOfASinglePlatformTag(t *testing.T) {
	c, _ := serve(t, map[string]route{
		"/token": {body: `{"token":"anon"}`},
		"/registry/v2/library/debian/manifests/trixie-slim": {
			contentType: "application/vnd.oci.image.manifest.v1+json",
			header:      map[string]string{"Docker-Content-Digest": "sha256:single"},
			body:        `{"mediaType":"application/vnd.oci.image.manifest.v1+json","layers":[]}`,
		},
	})
	d, err := c.ImageDigest(context.Background(), "library/debian", "trixie-slim", Platform{OS: "linux", Architecture: "amd64"})
	if err != nil || d != "sha256:single" {
		t.Errorf("digest = %s, %v; want sha256:single", d, err)
	}
}

func TestImageDigestMissingPlatform(t *testing.T) {
	c, _ := serve(t, map[string]route{
		"/token": {body: `{"token":"anon"}`},
		"/registry/v2/library/debian/manifests/trixie-slim": {body: indexBody},
	})
	_, err := c.ImageDigest(context.Background(), "library/debian", "trixie-slim", Platform{OS: "linux", Architecture: "riscv64"})
	if err == nil || !strings.Contains(err.Error(), "linux/riscv64") {
		t.Errorf("err = %v, want one naming the platform", err)
	}
}

// Every lookup names its source when the source fails or lists nothing.
func TestFailuresNameTheSource(t *testing.T) {
	c, _ := serve(t, map[string]route{
		"/go":     {body: `not json`},
		"/node":   {body: `[{"version":"v27.0.0","lts":false}]`},
		"/rust":   {body: `[pkg.cargo]` + "\nversion = \"1\"\n"},
		"/rustup": {body: `= broken`},
	})
	ctx := context.Background()
	for name, tc := range map[string]struct {
		source string
		call   func() (Version, error)
	}{
		"github not found": {c.GitHubAPI + "/repos/o/r/releases", func() (Version, error) { return c.GitHubRelease(ctx, "o/r") }},
		"go unparsable":    {c.GoReleases, func() (Version, error) { return c.GoStable(ctx) }},
		"node no lts":      {c.NodeReleases, func() (Version, error) { return c.NodeLTS(ctx) }},
		"python not found": {c.PythonReleases, func() (Version, error) { return c.CPython(ctx) }},
		"rust no pkg.rust": {c.RustChannel, func() (Version, error) { return c.RustStable(ctx) }},
		"rustup broken":    {c.RustupChannel, func() (Version, error) { return c.RustupStable(ctx) }},
		"registry token": {c.RegistryAuth, func() (Version, error) {
			_, err := c.ImageDigest(ctx, "library/debian", "trixie-slim", Platform{OS: "linux", Architecture: "amd64"})
			return Version{}, err
		}},
	} {
		t.Run(name, func(t *testing.T) {
			_, err := tc.call()
			if err == nil || !strings.Contains(err.Error(), tc.source) {
				t.Errorf("err = %v, want one naming %s", err, tc.source)
			}
		})
	}
}

func TestParseModules(t *testing.T) {
	stream := `{"Path":"example.com/me","Main":true}
{"Path":"github.com/a/old","Version":"v1.0.0","Update":{"Path":"github.com/a/old","Version":"v1.2.0"}}
{"Path":"github.com/b/current","Version":"v2.0.0"}
`
	got, err := parseModules(strings.NewReader(stream))
	if err != nil {
		t.Fatal(err)
	}
	want := []ModuleUpdate{{Path: "github.com/a/old", Version: "v1.0.0", Latest: "v1.2.0"}}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("got %v, want %v", got, want)
	}

	_, err = parseModules(strings.NewReader(`{"Path":"github.com/x","Error":{"Err":"not found"}}`))
	if err == nil || !strings.Contains(err.Error(), goListCommand) || !strings.Contains(err.Error(), "github.com/x") {
		t.Errorf("err = %v, want one naming go list and the module", err)
	}
}
