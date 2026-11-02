from pathlib import Path
import subprocess,json,hashlib,shutil,datetime
stage=Path(__file__).resolve().parent/'g03-adc-work';root=Path('D:/ADMIN/Desktop/WEIJI/zonghe')
run=Path('evidence/runs/20261031-G03-real-adc-r4');out=root/run
assert not out.exists()
for name in ['checks-1-final','checks-2-final','checks-3-final','adc-checks-02']:
    assert json.loads((stage/run/name/'result.json').read_text())['checks']=='passed'
shutil.copytree(stage/run,out);(out/'raw').mkdir()
manifest=[]
for directory in ['BMS_EXv1.1/BMS_EX/BSP','scripts','tests']:
    for src in (stage/directory).rglob('*'):
        if src.suffix not in ('.c','.h','.py'):continue
        rel=src.relative_to(stage);dst=root/rel
        if dst.exists() and dst.read_bytes()==src.read_bytes():continue
        oldhash=hashlib.sha256(dst.read_bytes()).hexdigest() if dst.exists() else None
        if dst.exists():
            backup=out/'before'/rel;backup.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(dst,backup)
        shutil.copyfile(src,dst);manifest.append(dict(path=str(rel),before_sha256=oldhash,after_sha256=hashlib.sha256(dst.read_bytes()).hexdigest()))
firmware={}
for target in ['BMS_EX_Release','BMS_EX_Debug']:
    src=stage/'BMS_EXv1.1/BMS_EX/MDK-ARM/Appli'/target/(target+'.hex');dst=out/'firmware'/target/src.name
    dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst);firmware[target]={'path':str(dst),'sha256':hashlib.sha256(dst.read_bytes()).hexdigest()}
(out/'delivery-manifest.json').write_text(json.dumps(dict(files=manifest,firmware=firmware),indent=2))
(out/'source-manifest.json').write_text(json.dumps({str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'BMS_EXv1.1/BMS_EX').rglob('*') if p.suffix.lower() in ('.c','.h','.s','.sct','.uvprojx')},indent=2))
(out/'manifest.json').write_text(json.dumps(dict(firmware='g03-adc-r4',evidence_scope=['static','build','simulation','bench'],actual_power_allowed=False,board=dict(batteries='three real cells per user',load_ohm=33,charge_port='open'),change='persistent ADC acquisition profiles 4/5; 64 retained samples, first 16 explicit startup, last 48 stable within 32 codes; fresh disabled preflight must remain within accepted baseline window',warmup_is_not_power_protection=True,physical_valid=False),indent=2))
old=json.loads((root/'evidence/runs/20261031-G03-disabled/flash-result-01.json').read_text())
conn=[old['command'][0],'-c','port=SWD','sn=16004A002933353739303541','freq=100']
cmd=conn+['mode=UR','reset=HWrst','-el',old['command'][old['command'].index('-el')+1],'-w',firmware['BMS_EX_Release']['path'],'-v']
start=datetime.datetime.now(datetime.timezone.utc).isoformat()
r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180)
(out/'raw/flash-01.stdout').write_bytes(r.stdout);(out/'raw/flash-01.stderr').write_bytes(r.stderr)
verified=r.returncode==0 and b'Download verified successfully' in r.stdout
result=dict(command=cmd,start_utc=start,end_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),exit_code=r.returncode,verified=verified,sha256=firmware['BMS_EX_Release']['sha256'])
(out/'flash-result-01.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,ensure_ascii=True))
if not verified:print(json.dumps(r.stdout.decode(errors='replace'),ensure_ascii=True));raise SystemExit(1)
reset=subprocess.run(conn+['mode=HOTPLUG','-rst'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
(out/'raw/software-reset-01.stdout').write_bytes(reset.stdout);(out/'raw/software-reset-01.stderr').write_bytes(reset.stderr)
print(json.dumps({'reset_exit':reset.returncode,'stdout':reset.stdout.decode(errors='replace')},ensure_ascii=True))
