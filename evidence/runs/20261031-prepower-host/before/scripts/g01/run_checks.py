"""Build/run host fault injection plus recorder replay against production sources."""
import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys
import hashlib

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--cc',default='gcc')
    a=p.parse_args();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parents[2];bsp=root/'BMS_EXv1.1/BMS_EX/BSP';test=root/'tests/g01'
    results=[]
    def run(name,cmd,stdout_name=None):
        r=subprocess.run([str(x) for x in cmd],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        (out/(stdout_name or name+'.stdout')).write_bytes(r.stdout)
        (out/(name+'.stderr')).write_bytes(r.stderr)
        results.append(dict(name=name,command=[str(x) for x in cmd],exit_code=r.returncode))
        (out/'checks.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
        if r.returncode: raise RuntimeError(name+' failed: '+r.stderr.decode(errors='replace'))
        return r
    exe=out/'native-tests.exe'
    run('gcc',[a.cc,'-std=c99','-Wall','-Wextra','-Werror','-I'+str(test/'stubs'),'-I'+str(bsp),
               test/'test_measurement.c',bsp/'measurement_core.c',bsp/'adbms_acquisition.c',bsp/'measurement.c','-lm','-o',exe])
    run('native',[exe],'simulated-uart.bin')
    run('python-tests',[sys.executable,'-m','unittest','discover','-s',test,'-p','test_*.py','-v'])
    run('replay',[sys.executable,root/'scripts/g01/g01_capture.py','--replay',out/'simulated-uart.bin','--out',out/'replay'])
    manifest=json.loads((out/'replay/manifest.json').read_text())
    assert manifest['rows']==36 and manifest['errors']==0 and manifest['simulated'] is True
    with (out/'replay/derived/device.csv').open(newline='',encoding='utf-8') as f: rows=list(csv.DictReader(f))
    assert len({r['channel'] for r in rows})==9
    assert all(r['physical_valid']=='0' and r['physical_value']=='' and r['reference']=='' for r in rows)
    main_source=(root/'BMS_EXv1.1/BMS_EX/Appli/Core/Src/main.c').read_text(encoding='utf-8-sig')
    assert 'hadc1.Init.ExternalTrigConv = ADC_SOFTWARE_START;' in main_source
    assert 'Measurement_Task();' in main_source
    assert 'HAL_TIM_PWM_Start' not in main_source and 'HAL_TIM_Base_Start' not in main_source
    assert 'BMS_ReadSample' not in main_source and 'uart_send_dma(uart_rx_data()' not in main_source
    report=dict(scope=['static','simulation'],verdict=None,checks='passed',rows=36,channels=9,
                raw_source='synthetic HAL fault injection; not board capture',hardware_verified=False,
                sha256={str(x.relative_to(root)):hashlib.sha256(x.read_bytes()).hexdigest()
                        for x in [bsp/'measurement_core.c',bsp/'adbms_acquisition.c',bsp/'measurement.c',test/'test_measurement.c',test/'test_recorder.py',test/'test_voltage_calibration.py',
                                root/'scripts/g01/g01_capture.py',root/'scripts/g01/voltage_calibration.py',Path(__file__)]})
    (out/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('PASS: production C fault injection, parser checks, 36-row end-to-end replay; hardware/calibration pending.')

if __name__=='__main__':main()
