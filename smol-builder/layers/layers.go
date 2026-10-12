// Package layers holds the layer library shipped with smol-builder.
//
// Each subdirectory is one layer: a Dockerfile and the files it copies.
// The base layer starts from a pinned image; every other layer starts with
// ARG BASE / FROM ${BASE} so it can go on top of any chain.
package layers

import "embed"

// FS is the shipped layer library, one directory per layer.
//
//go:embed all:base all:go all:node all:python all:rust
var FS embed.FS
