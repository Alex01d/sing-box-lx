//go:build !with_lx_command

package daemon

import "github.com/sagernet/sing-box/adapter"

func tailscaleTransportToProtoLX(s *adapter.TailscaleTransportStatus) *TailscaleTransportStatus {
	return nil
}
