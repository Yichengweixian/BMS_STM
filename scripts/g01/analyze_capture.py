"""Summarize an existing G01 capture without modifying raw files or calibration."""
import argparse,csv,json,statistics
from collections import Counter,defaultdict
from pathlib import Path
CHANNELS=['cell1','cell7','cell13','current_afe_gpio1','temperature_gpio2',
          'temperature_gpio3','temperature_gpio4','current_mcu_adc1','afe_vref2']
def analyze(folder):
    folder=Path(folder)
    manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    with (folder/'derived/device.csv').open(newline='',encoding='utf-8') as f: rows=list(csv.DictReader(f))
    events=[json.loads(x) for x in (folder/'raw/events.jsonl').read_text(encoding='utf-8').splitlines() if x]
    grouped=defaultdict(list); cycles=defaultdict(set)
    for r in rows:
        grouped[r['channel']].append(r)
        cycles[(r['boot_id'],int(r['seq']))].add(r['channel'])
    stats={}
    for ch in CHANNELS:
        data=grouped[ch];raw=[int(r['raw']) for r in data if r['raw']]
        valid=[int(r['raw']) for r in data if r['raw_valid']=='1']
        dt=[];seq_gaps=[];duplicates=0
        for before,after in zip(data,data[1:]):
            if before['boot_id']!=after['boot_id']:continue
            step=(int(after['seq'])-int(before['seq']))&0xffffffff
            if step==0:duplicates+=1
            if 1<step<0x80000000:seq_gaps.append(step-1)
            delta=(int(after['end_ms'])-int(before['end_ms']))&0xffffffff
            if delta<0x80000000:dt.append(delta)
        stats[ch]=dict(records=len(data),raw_valid=len(valid),raw_invalid=len(data)-len(valid),
            status_counts=dict(Counter(r['status'] for r in data)),
            raw_min=min(raw) if raw else None,raw_max=max(raw) if raw else None,
            valid_raw_mean=statistics.mean(valid) if valid else None,
            period_ms_median=statistics.median(dt) if dt else None,period_ms_max=max(dt) if dt else None,
            missing_sequences=sum(seq_gaps),duplicates=duplicates)
    incomplete=[dict(boot_id=b,seq=s,missing=sorted(set(CHANNELS)-channels)) for (b,s),channels in cycles.items() if len(channels)!=9]
    result=dict(source_capture=str(folder),evidence_scope=manifest['evidence_scope'],simulated=manifest['simulated'],
        firmware_sha256=manifest['firmware_sha256'],metadata=manifest['metadata'],rows=len(rows),
        boot_segments=sorted(set(r['boot_id'] for r in rows)),complete_groups=sum(len(ch)==9 for ch in cycles.values()),
        incomplete_groups=incomplete,event_counts=dict(Counter(e['event'] for e in events)),channels=stats,
        all_nine_channels_present=all(stats[ch]['records']>0 for ch in CHANNELS),
        all_recorded_raw_valid=bool(rows) and all(r['raw_valid']=='1' for r in rows),
        formal_G01_verdict=None,calibration_verified=False,
        note='Capture edges may have incomplete groups. Inspect events; stable raw is not calibrated accuracy.')
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('capture');p.add_argument('--out',required=True)
    a=p.parse_args();result=analyze(a.capture)
    with Path(a.out).open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,ensure_ascii=False)
    print(json.dumps(result,ensure_ascii=False,indent=2))
