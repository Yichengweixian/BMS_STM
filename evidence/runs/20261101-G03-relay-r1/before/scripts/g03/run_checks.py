"""Compile and exercise the actual disabled G03 MCU state machine and adapter."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
import xml.etree.ElementTree as ET

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--cc',default='gcc');a=p.parse_args()
    root=Path(__file__).resolve().parents[2];out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False)
    bsp=root/'BMS_EXv1.1/BMS_EX/BSP';test=root/'tests/g03';results=[]
    def run(name,cmd):
        cmd=[str(x) for x in cmd];r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        (out/(name+'.stdout')).write_bytes(r.stdout);(out/(name+'.stderr')).write_bytes(r.stderr)
        results.append(dict(name=name,command=cmd,exit_code=r.returncode))
        (out/'checks.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
        if r.returncode:raise RuntimeError(name+' failed')
    flags=[a.cc,'-std=c99','-Wall','-Wextra','-Werror','-pedantic','-I'+str(bsp)]
    run('compiler',[a.cc,'--version'])
    run('build-core',flags+[test/'test_control.c',bsp/'g03_control.c','-o',out/'core.exe'])
    run('core',[out/'core.exe'])
    run('build-port',flags+['-I'+str(root/'tests/g02/stubs'),test/'test_port.c',
        bsp/'g02_control.c',bsp/'g02_port.c',bsp/'g03_control.c',bsp/'g03_port.c',root/'tests/g03/adc_bridge_stub.c','-o',out/'port.exe'])
    run('port',[out/'port.exe'])
    run('build-link',flags+['-I'+str(root/'tests/g02/stubs'),test/'test_link.c',
        bsp/'g02_control.c',bsp/'g02_port.c',bsp/'g02_link.c',bsp/'g03_control.c',bsp/'g03_port.c',root/'tests/g03/adc_bridge_stub.c','-o',out/'link.exe'])
    run('link',[out/'link.exe'])
    sys.path.insert(0,str(root/'scripts/g03'))
    from disabled_diagnostics import parse
    replies=[parse(x) for x in (out/'link.stdout').read_bytes().splitlines() if x.startswith(b'#G03,')]
    assert replies and all(x['synthetic']==1 and x['power_capable']==x['actual_bits']==0 for x in replies)
    assert next(x for x in replies if x['id']==24)['faults']==128
    assert replies[-1]['state']==0
    run('host-python',[sys.executable,'-m','unittest','discover','-s',test,'-p','test_host.py','-v'])
    for line in (out/'port.stdout').read_text().splitlines():
        if line.startswith('#G03,'):
            values=list(map(int,line.split(',')[2:]));expected=values[1]
            assert values[2]==6 and (values[4] & (expected or 128))
            assert values[9]==values[10]==values[11]==0 and values[-2:]==[1,0]
    project=root/'BMS_EXv1.1/BMS_EX/MDK-ARM/Appli/BMS_EX_Appli.uvprojx'
    for target in ET.parse(str(project)).findall('./Targets/Target'):
        files=[x.text for x in target.findall('.//FileName')]
        assert files.count('g03_control.c')==files.count('g03_port.c')==1
        assert not any('G02_ALLOW_PIN_OUTPUT=1' in (x.text or '') for x in target.findall('.//Define'))
    adapter=(bsp/'g03_port.c').read_text()
    assert 'HAL_TIM_PWM_Start' not in adapter and 'HAL_GPIO_WritePin' not in adapter
    it=(root/'BMS_EXv1.1/BMS_EX/Appli/Core/Src/stm32n6xx_it.c').read_text(encoding='utf-8-sig')
    assert 'HAL_IncTick();\n  G03_TickIRQ();' in it
    sources=list(bsp.glob('g03_*.[ch]'))+list(test.glob('*.c'))+list(test.glob('*.py'))+list((root/'scripts/g03').glob('*.py'))
    (out/'result.json').write_text(json.dumps(dict(status='complete',verdict=None,evidence_scope=['static','simulation'],
        checks='passed',physical_outputs_verified=False,sha256={str(x.relative_to(root)):hashlib.sha256(x.read_bytes()).hexdigest() for x in sources}),indent=2),encoding='utf-8')
    print('PASS: G03 core/adapter, 10000 event sequences, synthetic faults, no output-enable API, SysTick hook.')

if __name__=='__main__':main()
