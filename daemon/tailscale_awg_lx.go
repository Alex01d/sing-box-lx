//go:build with_lx_command

package daemon

import "github.com/sagernet/sing-box/adapter"

func tailscaleTransportToProtoLX(s *adapter.TailscaleTransportStatus) *TailscaleTransportStatus {
	if s == nil {
		return nil
	}
	return &TailscaleTransportStatus{ConfiguredMode: s.ConfiguredMode, AppliedMode: s.AppliedMode, ProfileID: s.ProfileID, ProfileFingerprint: s.ProfileFingerprint, Applied: s.Applied, LastError: s.LastError}
}
