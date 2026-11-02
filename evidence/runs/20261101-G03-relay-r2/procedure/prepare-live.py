import hashlib,json,sys,datetime
from pathlib import Path
root=Path(r'D:\ADMIN\Desktop\WEIJI\zonghe')
run=root/'evidence/runs/20261101-G03-relay-r2'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
p=read(run/'conditions-frozen.json');r=read(run/'board-rehearsal-01/result.json');rows=read(run/'board-rehearsal-01/samples.json')
flash=next(run.glob('flash-romboot-*/result.json'));f=read(flash)
assert f['verified'] and f['sha256']==p['firmware_sha256']
assert sha(run/'firmware/BMS_EX_Release/BMS_EX_Release.hex')==p['firmware_sha256']
assert r['verdict']=='pass' and r['analysis']['observation_ready']
assert r['initial']['firmware']==r['final']['firmware']=='g03-relay-r2'
assert r['initial']['state']==0 and r['final']['state']==5
assert r['final']['live']==0 and r['final']['live_gate']==1 and r['final']['live_used']==0
assert r['final']['actual_bits']==r['final']['faults']==0 and len(rows)==102
assert all(x['bits']==0 and all(s['raw_valid'] and s['status']&~128==0 for s in x['samples']) for x in rows)
assert all(p['cell_code_low']<=s['raw']<=p['cell_code_high'] for x in rows for s in x['samples'][:3])
assert p['afe_baseline_code_low']<=r['analysis']['baseline_min']<=r['analysis']['baseline_max']<=p['afe_baseline_code_high']
evidence=[flash,run/'conditions-frozen.json',run/'board-rehearsal-01/result.json',run/'board-rehearsal-01/samples.json']
p.update(live_ready=True,pending=[],ready_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),normal_boot_confirmed_by_user=True,ready_evidence={str(x.relative_to(root)):sha(x) for x in evidence})
with (run/'conditions-ready.json').open('x',encoding='utf-8') as out:json.dump(p,out,indent=2)
print(json.dumps(dict(live_ready=True,baseline=[r['analysis']['baseline_min'],r['analysis']['baseline_max']],cells=[[min(x['samples'][i]['raw'] for x in rows),max(x['samples'][i]['raw'] for x in rows)] for i in range(3)],window_ms=r['analysis']['software_window_ms']),indent=2))
# Explicit terminal clear after records were safely saved. Never starts a capture.
sys.path.insert(0,str(root/'scripts/g03'))
from relay_capture import Session,ok
import serial
out=run/'pre-live-clear-01';out.mkdir(exist_ok=False)
link=serial.Serial();link.port='COM11';link.baudrate=115200;link.timeout=.05;link.write_timeout=1;link.dtr=link.rts=False
s=Session(link,out);result={}
try:
    link.open();before=ok(s.request(30));result['before']=before;s.identified=True
    assert before['state']==5 and before['live_used']==0 and before['actual_bits']==0 and not before['faults']
    cleared=ok(s.request(35));result['cleared']=cleared
    assert cleared['state']==0 and not cleared['actual_bits'] and not cleared['live_used']
finally:
    s.close();(out/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(dict(cleared=True,actual_bits=cleared['actual_bits'],live_used=cleared['live_used'])))
