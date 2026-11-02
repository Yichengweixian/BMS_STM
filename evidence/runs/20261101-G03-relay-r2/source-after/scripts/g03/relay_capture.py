"""Single relay capture. Default is disabled rehearsal; never retries a start."""
import argparse,binascii,csv,hashlib,json,re,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'g02'))
from host_diagnostics import frame
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'g01'))
from g01_capture import pec15
STATUS='id result state faults reason live written base_count center tolerance on_ms off_ms recover_count actual_bits on_cycles off_cycles irq_max_cycles cpu_hz live_gate live_used period_ms stale_ms physical_valid'.split()
CHANNELS=['cell1','cell7','cell13','afe_current','mcu_current']
def parse(line):
    body,crc=line.rstrip(b'\r\n').rsplit(b'*',1)
    if not re.fullmatch(b'[0-9A-F]{4}',crc) or int(crc,16)!=binascii.crc_hqx(body,65535):raise ValueError('CRC')
    parts=body.decode('ascii').split(',');kind,firmware=parts[:2];v=parts[2:]
    if firmware not in ('g03-relay-r1','g03-relay-r2'):raise ValueError('Firmware identity')
    def num(s):
        if not re.fullmatch('[0-9]+',s) or int(s)>0xffffffff:raise ValueError('uint32')
        return int(s)
    if kind=='#G3R':
        if len(v)!=len(STATUS):raise ValueError('Status length')
        r=dict(zip(STATUS,map(num,v)))
        if r['physical_valid'] or r['actual_bits']&~16:raise ValueError('Output/quality invariant')
    elif kind=='#G3S':
        if len(v)!=37:raise ValueError('Sample length')
        r=dict(zip('id result seq phase at_ms done_ms bits'.split(),map(num,v[:7])))
        r['samples']=[]
        for i,ch in enumerate(CHANNELS):
            a=v[7+6*i:13+6*i]
            s=dict(zip('start_ms end_ms raw status raw_valid'.split(),map(num,a[:5])))
            if not re.fullmatch('[0-9A-F]{16}',a[5]):raise ValueError('Raw frame')
            if s['raw_valid'] not in (0,1) or s['raw']>65535 or (s['raw_valid'] and s['status']&~128):raise ValueError('Sample validity')
            if i<4 and s['raw_valid']:
                f=bytes.fromhex(a[5])
                if pec15(f[:6])!=int.from_bytes(f[6:],'big') or int.from_bytes(f[:2],'little')!=s['raw']:raise ValueError('AFE PEC/raw mismatch')
            s.update(channel=ch,frame_hex=a[5]);r['samples'].append(s)
    else:raise ValueError('Schema')
    r.update(kind=kind,firmware=firmware);return r
class Session:
    def __init__(self,link,out):
        self.link=link;self.out=out;self.pending=b'';self.counter=int(time.time()*1000)&0xffffffff;self.identified=False
        self.raw=(out/'serial.bin').open('xb');self.events=(out/'events.jsonl').open('x',encoding='utf-8')
    def event(self,**kw):self.events.write(json.dumps(dict(host_monotonic=time.monotonic(),**kw))+'\n');self.events.flush()
    def request(self,op,arg=0,timeout=8):
        if not 30<=op<=36:raise ValueError('Relay command only')
        self.counter+=1;wire=frame(self.counter,op,arg);self.event(tx_hex=wire.hex(),op=op)
        if self.link.write(wire)!=len(wire):raise IOError('Short request; do not replay')
        until=time.monotonic()+timeout
        while time.monotonic()<until:
            data=self.link.read(max(1,min(self.link.in_waiting,4096)));self.raw.write(data);self.pending+=data
            while b'\n' in self.pending:
                line,self.pending=self.pending.split(b'\n',1)
                if line.startswith(b'#BOOT,') and self.identified:raise RuntimeError('Reset detected; no restart')
                if not line.startswith((b'#G3R,',b'#G3S,')):continue
                r=parse(line);self.event(report=r)
                if r['id']==self.counter:return r
            if len(self.pending)>4096:raise RuntimeError('Unterminated report')
        raise TimeoutError('No response; command will not be replayed')
    def close(self):self.raw.close();self.events.close();self.link.close()
def ok(r):
    if r['result']:raise RuntimeError('Command rejected: '+str(r))
    return r
def analyze(status,rows):
    window=[];latencies=[];starts=[];base=[];post=[]
    for row in rows:
        req=row['samples'][:4];latencies.append((row['done_ms']-row['at_ms'])&0xffffffff);starts.append(row['at_ms'])
        valid=all(s['raw_valid'] for s in req)
        if row['phase']==2 and valid:base.append(req[3]['raw'])
        if row['phase']==3 and valid and all(((s['start_ms']-status['on_ms'])&0xffffffff)<=100 and ((status['off_ms']-s['end_ms'])&0xffffffff)<=100 for s in req):window.append(req[3]['raw'])
        if row['phase']==4 and valid:post.append(req[3]['raw'])
    response=[x-status['center'] for x in window if abs(x-status['center'])>status['tolerance']]
    coherent=len(response)>=3 and (all(x>0 for x in response) or all(x<0 for x in response))
    recovered=len(post)>=5 and all(abs(x-status['center'])<=status['tolerance'] for x in post[-5:])
    width=((status['off_cycles']-status['on_cycles'])&0xffffffff)*1000/status['cpu_hz'] if status['on_cycles'] else None
    if not status['live']:conclusion='disabled_rehearsal_only'
    elif status['faults']:conclusion='aborted'
    elif len(window)<3:conclusion='insufficient_observation'
    elif coherent and recovered:conclusion='response_and_recovery'
    elif not recovered:conclusion='not_recovered'
    else:conclusion='no_clear_response'
    return dict(conclusion=conclusion,valid_window_samples=len(window),response_codes=response,recovered=recovered,
        capture_max_ms=max(latencies,default=None),start_gap_max_ms=max(((b-a)&0xffffffff for a,b in zip(starts,starts[1:])),default=None),
        baseline_min=min(base,default=None),baseline_max=max(base,default=None),software_window_ms=width,command_high_ms=width if status['live'] else None,
        observation_ready=not status['faults'] and status['state']==5 and len(window)>=3 and recovered and max(latencies,default=999)<=20 and width is not None and 0<width<=100,
        physical_current_calibrated=False)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',required=True);p.add_argument('--out',required=True)
    p.add_argument('--live',action='store_true');p.add_argument('--profile');p.add_argument('--firmware-sha256',required=True);a=p.parse_args()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=False)
    import serial
    link=serial.Serial();link.port=a.port;link.baudrate=115200;link.timeout=.05;link.write_timeout=1;link.dtr=link.rts=False
    s=Session(link,out);result=dict(evidence_scope=['bench'],mode='live' if a.live else 'disabled',trigger_sent=False,verdict=None)
    rows=[];status=None
    try:
        link.open();status=ok(s.request(30));s.identified=True;result['initial']=status
        if status['state']!=0 or status['actual_bits']:raise RuntimeError('Require explicit idle state; no automatic clear')
        if a.live:
            if not a.profile:raise RuntimeError('Frozen profile required')
            profile=json.loads(Path(a.profile).read_text(encoding='utf-8'))
            if not profile.get('live_ready') or profile.get('firmware_sha256')!=a.firmware_sha256 or not profile.get('battery_disconnect_confirmed'):raise RuntimeError('Profile not ready or identity mismatch')
            if not status['live_gate'] or status['live_used']:raise RuntimeError('Live firmware gate closed or pulse consumed')
            result['profile']=profile
        result['trigger_sent']=True
        status=ok(s.request(32 if a.live else 31));result['final']=status
        if status['state'] not in (5,6):raise RuntimeError('Capture did not reach latched terminal state')
        # Alert before the potentially slow record dump, never after it.
        if a.live and (status['recover_count']<5 or status['faults']):
            print('恢复未确认或检测到异常：请立即按预定方式断开电池侧供能。',flush=True)
        for i in range(status['written']):rows.append(ok(s.request(36,i)))
        if [r['seq'] for r in rows]!=list(range(status['written'])):raise RuntimeError('Capture sequence gap')
        result['analysis']=analyze(status,rows)
        result['verdict']='pass' if not a.live and result['analysis']['observation_ready'] else ('inconclusive' if not status['faults'] else 'fail')
        if a.live and not result['analysis']['recovered']:print('电流未确认恢复：请立即按预定方式断开电池侧供能。',flush=True)
        if status['actual_bits']:raise RuntimeError('Output command still active')
    except Exception as e:
        result['error']=repr(e)
        if s.identified:
            try:result['stop_after_error']=s.request(34)
            except Exception as stop:result['stop_error']=repr(stop)
        if a.live and result['trigger_sent']:print('运行结果未确认：请检查并按预定方式断开电池侧供能。',flush=True)
    finally:
        s.close();(out/'samples.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
        flat=[dict(seq=r['seq'],phase=r['phase'],at_ms=r['at_ms'],done_ms=r['done_ms'],bits=r['bits'],**s) for r in rows for s in r['samples']]
        if flat:
            with (out/'samples.csv').open('x',newline='',encoding='utf-8') as f:
                w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
        result['sha256']={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in out.iterdir() if x.is_file()}
        (out/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        (out/'manifest.json').write_text(json.dumps(dict(run_id=out.name,firmware_sha256=a.firmware_sha256,mode=result['mode'],physical_valid=0),indent=2))
        print(json.dumps(result,indent=2))
    return 0 if 'error' not in result else 1
if __name__=='__main__':raise SystemExit(main())
