//go:build with_awg

package awgprofile

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"regexp"
	"strconv"
	"strings"

	"github.com/sagernet/sing-box/log"
	"github.com/sagernet/sing-box/option"
	"github.com/sagernet/wireguard-go/device"
)

var profileIDPattern = regexp.MustCompile(`^[A-Za-z0-9._-]{1,64}$`)

// Profile is an immutable, validated per-device profile. IPC is deliberately
// private: callers can apply typed options, not submit arbitrary device commands.
type Profile struct {
	Mode        string
	ID          string
	Fingerprint string
	parameters  option.AmneziaWGOptions
	ipc         string
}

func CompileTailscale(o option.TailscaleAWGOptions) (*Profile, error) {
	if o.Version != 2 && o.Version != 3 {
		return nil, errors.New("awg.version must be 2 or 3")
	}
	if o.ProfileID != "" && !profileIDPattern.MatchString(o.ProfileID) {
		return nil, errors.New("awg.profile_id is invalid")
	}
	p := o.Parameters
	if len(p.HeaderProtectionKey) > 128 {
		return nil, errors.New("awg.parameters.header_protection_key is invalid")
	}
	for _, v := range []struct{ name, value string }{{"i1", p.I1}, {"i2", p.I2}, {"i3", p.I3}, {"i4", p.I4}, {"i5", p.I5}, {"id", p.Id}, {"ip", p.Ip}, {"ib", p.Ib}, {"header_protection_key", p.HeaderProtectionKey}} {
		if strings.ContainsAny(v.value, "\r\n\x00") {
			return nil, fmt.Errorf("awg.parameters.%s contains control characters", v.name)
		}
	}
	for i, value := range []string{p.I1, p.I2, p.I3, p.I4, p.I5} {
		if value != "" {
			if err := validateProfileCPS(value); err != nil {
				return nil, fmt.Errorf("awg.parameters.i%d is invalid", i+1)
			}
		}
	}
	if o.Version == 2 && (p.HeaderProtectionKey != "" || p.ContentPaddingAddition != "" || p.RekeyAfterTime != "" || p.RekeyTimeout != "" || p.RejectAfterTime != "" || p.KeepaliveTimeout != "" || p.MaxHandshakeAttempts != "" || p.RandomTrailers || p.DisableCookies) {
		return nil, errors.New("awg.parameters contains AWG3 fields in version 2")
	}
	// Bound allocations and complete wire messages, not just individual uints.
	if p.Jc > 128 || uint64(p.Jc)*uint64(p.Jmax) > 1<<20 {
		return nil, errors.New("awg.parameters.jc/jmax exceed the per-handshake junk budget")
	}
	if p.Jmin > p.Jmax || p.Jmax > 65507 {
		return nil, errors.New("awg.parameters.jmin/jmax are invalid")
	}
	for _, v := range []struct {
		name     string
		n        uint32
		overhead uint32
	}{{"s1", p.S1, 148}, {"s2", p.S2, 92}, {"s3", p.S3, 64}, {"s4", p.S4, 1312}} {
		if v.n > 65507-v.overhead {
			return nil, fmt.Errorf("awg.parameters.%s exceeds the datagram budget", v.name)
		}
	}
	contentPaddingEffective := false
	if spec, err := p.ContentPaddingAddition.Spec(); err != nil {
		return nil, errors.New("awg.parameters.content_padding_addition is invalid")
	} else if spec != "" {
		parts := strings.Split(spec, "-")
		upper, _ := strconv.ParseUint(parts[len(parts)-1], 10, 32)
		contentPaddingEffective = upper > 0
		if upper+uint64(p.S4)+1312 > 65507 {
			return nil, errors.New("awg.parameters.content_padding_addition exceeds the datagram budget")
		}
	}
	effective := (p.Jc > 0 && p.Jmax > 0) || p.S1 > 0 || p.S2 > 0 || p.S3 > 0 || p.S4 > 0 || p.I1 != "" || p.I2 != "" || p.I3 != "" || p.I4 != "" || p.I5 != "" || p.Ip != "" || p.HeaderProtectionKey != "" || contentPaddingEffective || p.RandomTrailers
	headers := []option.AWGRange{p.H1, p.H2, p.H3, p.H4}
	type interval struct{ lo, hi uint64 }
	var ranges []interval
	for i, h := range headers {
		spec, err := h.Spec()
		if err != nil {
			return nil, fmt.Errorf("awg.parameters.h%d is invalid", i+1)
		}
		if spec == "" {
			spec = strconv.Itoa(i + 1)
		}
		parts := strings.Split(spec, "-")
		lo, _ := strconv.ParseUint(parts[0], 10, 32)
		hi := lo
		if len(parts) == 2 {
			hi, _ = strconv.ParseUint(parts[1], 10, 32)
		}
		if lo != uint64(i+1) || hi != uint64(i+1) {
			effective = true
		}
		for _, prev := range ranges {
			if lo <= prev.hi && prev.lo <= hi {
				return nil, errors.New("awg.parameters.h1-h4 overlap")
			}
		}
		ranges = append(ranges, interval{lo, hi})
	}
	if !p.IsSet() || !effective {
		return nil, errors.New("awg.parameters must enable non-standard framing or decoys")
	}
	ipc, err := IPC(p)
	if err != nil {
		// The standalone codec retains its existing diagnostics; profiles must
		// never echo CPS contents, domain values, ranges, or a header key.
		field := "parameters"
		for _, name := range []string{"header_protection_key", "jmin", "jmax", "i1", "i2", "i3", "i4", "i5", "s1", "s2", "s3", "s4", "h1", "h2", "h3", "h4", "content_padding_addition", "rekey_after_time", "rekey_timeout", "reject_after_time", "keepalive_timeout", "max_handshake_attempts"} {
			if strings.Contains(strings.ToLower(err.Error()), name) {
				field = "parameters." + name
				break
			}
		}
		return nil, fmt.Errorf("awg.%s is invalid", field)
	}
	digest := sha256.Sum256([]byte(strconv.Itoa(o.Version) + "\n" + ipc))
	return &Profile{Mode: fmt.Sprintf("awg%d", o.Version), ID: o.ProfileID, Fingerprint: hex.EncodeToString(digest[:]), parameters: p, ipc: ipc}, nil
}

func (p *Profile) Apply(d *device.Device, logger log.ContextLogger) error {
	if err := d.IpcSet(strings.TrimSpace(p.ipc) + "\n\n"); err != nil {
		return errors.New("AWG device profile could not be applied")
	}
	d.SetDecoyPacketsFunc(DecoyPackets(p.parameters, logger))
	return nil
}
