"""Resume the verified r1 candidate download after the user selected ROM boot."""
from pathlib import Path
import hashlib,json,subprocess,datetime,shutil
root=Path('D:/ADMIN/Desktop/WEIJI/zonghe')
run=root/'evidence/runs/20261101-G03-relay-r1'
fw=root/'evidence/runs/20261101-G03-relay-r1/firmware/BMS_EX_Release/BMS_EX_Release.hex'
expected='529e6b83280d724f226e462dad59624f39552d640ba0eb9ec3366ccc694895bf'
assert hashlib.sha256(fw.read_bytes()).hexdigest()==expected
assert '#define G3R_LIVE_PROFILE_VERIFIED 0U' in (root/'BMS_EXv1.1/BMS_EX/BSP/g03_relay_profile.h').read_text()
out=run/('flash-romboot-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));out.mkdir(exist_ok=False)
shutil.copy2(__file__,out/'procedure.py')
cli='E:/ST/STM32CubeIDE_1.19.0/STM32CubeIDE/plugins/com.st.stm32cube.ide.mcu.externaltools.cubeprogrammer.win32_2.2.200.202503041107/tools/bin/STM32_Programmer_CLI.exe'
loader=root/'tools/flash-loaders/MX25UM25645G_ATK-CNN647B_ExtMemLoader.stldr'
cmd=[cli,'-c','port=SWD','sn=16004A002933353739303541','freq=100','mode=UR','reset=HWrst','-el',str(loader),'-w',str(fw),'-v']
start=datetime.datetime.now(datetime.timezone.utc).isoformat()
with (out/'programmer.stdout').open('wb') as stdout,(out/'programmer.stderr').open('wb') as stderr:
    r=subprocess.run(cmd,stdout=stdout,stderr=stderr,timeout=300)
txt=(out/'programmer.stdout').read_text(errors='replace')
verified=r.returncode==0 and 'Download verified successfully' in txt
result=dict(command=cmd,start_utc=start,exit_code=r.returncode,verified=verified,sha256=expected,boot_mode='user confirmed BOOT1=1 BOOT0=0',normal_boot_confirmed=False)
(out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2),flush=True);print(txt[-2500:],flush=True)
raise SystemExit(0 if verified else 1)
