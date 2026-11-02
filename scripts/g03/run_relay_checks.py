"""Production relay core/adapter/link; register simulation is not electrical evidence."""
import argparse,subprocess,sys,json
from pathlib import Path
def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--cc',required=True);a=p.parse_args()
    root=Path(__file__).resolve().parents[2];out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False)
    bsp=root/'BMS_EXv1.1/BMS_EX/BSP';test=root/'tests/g03';results=[]
    def run(name,cmd):
        r=subprocess.run(list(map(str,cmd)),capture_output=True)
        (out/(name+'.stdout')).write_bytes(r.stdout);(out/(name+'.stderr')).write_bytes(r.stderr)
        results.append(dict(name=name,exit_code=r.returncode,command=list(map(str,cmd))))
        (out/'checks.json').write_text(json.dumps(results,indent=2))
        if r.returncode:raise RuntimeError(name+': '+r.stderr.decode(errors='replace'))
    flags=[a.cc,'-std=c99','-Wall','-Wextra','-Werror','-pedantic','-I'+str(bsp)]
    run('build-core',flags+[test/'test_relay_core.c',bsp/'g03_relay_core.c','-o',out/'core.exe'])
    run('core',[out/'core.exe'])
    run('adapter-stack-frame',flags+['-Wframe-larger-than=512','-I'+str(root/'tests/g02/stubs'),'-c',bsp/'g03_relay_port.c','-o',out/'relay.o'])
    sources=[test/'test_relay_port.c']+[bsp/n for n in ['g02_control.c','g02_port.c','g02_link.c','g03_control.c','g03_port.c','g03_adc_core.c','g03_adc_port.c','g03_relay_core.c','g03_relay_port.c','measurement_core.c']]
    for name,defs in [('disabled',['-DG3R_LIVE_PROFILE_VERIFIED=0']),('live-register-fixture',['-DG3R_LIVE_PROFILE_VERIFIED=1','-DG3R_CELL_LOW_CODE=36000','-DG3R_CELL_HIGH_CODE=41000'])]:
        run('build-'+name,flags+defs+['-include','stdlib.h','-I'+str(root/'tests/g02/stubs')]+sources+['-lm','-o',out/(name+'.exe')])
        run(name,[out/(name+'.exe')])
    run('host',[sys.executable,'-m','unittest','discover','-s',test,'-p','test_relay_host.py','-v'])
    (out/'result.json').write_text(json.dumps(dict(checks='passed',evidence_scope=['simulation'],physical_limits_verified=False),indent=2))
    print('PASS relay core + production adapter/link, disabled and synthetic live register fixtures')
if __name__=='__main__':main()
