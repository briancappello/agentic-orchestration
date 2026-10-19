// Command acp-broker relays an Agent Client Protocol session between a
// driving client on standard input and output and an agent it launches, and
// serves human viewers on a Unix socket.
//
// Usage:
//
//	acp-broker [FLAGS] -- AGENT [ARGS...]
//	acp-broker ls [-registry-dir DIR]
//	acp-broker attach [-key KEY | -socket PATH] [-follow]
//	acp-broker send [-key KEY | -socket PATH] OP [WORDS...]
//
// Each broker serves its own socket, KEY.PID.sock, and writes a record,
// KEY.PID.json, in the registry directory, $XDG_RUNTIME_DIR/acp-broker by
// default. Under Sortie, KEY is the issue identifier; otherwise it is the
// base name of the working directory. One issue has a new broker for every
// dispatch; attach and send pick the newest live one for KEY, and attach
// -follow moves to the next session when the current one ends. A broker
// whose Sortie session only verifies a credential relays and nothing else.
package main

import (
	"os"
)

func main() {
	os.Exit(run(os.Args[1:]))
}

// run runs the broker or one of its client subcommands and returns the
// exit code.
func run(args []string) int {
	if len(args) > 0 {
		switch args[0] {
		case "attach":
			return runAttach(args[1:])
		case "send":
			return runSend(args[1:])
		case "ls":
			return runList(args[1:])
		}
	}
	return runBroker(args)
}
