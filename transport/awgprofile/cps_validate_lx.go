//go:build with_awg

package awgprofile

import (
	"encoding/hex"
	"errors"
	"strconv"
	"strings"
)

// Validate the typed CPS boundary before device.IpcSet can log a parser error.
// This does not generate packets or duplicate the wireguard-go obfuscators.
func validateProfileCPS(spec string) error {
	remaining := strings.TrimSpace(spec)
	total := 0
	for remaining != "" {
		if remaining[0] != '<' {
			return errors.New("CPS text outside a tag")
		}
		end := strings.IndexByte(remaining, '>')
		if end < 0 {
			return errors.New("unterminated CPS tag")
		}
		parts := strings.Fields(remaining[1:end])
		if len(parts) == 0 {
			return errors.New("empty CPS tag")
		}
		switch parts[0] {
		case "b":
			if len(parts) != 2 {
				return errors.New("invalid CPS bytes")
			}
			hexBytes := strings.TrimPrefix(parts[1], "0x")
			if len(hexBytes) > 2*65507 {
				return errors.New("CPS exceeds the datagram budget")
			}
			bytes, err := hex.DecodeString(hexBytes)
			if err != nil || len(bytes) == 0 {
				return errors.New("invalid CPS bytes")
			}
			total += len(bytes)
		case "r", "rc", "rd", "dz":
			if len(parts) != 2 {
				return errors.New("invalid CPS length")
			}
			n, err := strconv.Atoi(parts[1])
			if err != nil || n < 0 || n > 65507 {
				return errors.New("invalid CPS length")
			}
			total += n
		case "t":
			if len(parts) != 1 {
				return errors.New("invalid timestamp tag")
			}
			total += 4
		case "d", "ds":
			if len(parts) != 1 {
				return errors.New("invalid data tag")
			}
		default:
			return errors.New("unknown CPS tag")
		}
		if total > 65507 {
			return errors.New("CPS exceeds the datagram budget")
		}
		remaining = strings.TrimSpace(remaining[end+1:])
	}
	if total == 0 {
		return errors.New("CPS produces no decoy")
	}
	return nil
}
