from pathlib import Path
import datetime,hashlib,json,os,subprocess

OUT=Path(__file__).parent
WORK=OUT.parent/'workspace'
BSP=WORK/'BMS_EXv1.1/BMS_EX/BSP'
TEST=WORK/'tests/g03/test_pwm_port.c'
STUB=WORK/'tests/g03/pwm_port_fixture'
GXX=Path(r'D:\Program Files\JetBrains\CLion 2025.2.3\bin\mingw\bin\g++.exe')
env=os.environ.copy();env['PATH']=str(GXX.parent)+os.pathsep+env.get('PATH','')
records=[]
run=OUT/('attempt-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
run.mkdir(exist_ok=False)
def invoke(name,args):
    r=subprocess.run(list(map(str,args)),cwd=OUT,env=env,capture_output=True,timeout=40)
    (run/(name+'.stdout')).write_bytes(r.stdout);(run/(name+'.stderr')).write_bytes(r.stderr)
    records.append(dict(name=name,command=list(map(str,args)),exit_code=r.returncode))
    (run/'commands.json').write_text(json.dumps(records,indent=2))
    if r.returncode:raise RuntimeError(name+': '+r.stderr.decode(errors='replace')+r.stdout.decode(errors='replace'))
    return r.stdout.decode(errors='replace')
sources=[BSP/'g03_pwm_port.c',BSP/'g03_pwm_port.h',BSP/'pwm_oneshot.c',BSP/'pwm_oneshot.h',TEST,STUB/'main.h']
hashes={str(p.relative_to(WORK)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
cases=['deadline','wrap','stop','protocol','preflight','clock','preflight_protocol','fault_flags','fifo','buffer','overrun_scenario','awd_low','awd_high','cleanup_failure','cleanup_failure_readback']
try:
    invoke('build',[GXX,'-x','c++','-std=c++17','-O2','-Wall','-Werror',
                    '-Wno-missing-field-initializers','-Wno-misleading-indentation',
                    '-DG03_PWM_DISABLED_BUILD=1','-DG3R_LIVE_PROFILE_VERIFIED=0',
                    '-I'+str(STUB),'-I'+str(BSP),'-include',STUB/'main.h',
                    BSP/'g03_pwm_port.c',BSP/'pwm_oneshot.c',TEST,'-o',run/'test_pwm_port.exe'])
    for case in cases:print(invoke(case,[run/'test_pwm_port.exe',case]).strip())
    verdict='pass'
except Exception as error:
    verdict='fail';print(repr(error))
finally:
    stable=all(hashlib.sha256((WORK/p).read_bytes()).hexdigest()==v for p,v in hashes.items())
    manifest=dict(scope='Unmodified production adapter and core compiled as C++ against side-effect register/HAL model; no hardware',
                  verdict=verdict,test_groups=len(cases),cases=cases,source_sha256=hashes,sources_unchanged_during_test=stable,
                  caveat='Model exercises register semantics and adapter integration; real peripheral timing/NVIC effects remain board tests.')
    (run/'validation.json').write_text(json.dumps(manifest,indent=2))
    print(run)
    if verdict!='pass' or not stable:raise SystemExit(1)
