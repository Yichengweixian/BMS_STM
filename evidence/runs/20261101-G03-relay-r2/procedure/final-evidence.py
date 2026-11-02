import csv,datetime,hashlib,json,statistics,sys
from pathlib import Path
root=Path(r'D:\ADMIN\Desktop\WEIJI\zonghe')
run=root/'evidence/runs/20261101-G03-relay-r2'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,obj):
    with p.open('x',encoding='utf-8') as f:json.dump(obj,f,indent=2,ensure_ascii=False)
sys.path.insert(0,str(root/'scripts/g03'))
from relay_capture import Session,ok,parse,analyze
import serial
out=run/'final-status-01';out.mkdir(exist_ok=False)
link=serial.Serial();link.port='COM11';link.baudrate=115200;link.timeout=.05;link.write_timeout=1;link.dtr=link.rts=False
s=Session(link,out)
try:
    link.open();status=ok(s.request(30));save(out/'result.json',status)
finally:s.close()
assert status['firmware']=='g03-relay-r2' and status['state']==5 and status['live_used']==1 and status['actual_bits']==0 and status['faults']==0
save(out/'manifest.json',dict(mode='query_only',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),firmware_sha256=read(run/'conditions-ready.json')['firmware_sha256'],physical_valid=0))
sys.path.insert(0,str(root/'scripts/g01'))
from analyze_capture import analyze as g01_analyze
g01=g01_analyze(run/'g01-recovery-01');save(run/'g01-recovery-analysis.json',g01)
for name in ['board-rehearsal-01','live-01']:
    folder=run/name;r=read(folder/'result.json');rows=read(folder/'samples.json');st=r['final']
    # Independent reparse of the unmodified wire frames, with CRC and AFE PEC checks.
    wire=[parse(x) for x in (folder/'serial.bin').read_bytes().splitlines() if x.startswith((b'#G3R,',b'#G3S,'))]
    assert [x for x in wire if x['kind']=='#G3S']==rows
    assert analyze(st,rows)==r['analysis']
    assert len(rows)==st['written'] and all(x['seq']==i for i,x in enumerate(rows))
    derived=folder/'derived';derived.mkdir(exist_ok=False)
    channels={}
    for i,ch in enumerate(['cell1','cell7','cell13','afe_current','mcu_current']):
        samples=[x['samples'][i] for x in rows];base=[x['samples'][i]['raw'] for x in rows if x['phase']==2]
        pulse=[x['samples'][i]['raw'] for x in rows if x['phase']==3]
        post=[x['samples'][i]['raw'] for x in rows if x['phase']==4]
        dt=[(s['end_ms']-s['start_ms'])&0xffffffff for s in samples]
        gaps=[(b['start_ms']-a['start_ms'])&0xffffffff for a,b in zip(samples,samples[1:])]
        channels[ch]=dict(raw_valid=sum(s['raw_valid'] for s in samples),raw_min=min(s['raw'] for s in samples),raw_max=max(s['raw'] for s in samples),conversion_ms_min=min(dt),conversion_ms_max=max(dt),conversion_ms_mean=statistics.mean(dt),start_interval_ms_min=min(gaps),start_interval_ms_max=max(gaps),start_interval_ms_median=statistics.median(gaps),baseline_min=min(base),baseline_max=max(base),baseline_mean=statistics.mean(base),baseline_stddev_codes=statistics.pstdev(base),pulse_min=min(pulse),pulse_max=max(pulse),post_min=min(post),post_max=max(post))
    recovery=[x['samples'][3] for x in rows if x['phase']==4 and x['samples'][3]['raw_valid'] and abs(x['samples'][3]['raw']-st['center'])<=st['tolerance']]
    stats=dict(recomputed_analysis=r['analysis'],channels=channels,phase_counts={str(p):sum(x['phase']==p for x in rows) for p in [2,3,4]},bits_seen=sorted(set(x['bits'] for x in rows)),max_irq_gap_ms=st['irq_max_cycles']/st['cpu_hz']*1000,first_in_band_post_conversion_ms=[(recovery[0]['start_ms']-st['off_ms'])&0xffffffff,(recovery[0]['end_ms']-st['off_ms'])&0xffffffff],physical_valid=0)
    save(derived/'metrics.json',stats)
    events=[dict(event='command_window_start',tick_ms=st['on_ms'],dwt_cycles=st['on_cycles'],pg5_command=int(st['live'] and st['live_used']),source='MCU recorded GPIO command bracket; no contact measurement'),dict(event='command_window_stop',tick_ms=st['off_ms'],dwt_cycles=st['off_cycles'],pg5_command=0,reason=st['reason'],reason_name='deadline' if st['reason']==1 else 'other',faults=st['faults']),dict(event='terminal_snapshot',state=st['state'],actual_bits=st['actual_bits'],recover_count=st['recover_count'],live_used=st['live_used'])]
    save(derived/'gpio-stop-events.json',events)
    flat=[]
    for x in rows:
        for i,sm in enumerate(x['samples']):
            valid=sm['raw_valid'];v=sm['raw']*(0.0004395604191813618 if i==4 else .0001) if valid else None
            estimate=(v-.9)*1.3266666730244954 if valid and i>=3 else v
            flat.append(dict(seq=x['seq'],phase=x['phase'],channel=sm['channel'],start_ms=sm['start_ms'],end_ms=sm['end_ms'],raw=sm['raw'],raw_valid=valid,status=sm['status'],sensor_V_nominal=v,estimate_nominal=estimate,unit='A' if i>=3 else 'V',physical_value='',physical_valid=0,sign_verified=0,current_model='hex-dd44fae1-nominal-v1' if i>=3 else 'AFE-100uV-per-code-nominal'))
    with (derived/'nominal.csv').open('x',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
    save(derived/'manifest.json',dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),analysis_script_sha256=sha(Path(__file__)),input_hashes={x.name:sha(x) for x in [folder/'serial.bin',folder/'samples.json',folder/'result.json']},output_hashes={x.name:sha(x) for x in derived.iterdir()},nominal_note='Uncalibrated host double-precision evaluation of the documented nominal model; separate from raw and not measured physical current. No invalid value is replaced with zero.'))
    print(json.dumps(dict(run=name,metrics=stats),ensure_ascii=False))
print(json.dumps(dict(g01_rows=g01['rows'],complete_groups=g01['complete_groups'],events=g01['event_counts'],raw_valid=g01['all_recorded_raw_valid'],seq_gaps=sum(x['missing_sequences'] for x in g01['channels'].values()),duplicates=sum(x['duplicates'] for x in g01['channels'].values()),final_status=status),ensure_ascii=False))
