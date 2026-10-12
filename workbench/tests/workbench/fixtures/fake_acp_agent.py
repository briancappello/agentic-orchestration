"""A minimal ACP agent for tests: echoes prompts and asks permission on request."""

import json
import sys
import threading

lock = threading.Lock()
pending = {}


def send(msg):
    with lock:
        sys.stdout.write(json.dumps(msg) + "\n")
        sys.stdout.flush()


def say(session, text):
    send({"jsonrpc": "2.0", "method": "session/update", "params": {
        "sessionId": session, "update": {"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": text}}}})


def handle_prompt(msg):
    p = msg["params"]
    session = p["sessionId"]
    text = " ".join(b.get("text", "") for b in p["prompt"] if b.get("type") == "text")
    say(session, "echo: " + text)
    if "ASK-PERMISSION" in text:
        ev = threading.Event()
        pending["perm-1"] = {"event": ev}
        send({"jsonrpc": "2.0", "id": "perm-1", "method": "session/request_permission", "params": {
            "sessionId": session,
            "toolCall": {"toolCallId": "call-1", "title": "run planlib validate", "kind": "execute", "status": "pending"},
            "options": [
                {"optionId": "allow", "name": "Allow", "kind": "allow_once"},
                {"optionId": "deny", "name": "Deny", "kind": "reject_once"},
            ]}})
        ev.wait(30)
        outcome = pending.pop("perm-1").get("result", {}).get("outcome", {})
        say(session, "permission: " + json.dumps(outcome, sort_keys=True))
    send({"jsonrpc": "2.0", "id": msg["id"], "result": {"stopReason": "end_turn"}})


for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    msg = json.loads(line)
    method = msg.get("method")
    if method is None and "id" in msg:
        entry = pending.get(msg["id"])
        if entry:
            entry["result"] = msg.get("result", {})
            entry["event"].set()
        continue
    if method == "initialize":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {
            "protocolVersion": 1, "agentCapabilities": {}, "authMethods": [], "agentInfo": {"name": "fake", "version": "0"}}})
    elif method == "session/new":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"sessionId": "sess-1"}})
    elif method == "session/prompt":
        threading.Thread(target=handle_prompt, args=(msg,), daemon=True).start()
    elif method == "session/cancel":
        pass
    elif "id" in msg:
        send({"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": "method not found"}})
