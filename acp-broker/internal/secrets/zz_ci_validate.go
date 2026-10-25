package secrets

import "os"

// Deliberate lint failure: an unchecked error in an unused function.
func ciValidate() { os.Remove("ci-validate") }
