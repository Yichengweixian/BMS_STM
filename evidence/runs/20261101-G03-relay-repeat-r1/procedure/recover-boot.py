import argparse,datetime,json,subprocess
from pathlib import Path
root=Path(r'D:\ADMIN\Desktop\WEIJI\zonghe');run=root/'evidence/runs/20261101-G03-relay-repeat-r1'
p=argparse.ArgumentParser();p.add_argument('--for-third',action='store_true');a=p.parse_args()
if a.for_third:
    previous=json.loads((run/'repeat-02/result.json').read_text(encoding='utf-8'))
    assert previous['analysis']['conclusion']=='response_and_recovery' and previous['final']['actual_bits']==0 and previous['final']['faults']==0
    assert not (run/'repeat-03').exists()
out=run/('software-reset-for-repeat-03' if a.for_third else 'boot-software-reset-01');out.mkdir(exist_ok=False)
cli=r'E:\ST\STM32CubeIDE_1.19.0\STM32CubeIDE\plugins\com.st.stm32cube.ide.mcu.externaltools.cubeprogrammer.win32_2.2.200.202503041107\tools\bin\STM32_Programmer_CLI.exe'
cmd=[cli,'-c','port=SWD','sn=16004A002933353739303541','freq=100','mode=HOTPLUG','-rst']
r=subprocess.run(cmd,capture_output=True,timeout=30)
(out/'programmer.stdout').write_bytes(r.stdout);(out/'programmer.stderr').write_bytes(r.stderr)
(out/'result.json').write_text(json.dumps(dict(command=cmd,created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),exit_code=r.returncode,reason='Explicit software reset for the separately evaluated third trial; previous trial recovered' if a.for_third else 'User normal-BOOT reset left VTOR=0x18000000 and UART silent; one existing software-reset recovery',power_trigger_sent=False),indent=2),encoding='utf-8')
print(r.stdout.decode(errors='replace')[-850:]);raise SystemExit(r.returncode)
