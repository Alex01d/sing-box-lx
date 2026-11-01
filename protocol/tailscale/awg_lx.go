//go:build with_gvisor && with_tailscale && with_awg && with_tailscale_awg

package tailscale

import (
	"errors"

	"github.com/sagernet/sing-box/option"
	"github.com/sagernet/sing-box/transport/wireguard"
	"github.com/sagernet/wireguard-go/device"
)

func configureAWGEndpoint(t *Endpoint, o *option.TailscaleAWGOptions, underlayMode string) error {
	if o != nil || underlayMode != "" {
		if err := configureAWGUnderlay(t, underlayMode); err != nil {
			return err
		}
	}
	if o == nil {
		return nil
	}
	if t.relayServerPort != nil {
		return errors.New("awg_peer_relay_unsupported: use direct UDP or DERP")
	}
	if t.sshServerOptions != nil && t.sshServerOptions.Enabled {
		return errors.New("awg_ssh_server_unsupported: engineering builds are client-only")
	}
	t.logger.Warn("AWG engineering transport: peer relays are unsupported; direct UDP and DERP are available")
	p, err := wireguard.CompileTailscaleAWGProfile(*o)
	if err != nil {
		return err
	}
	t.awgTransport = &awgTransportState{mode: p.Mode, profileID: p.ID, fingerprint: p.Fingerprint}
	t.server.WireGuardDeviceInit = func(d *device.Device) error {
		if err := p.Apply(d, t.logger); err != nil {
			message := "device_profile_apply_failed"
			t.awgTransport.lastError.Store(&message)
			return err
		}
		t.awgTransport.applied.Store(true)
		return nil
	}
	return nil
}
