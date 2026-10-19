package sortieclient

import "strings"

// Names of the session environment Sortie gives the agent command.
const (
	EnvAPIURL          = "SORTIE_API_URL"
	EnvIssueIdentifier = "SORTIE_ISSUE_IDENTIFIER"
	EnvSessionPurpose  = "SORTIE_SESSION_PURPOSE"
	EnvSessionToken    = "SORTIE_SESSION_TOKEN" //nolint:gosec // a variable name, not a credential
	EnvRule            = "SORTIE_RULE"
	EnvChainID         = "SORTIE_CHAIN_ID"
	EnvAttempt         = "SORTIE_ATTEMPT"
	EnvDispatchID      = "SORTIE_DISPATCH_ID"
)

// Values of EnvSessionPurpose.
const (
	PurposeWork            = "work"
	PurposeCredentialCheck = "credential-check" //nolint:gosec // a purpose label, not a credential
)

// Session is what the broker learns about its Sortie run from the
// environment.
type Session struct {
	APIURL     string
	Identifier string
	Purpose    string
	Token      string
	Rule       string
	ChainID    string
	Attempt    string
	DispatchID string
}

// SessionFromEnv reads the session environment through getenv.
func SessionFromEnv(getenv func(string) string) Session {
	return Session{
		APIURL:     strings.TrimSpace(getenv(EnvAPIURL)),
		Identifier: strings.TrimSpace(getenv(EnvIssueIdentifier)),
		Purpose:    strings.TrimSpace(getenv(EnvSessionPurpose)),
		Token:      strings.TrimSpace(getenv(EnvSessionToken)),
		Rule:       getenv(EnvRule),
		ChainID:    getenv(EnvChainID),
		Attempt:    getenv(EnvAttempt),
		DispatchID: strings.TrimSpace(getenv(EnvDispatchID)),
	}
}

// CredentialCheck reports whether Sortie launched the broker only to
// verify the agent's credential.
func (s Session) CredentialCheck() bool { return s.Purpose == PurposeCredentialCheck }

// Supervised reports whether the broker can call Sortie: it runs a work
// session and every value a call needs is present.
func (s Session) Supervised() bool {
	return s.APIURL != "" && s.Identifier != "" && s.Purpose == PurposeWork && s.Token != ""
}

// Config returns the client configuration for the session.
func (s Session) Config() Config {
	return Config{BaseURL: s.APIURL, Identifier: s.Identifier, Token: s.Token}
}

// AgentEnv returns environ without the session token, so the agent the
// broker launches does not inherit it. Every other entry is kept as is.
func AgentEnv(environ []string) []string {
	out := make([]string, 0, len(environ))
	for _, entry := range environ {
		if name, _, _ := strings.Cut(entry, "="); name == EnvSessionToken {
			continue
		}
		out = append(out, entry)
	}
	return out
}
