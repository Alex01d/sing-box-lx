//go:build with_gvisor && with_tailscale

package tailscale

import (
	"context"
	"net/netip"
	"testing"

	mDNS "github.com/miekg/dns"
	nDNS "github.com/sagernet/tailscale/net/dns"
	"github.com/sagernet/tailscale/types/dnstype"
	"github.com/sagernet/tailscale/util/dnsname"
)

func TestTailscaleDNSIsolationRegressionLX(t *testing.T) {
	cfg := &nDNS.Config{
		Hosts: map[dnsname.FQDN][]netip.Addr{"Node.Private.Example.": {netip.MustParseAddr("100.111.143.10")}},
		Routes: map[dnsname.FQDN][]*dnstype.Resolver{
			"private.example.": nil,
			"example.":         {{Addr: "192.0.2.53"}},
			"corp.example.":    {{Addr: "192.0.2.54"}},
		},
		SearchDomains: []dnsname.FQDN{"Private.Example."},
	}
	domains := newTailnetDomains(cfg)
	if !domains.match(nil, "node.private.example.", false) || !domains.match(nil, "node.", true) || domains.match(nil, "absent.", true) {
		t.Fatal("canonical names or bounded short-name matching regressed")
	}
	if suffix, forwarded := domains.matchRoute("missing.private.example."); suffix != "private.example." || forwarded {
		t.Fatal("resolver-less suffix leaked to the forwarded parent")
	}
	if suffix, forwarded := domains.matchRoute("node.corp.example."); suffix != "corp.example." || !forwarded {
		t.Fatal("longest forwarded suffix lost precedence")
	}
	transport := &DNSTransport{domains: domains}
	for _, q := range []struct {
		name  string
		rcode int
		count int
	}{{"NODE.PRIVATE.EXAMPLE.", mDNS.RcodeSuccess, 1}, {"missing.PRIVATE.EXAMPLE.", mDNS.RcodeNameError, 0}} {
		message := new(mDNS.Msg)
		message.SetQuestion(q.name, mDNS.TypeA)
		called := false
		transport.exchangeOnce(context.Background(), message, true, func(response *mDNS.Msg, err error) {
			called = true
			if err != nil || response == nil || response.Rcode != q.rcode || len(response.Answer) != q.count || response.Question[0].Name != q.name {
				t.Fatalf("local resolution changed for %s: err=%v", q.name, err)
			}
		})
		if !called {
			t.Fatal("local-only lookup unexpectedly became asynchronous")
		}
	}
	original := mDNS.Question{Name: "NODE.", Qtype: mDNS.TypeA, Qclass: mDNS.ClassINET}
	response := &mDNS.Msg{Answer: []mDNS.RR{&mDNS.A{Hdr: mDNS.RR_Header{Name: "node.private.example.", Rrtype: mDNS.TypeA}}}}
	restoreOriginalQuestion(response, "node.private.example.", original)
	if response.Question[0] != original || response.Answer[0].Header().Name != original.Name {
		t.Fatal("search expansion changed the question or answer owner")
	}
}
