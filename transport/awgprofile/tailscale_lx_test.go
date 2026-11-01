//go:build with_awg

package awgprofile

import (
	"strings"
	"testing"

	"github.com/sagernet/sing-box/option"
)

func TestTailscaleAWGProfileValidationLX(t *testing.T) {
	valid := option.TailscaleAWGOptions{Version: 2, ProfileID: "lab", Parameters: option.AmneziaWGOptions{S1: 64, S2: 64, S3: 32, S4: 16, H1: "100000-199999", H2: "200000-299999", H3: "300000-399999", H4: "400000-499999"}}
	p, err := CompileTailscale(valid)
	if err != nil {
		t.Fatal(err)
	}
	renamed := valid
	renamed.ProfileID = "renamed"
	other, err := CompileTailscale(renamed)
	if err != nil {
		t.Fatal(err)
	}
	if p.Fingerprint != other.Fingerprint {
		t.Fatal("label changed wire fingerprint")
	}
	for _, name := range []string{"empty", "version", "classic", "classic-range", "overlap", "injection", "huge", "v3in2", "oversized-key", "oversized-cps", "secret"} {
		t.Run(name, func(t *testing.T) {
			o := valid
			switch name {
			case "empty":
				o.Parameters = option.AmneziaWGOptions{}
			case "version":
				o.Version = 4
			case "classic":
				o.Parameters = option.AmneziaWGOptions{H1: "1", H2: "2", H3: "3", H4: "4"}
			case "classic-range":
				o.Parameters = option.AmneziaWGOptions{H1: "1-1", H2: "2-2", H3: "3-3", H4: "4-4"}
			case "overlap":
				o.Parameters.H2 = o.Parameters.H1
			case "injection":
				o.Parameters.I1 = "<r 10>\nprivate_key=secret"
			case "huge":
				o.Parameters.S4 = 65535
			case "v3in2":
				o.Parameters.RandomTrailers = true
			case "oversized-key":
				o.Version = 3
				o.Parameters.HeaderProtectionKey = strings.Repeat("A", 1<<18)
			case "oversized-cps":
				o.Parameters.I1 = "<b 0x" + strings.Repeat("ab", 65508) + ">"
			case "secret":
				o.Version = 3
				o.Parameters.HeaderProtectionKey = "private-invalid-secret"
			}
			_, err := CompileTailscale(o)
			if err == nil {
				t.Fatal("invalid profile accepted")
			}
			if strings.Contains(err.Error(), "private-invalid-secret") || strings.Contains(err.Error(), "private_key=secret") {
				t.Fatal("secret in diagnostic")
			}
		})
	}
}
