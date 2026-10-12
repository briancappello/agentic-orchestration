// Command smol-builder turns a repository's smol-builder.toml into a smolvm pack.
package main

import (
	"fmt"
	"os"
)

func main() {
	fmt.Fprintln(os.Stderr, "usage: smol-builder build --repo <dir> --output <file> [--layers <dir>]")
	os.Exit(2)
}
