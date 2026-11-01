#!/usr/bin/env python3
"""SPEC 149 isolated G0 lab; no host TUN, routing, CA installation or live VPN access."""
import argparse
import base64
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import ssl
import subprocess
import time
import urllib.error
import urllib.request

LABEL = 'org.leadaxe.spec=143-tailscale-awg'
NETWORK = 'lx-awg-143-lab'
SUBNET = '10.253.143.0/24'
HS_IP = '10.253.143.2'
CONTROL = f'https://{HS_IP}:8443'
HS_IMAGE = 'ghcr.io/juanfont/headscale@sha256:11f81665e842809db9fe3006a38c56a66e968baa5abd4bac498e86445572b970'


def run(*args):
    p = subprocess.run(args, text=True, capture_output=True)
    if p.returncode:
        # Never include stdout: administrative commands can return registration keys.
        raise RuntimeError(f'{args[0]} {args[1]} failed: {p.stderr[-1500:]}')
    return p.stdout


def write(path, value, secret=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value if isinstance(value, str) else json.dumps(value, indent=2))
    if secret:
        path.chmod(0o600)


def request(url, ca=None, timeout=80):
    ctx = ssl.create_default_context(cafile=str(ca)) if ca else None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=ctx))
    with opener.open(url, timeout=timeout) as response:
        data=response.read()
        return json.loads(data) if data else {}


def wait_for(fn, seconds=100):
    deadline=time.monotonic()+seconds
    last=None
    while time.monotonic()<deadline:
        try:
            return fn()
        except Exception as e:
            last=e
            time.sleep(1)
    raise RuntimeError(f'lab readiness timeout: {last}')


def setup(root):
    inspect=subprocess.run(['docker','network','inspect',NETWORK],capture_output=True,text=True)
    if inspect.returncode==0:
        net=json.loads(inspect.stdout)[0]
        if net.get('Labels',{}).get('org.leadaxe.spec')!='143-tailscale-awg':
            raise RuntimeError('network name belongs to another task')
    else:
        # Do not introduce a more-specific host route over an existing LAN/VPN.
        for route in json.loads(run('ip','-j','route','show','table','all')):
            destination=route.get('dst','default')
            if destination!='default':
                existing=ipaddress.ip_network(destination,strict=False)
                if existing.version==4 and existing.overlaps(ipaddress.ip_network(SUBNET)):
                    raise RuntimeError('lab subnet overlaps an existing host route')
        for netid in run('docker','network','ls','-q').split():
            net=json.loads(run('docker','network','inspect',netid))[0]
            for cfg in net.get('IPAM',{}).get('Config') or []:
                if cfg.get('Subnet') and ipaddress.ip_network(cfg['Subnet']).version==4 and ipaddress.ip_network(SUBNET).overlaps(ipaddress.ip_network(cfg['Subnet'])):
                    raise RuntimeError('lab subnet overlaps existing Docker network')
        run('docker','network','create','--internal','--label',LABEL,'--subnet',SUBNET,NETWORK)
    cert=root/'tls';cert.mkdir(parents=True,exist_ok=True)
    if not (cert/'ca.crt').exists():
        run('openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(cert/'ca.key'),'-out',str(cert/'ca.crt'),'-days','7','-subj','/CN=LX AWG isolated lab CA')
        run('openssl','req','-newkey','rsa:2048','-nodes','-keyout',str(cert/'server.key'),'-out',str(cert/'server.csr'),'-subj','/CN=LX AWG isolated lab')
        write(cert/'ext.cnf',f'subjectAltName=IP:{HS_IP}\nextendedKeyUsage=serverAuth\nbasicConstraints=CA:FALSE\n')
        run('openssl','x509','-req','-in',str(cert/'server.csr'),'-CA',str(cert/'ca.crt'),'-CAkey',str(cert/'ca.key'),'-CAcreateserial','-out',str(cert/'server.crt'),'-days','7','-extfile',str(cert/'ext.cnf'))
        for key in cert.glob('*.key'): key.chmod(0o600)
    state=root/'headscale';state.mkdir(exist_ok=True)
    policy={'grants':[{'src':['100.111.143.0/24','fd7a:115c:a1e0:143::/64'],'dst':['100.111.143.0/24','fd7a:115c:a1e0:143::/64'],'ip':['tcp:8080','udp:8081']}]}
    if not (root/'policy.json').exists():write(root/'policy.json',policy)
    config={'server_url':CONTROL,'listen_addr':'0.0.0.0:8443','metrics_listen_addr':'','grpc_listen_addr':'127.0.0.1:50443','noise':{'private_key_path':'/var/lib/headscale/noise.key'},'prefixes':{'v4':'100.111.143.0/24','v6':'fd7a:115c:a1e0:143::/64','allocation':'sequential'},'database':{'type':'sqlite','sqlite':{'path':'/var/lib/headscale/db.sqlite','write_ahead_log':True}},'tls_cert_path':'/lab/tls/server.crt','tls_key_path':'/lab/tls/server.key','unix_socket':'/var/lib/headscale/headscale.sock','unix_socket_permission':'0770','disable_check_updates':True,'log':{'level':'warn','format':'json'},'policy':{'mode':'file','path':'/lab/policy.json'},'dns':{'magic_dns':True,'base_domain':'awg.lab','override_local_dns':False,'nameservers':{'global':[]}},'derp':{'server':{'enabled':True,'region_id':999,'region_code':'awg-lab','region_name':'AWG isolated lab','verify_clients':True,'stun_listen_addr':'0.0.0.0:3478','private_key_path':'/var/lib/headscale/derp.key','automatically_add_embedded_derp_region':True,'ipv4':HS_IP},'urls':[],'paths':[],'auto_update_enabled':False}}
    if not (root/'config.yaml').exists():write(root/'config.yaml',config)
    name='lx-awg-143-headscale'
    found=subprocess.run(['docker','inspect',name],capture_output=True)
    if found.returncode:
        run('docker','run','-d','--name',name,'--label',LABEL,'--network',NETWORK,'--ip',HS_IP,'--user',f'{os.getuid()}:{os.getgid()}','-v',f'{root}:/lab:ro','-v',f'{state}:/var/lib/headscale','-v',f'{root}/config.yaml:/etc/headscale/config.yaml:ro',HS_IMAGE,'serve')
    wait_for(lambda: request(CONTROL+'/health',cert/'ca.crt'))
    users=json.loads(run('docker','exec',name,'/ko-app/headscale','users','list','-o','json')) or []
    user=next((u for u in users if u['name']=='lab'),None)
    if user is None:
        user=json.loads(run('docker','exec',name,'/ko-app/headscale','users','create','lab','--email','lab@example.invalid','-o','json'))
    return str(user['id'])


def start_pair(root, binaries, mode, user):
    profile={'jc':4,'jmin':40,'jmax':70,'s1':64,'s2':64,'s3':32,'s4':16,'h1':'100000-199999','h2':'200000-299999','h3':'300000-399999','h4':'400000-499999'}
    if mode=='awg3':
        profile['header_protection_key']=hashlib.sha256(b'SPEC143 synthetic header key').hexdigest()
        profile['content_padding_addition']='10-40'
        profile['random_trailers']=True
    if mode=='plain': profile={}
    offset={'plain':10,'awg2':20,'awg3':30}[mode]
    pair=[]
    for i,role in enumerate(['reference','candidate']):
        d=root/mode/role;d.mkdir(parents=True,exist_ok=True)
        ip=f'10.253.143.{offset+i}'
        name=f'lx-awg-143-{mode}-{role}'
        existing=subprocess.run(['docker','inspect',name],capture_output=True,text=True)
        if existing.returncode==0:
            container=json.loads(existing.stdout)[0]
            if container.get('Config',{}).get('Labels',{}).get('org.leadaxe.spec')!='143-tailscale-awg':
                raise RuntimeError('container name belongs to another task')
            if container['State']['Running']:
                st=wait_for(lambda: request(f'http://{ip}:9080/status'),seconds=120)
                pair.append({'name':name,'underlay':ip,'tailnet':st['TailscaleIPs'][0],'tailnet_ips':st['TailscaleIPs']})
                continue
            run('docker','rm',name)
        key=json.loads(run('docker','exec','lx-awg-143-headscale','/ko-app/headscale','preauthkeys','create','--user',user,'--expiration','2h','-o','json'))['key']
        write(d/'auth.key',key,True)
        if role=='candidate':
            ipc='\n'.join(f'{k}={int(v) if isinstance(v,bool) else v}' for k,v in profile.items())
            write(d/'profile',ipc,True)
        else:
            write(d/'profile',profile if profile else '',True)
        run('docker','run','-d','--name',name,'--label',LABEL,'--network',NETWORK,'--ip',ip,'--cap-add','NET_ADMIN','--user',f'{os.getuid()}:{os.getgid()}','-e','SSL_CERT_FILE=/lab/tls/ca.crt','-v',f'{root}:/lab:ro','-v',f'{d}:/state','-v',f'{binaries}/{role}-probe:/probe:ro','lx-awg-143-lab','/probe','--control',CONTROL,'--auth-file','/state/auth.key','--profile','/state/profile','--state','/state/tsnet','--hostname',f'{mode}-{role}')
        st=wait_for(lambda: request(f'http://{ip}:9080/status'),seconds=120)
        pair.append({'name':name,'underlay':ip,'tailnet':st['TailscaleIPs'][0],'tailnet_ips':st['TailscaleIPs']})
    return pair


def test_pair(root, mode, pair):
    results=[]
    for path in ['direct','derp']:
        if path=='derp':
            for a,b in [pair,pair[::-1]]:
                run('docker','exec','--user','0',a['name'],'iptables','-A','OUTPUT','-p','udp','-d',b['underlay'],'-j','REJECT')
            time.sleep(5)
        for a,b in [pair,pair[::-1]]:
            for peer in b['tailnet_ips']:
                def probe():
                    result=request(f"http://{a['underlay']}:9080/probe?peer={peer}")
                    if result.get('path')!=path:
                        raise RuntimeError(f"expected {path}, got {result.get('path')}")
                    return result
                result=wait_for(probe,seconds=150)
                result.update({'mode':mode,'sender':a['name'],'expected_path':path,'family':ipaddress.ip_address(peer).version})
                results.append(result)
                write(root/f'{mode}-results.json',results)
                print(json.dumps(result),flush=True)
    for a,b in [pair,pair[::-1]]:
        run('docker','exec','--user','0',a['name'],'iptables','-D','OUTPUT','-p','udp','-d',b['underlay'],'-j','REJECT')
    return results


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--binaries',type=Path,required=True);ap.add_argument('--mode',choices=['plain','awg2','awg3','all'],default='all');ap.add_argument('--stop',action='store_true');args=ap.parse_args()
    root=args.root.resolve();root.mkdir(parents=True,exist_ok=True);root.chmod(0o700)
    if args.stop:
        ids=run('docker','ps','-aq','--filter','label='+LABEL).split()
        if ids: run('docker','rm','-f',*ids)
        run('docker','network','rm',NETWORK);return
    user=setup(root)
    manifest={'headscale_image':HS_IMAGE,'network':SUBNET,'control_url':CONTROL,'binary_sha256':{r:hashlib.sha256((args.binaries/f'{r}-probe').read_bytes()).hexdigest() for r in ['candidate','reference']},'results':[]}
    for mode in ['plain','awg2','awg3'] if args.mode=='all' else [args.mode]:
        pair=start_pair(root,args.binaries,mode,user)
        manifest['results']+=test_pair(root,mode,pair)
        write(root/'manifest.json',manifest)
    print('G0 traffic matrix passed; isolated lab remains running for inspection.',flush=True)

if __name__=='__main__':main()
