#!/usr/bin/env python3
"""A mock Agent Client Protocol (ACP) agent for the dev environment.

It speaks just enough ACP over standard input and output for Sortie to run
it, behind acp-broker, like a real agent: initialize, session/new, and
session/prompt, which streams a few message chunks over --turn-seconds and
then ends the turn. A session/cancel ends the running turn early. It changes
no files, so the dev workflow's after_run hook commits a placeholder.

Usage: mock_acp_agent.py [--turn-seconds N]
"""

import argparse
import itertools
import json
import sys
import threading

CHUNKS = ["Reading the story.", "Writing the change.", "Running the tests.", "Done."]

out_lock = threading.Lock()
sessions = itertools.count(1)
# The cancel event of each session's running turn.
turns: dict[str, threading.Event] = {}


def send(msg: dict) -> None:
    with out_lock:
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", **msg}) + "\n")
        sys.stdout.flush()


def reply(req_id, result=None, error=None) -> None:
    send({"id": req_id, "error": error} if error else {"id": req_id, "result": result})


def run_turn(req_id, session_id: str, seconds: float) -> None:
    cancel = turns[session_id] = threading.Event()
    step = seconds / len(CHUNKS)
    for text in CHUNKS:
        if cancel.wait(step):
            reply(req_id, {"stopReason": "cancelled"})
            return
        send({"method": "session/update", "params": {"sessionId": session_id, "update": {
            "sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": text + "\n"}}}})
    turns.pop(session_id, None)
    reply(req_id, {"stopReason": "end_turn"})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--turn-seconds", type=float, default=20.0)
    seconds = parser.parse_args().turn_seconds

    for line in sys.stdin:
        if not line.strip():
            continue
        msg = json.loads(line)
        method, req_id, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
        if method is None:
            continue  # a response to a request of ours; we send none
        if method == "initialize":
            reply(req_id, {"protocolVersion": params.get("protocolVersion", 1),
                           "agentCapabilities": {"loadSession": False, "promptCapabilities": {}},
                           "authMethods": [], "agentInfo": {"name": "dev-mock-acp", "version": "0.1.0"}})
        elif method == "session/new":
            reply(req_id, {"sessionId": f"mock-{next(sessions)}"})
        elif method == "session/prompt":
            threading.Thread(target=run_turn, args=(req_id, params["sessionId"], seconds), daemon=True).start()
        elif method == "session/cancel":
            if (event := turns.get(params.get("sessionId"))) is not None:
                event.set()
        elif method in ("session/close", "session/delete"):
            reply(req_id, {})
        elif req_id is not None:
            reply(req_id, error={"code": -32601, "message": f"method not found: {method}"})


if __name__ == "__main__":
    main()
