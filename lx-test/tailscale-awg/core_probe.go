//go:build ignore

// Isolated full-core harness. Never starts a host TUN or changes host routes.
package main

import (
	"bytes"
	"context"
	"crypto/tls"
	"encoding/base64"
	stdjson "encoding/json"
	"flag"
	"fmt"
	"github.com/sagernet/sing-box/daemon"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/metadata"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"sync"
	"sync/atomic"
	"time"

	box "github.com/sagernet/sing-box"
	"github.com/sagernet/sing-box/include"
	"github.com/sagernet/sing-box/option"
	"github.com/sagernet/sing-box/protocol/tailscale"
	"github.com/sagernet/sing/common/json"
)

func main() {
	configPath := flag.String("config", "/state/config.json", "isolated configuration")
	authPath := flag.String("auth-file", "", "synthetic registration key file")
	server := flag.Bool("server", false, "run isolated HTTPS origins and VLESS counting gate")
	flag.Parse()
	var mu sync.Mutex
	var instance *box.Box
	var mismatch bool
	var carrier string
	var apiSecret string
	restart := func() error {
		if instance != nil {
			if err := instance.Close(); err != nil {
				return err
			}
			instance = nil
		}
		data, err := os.ReadFile(*configPath)
		if err != nil {
			return err
		}
		var raw map[string]interface{}
		if err := stdjson.Unmarshal(data, &raw); err != nil {
			return err
		}
		endpoint := raw["endpoints"].([]interface{})[0].(map[string]interface{})
		if entries, ok := raw["services"].([]interface{}); ok {
			for _, entry := range entries {
				api := entry.(map[string]interface{})
				if api["type"] == "api" {
					apiSecret, _ = api["secret"].(string)
				}
			}
		}
		if *authPath != "" {
			key, err := os.ReadFile(*authPath)
			if err != nil {
				return err
			}
			endpoint["auth_key"] = string(bytes.TrimSpace(key))
		}
		if mismatch {
			endpoint["awg"].(map[string]interface{})["parameters"].(map[string]interface{})["header_protection_key"] = base64.StdEncoding.EncodeToString(bytes.Repeat([]byte{0xe1}, 32))
		}
		if carrier != "" {
			// Isolate carrier counters from the deliberately native second endpoint.
			raw["endpoints"] = raw["endpoints"].([]interface{})[:1]
			route := raw["route"].(map[string]interface{})
			var rules []interface{}
			for _, rule := range route["rules"].([]interface{}) {
				if rule.(map[string]interface{})["outbound"] != "plain" {
					rules = append(rules, rule)
				}
			}
			route["rules"] = rules
			endpoint["detour"] = "vless"
			if carrier == "derp" {
				endpoint["underlay_mode"] = "derp"
			}
		}
		data, err = stdjson.Marshal(raw)
		if err != nil {
			return err
		}
		ctx := include.Context(context.Background())
		options, err := json.UnmarshalExtendedContext[option.Options](ctx, data)
		if err != nil {
			return err
		}
		candidate, err := box.New(box.Options{Context: ctx, Options: options})
		if err != nil {
			return err
		}
		if err := candidate.Start(); err != nil {
			candidate.Close()
			return err
		}
		instance = candidate
		return nil
	}
	if err := restart(); err != nil {
		log.Fatal(err)
	}
	defer func() {
		mu.Lock()
		defer mu.Unlock()
		if instance != nil {
			instance.Close()
		}
	}()
	var vlessConnections atomic.Int64
	var privateRequests atomic.Int64
	var publicRequests atomic.Int64
	if *server {
		cert, err := tls.LoadX509KeyPair("/lab/tls/server.crt", "/lab/tls/server.key")
		if err != nil {
			log.Fatal(err)
		}
		origins := []struct{ address, label string }{{"10.77.1.203:8444", "private"}, {"100.64.0.10:8444", "private"}, {"10.253.144.10:8444", "private"}, {"0.0.0.0:9443", "public"}}
		for _, origin := range origins {
			label := origin.label
			listener, err := tls.Listen("tcp", origin.address, &tls.Config{Certificates: []tls.Certificate{cert}, MinVersion: tls.VersionTLS12})
			if err != nil {
				log.Fatal(err)
			}
			go func() {
				log.Print(http.Serve(listener, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
					if label == "private" {
						privateRequests.Add(1)
					} else {
						publicRequests.Add(1)
					}
					w.Header().Set("X-Lab-Origin", label)
					if r.URL.Path == "/denied" {
						w.WriteHeader(403)
						fmt.Fprint(w, "application-denied")
						return
					}
					w.Header().Set("Content-Type", "application/octet-stream")
					io.CopyN(w, bytes.NewReader(make([]byte, 16<<20)), 16<<20)
				})))
			}()
		}
		gate, err := net.Listen("tcp", "0.0.0.0:19000")
		if err != nil {
			log.Fatal(err)
		}
		go func() {
			for {
				client, err := gate.Accept()
				if err != nil {
					return
				}
				vlessConnections.Add(1)
				go func() {
					defer client.Close()
					upstream, err := net.Dial("tcp", "127.0.0.1:19001")
					if err != nil {
						return
					}
					defer upstream.Close()
					done := make(chan struct{})
					go func() {
						io.Copy(upstream, client)
						if c, ok := upstream.(*net.TCPConn); ok {
							c.CloseWrite()
						}
						close(done)
					}()
					io.Copy(client, upstream)
					if c, ok := client.(*net.TCPConn); ok {
						c.CloseWrite()
					}
					<-done
				}()
			}
		}()
	}
	endpoint := func() *tailscale.Endpoint {
		if instance == nil {
			return nil
		}
		ep, ok := instance.Endpoint().Get("aws")
		if !ok {
			return nil
		}
		return ep.(*tailscale.Endpoint)
	}
	// Keep status safe: configuration/state/auth key contents are never exposed.
	mux := http.NewServeMux()
	mux.HandleFunc("/status", func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		defer mu.Unlock()
		ep := endpoint()
		if ep == nil {
			http.Error(w, "not running", 503)
			return
		}
		st, err := ep.TailscaleStatus()
		if err != nil {
			http.Error(w, err.Error(), 503)
			return
		}
		result := map[string]interface{}{"groups": st.UserGroups, "backend": st.BackendState, "auth_url": st.AuthURL, "self": st.Self, "transport": st.Transport, "vless_connections": vlessConnections.Load(), "private_requests": privateRequests.Load(), "public_requests": publicRequests.Load()}
		if other, ok := instance.Endpoint().Get("plain"); ok {
			if otherStatus, err := other.(*tailscale.Endpoint).TailscaleStatus(); err == nil {
				result["other_transport"] = otherStatus.Transport
				result["other_self"] = otherStatus.Self
			}
		}
		stdjson.NewEncoder(w).Encode(result)
	})
	mux.HandleFunc("/rpc-status", func(w http.ResponseWriter, r *http.Request) {
		conn, err := grpc.NewClient("127.0.0.1:19143", grpc.WithTransportCredentials(insecure.NewCredentials()))
		if err != nil {
			http.Error(w, err.Error(), 500)
			return
		}
		defer conn.Close()
		ctx, cancel := context.WithTimeout(r.Context(), 10*time.Second)
		defer cancel()
		ctx = metadata.AppendToOutgoingContext(ctx, "authorization", "Bearer "+apiSecret)
		st, err := daemon.NewStartedServiceClient(conn).GetTailscaleStatus(ctx, &daemon.TailscaleStatusRequest{EndpointTag: "aws"})
		if err != nil {
			http.Error(w, err.Error(), 500)
			return
		}
		stdjson.NewEncoder(w).Encode(map[string]interface{}{"backend": st.GetBackendState(), "transport": st.GetTransport()})
	})

	mux.HandleFunc("/connection-test", func(w http.ResponseWriter, r *http.Request) {
		conn, err := grpc.NewClient("127.0.0.1:19143", grpc.WithTransportCredentials(insecure.NewCredentials()))
		if err != nil {
			http.Error(w, err.Error(), 500)
			return
		}
		defer conn.Close()
		ctx, cancel := context.WithTimeout(r.Context(), 30*time.Second)
		defer cancel()
		ctx = metadata.AppendToOutgoingContext(ctx, "authorization", "Bearer "+apiSecret)
		stream, err := daemon.NewStartedServiceClient(conn).StartConnectionTest(ctx, &daemon.ConnectionTestRequest{Link: "https://desktop.awg.lab:8444/denied", Source: &daemon.ConnectionTestSource{Inbound: "test-proxy"}, AppDNS: true, Timeout: 20000, MaxBytes: 1024})
		if err != nil {
			http.Error(w, err.Error(), 500)
			return
		}
		var kinds []string
		for {
			update, err := stream.Recv()
			if err != nil {
				http.Error(w, err.Error(), 500)
				return
			}
			if stage := update.GetStage(); stage != nil {
				kinds = append(kinds, stage.GetKind())
			}
			if result := update.GetResult(); result != nil {
				var findings []string
				for _, finding := range result.GetFindings() {
					findings = append(findings, finding.GetCode())
				}
				stdjson.NewEncoder(w).Encode(map[string]interface{}{"http_status": result.GetHttpStatus(), "error": result.GetError(), "root_cause": result.GetRootCause(), "stages": kinds, "findings": findings})
				return
			}
		}
	})
	mux.HandleFunc("/restart", func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		defer mu.Unlock()
		mismatch = r.URL.Query().Get("mismatch") == "1"
		carrier = r.URL.Query().Get("carrier")
		if err := restart(); err != nil {
			http.Error(w, err.Error(), 500)
			return
		}
		fmt.Fprint(w, "{}")
	})
	mux.HandleFunc("/logout", func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		defer mu.Unlock()
		ep := endpoint()
		if ep == nil {
			http.Error(w, "not running", 503)
			return
		}
		lc, err := ep.Server().LocalClient()
		if err == nil {
			err = lc.Logout(r.Context())
		}
		if err != nil {
			http.Error(w, err.Error(), 500)
			return
		}
		fmt.Fprint(w, "{}")
	})
	log.Fatal(http.ListenAndServe(":9080", mux))
}
