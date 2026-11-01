package wireguard

import (
	"github.com/sagernet/sing-box/log"
	"github.com/sagernet/sing-box/option"
	"github.com/sagernet/sing-box/transport/awgprofile"
	"github.com/sagernet/wireguard-go/device"
)

// Both endpoint types share the same validator, renderer and decoy generator.
func awgIpcLines(o option.AmneziaWGOptions) (string, error) { return awgprofile.IPC(o) }
func awgKeepaliveSpec(o option.AWGRange) (string, error)    { return awgprofile.KeepaliveSpec(o) }
func awgDecoyFunc(o option.AmneziaWGOptions, l log.ContextLogger) device.DecoyPacketsFunc {
	return awgprofile.DecoyPackets(o, l)
}
