// Package secrets keeps the credential values the broker knows about, and
// masks them in any text it logs or exports.
//
// A value is registered once, when it becomes known, and stays registered
// for the life of the process. Mask then replaces it wherever it occurs.
package secrets

import (
	"fmt"
	"log/slog"
	"slices"
	"strings"
	"sync"
	"sync/atomic"
	"unicode"
)

const (
	// Marker replaces each masked span.
	Marker = "[redacted]"

	// MinLen is the length in bytes of the shortest value that is masked.
	// Masking shorter values would hide too much ordinary text, so such a
	// value stays readable and a warning names its source instead.
	MinLen = 8
)

// secretSuffixes are the last name segments, split on "_" and "-", that
// mark a variable as holding a credential.
var secretSuffixes = []string{
	"KEY", "APIKEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "PASS", "PAT",
	"CREDENTIAL", "CREDENTIALS", "AUTH", "AUTHORIZATION", "COOKIE", "COOKIE2",
}

var (
	mu     sync.Mutex
	known  atomic.Pointer[[]string]
	warned = map[string]bool{}
)

// IsSecretName reports whether an environment variable name marks its
// value as a credential: its last segment is a known suffix, such as
// OPENAI_API_KEY, or it ends in _CONNECTION_STRING.
func IsSecretName(name string) bool {
	upper := strings.ToUpper(name)
	if strings.HasSuffix(strings.ReplaceAll(upper, "-", "_"), "_CONNECTION_STRING") {
		return true
	}
	parts := strings.FieldsFunc(upper, func(r rune) bool { return r == '_' || r == '-' })
	return len(parts) > 0 && slices.Contains(secretSuffixes, parts[len(parts)-1])
}

// Add registers value, which source names in a warning if the value is
// too short to mask. A value of several lines registers each line. A line
// with a space also registers what follows its first run of spaces, so
// the token of "Bearer <token>" is masked on its own too.
func Add(source, value string) {
	var pieces []string
	for line := range strings.SplitSeq(value, "\n") {
		line = strings.TrimSuffix(line, "\r")
		pieces = append(pieces, line)
		if _, rest, ok := strings.Cut(line, " "); ok {
			if rest = strings.TrimLeft(rest, " "); rest != "" {
				pieces = append(pieces, rest)
			}
		}
	}
	register(source, pieces, strings.IndexFunc(value, func(r rune) bool { return !unicode.IsSpace(r) }) >= 0)
}

// AddEnviron registers the values of the NAME=value entries in environ
// whose names mark a credential, and the user information of every other
// value that is a URL, such as https://user:password@host.
func AddEnviron(environ []string) {
	for _, entry := range environ {
		name, value, ok := strings.Cut(entry, "=")
		if !ok {
			continue
		}
		if IsSecretName(name) {
			Add(name, value)
			continue
		}
		if userinfo := urlUserinfo(value); userinfo != "" {
			pieces := []string{userinfo}
			if _, password, ok := strings.Cut(userinfo, ":"); ok {
				pieces = append(pieces, password)
			}
			register(name, pieces, true)
		}
	}
}

// urlUserinfo returns the "user:password" part of a URL as written, or ""
// when value is not a URL or has none.
func urlUserinfo(value string) string {
	_, rest, ok := strings.Cut(value, "://")
	if !ok {
		return ""
	}
	authority := rest
	if i := strings.IndexAny(rest, "/?#"); i >= 0 {
		authority = rest[:i]
	}
	at := strings.LastIndex(authority, "@")
	if at <= 0 {
		return ""
	}
	return authority[:at]
}

// register adds each piece long enough to mask. When none is, and the
// value was not blank, it warns once per source.
func register(source string, pieces []string, hasContent bool) {
	mu.Lock()
	var current []string
	if p := known.Load(); p != nil {
		current = slices.Clone(*p)
	}
	added, kept := false, false
	for _, p := range pieces {
		if len(p) < MinLen || strings.Contains(Marker, p) {
			continue
		}
		kept = true
		if !slices.Contains(current, p) {
			current = append(current, p)
			added = true
		}
	}
	if added {
		known.Store(&current)
	}
	warn := !kept && hasContent && !warned[source]
	if warn {
		warned[source] = true
	}
	mu.Unlock()
	if warn {
		slog.Default().Warn("secret value too short to mask", slog.String("name", source), slog.Int("min_bytes", MinLen))
	}
}

func values() []string {
	if p := known.Load(); p != nil {
		return *p
	}
	return nil
}

// span is the byte range [start, end) of a match.
type span struct{ start, end int }

// matches returns the spans of every occurrence of every value in s,
// sorted, with spans that overlap or touch merged into one.
func matches(s string, vals []string) []span {
	var found []span
	for _, v := range vals {
		for from := 0; from <= len(s)-len(v); {
			i := strings.Index(s[from:], v)
			if i < 0 {
				break
			}
			found = append(found, span{from + i, from + i + len(v)})
			from += i + 1
		}
	}
	slices.SortFunc(found, func(a, b span) int { return a.start - b.start })
	var merged []span
	for _, sp := range found {
		if n := len(merged); n > 0 && sp.start <= merged[n-1].end {
			merged[n-1].end = max(merged[n-1].end, sp.end)
			continue
		}
		merged = append(merged, sp)
	}
	return merged
}

func replace(s string, spans []span) string {
	var b strings.Builder
	last := 0
	for _, sp := range spans {
		b.WriteString(s[last:sp.start])
		b.WriteString(Marker)
		last = sp.end
	}
	b.WriteString(s[last:])
	return b.String()
}

// Mask replaces every occurrence of every registered value in s with
// Marker. Occurrences that overlap or touch become one Marker.
func Mask(s string) string {
	vals := values()
	if len(vals) == 0 {
		return s
	}
	spans := matches(s, vals)
	if len(spans) == 0 {
		return s
	}
	return replace(s, spans)
}

// MaskTruncated is Mask for s cut from the end of a longer text. The cut
// may have split a registered value, so it also drops the longest ending
// of s that is the start of a registered value. A whole value that
// begins before that ending is still masked whole.
func MaskTruncated(s string) string {
	vals := values()
	if len(vals) == 0 {
		return s
	}
	cut := 0
	for _, v := range vals {
		for n := min(len(v)-1, len(s)); n > cut; n-- {
			if strings.HasSuffix(s, v[:n]) {
				cut = n
				break
			}
		}
	}
	end := len(s) - cut
	var kept []span
	for _, sp := range matches(s, vals) {
		if sp.start >= end {
			break
		}
		kept = append(kept, sp)
		end = max(end, sp.end)
	}
	return replace(s[:end], kept)
}

// ReplaceAttr masks the text of a log attribute. Use it as the
// ReplaceAttr of a slog handler.
func ReplaceAttr(_ []string, a slog.Attr) slog.Attr {
	switch a.Key {
	case slog.TimeKey, slog.LevelKey, slog.SourceKey:
		return a
	}
	v := a.Value.Resolve()
	var text string
	switch v.Kind() {
	case slog.KindString:
		text = v.String()
	case slog.KindAny:
		switch x := v.Any().(type) {
		case error:
			text = x.Error()
		case fmt.Stringer:
			text = x.String()
		default:
			// Any other value, such as the agent's argv, as it would print.
			text = fmt.Sprint(x)
		}
	default:
		return a
	}
	if masked := Mask(text); masked != text {
		return slog.String(a.Key, masked)
	}
	return a
}
