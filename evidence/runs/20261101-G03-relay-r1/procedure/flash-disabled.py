"""Flash only the reviewed relay-disabled Release; preserve every attempt."""
from pathlib import Path
import hashlib,json,subprocess,datetime,shutil
root=Path(__file__).parent
out=root/'evidence/runs/20261101-G03-relay-r1'
profile=(root/'BMS_EXv1.1/BMS_EX/BSP/g03_relay_profile.h').read_text()
assert '#define G3R_LIVE_PROFILE_VERIFIED 0U' in profile
cli=Path('E:/ST/STM32CubeIDE_1.19.0/STM32CubeIDE/plugins/com.st.stm32cube.ide.mcu.externaltools.cubeprogrammer.win32_2.2.200.202503041107/tools/bin/STM32_Programmer_CLI.exe')
loader=Path('D:/ADMIN/Desktop/WEIJI/zonghe/tools/flash-loaders/MX25UM25645G_ATK-CNN647B_ExtMemLoader.stldr')
fw=root/'BMS_EXv1.1/BMS_EX/MDK-ARM/Appli/BMS_EX_Release/BMS_EX_Release.hex'
attempt=out/('flash-'+datetime.datetime.now().strftime('%H%M%S'));attempt.mkdir(exist_ok=False)
shutil.copy2(fw,attempt/fw.name)
source={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for base in ['BMS_EXv1.1/BMS_EX/BSP','BMS_EXv1.1/BMS_EX/Appli','scripts','tests'] for p in (root/base).rglob('*') if p.is_file() and p.suffix in ('.c','.h','.py','.s')}
(attempt/'source-manifest.json').write_text(json.dumps(source,indent=2))
cmd=[str(cli),'-c','port=SWD','sn=16004A002933353739303541','freq=100','mode=UR','reset=HWrst','-el',str(loader),'-w',str(attempt/fw.name),'-v']
start=datetime.datetime.now(datetime.timezone.utc).isoformat()
r=subprocess.run(cmd,capture_output=True,timeout=300)
(attempt/'programmer.stdout').write_bytes(r.stdout);(attempt/'programmer.stderr').write_bytes(r.stderr)
txt=r.stdout.decode(errors='replace')
verified=r.returncode==0 and 'Download verified successfully' in txt
result=dict(command=cmd,start_utc=start,exit_code=r.returncode,verified=verified,sha256=hashlib.sha256(fw.read_bytes()).hexdigest())
(attempt/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2),flush=True);print(txt[-2400:],flush=True)
if not verified:raise SystemExit(1)
# Only after explicit verification, reset from the same normal-BOOT connection.
cmd=[str(cli),'-c','port=SWD','sn=16004A002933353739303541','freq=100','mode=HOTPLUG','-rst']
r=subprocess.run(cmd,capture_output=True,timeout=30)
(attempt/'reset.stdout').write_bytes(r.stdout);(attempt/'reset.stderr').write_bytes(r.stderr)
print('reset exit',r.returncode,flush=True)
raise SystemExit(r.returncode)
