"""Compare independent captured relay runs. Offline only; never opens a port."""
import argparse,csv,hashlib,json,statistics,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/g03'))
from relay_capture import analyze,parse
RULES=['firmware_sha256','cell_code_low','cell_code_high','afe_baseline_code_low','afe_baseline_code_high','baseline_samples','baseline_peak_to_peak_max_codes','response_band_rule','sample_period_ms','required_sample_max_age_ms','command_deadline_ms','command_high_acceptance_max_ms','post_observation_ms','valid_window_min_complete_samples','recovery_consecutive_samples','wiring']
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def summarize(folder):
    folder=Path(folder);r=read(folder/'result.json');rows=read(folder/'samples.json');m=read(folder/'manifest.json');st=r['final']
    if r.get('error') or not r.get('trigger_sent') or r['mode']!='live' or st['live']!=1 or st['live_used']!=1:raise ValueError('Not a completed real command: '+str(folder))
    if m['firmware_sha256']!=r['profile']['firmware_sha256']:raise ValueError('Firmware manifest/profile mismatch')
    if any(x['firmware']!=st['firmware'] or x['bits']&~16 for x in rows):raise ValueError('Firmware/output invariant')
    for filename,digest in r['sha256'].items():
        if sha(folder/filename)!=digest:raise ValueError('Modified raw data: '+filename)
    wire=[parse(x) for x in (folder/'serial.bin').read_bytes().splitlines() if x.startswith((b'#G3R,',b'#G3S,'))]
    if [x for x in wire if x['kind']=='#G3S']!=rows:raise ValueError('Wire/rows mismatch')
    if [x['seq'] for x in rows]!=list(range(st['written'])):raise ValueError('Missing sample sequence')
    a=analyze(st,rows);complete=[]
    for x in rows:
        if x['phase']==3 and all(s['raw_valid'] and ((s['start_ms']-st['on_ms'])&0xffffffff)<=100 and ((st['off_ms']-s['end_ms'])&0xffffffff)<=100 for s in x['samples'][:4]):complete.append(x)
    channels={}
    for i,ch in enumerate(['cell1','cell7','cell13','afe_current','mcu_current']):
        base=[x['samples'][i]['raw'] for x in rows if x['phase']==2 and x['samples'][i]['raw_valid']]
        pulse=[x['samples'][i]['raw'] for x in complete if x['samples'][i]['raw_valid']]
        post=[x['samples'][i]['raw'] for x in rows if x['phase']==4 and x['samples'][i]['raw_valid']]
        channels[ch]=dict(baseline_n=len(base),baseline_median=statistics.median(base) if base else None,baseline_min=min(base,default=None),baseline_max=max(base,default=None),window_n=len(pulse),window_mean=statistics.mean(pulse) if pulse else None,window_median=statistics.median(pulse) if pulse else None,delta_median=statistics.median(pulse)-statistics.median(base) if pulse and base else None,last5_median=statistics.median(post[-5:]) if len(post)>=5 else None)
    tx=[json.loads(x) for x in (folder/'events.jsonl').read_text(encoding='utf-8').splitlines()]
    if sum(x.get('op')==32 for x in tx)!=1:raise ValueError('Must contain exactly one live request')
    return dict(path=str(folder.resolve()),request_id=st['id'],firmware_sha256=m['firmware_sha256'],rules={k:r['profile'][k] for k in RULES},analysis=a,channels=channels,actual_bits_final=st['actual_bits'],faults=st['faults'],physical_valid=0,input_hashes={n:sha(folder/n) for n in ['result.json','samples.json','serial.bin','events.jsonl','manifest.json']})
def compare(folders):
    if len({str(Path(x).resolve()) for x in folders})!=len(folders):raise ValueError('Duplicate run directory')
    runs=[summarize(x) for x in folders]
    if not runs:raise ValueError('No runs')
    if any(r['rules']!=runs[0]['rules'] for r in runs):raise ValueError('Frozen conditions differ; no pooled repeatability conclusion')
    if len({r['request_id'] for r in runs})!=len(runs):raise ValueError('Repeated request ID is not an independent run')
    values=[r['channels']['afe_current']['delta_median'] for r in runs]
    values=[x for x in values if x is not None]
    all_response=all(r['analysis']['conclusion']=='response_and_recovery' and r['analysis']['observation_ready'] and r['actual_bits_final']==0 and r['faults']==0 for r in runs)
    return dict(status='complete' if len(runs)>=3 else 'in_progress',verdict=('pass' if all_response else 'fail') if len(runs)>=3 else None,scope='same-condition response direction and recovery only; magnitude spread descriptive',runs=runs,run_count=len(runs),all_response_and_recovery=all_response,afe_delta_median_codes=values,afe_delta_spread_codes=max(values)-min(values) if values else None,afe_delta_mean_codes=statistics.mean(values) if values else None,physical_valid=0,formal_G03_verdict=None)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('runs',nargs='+');p.add_argument('--out',required=True);a=p.parse_args()
    r=compare(a.runs);out=Path(a.out);out.mkdir(parents=True,exist_ok=False)
    (out/'comparison.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
    rows=[dict(run=Path(x['path']).name,request_id=x['request_id'],command_ms=x['analysis']['command_high_ms'],valid_window=x['analysis']['valid_window_samples'],recovered=x['analysis']['recovered'],channel=ch,**data) for x in r['runs'] for ch,data in x['channels'].items()]
    with (out/'comparison.csv').open('x',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    (out/'manifest.json').write_text(json.dumps(dict(analysis_script_sha256=sha(Path(__file__)),input_runs=[x['input_hashes'] for x in r['runs']],outputs={n:sha(out/n) for n in ['comparison.json','comparison.csv']}),indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in r.items() if k!='runs'},indent=2))
if __name__=='__main__':main()
