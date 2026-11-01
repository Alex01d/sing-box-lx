//go:build with_gvisor

package tailscale

import (
	"github.com/sagernet/sing-box/adapter"
	"sync/atomic"
)

type awgTransportState struct {
	mode        string
	profileID   string
	fingerprint string
	applied     atomic.Bool
	lastError   atomic.Pointer[string]
}

func (t *Endpoint) awgTransportStatus() *adapter.TailscaleTransportStatus {
	if t.awgTransport == nil {
		applied := t.started.Load()
		s := &adapter.TailscaleTransportStatus{ConfiguredMode: "wireguard", Applied: applied}
		if applied {
			s.AppliedMode = "wireguard"
		}
		return s
	}
	a := t.awgTransport
	s := &adapter.TailscaleTransportStatus{ConfiguredMode: a.mode, ProfileID: a.profileID, ProfileFingerprint: a.fingerprint, Applied: a.applied.Load()}
	if s.Applied {
		s.AppliedMode = a.mode
	}
	if e := a.lastError.Load(); e != nil {
		s.LastError = *e
	}
	return s
}
