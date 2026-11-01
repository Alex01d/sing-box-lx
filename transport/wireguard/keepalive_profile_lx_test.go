//go:build with_awg

package wireguard

import (
	"github.com/stretchr/testify/require"
	"strings"
	"testing"
)

func TestAwgKeepalivePeerConfigLX(t *testing.T) {

	lines := peerConfig{publicKeyHex: "aa", keepalive: "25-35"}.GenerateIpcLines()
	require.True(t, strings.HasSuffix(lines, "\npersistent_keepalive_interval=25-35"), lines)
	lines = peerConfig{publicKeyHex: "aa", keepalive: ""}.GenerateIpcLines()
	require.NotContains(t, lines, "persistent_keepalive_interval")
}
