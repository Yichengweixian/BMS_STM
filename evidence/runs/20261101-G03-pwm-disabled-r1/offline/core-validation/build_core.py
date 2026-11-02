from pathlib import Path
import hashlib, json, os, re, subprocess

OUT = Path(__file__).parent
WORK = OUT.parent/'workspace'
BSP = WORK/'BMS_EXv1.1/BMS_EX/BSP'
SOURCE = BSP/'pwm_oneshot.c'
TEST = WORK/'tests/g03/test_pwm_oneshot.c'
GCC = Path(r'D:\Program Files\JetBrains\CLion 2025.2.3\bin\mingw\bin\gcc.exe')
ARM = Path(r'D:\K5\ARM\ARMCLANG\bin\armclang.exe')
env = os.environ.copy()
env['PATH'] = str(GCC.parent)+os.pathsep+env.get('PATH','')
flags = ['-std=c11','-Wall','-Wextra','-Werror','-Wconversion','-Wshadow','-pedantic','-O2']
records = []

def command(name, args):
    r = subprocess.run(list(map(str,args)),cwd=OUT,env=env,capture_output=True,timeout=40)
    (OUT/(name+'.stdout')).write_bytes(r.stdout)
    (OUT/(name+'.stderr')).write_bytes(r.stderr)
    records.append(dict(name=name,command=list(map(str,args)),exit_code=r.returncode))
    (OUT/'commands.json').write_text(json.dumps(records,indent=2))
    if r.returncode:
        raise RuntimeError(name+': '+r.stderr.decode(errors='replace')+r.stdout.decode(errors='replace'))
    return r.stdout.decode(errors='replace')

version = command('gcc-version',[GCC,'--version']).splitlines()[0]
command('gcc-build',[GCC,*flags,'-I'+str(BSP),SOURCE,TEST,'-o',OUT/'test_pwm_oneshot.exe'])
results = command('host-tests',[OUT/'test_pwm_oneshot.exe'])
arm_version = command('armclang-version',[ARM,'--version']).splitlines()[0]
command('cortex-m55-object',[ARM,'--target=arm-arm-none-eabi','-mcpu=cortex-m55',
                           '-std=c11','-O2','-Wall','-Wextra','-Werror',
                           '-c',SOURCE,'-o',OUT/'pwm_oneshot_m55.o'])
obj = OUT/'pwm_oneshot_m55.o'
assert obj.read_bytes().startswith(b'\x7fELF')
assert re.search(r'^PASS 21 tests;',results,re.M)
validation = dict(scope='Microsecond core host simulation and actual Cortex-M55 relocatable object compilation; no board validation',
                  gcc_version=version,armclang_version=arm_version,test_groups=21,
                  time_unit='us',timebase_contract='One naturally wrapping free-running uint32 1MHz counter',
                  source_basis='20261101-HEX-baseline-followup/candidate r2',
                  driver_deadtime_source_allows_zero_dtg=True,
                  host_verdict='pass',target_object_verdict='pass',
                  object_size=obj.stat().st_size,
                  sha256={str(p.relative_to(OUT.parent)):hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in (SOURCE,BSP/'pwm_oneshot.h',TEST,obj)})
(OUT/'validation.json').write_text(json.dumps(validation,indent=2))
print(results)
print(json.dumps(validation,indent=2))
