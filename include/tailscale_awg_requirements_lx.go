//go:build with_tailscale_awg && (!with_gvisor || !with_tailscale || !with_awg)

package include

// The capability must mean the integration is usable. Do not produce a binary
// whose version advertises it while a parent protocol is compiled out.
var _ = with_tailscale_awg_requires_with_gvisor_with_tailscale_and_with_awg
