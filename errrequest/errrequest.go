package errrequest

import (
	"fmt"
	"strconv"
	"strings"
)

const prefix = "errLength="

// New returns a new error request string that that returns an error with errLength bytes.
func New(errLength int) string {
	return prefix + strconv.Itoa(errLength)
}

// Parse parses an error request back into its error length.
func Parse(msg string) (int, error) {
	if len(msg) <= len(prefix) {
		return 0, fmt.Errorf("message too short: %#v", msg)
	}
	len, err := strconv.Atoi(msg[len(prefix):])
	if err != nil {
		return 0, fmt.Errorf("invalid message %#v: %w", msg, err)
	}
	if len <= 0 {
		return 0, fmt.Errorf("invalid length: %d", len)
	}
	return len, nil
}

// Generate parses an error request and generates a request of the appropriate length.
func Generate(msg string) (string, error) {
	errLength, err := Parse(msg)
	if err != nil {
		return "", err
	}

	const msgBase = "this is a long error message abcdefghijklmnopqrstuvwxyz 0123456789 "
	out := strings.Builder{}
	out.Grow(errLength)
	for out.Len() < errLength {
		next := len(msgBase)
		if out.Len()+next > errLength {
			next = errLength - out.Len()
		}
		out.WriteString(msgBase[:next])
	}
	ret := out.String()
	if len(ret) != errLength {
		panic(fmt.Sprintf("BUG: incorrect length %d != %d", len(ret), errLength))
	}
	return ret, nil
}
