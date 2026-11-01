#!/usr/bin/env python3
"""Exercise a real launcher-generated config inside the private Docker lab."""
import argparse
import json
from pathlib import Path
import time

import core_lab as core
from lab import LABEL, NETWORK, run, request, wait_for, write


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--binaries', type=Path, required=True)
    ap.add_argument('--config', type=Path, required=True, help='launcher config as strict JSON')
    ap.add_argument('--carrier-env', choices=['auto','derp'])
    args = ap.parse_args()
    root = args.root.resolve()
    directory = root / ('carrier-env-'+args.carrier_env if args.carrier_env else 'launcher')
    directory.mkdir(exist_ok=True, mode=0o700)
    # Only lab identifiers/paths change; route/DNS decisions stay as generated.
    cfg = json.loads(args.config.read_text().replace('lab-aws', 'aws').replace('lab-vless', 'vless'))
    endpoint = cfg['endpoints'][0]
    endpoint['state_directory'] = '/state/tsnet'
    endpoint['hostname'] = 'launcher-generated'
    if args.carrier_env:
        endpoint['detour']='vless';endpoint['underlay_mode']=args.carrier_env
    cfg['inbounds'][0]['listen'] = '0.0.0.0'
    cfg['inbounds'][0]['listen_port'] = 1080
    cfg['experimental']['cache_file']['path'] = '/state/cache.db'
    write(directory / 'config.json', cfg, True)
    users = json.loads(run('docker', 'exec', 'lx-awg-143-headscale', '/ko-app/headscale', 'users', 'list', '-o', 'json'))
    user = str(next(u['id'] for u in users if u['name'] == 'lab'))
    key = json.loads(run('docker', 'exec', 'lx-awg-143-headscale', '/ko-app/headscale', 'preauthkeys', 'create', '--user', user, '--expiration', '2h', '-o', 'json'))['key']
    write(directory / 'auth.key', key, True)
    name = 'lx-awg-143-carrier-env-'+args.carrier_env if args.carrier_env else 'lx-awg-143-launcher-client'
    client_ip={'auto':'10.253.143.53','derp':'10.253.143.54'}.get(args.carrier_env,'10.253.143.52')
    env=['-e','HTTPS_PROXY=http://127.0.0.1:9','-e','NO_PROXY='] if args.carrier_env else []
    setup='ip route replace default via 10.253.143.1; '
    if args.carrier_env:setup+='iptables -A OUTPUT -p tcp -d 10.253.143.2 --dport 8443 -j REJECT; iptables -A OUTPUT -p udp -d 10.253.143.50 -j REJECT; '
    setup+='exec /core-probe --config /state/config.json --auth-file /state/auth.key'
    run('docker', 'run', '-d', '--name', name, '--label', LABEL, '--network', NETWORK,
        '--ip', client_ip, '--cap-add', 'NET_ADMIN', '-e', 'SSL_CERT_FILE=/lab/tls/ca.crt',
        '-v', f'{root}:/lab:ro', '-v', f'{directory}:/state',
        '-v', f'{args.binaries.resolve()}/core-probe:/core-probe:ro', *env, 'lx-awg-143-lab', 'sh', '-c', setup)
    core.CLIENT = client_ip
    wait_for(lambda: core.running(root, core.CLIENT))
    dns_rule = ['-p', 'udp', '-d', '8.8.8.8', '--dport', '53', '-j', 'REJECT']
    run('docker', 'exec', '--user', '0', name, 'iptables', '-A', 'OUTPUT', *dns_rule)
    response = wait_for(lambda: core.fetch(root, 'desktop.awg.lab'))
    assert response['origin'] == 'private' and response['bytes'] == 16 << 20
    assert core.fetch(root, core.ROUTER, 9443)['origin'] == 'public'
    if args.carrier_env:
        counters=run('docker','exec','--user','0',name,'iptables','-L','OUTPUT','-n','-v','-x')
        for line in counters.splitlines():
            if 'REJECT' in line and ('10.253.143.2' in line or '10.253.143.50' in line):assert line.split()[0]=='0','native carrier bypass'
        result={'passed':True,'carrier':args.carrier_env,'ambient_https_proxy_ignored':True,'native_tcp_udp_packets':0,'private_https_bytes':response['bytes']}
        write(root/('carrier-env-'+args.carrier_env+'-results.json'),result);print(json.dumps(result),flush=True);return
    # Failed private resolution must never ask the public resolver.
    core.denied(root, 'unknown.desktop.awg.lab')
    request(f'http://{core.CLIENT}:9080/logout')
    time.sleep(2)
    core.denied(root, 'desktop.awg.lab')
    core.denied(root, 'unknown.desktop.awg.lab')
    assert core.fetch(root, core.ROUTER, 9443)['origin'] == 'public'
    counters = run('docker', 'exec', '--user', '0', name, 'iptables', '-L', 'OUTPUT', '-n', '-v', '-x')
    for line in counters.splitlines():
        if '8.8.8.8' in line:
            assert line.split()[0] == '0', 'private DNS reached the public resolver'
    result = {'passed': True, 'generated_config': True, 'private_https_bytes': response['bytes'],
              'public_vless': True, 'logout_fail_closed': True, 'public_dns_packets': 0}
    write(root / 'launcher-results.json', result)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
