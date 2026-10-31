// Package latest fetches the latest stable release of a dependency from its
// project's own release list.
//
// Every lookup that fails, because the source cannot be fetched or parsed or
// lists no stable release, returns an error that names the source.
package latest

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/BurntSushi/toml"
)

// Version is a release version of the form MAJOR.MINOR.PATCH.
type Version [3]int

var versionPattern = regexp.MustCompile(`^v?(\d+)\.(\d+)\.(\d+)$`)

// ParseVersion parses MAJOR.MINOR.PATCH, with an optional leading "v". It
// rejects anything else, so a prerelease suffix such as "-rc1" or "b2" is
// never a stable version.
func ParseVersion(s string) (Version, bool) {
	m := versionPattern.FindStringSubmatch(s)
	if m == nil {
		return Version{}, false
	}
	var v Version
	for i := range v {
		n, err := strconv.Atoi(m[i+1])
		if err != nil {
			return Version{}, false
		}
		v[i] = n
	}
	return v, true
}

// Less reports whether v is older than w.
func (v Version) Less(w Version) bool {
	for i := range v {
		if v[i] != w[i] {
			return v[i] < w[i]
		}
	}
	return false
}

func (v Version) String() string { return fmt.Sprintf("%d.%d.%d", v[0], v[1], v[2]) }

// Client looks up releases. The URL fields default to the public sources;
// tests point them at fixtures.
type Client struct {
	HTTP *http.Client
	// GitHubToken, when set, is sent to GitHub as a bearer token.
	GitHubToken string

	GitHubAPI      string
	GoReleases     string
	NodeReleases   string
	PythonReleases string
	RustChannel    string
	RustupChannel  string
	RegistryAuth   string
	Registry       string
}

// New returns a Client for the public sources, with the GitHub token from
// GH_TOKEN.
func New() *Client {
	return &Client{
		HTTP:           &http.Client{Timeout: 2 * time.Minute},
		GitHubToken:    os.Getenv("GH_TOKEN"),
		GitHubAPI:      "https://api.github.com",
		GoReleases:     "https://go.dev/dl/?mode=json",
		NodeReleases:   "https://nodejs.org/dist/index.json",
		PythonReleases: "https://www.python.org/api/v2/downloads/release/?is_published=true",
		RustChannel:    "https://static.rust-lang.org/dist/channel-rust-stable.toml",
		RustupChannel:  "https://static.rust-lang.org/rustup/release-stable.toml",
		RegistryAuth:   "https://auth.docker.io/token",
		Registry:       "https://registry-1.docker.io",
	}
}

// maxBody bounds a response; the Rust channel file is the largest, at about
// a megabyte.
const maxBody = 64 << 20

// get fetches rawURL and returns its body and headers. Errors name rawURL.
func (c *Client) get(ctx context.Context, rawURL string, header http.Header) ([]byte, http.Header, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, rawURL, nil)
	if err != nil {
		return nil, nil, fmt.Errorf("%s: %w", rawURL, err)
	}
	for k, vs := range header {
		for _, v := range vs {
			req.Header.Add(k, v)
		}
	}
	resp, err := c.HTTP.Do(req)
	if err != nil {
		return nil, nil, fmt.Errorf("%s: %w", rawURL, err)
	}
	defer func() { _ = resp.Body.Close() }()
	body, err := io.ReadAll(io.LimitReader(resp.Body, maxBody))
	if err != nil {
		return nil, nil, fmt.Errorf("%s: %w", rawURL, err)
	}
	if resp.StatusCode != http.StatusOK {
		return nil, nil, fmt.Errorf("%s: HTTP %s", rawURL, resp.Status)
	}
	return body, resp.Header, nil
}

// getJSON fetches rawURL and decodes its JSON body into v.
func (c *Client) getJSON(ctx context.Context, rawURL string, header http.Header, v any) error {
	body, _, err := c.get(ctx, rawURL, header)
	if err != nil {
		return err
	}
	if err := json.Unmarshal(body, v); err != nil {
		return fmt.Errorf("%s: parsing: %w", rawURL, err)
	}
	return nil
}

// newest returns the highest stable version among candidates, or an error
// naming source when there is none.
func newest(source string, candidates []string) (Version, error) {
	var best Version
	found := false
	for _, s := range candidates {
		v, ok := ParseVersion(s)
		if ok && (!found || best.Less(v)) {
			best, found = v, true
		}
	}
	if !found {
		return Version{}, fmt.Errorf("%s: no stable release listed", source)
	}
	return best, nil
}

// GitHubRelease returns the newest release of repo ("owner/name") on GitHub,
// skipping prereleases, drafts, and tags that are not MAJOR.MINOR.PATCH.
func (c *Client) GitHubRelease(ctx context.Context, repo string) (Version, error) {
	source := c.GitHubAPI + "/repos/" + repo + "/releases?per_page=100"
	header := http.Header{"Accept": {"application/vnd.github+json"}}
	if c.GitHubToken != "" {
		header.Set("Authorization", "Bearer "+c.GitHubToken)
	}
	var releases []struct {
		TagName    string `json:"tag_name"`
		Prerelease bool   `json:"prerelease"`
		Draft      bool   `json:"draft"`
	}
	if err := c.getJSON(ctx, source, header, &releases); err != nil {
		return Version{}, err
	}
	var tags []string
	for _, r := range releases {
		if !r.Prerelease && !r.Draft {
			tags = append(tags, r.TagName)
		}
	}
	return newest(source, tags)
}

// GoStable returns the newest stable Go release listed on go.dev/dl.
func (c *Client) GoStable(ctx context.Context) (Version, error) {
	var releases []struct {
		Version string `json:"version"`
		Stable  bool   `json:"stable"`
	}
	if err := c.getJSON(ctx, c.GoReleases, nil, &releases); err != nil {
		return Version{}, err
	}
	var vs []string
	for _, r := range releases {
		if r.Stable {
			vs = append(vs, strings.TrimPrefix(r.Version, "go"))
		}
	}
	return newest(c.GoReleases, vs)
}

// NodeLTS returns the newest Node.js LTS release.
func (c *Client) NodeLTS(ctx context.Context) (Version, error) {
	var releases []struct {
		Version string          `json:"version"`
		LTS     json.RawMessage `json:"lts"`
	}
	if err := c.getJSON(ctx, c.NodeReleases, nil, &releases); err != nil {
		return Version{}, err
	}
	var vs []string
	for _, r := range releases {
		// lts is false, or the name of the LTS line.
		if lts := strings.TrimSpace(string(r.LTS)); lts != "" && lts != "false" && lts != "null" {
			vs = append(vs, r.Version)
		}
	}
	return newest(c.NodeReleases, vs)
}

var pythonName = regexp.MustCompile(`^Python (\d+\.\d+\.\d+)$`)

// CPython returns the newest final CPython release listed by python.org.
func (c *Client) CPython(ctx context.Context) (Version, error) {
	var releases []struct {
		Name       string `json:"name"`
		PreRelease bool   `json:"pre_release"`
	}
	if err := c.getJSON(ctx, c.PythonReleases, nil, &releases); err != nil {
		return Version{}, err
	}
	var vs []string
	for _, r := range releases {
		// The list also holds other products, such as the install manager.
		if m := pythonName.FindStringSubmatch(r.Name); m != nil && !r.PreRelease {
			vs = append(vs, m[1])
		}
	}
	return newest(c.PythonReleases, vs)
}

// getTOML fetches rawURL and decodes its TOML body into v.
func (c *Client) getTOML(ctx context.Context, rawURL string, v any) error {
	body, _, err := c.get(ctx, rawURL, nil)
	if err != nil {
		return err
	}
	if err := toml.Unmarshal(body, v); err != nil {
		return fmt.Errorf("%s: parsing: %w", rawURL, err)
	}
	return nil
}

// RustStable returns the Rust release on the stable channel.
func (c *Client) RustStable(ctx context.Context) (Version, error) {
	var channel struct {
		Pkg map[string]struct {
			Version string `toml:"version"`
		} `toml:"pkg"`
	}
	if err := c.getTOML(ctx, c.RustChannel, &channel); err != nil {
		return Version{}, err
	}
	// The version reads "1.99.1 (58cf8f9c3 2026-10-13)".
	fields := strings.Fields(channel.Pkg["rust"].Version)
	if len(fields) == 0 {
		return Version{}, fmt.Errorf("%s: no [pkg.rust] version", c.RustChannel)
	}
	return newest(c.RustChannel, fields[:1])
}

// RustupStable returns the rustup release on rustup's stable channel, the
// one rustup itself updates to.
func (c *Client) RustupStable(ctx context.Context) (Version, error) {
	var channel struct {
		Version string `toml:"version"`
	}
	if err := c.getTOML(ctx, c.RustupChannel, &channel); err != nil {
		return Version{}, err
	}
	return newest(c.RustupChannel, []string{channel.Version})
}

// Platform selects one image of a multi-platform index.
type Platform struct {
	OS           string `json:"os"`
	Architecture string `json:"architecture"`
	Variant      string `json:"variant,omitempty"`
}

const (
	mediaOCIIndex       = "application/vnd.oci.image.index.v1+json"
	mediaDockerList     = "application/vnd.docker.distribution.manifest.list.v2+json"
	mediaOCIManifest    = "application/vnd.oci.image.manifest.v1+json"
	mediaDockerManifest = "application/vnd.docker.distribution.manifest.v2+json"
)

// ImageDigest returns the current digest of repository:tag on the registry
// for platform: the digest of that platform's manifest when the tag is a
// multi-platform index, else the digest of the tag's manifest. repository
// is a Docker Hub name such as "library/debian".
func (c *Client) ImageDigest(ctx context.Context, repository, tag string, platform Platform) (string, error) {
	authURL := c.RegistryAuth + "?" + url.Values{
		"service": {"registry.docker.io"},
		"scope":   {"repository:" + repository + ":pull"},
	}.Encode()
	var auth struct {
		Token string `json:"token"`
	}
	if err := c.getJSON(ctx, authURL, nil, &auth); err != nil {
		return "", err
	}
	if auth.Token == "" {
		return "", fmt.Errorf("%s: no token", authURL)
	}
	source := c.Registry + "/v2/" + repository + "/manifests/" + tag
	body, header, err := c.get(ctx, source, http.Header{
		"Authorization": {"Bearer " + auth.Token},
		"Accept":        {strings.Join([]string{mediaOCIIndex, mediaDockerList, mediaOCIManifest, mediaDockerManifest}, ", ")},
	})
	if err != nil {
		return "", err
	}
	var manifest struct {
		MediaType string `json:"mediaType"`
		Manifests []struct {
			Digest   string   `json:"digest"`
			Platform Platform `json:"platform"`
		} `json:"manifests"`
	}
	if err := json.Unmarshal(body, &manifest); err != nil {
		return "", fmt.Errorf("%s: parsing: %w", source, err)
	}
	mediaType := manifest.MediaType
	if mediaType == "" {
		mediaType, _, _ = strings.Cut(header.Get("Content-Type"), ";")
	}
	if mediaType != mediaOCIIndex && mediaType != mediaDockerList {
		digest := header.Get("Docker-Content-Digest")
		if digest == "" {
			return "", fmt.Errorf("%s: no Docker-Content-Digest", source)
		}
		return digest, nil
	}
	for _, m := range manifest.Manifests {
		if m.Platform == platform {
			return m.Digest, nil
		}
	}
	return "", fmt.Errorf("%s: no image for %s/%s%s", source, platform.OS, platform.Architecture, variantSuffix(platform.Variant))
}

func variantSuffix(v string) string {
	if v == "" {
		return ""
	}
	return "/" + v
}
