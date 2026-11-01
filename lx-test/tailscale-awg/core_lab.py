#!/usr/bin/env python3
"""Full core routing/HTTPS/VLESS acceptance, entirely inside the SPEC 149 lab."""
import argparse
import base64
import hashlib
import http.client
import json
from pathlib import Path
import ssl
import secrets
import time
import urllib.parse

from lab import LABEL, NETWORK, CONTROL, run, request, wait_for, write

UUID='3c3f3116-3811-4732-a441-c2f54b2dd037'  # synthetic lab identity
ROUTER='10.253.143.50'
CLIENT='10.253.143.51'
NAMES=['lx-awg-143-core-router','lx-awg-143-core-client']
PREFIXES=['10.77.0.0/16','100.64.0.0/16','10.253.144.0/24']


def state(root,ip):return request(f'http://{ip}:9080/status',timeout=15)


def running(root,ip):
    value=state(root,ip)
    if value.get('backend')!='Running':raise RuntimeError('not Running')
    return value


def fetch(root,host,port=8444,path='/blob',timeout=15):
    conn=http.client.HTTPSConnection(CLIENT,1080,timeout=timeout,context=ssl.create_default_context(cafile=str(root/'tls/ca.crt')))
    conn.set_tunnel(host,port)
    try:
        conn.request('GET',path)
        response=conn.getresponse();h=hashlib.sha256();n=0
        while True:
            b=response.read(65536)
            if not b:break
            h.update(b);n+=len(b)
        return {'status':response.status,'bytes':n,'sha256':h.hexdigest(),'origin':response.getheader('X-Lab-Origin')}
    finally:conn.close()


def denied(root,host):
    before=state(root,ROUTER)
    try:fetch(root,host,timeout=7)
    except Exception:pass
    else:raise RuntimeError('protected request unexpectedly succeeded')
    after=state(root,ROUTER)
    if after['vless_connections']!=before['vless_connections'] or after['private_requests']!=before['private_requests']:
        raise RuntimeError('protected failure leaked through VLESS or reached origin')


def prepare(root,binaries):
    # Reissue only the lab leaf; no host trust store changes.
    write(root/'tls/ext.cnf','subjectAltName=IP:10.253.143.2,IP:10.253.143.50,IP:10.77.1.203,IP:100.64.0.10,IP:10.253.144.10,DNS:*.awg.lab\nextendedKeyUsage=serverAuth\nbasicConstraints=CA:FALSE\n')
    run('openssl','x509','-req','-in',str(root/'tls/server.csr'),'-CA',str(root/'tls/ca.crt'),'-CAkey',str(root/'tls/ca.key'),'-CAcreateserial','-out',str(root/'tls/server.crt'),'-days','7','-extfile',str(root/'tls/ext.cnf'))
    config=json.loads((root/'config.yaml').read_text())
    config['dns']['extra_records']=[{'name':'beta.awg.lab','type':'A','value':'10.77.1.203'},{'name':'cache.awg.lab','type':'A','value':'100.64.0.10'},{'name':'desktop.awg.lab','type':'A','value':'10.253.144.10'}]
    write(root/'config.yaml',config)
    policy=json.loads((root/'policy.json').read_text())
    policy['grants'][0]['dst']=list(dict.fromkeys(policy['grants'][0]['dst']+PREFIXES))
    policy['grants'][0]['ip']=list(dict.fromkeys(policy['grants'][0]['ip']+['tcp:8444']))
    write(root/'policy.json',policy)
    run('docker','restart','lx-awg-143-headscale')
    wait_for(lambda:request(CONTROL+'/health',root/'tls/ca.crt'))
    users=json.loads(run('docker','exec','lx-awg-143-headscale','/ko-app/headscale','users','list','-o','json'))
    user=str(next(u['id'] for u in users if u['name']=='lab'))
    profile={'version':3,'profile_id':'isolated-awg3','parameters':{'jc':4,'jmin':40,'jmax':70,'s1':64,'s2':64,'s3':32,'s4':16,'h1':'100000-199999','h2':'200000-299999','h3':'300000-399999','h4':'400000-499999','header_protection_key':base64.b64encode(hashlib.sha256(b'SPEC143 synthetic header key').digest()).decode(),'content_padding_addition':'10-40','random_trailers':True}}
    write(root/'desktop-awg-profile.json',profile,True)
    for role,ip,name in [('router',ROUTER,NAMES[0]),('client',CLIENT,NAMES[1])]:
        d=root/'core'/role;d.mkdir(parents=True,exist_ok=True)
        ep={'type':'tailscale','tag':'aws','control_url':CONTROL,'hostname':'core-'+role,'state_directory':'/state/tsnet','accept_routes':True,'system_interface':False,'awg':profile,'listen_port':41641}
        if role=='router':ep['advertise_routes']=PREFIXES
        cfg={'log':{'level':'info'},'endpoints':[ep],'dns':{'servers':[{'type':'tailscale','tag':'tail-dns','endpoint':'aws'},{'type':'hosts','tag':'bootstrap','predefined':{}}],'rules':[{'domain_suffix':['awg.lab'],'server':'tail-dns'}],'final':'bootstrap','strategy':'ipv4_only'},'outbounds':[{'type':'direct','tag':'direct'}],'route':{'auto_detect_interface':True,'default_domain_resolver':'bootstrap','final':'direct'}}
        if role=='router':
            cfg['inbounds']=[{'type':'vless','tag':'vless-server','listen':'127.0.0.1','listen_port':19001,'users':[{'uuid':UUID}]}]
        else:
            plainkey=json.loads(run('docker','exec','lx-awg-143-headscale','/ko-app/headscale','preauthkeys','create','--user',user,'--expiration','2h','-o','json'))['key']
            cfg['endpoints'].append({'type':'tailscale','tag':'plain','control_url':CONTROL,'hostname':'core-plain','state_directory':'/state/plain','auth_key':plainkey,'listen_port':41642})
            cfg['services']=[{'type':'api','tag':'lx-desktop-api','listen':'127.0.0.1','listen_port':19143,'secret':secrets.token_urlsafe(32)}]
            cfg['inbounds']=[{'type':'mixed','tag':'test-proxy','listen':'0.0.0.0','listen_port':1080}]
            cfg['outbounds'].append({'type':'vless','tag':'vless','server':ROUTER,'server_port':19000,'uuid':UUID})
            cfg['route']['rules']=[{'ip_cidr':['100.111.143.1/32'],'action':'route','outbound':'plain'},{'ip_cidr':PREFIXES+['100.111.143.0/24','fd7a:115c:a1e0:143::/64'],'action':'route','outbound':'aws'},{'domain_suffix':['awg.lab'],'action':'resolve','server':'tail-dns'},{'domain_suffix':['awg.lab'],'action':'route','outbound':'aws'}]
            cfg['route']['final']='vless'
        write(d/'config.json',cfg,True)
        cmd=['docker','run','-d','--name',name,'--label',LABEL,'--network',NETWORK,'--ip',ip,'--cap-add','NET_ADMIN','-e','SSL_CERT_FILE=/lab/tls/ca.crt','-v',f'{root}:/lab:ro','-v',f'{d}:/state','-v',f'{binaries}/core-probe:/core-probe:ro','lx-awg-143-lab','sh','-c']
        setup='ip route replace default via 10.253.143.1; '
        if role=='router':
            key=json.loads(run('docker','exec','lx-awg-143-headscale','/ko-app/headscale','preauthkeys','create','--user',user,'--expiration','2h','-o','json'))['key'];write(d/'auth.key',key,True)
            setup+='ip addr add 10.77.1.203/32 dev lo; ip addr add 100.64.0.10/32 dev lo; ip addr add 10.253.144.10/32 dev lo; '
        else:
            setup+='iptables -A OUTPUT -p tcp -d 10.77.0.0/16 -j REJECT; iptables -A OUTPUT -p tcp -d 100.64.0.0/16 -j REJECT; '
        setup+='exec /core-probe --config /state/config.json'
        setup+=' --server --auth-file /state/auth.key' if role=='router' else ''
        run(*cmd,setup)
        if role=='router':wait_for(lambda:running(root,ip))
        else:
            def auth_request():
                st=state(root,ip)
                if not st.get('auth_url'):raise RuntimeError('awaiting auth request')
                return st['auth_url']
            # Existing state may already be registered after an interrupted run.
            if wait_for(lambda:state(root,ip)).get('backend')!='Running':
                url=wait_for(auth_request)
                authid=urllib.parse.urlparse(url).path.rsplit('/',1)[-1]
                run('docker','exec','lx-awg-143-headscale','/ko-app/headscale','auth','register','--auth-id',authid,'--user','lab')
                wait_for(lambda:running(root,ip))
    nodes=json.loads(run('docker','exec','lx-awg-143-headscale','/ko-app/headscale','nodes','list','-o','json'))
    router=next(n for n in nodes if n.get('given_name')=='core-router')
    run('docker','exec','lx-awg-143-headscale','/ko-app/headscale','nodes','approve-routes','--identifier',str(router['id']),'--routes',','.join(PREFIXES))
    return profile


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--binaries',type=Path,required=True);args=ap.parse_args();root=args.root.resolve()
    prepare(root,args.binaries.resolve())
    results=[]
    def record(name,details):
        results.append({'scenario':name,**details});write(root/'core-results.json',results);print(json.dumps(results[-1]),flush=True)
    initial=wait_for(lambda:running(root,CLIENT));identity=initial['self']['StableID']
    record('manual-registration',{'passed':True,'backend':initial['backend']})
    assert initial['other_transport']['ConfiguredMode']=='wireguard' and initial['transport']['ConfiguredMode']=='awg3'
    def plain_request():
        conn=http.client.HTTPConnection(CLIENT,1080,timeout=10)
        try:
            conn.request('GET','http://100.111.143.1:8080/blob');response=conn.getresponse();n=len(response.read());assert response.status==200 and n==16<<20
        finally:conn.close()
    wait_for(plain_request)
    record('two-endpoints-independent',{'passed':True,'modes':['wireguard','awg3']})
    rpc=request(f'http://{CLIENT}:9080/rpc-status');assert rpc['transport']['appliedMode']=='awg3'
    record('authenticated-started-service-status',{'passed':True,'mode':'awg3'})

    time.sleep(3)
    for host in ['beta.awg.lab','cache.awg.lab','desktop.awg.lab']:
        before=state(root,ROUTER)['vless_connections']
        response=wait_for(lambda:fetch(root,host),seconds=80)
        assert response['status']==200 and response['origin']=='private' and response['bytes']==16<<20
        assert state(root,ROUTER)['vless_connections']==before
        record('private-https-'+host,response)
    before=state(root,ROUTER)['vless_connections'];response=fetch(root,ROUTER,9443)
    assert response['origin']=='public' and state(root,ROUTER)['vless_connections']>before
    record('public-https-vless',response)
    response=fetch(root,'beta.awg.lab',path='/denied');assert response['status']==403
    record('application-http-403',response)
    trace=request(f'http://{CLIENT}:9080/connection-test',timeout=30)
    assert trace['http_status']==403 and trace['error']=='' and len(trace['stages'])>0
    record('start-connection-test-http-403',trace)
    request(f'http://{CLIENT}:9080/restart?mismatch=1');wait_for(lambda:running(root,CLIENT))
    for host in ['beta.awg.lab','cache.awg.lab']:denied(root,host)
    plain_request()
    assert fetch(root,ROUTER,9443)['status']==200
    record('profile-mismatch-fail-closed',{'passed':True,'public_vless_works':True})
    request(f'http://{CLIENT}:9080/restart');after=wait_for(lambda:running(root,CLIENT));assert after['self']['StableID']==identity
    wait_for(lambda:fetch(root,'beta.awg.lab'),seconds=80)
    record('reload-identity-retained',{'passed':True})
    # An explicit outer carrier must not open native peer UDP sockets.
    router_id=state(root,ROUTER)['self']['StableID']
    for carrier in ['udp','derp']:
        request(f'http://{CLIENT}:9080/restart?carrier={carrier}');wait_for(lambda:running(root,CLIENT))
        udp_rule=['-p','udp','-d',ROUTER,'-j','REJECT']
        control_rule=['-p','tcp','-d','10.253.143.2','--dport','8443','-j','REJECT']
        for rule in [udp_rule,control_rule]:run('docker','exec','--user','0',NAMES[1],'iptables','-A','OUTPUT',*rule)
        request(f'http://{CLIENT}:9080/restart?carrier={carrier}')
        wait_for(lambda:running(root,CLIENT))
        before=state(root,ROUTER)['vless_connections']
        response=wait_for(lambda:fetch(root,'desktop.awg.lab'),seconds=100)
        assert response['status']==200
        peers=[p for g in state(root,CLIENT)['groups'] for p in (g.get('Peers') or [])]
        peer=next(p for p in peers if p['StableID']==router_id)
        expected='derp' if carrier=='derp' else 'direct'
        assert peer['Path']==expected, peer['Path']
        assert state(root,ROUTER)['vless_connections']>=before
        counters=run('docker','exec','--user','0',NAMES[1],'iptables','-L','OUTPUT','-n','-v','-x')
        for line in counters.splitlines():
            if 'REJECT' in line and 'udp' in line and ROUTER in line:assert line.split()[0]=='0','native peer UDP bypassed carrier'
            if 'REJECT' in line and '10.253.143.2' in line and 'tcp' in line:assert line.split()[0]=='0','native control/DERP TCP bypassed carrier'
        record('awg-over-vless-'+carrier,{'passed':True,'path':peer['Path'],'https_bytes':response['bytes'],'native_peer_udp_packets':0})
        down_rule=['-p','tcp','-d',ROUTER,'--dport','19000','-j','REJECT']
        run('docker','exec','--user','0',NAMES[1],'iptables','-A','OUTPUT',*down_rule)
        denied(root,'desktop.awg.lab')
        record('outer-vless-outage-'+carrier,{'passed':True,'native_fallback':False})
        run('docker','exec','--user','0',NAMES[1],'iptables','-D','OUTPUT',*down_rule)
        for rule in [udp_rule,control_rule]:run('docker','exec','--user','0',NAMES[1],'iptables','-D','OUTPUT',*rule)
    request(f'http://{CLIENT}:9080/restart');wait_for(lambda:running(root,CLIENT));wait_for(lambda:fetch(root,'desktop.awg.lab'))
    policy=json.loads((root/'policy.json').read_text());denypolicy=json.loads(json.dumps(policy));denypolicy['grants'][0]['ip']=[x for x in denypolicy['grants'][0]['ip'] if x!='tcp:8444'];write(root/'policy.json',denypolicy);run('docker','kill','--signal','HUP','lx-awg-143-headscale');time.sleep(4)
    denied(root,'beta.awg.lab');assert fetch(root,ROUTER,9443)['status']==200
    record('acl-deny-fail-closed',{'passed':True,'public_vless_works':True})
    write(root/'policy.json',policy);run('docker','kill','--signal','HUP','lx-awg-143-headscale');time.sleep(3)
    wait_for(lambda:fetch(root,'beta.awg.lab'),seconds=80)
    request(f'http://{CLIENT}:9080/logout');time.sleep(2);denied(root,'beta.awg.lab');assert fetch(root,ROUTER,9443)['status']==200
    record('logout-fail-closed',{'passed':True,'public_vless_works':True})
    # Restore an interactive login so the lab is left ready for manual approval.
    request(f'http://{CLIENT}:9080/restart')
    text=run('docker','exec','--user','0',NAMES[1],'iptables','-L','OUTPUT','-n','-v','-x')
    for line in text.splitlines():
        if '10.77.0.0/16' in line or '100.64.0.0/16' in line:
            assert line.split()[0]=='0','protected direct packets observed'
    record('direct-leak-counters',{'passed':True,'protected_tcp_packets':0})
    print('Full-core lab acceptance passed; lab services remain available.',flush=True)

if __name__=='__main__':main()
