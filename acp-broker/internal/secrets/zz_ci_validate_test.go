package secrets

import "testing"

func TestCIValidateMustFail(t *testing.T) { t.Fatal("deliberate failure: CI must catch a failing Go test") }
