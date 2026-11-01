package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"github.com/sagernet/sing-box/cmd/internal/build_shared"
)

var (
	tailscaleAWGEnabledLX bool
	engineeringVersionLX  string
	engineeringOutputLX   string
	mobileBinLX           string
	androidVariantLX      string
)

func init() {
	flag.BoolVar(&tailscaleAWGEnabledLX, "with-tailscale-awg", false, "include experimental AWG/Tailscale (requires pinned dependency overlay)")
	flag.StringVar(&engineeringVersionLX, "version", "", "override engineering version; publication pins are unchanged")
	flag.StringVar(&engineeringOutputLX, "output-dir", "", "write artifacts to this directory without copying to sibling apps")
	flag.StringVar(&mobileBinLX, "mobile-bin", "", "directory containing pinned gomobile and gobind tools")
	flag.StringVar(&androidVariantLX, "android-variant", "both", "Android variants: modern, legacy, or both")
}

func configureEngineeringLX() {
	if androidVariantLX != "both" && androidVariantLX != "modern" && androidVariantLX != "legacy" {
		panic("invalid -android-variant; expected modern, legacy, or both")
	}
	if tailscaleAWGEnabledLX {
		sharedTags = append(sharedTags, "with_tailscale_awg")
	}
	if engineeringVersionLX != "" {
		sharedFlags = []string{"-trimpath", "-buildvcs=false", "-ldflags", build_shared.LinkerFlags(engineeringVersionLX, false)}
		debugFlags = []string{"-ldflags", build_shared.LinkerFlags(engineeringVersionLX, true)}
	}
	if engineeringOutputLX != "" {
		var err error
		engineeringOutputLX, err = filepath.Abs(engineeringOutputLX)
		if err != nil {
			panic(err)
		}
		if err = os.MkdirAll(engineeringOutputLX, 0o700); err != nil {
			panic(err)
		}
	}
}

func findMobileLX() {
	if mobileBinLX == "" {
		build_shared.FindMobile()
		return
	}
	for _, name := range []string{"gomobile", "gobind"} {
		info, err := os.Stat(filepath.Join(mobileBinLX, name))
		if err != nil || !info.Mode().IsRegular() {
			panic(fmt.Sprintf("missing pinned mobile tool: %s", name))
		}
	}
	build_shared.GoBinPath = mobileBinLX
}
