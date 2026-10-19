package sortieclient

import (
	"slices"
	"testing"
)

func envOf(m map[string]string) func(string) string {
	return func(k string) string { return m[k] }
}

func TestSessionFromEnv(t *testing.T) {
	t.Parallel()

	full := map[string]string{
		EnvAPIURL: "http://127.0.0.1:7678", EnvIssueIdentifier: "LIVE-1", EnvSessionPurpose: PurposeWork,
		EnvSessionToken: "_tok", EnvRule: "implement", EnvChainID: "c-42", EnvAttempt: "",
	}
	tests := []struct {
		name           string
		drop           string
		purpose        string
		wantSupervised bool
		wantCheck      bool
	}{
		{name: "under sortie", wantSupervised: true},
		{name: "standalone: no api url", drop: EnvAPIURL},
		{name: "no identifier", drop: EnvIssueIdentifier},
		{name: "no token", drop: EnvSessionToken},
		{name: "no purpose", drop: EnvSessionPurpose},
		{name: "credential check", purpose: PurposeCredentialCheck, wantCheck: true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			env := map[string]string{}
			for k, v := range full {
				if k != tt.drop {
					env[k] = v
				}
			}
			if tt.purpose != "" {
				env[EnvSessionPurpose] = tt.purpose
			}
			s := SessionFromEnv(envOf(env))
			if s.Supervised() != tt.wantSupervised || s.CredentialCheck() != tt.wantCheck {
				t.Errorf("Supervised = %v, CredentialCheck = %v, want %v, %v", s.Supervised(), s.CredentialCheck(), tt.wantSupervised, tt.wantCheck)
			}
			if tt.wantSupervised && (s.Config().Identifier != "LIVE-1" || s.Rule != "implement" || s.ChainID != "c-42") {
				t.Errorf("session = %+v", s)
			}
		})
	}
}

func TestAgentEnv_DropsOnlyTheSessionToken(t *testing.T) {
	t.Parallel()

	in := []string{"PATH=/bin", "SORTIE_SESSION_TOKEN=_secret", "SORTIE_ISSUE_IDENTIFIER=LIVE-1", "SORTIE_SESSION_TOKEN_X=keep", "EMPTY="}
	got := AgentEnv(in)
	want := []string{"PATH=/bin", "SORTIE_ISSUE_IDENTIFIER=LIVE-1", "SORTIE_SESSION_TOKEN_X=keep", "EMPTY="}
	if !slices.Equal(got, want) {
		t.Errorf("AgentEnv() = %v, want %v", got, want)
	}
}

func TestSessionFromEnv_Labels(t *testing.T) {
	t.Parallel()

	s := SessionFromEnv(envOf(map[string]string{
		EnvIssueIdentifier: "LIVE-1", EnvRule: "implement", EnvChainID: "c-42", EnvDispatchID: "D1", EnvAttempt: "2",
	}))
	if s.Identifier != "LIVE-1" || s.Rule != "implement" || s.ChainID != "c-42" || s.DispatchID != "D1" || s.Attempt != "2" {
		t.Errorf("labels = %+v, want all five read", s)
	}
	if empty := SessionFromEnv(envOf(map[string]string{})); empty.Identifier != "" || empty.Rule != "" || empty.ChainID != "" || empty.DispatchID != "" || empty.Attempt != "" {
		t.Errorf("labels without the variables = %+v, want all empty", empty)
	}
}
