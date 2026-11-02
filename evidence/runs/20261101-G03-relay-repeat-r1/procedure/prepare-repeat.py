import datetime,hashlib,json,sys
from pathlib import Path
root=Path(r'D:\ADMIN\Desktop\WEIJI\zonghe')
prior=root/'evidence/runs/20261101-G03-relay-r2'
run=root/'evidence/runs/20261101-G03-relay-repeat-r1'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
profile=read(prior/'conditions-ready.json')
assert sha(prior/'firmware/BMS_EX_Release/BMS_EX_Release.hex')==profile['firmware_sha256']
assert read(prior/'live-01/result.json')['analysis']['conclusion']=='response_and_recovery'
run.mkdir(exist_ok=False)
profile.update(live_ready=False,study_id=run.name,source_profile_sha256=sha(prior/'conditions-ready.json'),new_attempts_planned=2,per_attempt_limit=1,reset_required_between_attempts=True,automatic_reset=False,automatic_retry=False,comparison=dict(required='Each independently triggered run has coherent response, recovery, no faults, and complete sample coverage under the unchanged rules',magnitude_spread='descriptive only; no accuracy/repeatability percentage invented',reference_run='20261101-G03-relay-r2/live-01'),frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
(run/'conditions-frozen.json').write_text(json.dumps(profile,indent=2),encoding='utf-8')
(run/'manifest.json').write_text(json.dumps(dict(run_id=run.name,status='in_progress',verdict=None,evidence_scope=['static'],firmware_sha256=profile['firmware_sha256'],conditions='conditions-frozen.json',actual_new_triggers=0),indent=2),encoding='utf-8')
sys.path.insert(0,str(root/'scripts/g03'))
from relay_capture import Session,ok
import serial
out=run/'initial-status';out.mkdir()
link=serial.Serial();link.port='COM11';link.baudrate=115200;link.timeout=.05;link.write_timeout=1;link.dtr=link.rts=False
s=Session(link,out)
try:
    link.open();st=ok(s.request(30));(out/'result.json').write_text(json.dumps(st,indent=2),encoding='utf-8')
finally:s.close()
assert st['firmware']=='g03-relay-r2' and st['actual_bits']==0 and st['faults']==0
print(json.dumps(dict(frozen=True,firmware=st['firmware'],state=st['state'],live_used=st['live_used'],actual_bits=st['actual_bits'],next='normal BOOT RESET, then verify new idle state; no output sent')))
