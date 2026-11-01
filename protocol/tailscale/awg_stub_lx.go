//go:build with_gvisor && (!with_tailscale || !with_awg || !with_tailscale_awg)

package tailscale

import (
	"errors"
	"github.com/sagernet/sing-box/option"
)

func configureAWGEndpoint(t *Endpoint, o *option.TailscaleAWGOptions, underlayMode string) error {
	if o != nil || underlayMode != "" {
		return errors.New("tailscale_awg_core_unsupported: requires with_tailscale, with_awg and with_tailscale_awg")
	}
	return nil
}
