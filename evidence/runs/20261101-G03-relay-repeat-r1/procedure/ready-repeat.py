import argparse,datetime,hashlib,json,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('attempt',choices=['02','03']);p.add_argument('--check-suffix',default='');a=p.parse_args()
root=Path(r'D:\ADMIN\Desktop\WEIJI\zonghe');run=root/'evidence/runs/20261101-G03-relay-repeat-r1'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
profile=read(run/'conditions-frozen.json')
if a.attempt=='03':assert read(run/'repeat-02/result.json')['analysis']['conclusion']=='response_and_recovery'
assert not (run/('repeat-'+a.attempt)).exists(),'Attempt already exists; no replay'
sys.path.insert(0,str(root/'scripts/g03'))
from relay_capture import Session,ok
import serial
out=run/('pre-repeat-'+a.attempt+a.check_suffix);out.mkdir(exist_ok=False)
link=serial.Serial();link.port='COM11';link.baudrate=115200;link.timeout=.05;link.write_timeout=1;link.dtr=link.rts=False
s=Session(link,out)
try:
    link.open();st=ok(s.request(30));(out/'result.json').write_text(json.dumps(st,indent=2),encoding='utf-8')
except Exception as e:
    (out/'result.json').write_text(json.dumps(dict(error=repr(e),power_trigger_sent=False)),encoding='utf-8');raise
finally:s.close()
assert st['firmware']=='g03-relay-r2' and st['state']==0 and st['live_gate']==1 and st['live_used']==0 and st['actual_bits']==0 and st['faults']==0
profile.update(live_ready=True,attempt_id='repeat-'+a.attempt,normal_boot_reset_confirmed_by_user=a.attempt=='02',reset_method='explicit SWD software reset after confirmed previous recovery' if a.attempt=='03' else 'user reset then SWD software-reset recovery',ready_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),idle_status_sha256=hashlib.sha256((out/'result.json').read_bytes()).hexdigest())
with (run/('conditions-ready-'+a.attempt+'.json')).open('x',encoding='utf-8') as f:json.dump(profile,f,indent=2)
print(json.dumps(dict(attempt=a.attempt,ready=True,state=st['state'],output=st['actual_bits'],live_used=st['live_used'])))
