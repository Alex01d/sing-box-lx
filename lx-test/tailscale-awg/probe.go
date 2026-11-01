//go:build ignore

// Isolated G0 peer. This program never opens a host TUN or edits host routes.
package main

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/sagernet/tailscale/net/netns"
	"github.com/sagernet/tailscale/tsnet"
	"github.com/sagernet/wireguard-go/device"
)

const blobSize = 16 << 20

func configure(s *tsnet.Server, profile string) error {
	data, err := os.ReadFile(profile)
	if err != nil {
		return err
	}
	if len(bytes.TrimSpace(data)) == 0 {
		return nil
	}
	s.WireGuardDeviceInit = func(d *device.Device) error { return d.IpcSet(string(data) + "\n\n") }
	return nil
}

func main() {
	control := flag.String("control", "", "isolated Headscale URL")
	auth := flag.String("auth-file", "", "synthetic registration key file")
	profile := flag.String("profile", "", "synthetic device profile file")
	state := flag.String("state", "/state/tsnet", "private lab state")
	hostname := flag.String("hostname", "candidate", "lab node name")
	flag.Parse()
	key, err := os.ReadFile(*auth)
	if err != nil {
		log.Fatal(err)
	}
	netns.SetEnabled(false)
	s := &tsnet.Server{Dir: *state, Hostname: *hostname, ControlURL: *control, AuthKey: strings.TrimSpace(string(key)), Port: 41641, Logf: log.Printf}
	if err := configure(s, *profile); err != nil {
		log.Fatal(err)
	}
	defer s.Close()
	ctx, cancel := context.WithTimeout(context.Background(), 90*time.Second)
	status, err := s.Up(ctx)
	cancel()
	if err != nil {
		log.Fatal(err)
	}
	log.Printf("lab node ready: %s", status.TailscaleIPs)
	listener, err := s.Listen("tcp", ":8080")
	if err != nil {
		log.Fatal(err)
	}
	mux := http.NewServeMux()
	mux.HandleFunc("/blob", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/octet-stream")
		io.CopyN(w, bytes.NewReader(make([]byte, blobSize)), blobSize)
	})
	mux.HandleFunc("/upload", func(w http.ResponseWriter, r *http.Request) {
		h := sha256.New()
		n, err := io.Copy(h, io.LimitReader(r.Body, blobSize+1))
		if err != nil || n != blobSize {
			http.Error(w, "size", 400)
			return
		}
		fmt.Fprintf(w, "%x", h.Sum(nil))
	})
	go func() { log.Print(http.Serve(listener, mux)) }()
	for _, ip := range status.TailscaleIPs {
		packet, err := s.ListenPacket("udp", net.JoinHostPort(ip.String(), "8081"))
		if err != nil {
			log.Fatal(err)
		}
		go func() {
			b := make([]byte, 65535)
			for {
				n, addr, err := packet.ReadFrom(b)
				if err != nil {
					return
				}
				if _, err = packet.WriteTo(b[:n], addr); err != nil {
					log.Print(err)
				}
			}
		}()
	}
	admin := http.NewServeMux()
	admin.HandleFunc("/status", func(w http.ResponseWriter, r *http.Request) {
		lc, err := s.LocalClient()
		if err != nil {
			http.Error(w, err.Error(), 500)
			return
		}
		st, err := lc.Status(r.Context())
		if err != nil {
			http.Error(w, err.Error(), 500)
			return
		}
		json.NewEncoder(w).Encode(st)
	})
	admin.HandleFunc("/probe", func(w http.ResponseWriter, r *http.Request) {
		ctx, cancel := context.WithTimeout(r.Context(), 70*time.Second)
		defer cancel()
		peer := r.URL.Query().Get("peer")
		result := map[string]any{"peer": peer}
		fail := func(err error) { result["error"] = err.Error(); w.WriteHeader(502); json.NewEncoder(w).Encode(result) }
		tr := &http.Transport{DialContext: s.Dial, DisableKeepAlives: true}
		defer tr.CloseIdleConnections()
		client := &http.Client{Transport: tr}
		req, _ := http.NewRequestWithContext(ctx, "GET", "http://"+net.JoinHostPort(peer, "8080")+"/blob", nil)
		resp, err := client.Do(req)
		if err != nil {
			fail(err)
			return
		}
		h := sha256.New()
		n, err := io.Copy(h, resp.Body)
		resp.Body.Close()
		if err != nil || n != blobSize {
			fail(fmt.Errorf("download: bytes=%d err=%v", n, err))
			return
		}
		expected := sha256.Sum256(make([]byte, blobSize))
		sum := hex.EncodeToString(h.Sum(nil))
		if sum != hex.EncodeToString(expected[:]) {
			fail(fmt.Errorf("download checksum"))
			return
		}
		req, _ = http.NewRequestWithContext(ctx, "POST", "http://"+net.JoinHostPort(peer, "8080")+"/upload", bytes.NewReader(make([]byte, blobSize)))
		resp, err = client.Do(req)
		if err != nil {
			fail(err)
			return
		}
		body, err := io.ReadAll(resp.Body)
		resp.Body.Close()
		if err != nil || string(body) != sum {
			fail(fmt.Errorf("upload checksum"))
			return
		}
		result["tcp_bytes_each_direction"] = blobSize
		result["sha256"] = sum
		var sizes []int
		for _, size := range []int{64, 512, 1200} {
			conn, err := s.Dial(ctx, "udp", net.JoinHostPort(peer, "8081"))
			if err != nil {
				fail(err)
				return
			}
			conn.SetDeadline(time.Now().Add(10 * time.Second))
			b := bytes.Repeat([]byte{byte(size % 251)}, size)
			_, err = conn.Write(b)
			if err == nil {
				reply := make([]byte, size+1)
				var n int
				n, err = conn.Read(reply)
				if err == nil && !bytes.Equal(b, reply[:n]) {
					err = fmt.Errorf("UDP payload mismatch")
				}
			}
			conn.Close()
			if err != nil {
				fail(err)
				return
			}
			sizes = append(sizes, size)
		}
		result["udp_payloads"] = sizes
		lc, err := s.LocalClient()
		if err != nil {
			fail(err)
			return
		}
		st, err := lc.Status(ctx)
		if err != nil {
			fail(err)
			return
		}
		for _, p := range st.Peer {
			for _, ip := range p.TailscaleIPs {
				if ip.String() == peer {
					path := "derp"
					if p.CurAddr != "" {
						path = "direct"
					}
					result["path"] = path
					result["last_handshake"] = p.LastHandshake
				}
			}
		}
		json.NewEncoder(w).Encode(result)
	})
	log.Fatal(http.ListenAndServe(":9080", admin))
}
