package main

import (
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"testing"
	"time"
)

// otlpSink is a fake OTLP/HTTP endpoint that keeps every export body.
type otlpSink struct {
	mu     sync.Mutex
	bodies []string
	auth   []string
	srv    *httptest.Server
}

func newOTLPSink(t *testing.T) *otlpSink {
	t.Helper()
	s := &otlpSink{}
	s.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		s.mu.Lock()
		if r.URL.Path == "/v1/traces" {
			s.bodies = append(s.bodies, string(body))
			s.auth = append(s.auth, r.Header.Get("Authorization"))
		}
		s.mu.Unlock()
	}))
	t.Cleanup(s.srv.Close)
	return s
}

func (s *otlpSink) received() ([]string, []string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return append([]string(nil), s.bodies...), append([]string(nil), s.auth...)
}

// runOneTurn drives a session through one prompt and closes the broker's
// input, so it exits.
func runOneTurn(t *testing.T, p *brokerProcess) {
	t.Helper()
	p.sendLine(t, `{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":1}}`)
	p.sendLine(t, `{"jsonrpc":"2.0","id":2,"method":"session/new","params":{"cwd":"/w","mcpServers":[]}}`)
	p.sendLine(t, `{"jsonrpc":"2.0","id":3,"method":"session/prompt","params":{"sessionId":"sess-fake","prompt":[{"type":"text","text":"do the ticket"}]}}`)
	for {
		line, err := p.stdout.ReadString('\n')
		if err != nil {
			t.Fatalf("driver output ended: %v", err)
		}
		if strings.Contains(line, `"id":3`) {
			break
		}
	}
	_ = p.stdin.Close()
	if code := p.exitCode(t); code != 0 {
		t.Fatalf("broker exit code = %d", code)
	}
}

func writeFile(t *testing.T, dir, name, content string) string {
	t.Helper()
	path := filepath.Join(dir, name)
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatal(err)
	}
	return path
}

func TestTelemetry_ExportsEachTurnWithItsLabels(t *testing.T) {
	sink := newOTLPSink(t)
	dir := shortTempDir(t)
	headers := writeFile(t, dir, "headers", "# credentials for the collector\nAuthorization: Bearer collector-token-1234\n")
	p := startBrokerProcessFlags(t, dir, []string{"-otlp-endpoint", sink.srv.URL, "-otlp-headers-file", headers}, 0, 0,
		"SORTIE_ISSUE_IDENTIFIER=LIVE-1", "SORTIE_RULE=implement", "SORTIE_CHAIN_ID=c-42", "SORTIE_DISPATCH_ID=D1",
		"SORTIE_ATTEMPT=2", "SORTIE_SESSION_PURPOSE=work")
	runOneTurn(t, p)

	// The broker flushes before it exits, so the export has arrived.
	bodies, auth := sink.received()
	all := strings.Join(bodies, "\n")
	if len(bodies) == 0 || auth[0] != "Bearer collector-token-1234" {
		t.Fatalf("exports = %d with auth %q, want the turn exported with the configured header", len(bodies), auth)
	}
	for _, want := range []string{
		`"name":"turn driver"`, `"langfuse.session.id","value":{"stringValue":"D1"}`,
		`"langfuse.trace.metadata.rule","value":{"stringValue":"implement"}`, `"acp.agent.name","value":{"stringValue":"fake-agent"}`,
		`"langfuse.observation.usage_details","value":{"stringValue":"{\"input\":4,\"output\":102,\"total\":106}"}`,
	} {
		if !strings.Contains(all, want) {
			t.Errorf("export lacks %s:\n%s", want, all)
		}
	}
	if strings.Contains(all, "do the ticket") {
		t.Errorf("export carries the prompt text without -telemetry-content:\n%s", all)
	}
}

func TestTelemetry_CredentialCheckExportsNothing(t *testing.T) {
	sink := newOTLPSink(t)
	dir := shortTempDir(t)
	p := startBrokerProcessFlags(t, dir, []string{"-otlp-endpoint", sink.srv.URL}, 0, 0,
		"SORTIE_ISSUE_IDENTIFIER=LIVE-1", "SORTIE_SESSION_PURPOSE=credential-check")
	runOneTurn(t, p)
	time.Sleep(50 * time.Millisecond)
	if bodies, _ := sink.received(); len(bodies) != 0 {
		t.Errorf("a credential-check broker exported %d requests, want none", len(bodies))
	}
}

func TestTelemetry_AgentEnvironmentIsUnchanged(t *testing.T) {
	sink := newOTLPSink(t)
	dir := shortTempDir(t)
	headers := writeFile(t, dir, "headers", "Authorization: Bearer collector-token-1234\n")
	environ := func(flags []string) string {
		p := startBrokerProcessFlags(t, dir, flags, 0, 0, "SORTIE_ISSUE_IDENTIFIER=LIVE-1")
		_ = p.stdin.Close()
		p.exitCode(t)
		for line := range strings.SplitSeq(p.recorded(t), "\n") {
			if rest, ok := strings.CutPrefix(line, "environ "); ok {
				return rest
			}
		}
		t.Fatal("the agent recorded no environment")
		return ""
	}
	without := environ(nil)
	with := environ([]string{"-otlp-endpoint", sink.srv.URL, "-otlp-headers-file", headers, "-telemetry-content"})
	if with != without {
		var a, b []string
		_ = json.Unmarshal([]byte(without), &a)
		_ = json.Unmarshal([]byte(with), &b)
		t.Errorf("agent environment changed with telemetry:\nwithout %v\nwith    %v", a, b)
	}
}

func TestTelemetry_BadConfigurationStopsBeforeTheAgent(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("uses Unix sockets")
	}
	exe, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	dir := t.TempDir()
	badHeaders := writeFile(t, dir, "bad-headers", "Authorization Bearer missing-colon\n")
	tests := map[string][]string{
		"not a URL":            {"-otlp-endpoint", "::not a url"},
		"not http":             {"-otlp-endpoint", "ftp://collector:4318"},
		"no host":              {"-otlp-endpoint", "http://"},
		"unreadable headers":   {"-otlp-endpoint", "http://127.0.0.1:4318", "-otlp-headers-file", filepath.Join(dir, "missing")},
		"malformed headers":    {"-otlp-endpoint", "http://127.0.0.1:4318", "-otlp-headers-file", badHeaders},
		"headers, no endpoint": {"-otlp-headers-file", badHeaders},
		"content max zero":     {"-otlp-endpoint", "http://127.0.0.1:4318", "-telemetry-content-max", "0"},
	}
	for name, flags := range tests {
		rec := filepath.Join(dir, strings.ReplaceAll(name, " ", "-")+".rec")
		cmd := exec.Command(exe, append(flags, "--", exe, "fake-agent", rec, "0", "0")...)
		cmd.Env = append(os.Environ(), "ACP_BROKER_TEST_ROLE=broker", "XDG_RUNTIME_DIR="+dir)
		out, err := cmd.CombinedOutput()
		exitErr, ok := errors.AsType[*exec.ExitError](err)
		if !ok || exitErr.ExitCode() != 2 || !strings.Contains(string(out), "-otlp") && !strings.Contains(string(out), "-telemetry") {
			t.Errorf("%s: err %v, output %q; want exit 2 naming the flag", name, err, out)
		}
		if _, err := os.Stat(rec); err == nil {
			t.Errorf("%s: the agent was started although the broker refused its configuration", name)
		}
	}
}
