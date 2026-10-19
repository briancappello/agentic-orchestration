package main

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"
)

// fakeSortieAPI records the broker reports it receives.
type fakeSortieAPI struct {
	srv     *httptest.Server
	mu      sync.Mutex
	reports []map[string]string
	auth    []string
}

func newFakeSortieAPI(t *testing.T) *fakeSortieAPI {
	t.Helper()
	f := &fakeSortieAPI{}
	f.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.HasSuffix(r.URL.Path, "/broker") {
			var body map[string]string
			data, _ := io.ReadAll(r.Body)
			_ = json.Unmarshal(data, &body)
			f.mu.Lock()
			f.reports = append(f.reports, body)
			f.auth = append(f.auth, r.Header.Get("Authorization"))
			f.mu.Unlock()
		}
		w.WriteHeader(http.StatusOK)
	}))
	t.Cleanup(f.srv.Close)
	return f
}

func (f *fakeSortieAPI) waitReport(t *testing.T) (map[string]string, string) {
	t.Helper()
	deadline := time.Now().Add(10 * time.Second)
	for time.Now().Before(deadline) {
		f.mu.Lock()
		if len(f.reports) > 0 {
			defer f.mu.Unlock()
			return f.reports[0], f.auth[0]
		}
		f.mu.Unlock()
		time.Sleep(20 * time.Millisecond)
	}
	t.Fatal("no broker report reached Sortie")
	return nil, ""
}

func TestBroker_ReportsItsHTTPListenerToSortie(t *testing.T) {
	api := newFakeSortieAPI(t)
	dir := shortTempDir(t)
	token := writeFile(t, dir, "viewer-token", "viewer-token-for-test-1234\n")
	p := startBrokerProcessFlags(t, dir, []string{"-http", "127.0.0.1:0", "-viewer-token-file", token}, 0, 0,
		"SORTIE_ISSUE_IDENTIFIER=LIVE-1", "SORTIE_SESSION_PURPOSE=work",
		"SORTIE_API_URL="+api.srv.URL, "SORTIE_SESSION_TOKEN=_session-token-1234")

	report, auth := api.waitReport(t)
	if !strings.HasPrefix(report["http_url"], "http://127.0.0.1:") || report["http_url"] == "http://127.0.0.1:0" ||
		report["viewer_token"] != "viewer-token-for-test-1234" || auth != "Bearer _session-token-1234" {
		t.Errorf("report = %v with %q, want the bound URL, the viewer token, and the session token", report, auth)
	}
	_ = p.stdin.Close()
	p.exitCode(t)
}

// With Sortie down, the session still runs.
func TestBroker_RunsWhenSortieIsDown(t *testing.T) {
	dir := shortTempDir(t)
	token := writeFile(t, dir, "viewer-token", "viewer-token-for-test-1234\n")
	p := startBrokerProcessFlags(t, dir, []string{"-http", "127.0.0.1:0", "-viewer-token-file", token}, 0, 0,
		"SORTIE_ISSUE_IDENTIFIER=LIVE-3", "SORTIE_SESSION_PURPOSE=work",
		"SORTIE_API_URL=http://127.0.0.1:1", "SORTIE_SESSION_TOKEN=_session-token-1234")
	p.sendLine(t, `{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":1}}`)
	if reply, err := p.stdout.ReadString('\n'); err != nil || !strings.Contains(reply, `"id":1`) {
		t.Fatalf("initialize through a broker whose Sortie is down = %q, %v", reply, err)
	}
	_ = p.stdin.Close()
	p.exitCode(t)
}

// A credential check serves no viewers, so it reports nothing.
func TestBroker_CredentialCheckReportsNothing(t *testing.T) {
	api := newFakeSortieAPI(t)
	dir := shortTempDir(t)
	token := writeFile(t, dir, "viewer-token", "viewer-token-for-test-1234\n")
	p := startBrokerProcessFlags(t, dir, []string{"-http", "127.0.0.1:0", "-viewer-token-file", token}, 0, 0,
		"SORTIE_ISSUE_IDENTIFIER=LIVE-4", "SORTIE_SESSION_PURPOSE=credential-check",
		"SORTIE_API_URL="+api.srv.URL, "SORTIE_SESSION_TOKEN=_session-token-1234")
	p.sendLine(t, `{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":1}}`)
	if _, err := p.stdout.ReadString('\n'); err != nil {
		t.Fatal(err)
	}
	_ = p.stdin.Close()
	p.exitCode(t)
	api.mu.Lock()
	defer api.mu.Unlock()
	if len(api.reports) != 0 {
		t.Errorf("a credential check reported %v", api.reports)
	}
}
