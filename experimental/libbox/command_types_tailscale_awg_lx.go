//go:build with_lx_command

package libbox

import "github.com/sagernet/sing-box/daemon"

func tailscaleTransportFromGRPCLX(s *daemon.TailscaleTransportStatus) *TailscaleTransportStatus {
	if s == nil {
		return nil
	}
	return &TailscaleTransportStatus{ConfiguredMode: s.ConfiguredMode, AppliedMode: s.AppliedMode, ProfileID: s.ProfileID, ProfileFingerprint: s.ProfileFingerprint, Applied: s.Applied, LastError: s.LastError}
}
