//go:build !with_tailscale_awg

package libbox

// TailscaleAWGSupported reports compiled support instead of guessing from Version.
func TailscaleAWGSupported() bool { return false }
