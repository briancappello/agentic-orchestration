// Package broker relays one Agent Client Protocol session between a
// driving client and an agent, and lets human viewers watch the session,
// steer it, take it over, and hand it back to the driver.
package broker

import (
	"encoding/json"
)

// message is one newline-delimited JSON-RPC message. Only the members the
// broker routes on are decoded; the original bytes are forwarded unchanged
// whenever the broker does not rewrite the message.
type message struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id,omitempty"`
	Method  string          `json:"method,omitempty"`
	Params  json.RawMessage `json:"params,omitempty"`
	Result  json.RawMessage `json:"result,omitempty"`
	Error   json.RawMessage `json:"error,omitempty"`
}

func (m *message) hasID() bool {
	return len(m.ID) > 0 && string(m.ID) != "null"
}

func (m *message) isRequest() bool { return m.Method != "" && m.hasID() }

func (m *message) isNotification() bool { return m.Method != "" && !m.hasID() }

func (m *message) isResponse() bool { return m.Method == "" && m.hasID() }

// idKey returns a map key for the message ID. JSON-RPC IDs are a number or
// a string; the raw encoding keeps the two apart.
func (m *message) idKey() string { return string(m.ID) }

const (
	methodInitialize    = "initialize"
	methodSessionNew    = "session/new"
	methodSessionLoad   = "session/load"
	methodSessionPrompt = "session/prompt"
	methodSessionCancel = "session/cancel"
	methodSessionUpdate = "session/update"
	methodSteering      = "_session/steering"

	methodSetConfigOption = "session/set_config_option"

	methodRequestPermission = "session/request_permission"
)

// stopReasonResult builds a session/prompt result carrying stopReason.
func stopReasonResult(stopReason string) json.RawMessage {
	b, _ := json.Marshal(map[string]string{"stopReason": stopReason})
	return b
}

func encode(m message) []byte {
	m.JSONRPC = "2.0"
	b, err := json.Marshal(m)
	if err != nil {
		// Every field is either a string or already-valid raw JSON.
		panic("broker: encode message: " + err.Error())
	}
	return append(b, '\n')
}

// textPrompt builds a prompt content array holding one text block per text.
func textPrompt(texts ...string) json.RawMessage {
	blocks := make([]map[string]string, 0, len(texts))
	for _, text := range texts {
		blocks = append(blocks, map[string]string{"type": "text", "text": text})
	}
	b, _ := json.Marshal(blocks)
	return b
}
