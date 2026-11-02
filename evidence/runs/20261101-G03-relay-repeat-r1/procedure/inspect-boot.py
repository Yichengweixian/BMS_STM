import datetime,json,subprocess
from pathlib import Path
root=Path(r'D:\ADMIN\Desktop\WEIJI\zonghe');run=root/'evidence/runs/20261101-G03-relay-repeat-r1'
out=run/'boot-inspect-01';out.mkdir(exist_ok=False)
cli=r'E:\ST\STM32CubeIDE_1.19.0\STM32CubeIDE\plugins\com.st.stm32cube.ide.mcu.externaltools.cubeprogrammer.win32_2.2.200.202503041107\tools\bin\STM32_Programmer_CLI.exe'
conn=[cli,'-c','port=SWD','sn=16004A002933353739303541','freq=100','mode=HOTPLUG']
records=[]
for name,address,length in [('vector',0xe000ed08,4),('faults',0xe000ed24,24),('debug-status',0xe000edf0,4)]:
    cmd=conn+['-r32',hex(address),str(length)]
    r=subprocess.run(cmd,capture_output=True,timeout=25)
    (out/(name+'.stdout')).write_bytes(r.stdout);(out/(name+'.stderr')).write_bytes(r.stderr)
    records.append(dict(name=name,command=cmd,exit_code=r.returncode))
    print(name,r.returncode,r.stdout.decode(errors='replace')[-700:],flush=True)
(out/'manifest.json').write_text(json.dumps(dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),mode='hotplug read-only; no halt/reset/write',commands=records),indent=2),encoding='utf-8')
