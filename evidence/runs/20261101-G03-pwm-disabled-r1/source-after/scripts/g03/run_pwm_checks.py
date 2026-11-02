"""One-shot core, production disabled adapter model, and host protocol checks.
No serial, SWD, flashing or power access.
"""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,sys

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--cc',default=r'D:\Program Files\JetBrains\CLion 2025.2.3\bin\mingw\bin\gcc.exe')
    p.add_argument('--cxx',default=r'D:\Program Files\JetBrains\CLion 2025.2.3\bin\mingw\bin\g++.exe')
    p.add_argument('--arm',default=r'D:\K5\ARM\ARMCLANG\bin\armclang.exe')
    a=p.parse_args();root=Path(__file__).resolve().parents[2];out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    bsp=root/'BMS_EXv1.1/BMS_EX/BSP';test=root/'tests/g03';stub=test/'pwm_port_fixture'
    env=os.environ.copy();env['PATH']=str(Path(a.cxx).parent)+os.pathsep+env.get('PATH','');records=[]
    inputs=[bsp/n for n in ('pwm_oneshot.c','pwm_oneshot.h','g03_pwm_port.c','g03_pwm_port.h')]+[test/'test_pwm_oneshot.c',test/'test_pwm_port.c',stub/'main.h',root/'scripts/g03/pwm_disabled.py',test/'test_pwm_disabled_host.py']
    hashes={str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in inputs}
    def run(name,args):
        args=list(map(str,args));r=subprocess.run(args,cwd=root,env=env,capture_output=True,timeout=50)
        (out/(name+'.stdout')).write_bytes(r.stdout);(out/(name+'.stderr')).write_bytes(r.stderr)
        records.append(dict(name=name,command=args,exit_code=r.returncode));(out/'commands.json').write_text(json.dumps(records,indent=2))
        if r.returncode:raise RuntimeError(name+': '+r.stderr.decode(errors='replace')+r.stdout.decode(errors='replace'))
        return r.stdout
    result=dict(evidence_scope=['simulation','build'],hardware_access=False,source_sha256=hashes)
    try:
        run('build-core',[a.cc,'-std=c11','-O2','-Wall','-Wextra','-Werror','-Wconversion','-Wshadow','-pedantic','-I'+str(bsp),bsp/'pwm_oneshot.c',test/'test_pwm_oneshot.c','-o',out/'core.exe'])
        assert b'PASS 21 tests;' in run('core',[out/'core.exe'])
        run('m55-object',[a.arm,'--target=arm-arm-none-eabi','-mcpu=cortex-m55','-std=c11','-O2','-Wall','-Wextra','-Werror','-c',bsp/'pwm_oneshot.c','-o',out/'core_m55.o'])
        assert (out/'core_m55.o').read_bytes().startswith(b'\x7fELF')
        run('build-port-model',[a.cxx,'-x','c++','-std=c++17','-O2','-Wall','-Werror','-Wno-missing-field-initializers','-Wno-misleading-indentation',
            '-DG03_PWM_DISABLED_BUILD=1','-DG3R_LIVE_PROFILE_VERIFIED=0','-I'+str(stub),'-I'+str(bsp),'-include',stub/'main.h',
            bsp/'g03_pwm_port.c',bsp/'pwm_oneshot.c',test/'test_pwm_port.c','-o',out/'port.exe'])
        cases=['deadline','wrap','stop','protocol','preflight','clock','preflight_protocol','fault_flags','fifo','buffer','overrun_scenario','awd_low','awd_high','cleanup_failure','cleanup_failure_readback']
        for case in cases:run('port-'+case,[out/'port.exe',case])
        run('host',[sys.executable,'-m','unittest','discover','-s',test,'-p','test_pwm_disabled_host.py','-v'])
        assert all(hashlib.sha256((root/f).read_bytes()).hexdigest()==h for f,h in hashes.items())
        result.update(verdict='pass',core_groups=21,port_groups=len(cases),target_object_compiled=True,
            caveat='Port model compiles unchanged .c files as C++ for side-effect registers. Keil C build and physical peripheral tests are separate.')
    except Exception as error:result.update(verdict='fail',error=repr(error))
    (out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
    return 0 if result['verdict']=='pass' else 1
if __name__=='__main__':raise SystemExit(main())
