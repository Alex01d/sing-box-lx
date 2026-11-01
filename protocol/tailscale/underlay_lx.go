//go:build with_gvisor && with_tailscale && with_awg && with_tailscale_awg

package tailscale

import (
	"context"
	"errors"
	"net"
	"net/netip"
	"strconv"
	"time"

	M "github.com/sagernet/sing/common/metadata"
	N "github.com/sagernet/sing/common/network"
	"github.com/sagernet/tailscale/types/nettype"
)

func configureAWGUnderlay(t *Endpoint, mode string) error {
	if mode != "" && mode != "auto" && mode != "derp" {
		return errors.New("underlay_mode must be auto or derp")
	}
	if t.detour != "" {
		t.server.Dialer = &underlayDialerLX{t.server.Dialer}
	}
	t.server.ForceDERPLX = mode == "derp"
	if t.detour != "" && mode != "derp" {
		t.server.PacketListenerLX = &underlayListenerLX{ctx: t.ctx, dialer: t.server.Dialer}
	}
	return nil
}

// This listener belongs to one endpoint. A proxy error never falls back to a
// native socket, and disabling UDP explicitly still permits DERP over its dialer.
type underlayListenerLX struct {
	ctx    context.Context
	dialer N.Dialer
}

func (l *underlayListenerLX) ListenPacket(_ context.Context, network, address string) (nettype.PacketConn, error) {
	ip := netip.IPv4Unspecified()
	if network == "udp6" {
		ip = netip.IPv6Unspecified()
	} else if network != "udp4" {
		return nil, errors.New("unsupported underlay network")
	}
	_, port, err := net.SplitHostPort(address)
	if err != nil {
		return nil, errors.New("invalid underlay bind address")
	}
	bindPort, err := strconv.ParseUint(port, 10, 16)
	if err != nil {
		return nil, errors.New("invalid underlay bind port")
	}
	ctx, cancel := context.WithTimeout(l.ctx, 15*time.Second)
	conn, err := l.dialer.ListenPacket(ctx, M.Socksaddr{Addr: ip})
	if err != nil {
		cancel()
		return nil, errors.New("Tailscale UDP underlay proxy is unavailable")
	}
	return &underlayPacketConnLX{PacketConn: conn, cancel: cancel, local: net.UDPAddrFromAddrPort(netip.AddrPortFrom(ip, uint16(bindPort)))}, nil
}

type underlayPacketConnLX struct {
	net.PacketConn
	cancel context.CancelFunc
	local  *net.UDPAddr
}

func (c *underlayPacketConnLX) LocalAddr() net.Addr { return c.local }
func (c *underlayPacketConnLX) ReadFromUDPAddrPort(p []byte) (int, netip.AddrPort, error) {
	n, addr, err := c.ReadFrom(p)
	if err != nil {
		return n, netip.AddrPort{}, err
	}
	return n, M.SocksaddrFromNet(addr).AddrPort(), nil
}
func (c *underlayPacketConnLX) WriteToUDPAddrPort(p []byte, addr netip.AddrPort) (int, error) {
	return c.WriteTo(p, net.UDPAddrFromAddrPort(addr))
}
func (c *underlayPacketConnLX) Close() error {
	c.cancel()
	return c.PacketConn.Close()
}

// A per-device opt-in recognized by the thin dependency's DERP dialer. This
// includes DERP latency probes; a configured proxy failure cannot dial directly.
type underlayDialerLX struct{ N.Dialer }

func (*underlayDialerLX) TailscaleUseConfiguredDialerLX() bool { return true }
