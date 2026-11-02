import csv,datetime,hashlib,json,sys
from pathlib import Path
root=Path(r'D:\ADMIN\Desktop\WEIJI\zonghe');run=root/'evidence/runs/20261101-G03-relay-repeat-r1'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):
    with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2)
sys.path.insert(0,str(root/'scripts/g03'))
from relay_capture import Session,ok
import serial
out=run/'final-status';out.mkdir(exist_ok=False)
link=serial.Serial();link.port='COM11';link.baudrate=115200;link.timeout=.05;link.write_timeout=1;link.dtr=link.rts=False
s=Session(link,out)
try:
    link.open();st=ok(s.request(30));save(out/'result.json',st)
finally:s.close()
assert st['firmware']=='g03-relay-r2' and st['state']==5 and st['live_used']==1 and st['actual_bits']==st['faults']==0
save(out/'manifest.json',dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),operation='query only',firmware_sha256=read(run/'conditions-frozen.json')['firmware_sha256'],files={p.name:sha(p) for p in out.iterdir()}))
if not (run/'pre-repeat-02/result.json').exists():save(run/'pre-repeat-02/result.json',dict(error='TimeoutError: no status response in 8 seconds',record_type='posthoc diagnostic from preserved empty serial.bin and single op30 event',real_trigger_sent=False))
for name in ['repeat-02','repeat-03']:
    d=run/name;result=read(d/'result.json');status=result['final'];rows=read(d/'samples.json');out=d/'derived';out.mkdir(exist_ok=False)
    save(out/'gpio-stop-events.json',[dict(event='PG5_command_high',at_ms=status['on_ms'],dwt_cycles=status['on_cycles'],request_id=status['id'],scope='GPIO command bracket; no contact measurement'),dict(event='PG5_command_low',at_ms=status['off_ms'],dwt_cycles=status['off_cycles'],reason=status['reason'],faults=status['faults'],command_ms=result['analysis']['command_high_ms']),dict(event='terminal',state=status['state'],actual_bits=status['actual_bits'],recover_count=status['recover_count'],live_used=status['live_used'])])
    flat=[]
    for row in rows:
        for i,sample in enumerate(row['samples']):
            valid=sample['raw_valid'];v=sample['raw']*(.0004395604191813618 if i==4 else .0001) if valid else None
            est=(v-.9)*1.3266666730244954 if valid and i>=3 else v
            flat.append(dict(seq=row['seq'],phase=row['phase'],channel=sample['channel'],start_ms=sample['start_ms'],end_ms=sample['end_ms'],raw=sample['raw'],raw_valid=valid,status=sample['status'],sensor_V_nominal=v,estimate_nominal=est,unit='A' if i>=3 else 'V',physical_value='',physical_valid=0,sign_verified=0))
    with (out/'nominal.csv').open('x',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
    save(out/'manifest.json',dict(inputs={n:sha(d/n) for n in ['result.json','samples.json','serial.bin']},files={p.name:sha(p) for p in out.iterdir()},analysis_script_sha256=sha(Path(__file__)),nominal_model='hex-dd44fae1-nominal-v1, host double precision; not calibrated physical values'))
print(json.dumps(dict(final_state=st['state'],actual_bits=st['actual_bits'],faults=st['faults'],live_used=st['live_used'],new_runs=2)))
