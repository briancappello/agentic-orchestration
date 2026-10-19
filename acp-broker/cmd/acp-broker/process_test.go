package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"slices"
	"strconv"
	"strings"
	"testing"
	"time"
)

// The test binary plays two more roles, chosen before any test runs: the
// broker itself when ACP_BROKER_TEST_ROLE is "broker", and a fake agent
// when its first argument is "fake-agent".
func TestMain(m *testing.M) {
	if len(os.Args) > 1 && os.Args[1] == "fake-agent" {
		os.Exit(fakeAgent(os.Args[2:]))
	}
	if os.Getenv("ACP_BROKER_TEST_ROLE") == "broker" {
		os.Exit(run(os.Args[1:]))
	}
	os.Exit(m.Run())
}

// fakeAgent records every line it reads to the file args[0], answers a
// line holding "custom" with a fixed reply, exits with args[1] when a line
// holds "please-exit", and on end of input writes "stdin-closed" to the
// record and exits with args[2].
func fakeAgent(args []string) int {
	record, err := os.OpenFile(args[0], os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o600)
	if err != nil {
		return 90
	}
	defer record.Close() //nolint:errcheck // test fixture
	_, tokenSet := os.LookupEnv("SORTIE_SESSION_TOKEN")
	_, _ = fmt.Fprintf(record, "env issue=%s token=%v\n", os.Getenv("SORTIE_ISSUE_IDENTIFIER"), tokenSet)
	environ, _ := json.Marshal(slices.Sorted(slices.Values(os.Environ())))
	_, _ = fmt.Fprintf(record, "environ %s\n", environ)
	exitOnRequest, _ := strconv.Atoi(args[1])
	exitOnEOF, _ := strconv.Atoi(args[2])
	r := bufio.NewReader(os.Stdin)
	for {
		line, err := r.ReadBytes('\n')
		if len(line) > 0 {
			_, _ = record.Write(line)
			var msg struct {
				ID     json.RawMessage `json:"id"`
				Method string          `json:"method"`
			}
			_ = json.Unmarshal(line, &msg)
			switch {
			case bytes.Contains(line, []byte("please-exit")):
				return exitOnRequest
			case bytes.Contains(line, []byte("custom")):
				_, _ = os.Stdout.WriteString(customReply)
			case msg.Method == "initialize":
				_, _ = fmt.Fprintf(os.Stdout, `{"jsonrpc":"2.0","id":%s,"result":{"protocolVersion":1,"agentInfo":{"name":"fake-agent","version":"1.2.3"}}}`+"\n", msg.ID)
			case msg.Method == "session/new":
				_, _ = fmt.Fprintf(os.Stdout, `{"jsonrpc":"2.0","id":%s,"result":{"sessionId":"sess-fake"}}`+"\n", msg.ID)
			case msg.Method == "session/prompt":
				_, _ = fmt.Fprintf(os.Stdout, `{"jsonrpc":"2.0","id":%s,"result":{"stopReason":"end_turn","usage":{"inputTokens":4,"outputTokens":102,"totalTokens":106}}}`+"\n", msg.ID)
			}
		}
		if err != nil {
			_, _ = record.WriteString("stdin-closed\n")
			return exitOnEOF
		}
	}
}

// customReply is deliberately formatted the way no JSON encoder would
// write it, so a re-encoded copy cannot pass for the original.
const customReply = `{ "id" : 9,  "result":{"z":1,"a":[ 2 ]}, "jsonrpc":"2.0" }` + "\n"

const customRequest = `{"jsonrpc":"2.0","id":9,"method":"x/custom","params":{ "keep" : "these bytes" }}` + "\n"

type brokerProcess struct {
	cmd    *exec.Cmd
	stdin  io.WriteCloser
	stdout *bufio.Reader
	record string
}

func startBrokerProcess(t *testing.T, exitOnRequest, exitOnEOF int, env ...string) *brokerProcess {
	t.Helper()
	return startBrokerProcessWith(t, shortTempDir(t), exitOnRequest, exitOnEOF, env...)
}

// startBrokerProcessIn starts another broker sharing dir.
func startBrokerProcessIn(t *testing.T, dir string, env ...string) *brokerProcess {
	t.Helper()
	return startBrokerProcessWith(t, dir, 0, 0, env...)
}

// shortTempDir returns a temporary directory short enough for the Unix
// socket paths a broker creates under it.
func shortTempDir(t *testing.T) string {
	t.Helper()
	dir, err := os.MkdirTemp("", "acpb")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = os.RemoveAll(dir) })
	return dir
}

func startBrokerProcessWith(t *testing.T, dir string, exitOnRequest, exitOnEOF int, env ...string) *brokerProcess {
	t.Helper()
	return startBrokerProcessFlags(t, dir, nil, exitOnRequest, exitOnEOF, env...)
}

// startBrokerProcessFlags starts a broker with flags in dir.
func startBrokerProcessFlags(t *testing.T, dir string, flags []string, exitOnRequest, exitOnEOF int, env ...string) *brokerProcess {
	t.Helper()
	if runtime.GOOS == "windows" {
		t.Skip("uses Unix sockets and process groups")
	}
	exe, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	record, err := os.CreateTemp(dir, "agent-input-")
	if err != nil {
		t.Fatal(err)
	}
	_ = record.Close()
	args := append(slices.Clone(flags), "--", exe, "fake-agent", record.Name(), strconv.Itoa(exitOnRequest), strconv.Itoa(exitOnEOF))
	cmd := exec.Command(exe, args...)
	cmd.Env = append(append(os.Environ(), "ACP_BROKER_TEST_ROLE=broker", "XDG_RUNTIME_DIR="+dir), env...)
	cmd.Dir = dir
	stdin, err := cmd.StdinPipe()
	if err != nil {
		t.Fatal(err)
	}
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		t.Fatal(err)
	}
	if err := cmd.Start(); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		_ = cmd.Process.Kill()
		_ = cmd.Wait()
	})
	return &brokerProcess{cmd: cmd, stdin: stdin, stdout: bufio.NewReader(stdout), record: record.Name()}
}

func (p *brokerProcess) exitCode(t *testing.T) int {
	t.Helper()
	done := make(chan error, 1)
	go func() { done <- p.cmd.Wait() }()
	select {
	case err := <-done:
		if exitErr, ok := errors.AsType[*exec.ExitError](err); ok {
			return exitErr.ExitCode()
		}
		if err != nil {
			t.Fatalf("broker wait: %v", err)
		}
		return 0
	case <-time.After(10 * time.Second):
		t.Fatal("broker did not exit")
	}
	return -1
}

func (p *brokerProcess) recorded(t *testing.T) string {
	t.Helper()
	data, err := os.ReadFile(p.record)
	if err != nil {
		t.Fatal(err)
	}
	return string(data)
}

func TestRelay_PassesUnhandledMessagesThroughUnchanged(t *testing.T) {
	p := startBrokerProcess(t, 0, 0)
	if _, err := io.WriteString(p.stdin, customRequest); err != nil {
		t.Fatal(err)
	}
	reply, err := p.stdout.ReadString('\n')
	if err != nil {
		t.Fatal(err)
	}
	if reply != customReply {
		t.Errorf("driver received %q, want the agent's bytes %q", reply, customReply)
	}
	_ = p.stdin.Close()
	p.exitCode(t)
	if got := p.recorded(t); !strings.Contains(got, "\n"+customRequest) {
		t.Errorf("agent received %q, want the driver's bytes %q", got, customRequest)
	}
}

func TestRelay_ExitsWithTheAgentsExitCode(t *testing.T) {
	p := startBrokerProcess(t, 3, 0)
	if _, err := io.WriteString(p.stdin, `{"jsonrpc":"2.0","method":"please-exit"}`+"\n"); err != nil {
		t.Fatal(err)
	}
	if code := p.exitCode(t); code != 3 {
		t.Errorf("broker exit code = %d, want the agent's 3", code)
	}
}

func TestRelay_ClosingDriverInputClosesAgentInput(t *testing.T) {
	p := startBrokerProcess(t, 0, 7)
	if err := p.stdin.Close(); err != nil {
		t.Fatal(err)
	}
	if code := p.exitCode(t); code != 7 {
		t.Errorf("broker exit code = %d, want 7, the code the agent exits with on end of input", code)
	}
	if got := p.recorded(t); !strings.Contains(got, "stdin-closed") {
		t.Errorf("agent record = %q, want it to have seen its input close", got)
	}
}

func TestAgentEnv_KeepsTheSessionButNotItsToken(t *testing.T) {
	p := startBrokerProcess(t, 0, 0,
		"SORTIE_ISSUE_IDENTIFIER=LIVE-1", "SORTIE_SESSION_TOKEN=_secret-session-token",
		"SORTIE_SESSION_PURPOSE=work", "SORTIE_API_URL=http://127.0.0.1:1")
	_ = p.stdin.Close()
	p.exitCode(t)
	if got := p.recorded(t); !strings.HasPrefix(got, "env issue=LIVE-1 token=false\n") {
		t.Errorf("agent saw %q, want SORTIE_ISSUE_IDENTIFIER and no SORTIE_SESSION_TOKEN", got)
	}
}

func TestHTTPListener_RefusesToStartWithoutAViewerToken(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("uses Unix sockets")
	}
	exe, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	dir := t.TempDir()
	cmd := exec.Command(exe, "-http", "127.0.0.1:0", "--", exe, "fake-agent", filepath.Join(dir, "rec"), "0", "0")
	cmd.Env = append(os.Environ(), "ACP_BROKER_TEST_ROLE=broker", "XDG_RUNTIME_DIR="+dir)
	out, err := cmd.CombinedOutput()
	exitErr, ok := errors.AsType[*exec.ExitError](err)
	if !ok || exitErr.ExitCode() != 2 || !strings.Contains(string(out), "-viewer-token-file") {
		t.Errorf("broker with -http and no token: err %v, output %q; want exit 2 naming -viewer-token-file", err, out)
	}
	if _, err := os.Stat(filepath.Join(dir, "rec")); err == nil {
		t.Error("the agent was started although the broker refused its configuration")
	}
}

// sendLine writes one JSON-RPC line to the broker.
func (p *brokerProcess) sendLine(t *testing.T, line string) {
	t.Helper()
	if _, err := io.WriteString(p.stdin, line+"\n"); err != nil {
		t.Fatal(err)
	}
}

func registryDirOf(p *brokerProcess) string {
	return filepath.Join(filepath.Dir(p.record), "acp-broker")
}

func waitForRecord(t *testing.T, dir string, match func(map[string]any) bool) map[string]any {
	t.Helper()
	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		paths, _ := filepath.Glob(filepath.Join(dir, "*.json"))
		for _, path := range paths {
			data, err := os.ReadFile(path)
			if err != nil {
				continue
			}
			var rec map[string]any
			if json.Unmarshal(data, &rec) == nil && match(rec) {
				return rec
			}
		}
		time.Sleep(20 * time.Millisecond)
	}
	t.Fatalf("no matching record in %s", dir)
	return nil
}

func TestRegistry_RecordDescribesTheSortieSession(t *testing.T) {
	p := startBrokerProcess(t, 0, 0,
		"SORTIE_ISSUE_IDENTIFIER=LIVE-1", "SORTIE_RULE=implement", "SORTIE_CHAIN_ID=c-42", "SORTIE_ATTEMPT=",
		"SORTIE_SESSION_PURPOSE=work")
	p.sendLine(t, `{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":1}}`)
	p.sendLine(t, `{"jsonrpc":"2.0","id":2,"method":"session/new","params":{"cwd":"/w","mcpServers":[]}}`)

	dir := registryDirOf(p)
	rec := waitForRecord(t, dir, func(r map[string]any) bool { return r["session_id"] == "sess-fake" })
	agent, _ := rec["agent"].(map[string]any)
	if rec["key"] != "LIVE-1" || rec["issue"] != "LIVE-1" || rec["rule"] != "implement" || rec["chain_id"] != "c-42" ||
		agent["name"] != "fake-agent" || agent["version"] != "1.2.3" || rec["pid"] != float64(p.cmd.Process.Pid) {
		t.Errorf("record = %v, want LIVE-1 on implement in c-42, the agent, and the broker's pid", rec)
	}
	socket, _ := rec["socket"].(string)
	if filepath.Base(socket) != "LIVE-1."+strconv.Itoa(p.cmd.Process.Pid)+".sock" {
		t.Errorf("record socket = %q", socket)
	}

	_ = p.stdin.Close()
	p.exitCode(t)
	for _, pattern := range []string{"LIVE-1.*.json", "LIVE-1.*.sock"} {
		if left, _ := filepath.Glob(filepath.Join(dir, pattern)); len(left) != 0 {
			t.Errorf("files left after the broker exited: %v", left)
		}
	}
}

func TestRegistry_CredentialCheckOnlyRelays(t *testing.T) {
	// -http without a token would refuse to start a viewer-serving broker.
	if runtime.GOOS == "windows" {
		t.Skip("uses Unix sockets")
	}
	exe, _ := os.Executable()
	dir := shortTempDir(t)
	check := exec.Command(exe, "-http", "127.0.0.1:0", "--", exe, "fake-agent", filepath.Join(dir, "check-rec"), "0", "0")
	check.Env = append(os.Environ(), "ACP_BROKER_TEST_ROLE=broker", "XDG_RUNTIME_DIR="+dir,
		"SORTIE_ISSUE_IDENTIFIER=LIVE-2", "SORTIE_SESSION_PURPOSE=credential-check")
	in, _ := check.StdinPipe()
	out, _ := check.StdoutPipe()
	if err := check.Start(); err != nil {
		t.Fatal(err)
	}
	r := bufio.NewReader(out)
	if _, err := io.WriteString(in, `{"jsonrpc":"2.0","id":1,"method":"session/new","params":{}}`+"\n"); err != nil {
		t.Fatal(err)
	}
	reply, err := r.ReadString('\n')
	if err != nil || !strings.Contains(reply, "sess-fake") {
		t.Fatalf("credential-check broker relayed %q, %v", reply, err)
	}
	for _, pattern := range []string{"LIVE-2.*.json", "LIVE-2.*.sock"} {
		if left, _ := filepath.Glob(filepath.Join(dir, "acp-broker", pattern)); len(left) != 0 {
			t.Errorf("a credential-check broker left %v; want no record and no socket", left)
		}
	}
	_ = in.Close()
	if err := check.Wait(); err != nil {
		t.Errorf("credential-check broker: %v", err)
	}
}

func TestRegistry_AttachFollowsAKeyAcrossBrokers(t *testing.T) {
	first := startBrokerProcess(t, 0, 0, "SORTIE_ISSUE_IDENTIFIER=LIVE-9", "SORTIE_SESSION_PURPOSE=work")
	dir := filepath.Dir(first.record)
	waitForRecord(t, registryDirOf(first), func(r map[string]any) bool { return r["key"] == "LIVE-9" })

	exe, _ := os.Executable()
	attach := exec.Command(exe, "attach", "-key", "LIVE-9", "-follow")
	attach.Env = append(os.Environ(), "ACP_BROKER_TEST_ROLE=broker", "XDG_RUNTIME_DIR="+dir)
	attachIn, _ := attach.StdinPipe()
	attachOut, _ := attach.StdoutPipe()
	if err := attach.Start(); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		_ = attachIn.Close()
		_ = attach.Process.Kill()
		_ = attach.Wait()
	})
	lines := make(chan string, 64)
	go func() {
		sc := bufio.NewScanner(attachOut)
		for sc.Scan() {
			lines <- sc.Text()
		}
		close(lines)
	}()
	waitAttached := func(pid int) {
		t.Helper()
		want := "[attached] LIVE-9." + strconv.Itoa(pid) + ".sock"
		timeout := time.After(10 * time.Second)
		for {
			select {
			case line := <-lines:
				if line == want {
					return
				}
			case <-timeout:
				t.Fatalf("attach never printed %q", want)
			}
		}
	}
	waitAttached(first.cmd.Process.Pid)

	// The first session ends and the next dispatch starts a new broker.
	_ = first.stdin.Close()
	first.exitCode(t)
	second := startBrokerProcessIn(t, dir, "SORTIE_ISSUE_IDENTIFIER=LIVE-9", "SORTIE_SESSION_PURPOSE=work")
	waitAttached(second.cmd.Process.Pid)
}
