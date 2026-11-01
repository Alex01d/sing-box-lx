//go:build !with_lx_command

package libbox

import "github.com/sagernet/sing-box/daemon"

func tailscaleTransportFromGRPCLX(s *daemon.TailscaleTransportStatus) *TailscaleTransportStatus {
	return nil
}
