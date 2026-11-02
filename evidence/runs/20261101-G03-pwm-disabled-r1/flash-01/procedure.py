from pathlib import Path
import datetime,hashlib,json,subprocess
ROOT=Path(r'D:\ADMIN\Desktop\WEIJI\zonghe')
RUN=ROOT/'evidence/runs/20261101-G03-pwm-disabled-r1'
IMAGE=RUN/'firmware/BMS_PWM_Disabled_Release/BMS_PWM_Disabled_Release.hex'
EXPECTED='9126778404c6f9a9890ab729522f7fbd9fe7fe0a380436694494ebecde81f9fb'
CLI=r'E:\ST\STM32CubeIDE_1.19.0\STM32CubeIDE\plugins\com.st.stm32cube.ide.mcu.externaltools.cubeprogrammer.win32_2.2.200.202503041107\tools\bin\STM32_Programmer_CLI.exe'
LOADER=ROOT/'tools/flash-loaders/MX25UM25645G_ATK-CNN647B_ExtMemLoader.stldr'
assert hashlib.sha256(IMAGE.read_bytes()).hexdigest()==EXPECTED
out=RUN/'flash-01';out.mkdir(exist_ok=False)
(out/'procedure.py').write_bytes(Path(__file__).read_bytes())
command=[CLI,'-c','port=SWD','sn=16004A002933353739303541','freq=100','mode=UR','reset=HWrst','-el',str(LOADER),'-w',str(IMAGE),'-v']
record=dict(command=command,firmware_sha256=EXPECTED,loader_sha256=hashlib.sha256(LOADER.read_bytes()).hexdigest(),started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),user_confirmed_boot_download=True,verdict=None)
def save(): (out/'result.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
save()
try:
    result=subprocess.run(command,capture_output=True,timeout=180)
    (out/'stdout.txt').write_bytes(result.stdout);(out/'stderr.txt').write_bytes(result.stderr)
    output=result.stdout.decode(errors='replace')
    record.update(exit_code=result.returncode,verdict='pass' if result.returncode==0 and 'Download verified successfully' in output else 'fail')
    print(output,flush=True)
except subprocess.TimeoutExpired as error:
    (out/'stdout.txt').write_bytes(error.stdout or b'');(out/'stderr.txt').write_bytes(error.stderr or b'')
    record.update(verdict='fail',error=repr(error))
finally:
    record['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();save()
print(json.dumps(record,indent=2),flush=True)
raise SystemExit(0 if record['verdict']=='pass' else 1)
