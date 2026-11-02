"""Compile production real-ADC core/adapter against explicit register/HAL stimuli."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--cc',default='gcc');a=p.parse_args()
    root=Path(__file__).resolve().parents[2];out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False)
    bsp=root/'BMS_EXv1.1/BMS_EX/BSP';test=root/'tests/g03';results=[]
    def run(name,cmd):
        r=subprocess.run(list(map(str,cmd)),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        (out/(name+'.stdout')).write_bytes(r.stdout);(out/(name+'.stderr')).write_bytes(r.stderr)
        results.append(dict(name=name,command=list(map(str,cmd)),exit_code=r.returncode))
        (out/'checks.json').write_text(json.dumps(results,indent=2))
        if r.returncode:raise RuntimeError(name+' failed: '+r.stderr.decode(errors='replace'))
    flags=[a.cc,'-std=c99','-Wall','-Wextra','-Werror','-pedantic','-I'+str(bsp)]
    run('build-core',flags+[test/'test_adc_core.c',bsp/'g03_adc_core.c','-lm','-o',out/'core.exe'])
    run('core',[out/'core.exe'])
    run('build-port',flags+['-I'+str(root/'tests/g02/stubs'),test/'test_adc_port.c',
        bsp/'g02_control.c',bsp/'g02_port.c',bsp/'g03_control.c',bsp/'g03_port.c',
        bsp/'g03_adc_core.c',bsp/'g03_adc_port.c','-lm','-o',out/'port.exe'])
    run('port',[out/'port.exe'])
    run('build-link',flags+['-I'+str(root/'tests/g02/stubs'),test/'test_adc_link.c',
        bsp/'g02_control.c',bsp/'g02_port.c',bsp/'g03_control.c',bsp/'g03_port.c',bsp/'g02_link.c',
        bsp/'g03_adc_core.c',bsp/'g03_adc_port.c','-lm','-o',out/'link.exe'])
    run('link',[out/'link.exe'])
    sys.path.insert(0,str(root/'scripts/g03'))
    from adc_diagnostics import parse
    reports=[parse(x) for x in (out/'link.stdout').read_bytes().splitlines()
             if x.startswith((b'#G3A,',b'#G3D,',b'#G3T,')) and b'*' in x]
    assert reports and all(r.get('actual_bits',0)==r.get('power_capable',0)==0 for r in reports)
    assert next(r for r in reports if r['id']==104)['faults']&8
    run('python',[sys.executable,'-m','unittest','discover','-s',test,'-p','test_adc_host.py','-v'])
    adapter=(bsp/'g03_adc_port.c').read_text()
    assert all(x not in adapter for x in ['HAL_TIM_PWM_Start','HAL_GPIO_WritePin','TIM1->CCR2 =','TIM1->CCR2='])
    files=list(bsp.glob('g03_adc*'))+[bsp/'nominal_current.h',test/'test_adc_core.c',test/'test_adc_port.c']
    (out/'result.json').write_text(json.dumps(dict(checks='passed',evidence_scope=['static','simulation'],bench=False,
        source_sha256={str(x.relative_to(root)):hashlib.sha256(x.read_bytes()).hexdigest() for x in files}),indent=2))
    print('PASS real ADC core/adapter simulation; no electrical timing claim')
if __name__=='__main__':main()
