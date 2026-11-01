#!/usr/bin/env python3
"""Build independent lab peers and a candidate core from immutable source pins."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

from reference_overlay import prepare_reference_overlay, validate_reference


def run(args, cwd=None, env=None):
    subprocess.run(args, cwd=cwd, env=env, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workspace', type=Path, required=True, help='new external directory')
    ap.add_argument('--stock-reference', action='store_true', help='build the unpatched reference control explicitly')
    args = ap.parse_args()
    here = Path(__file__).resolve().parent
    core = here.parents[1]
    work = args.workspace.resolve()
    if work.exists():
        raise SystemExit('Use a new workspace; existing files will not be overwritten')
    work.mkdir(parents=True, mode=0o700)
    run(['python3', str(here / 'bootstrap.py'), '--workspace', str(work / 'dependency'), '--core', str(core)])
    pins = json.loads((here / 'dependencies.json').read_text())
    reference = work / 'reference'
    run(['git', 'clone', '--no-checkout', pins['reference']['repository'], str(reference)])
    run(['git', 'checkout', '--detach', pins['reference']['revision']], cwd=reference)
    reference_info = prepare_reference_overlay(reference, work / 'reference-overlay', stock=args.stock_reference)
    # This adapter is generated OUTSIDE the unmodified reference checkout.
    source = (here / 'probe.go').read_text().replace('github.com/sagernet/tailscale/', 'tailscale.com/')
    source = source.replace('"github.com/sagernet/wireguard-go/device"', '"tailscale.com/ipn"')
    start = source.index('func configure(')
    end = source.index('\nfunc main()', start)
    source = source[:start] + '''func configure(s *tsnet.Server, profile string) error {
 data,err:=os.ReadFile(profile);if err!=nil{return err};if len(bytes.TrimSpace(data))==0{return nil}
 var p ipn.AmneziaWGPrefs
 if err:=json.Unmarshal(data,&p);err!=nil{return err}
 if err:=ipn.ValidateAmneziaWGConfig(p);err!=nil{return err}
 if err:=s.Start();err!=nil{return err}
 lc,err:=s.LocalClient();if err!=nil{return err}
 _,err=lc.EditPrefs(context.Background(),&ipn.MaskedPrefs{Prefs:ipn.Prefs{AmneziaWG:p},AmneziaWGSet:true})
 return err
}
''' + source[end:]
    (work / 'reference-probe.go').write_text(source)
    env = dict(os.environ, GOTOOLCHAIN='go1.26.10', GOWORK=str(work / 'dependency/go.work'), CGO_ENABLED='0')
    run(['go', 'build', '-p', '3', '-ldflags=-checklinkname=0', '-o', str(work / 'candidate-probe'), str(here / 'probe.go')], cwd=core, env=env)
    tags = 'with_gvisor,with_tailscale,with_awg,with_tailscale_awg,with_lx_command,with_clash_api'
    run(['go', 'build', '-p', '3', '-tags', tags, '-ldflags=-checklinkname=0', '-o', str(work / 'core-probe'), str(here / 'core_probe.go')], cwd=core, env=env)
    env.update(GOTOOLCHAIN='go' + pins['reference']['go'], GOWORK='off')
    reference_args = ['go', 'build', '-mod=readonly', '-p', '3']
    if reference_info['go_overlay']:
        reference_args.append('-overlay=' + reference_info['go_overlay'])
    reference_args.extend(['-o', str(work / 'reference-probe'), str(work / 'reference-probe.go')])
    run(reference_args, cwd=reference, env=env)
    validate_reference(reference, pins['reference'])
    reference_info['command'] = reference_args
    reference_info['binary_sha256'] = hashlib.sha256((work / 'reference-probe').read_bytes()).hexdigest()
    (work / 'reference-build.json').write_text(json.dumps(reference_info, indent=2) + '\n')
    run(['docker', 'build', '-t', 'lx-awg-143-lab', '-f', str(here / 'Dockerfile.lab'), str(here)])
    print('Run lab.py and core_lab.py with --root ' + str(work / 'lab') + ' --binaries ' + str(work))


if __name__ == '__main__':
    main()
