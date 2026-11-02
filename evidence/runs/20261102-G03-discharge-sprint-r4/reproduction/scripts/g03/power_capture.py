"""One fixed-D transaction. Query is default; never resets or retries a start."""
from pathlib import Path
import argparse,binascii,csv,datetime,hashlib,json,re,sys,time,statistics
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'g01'))
from g01_capture import pec15
FW='g03-power-points-r4'
PROFILE=0x50393301
POINTS={0x50393301:(1800,100000),0x50393302:(1600,100000),0x50393303:(1800,2000000),0x50393304:(1600,2000000)}
STATUS=('id result phase faults used owned live start_id profile ccr arr run_us rows bits restored '
        'pwm_on_us pwm_off_us relay_on_us relay_off_us max_irq_gap_us zero recovery_good power_capable physical_valid core_state').split()
ROW='id result seq phase begin_us end_us ccr arr bits adc_status adc_begin_us adc_end_us vb_raw vs_raw vl_raw'.split()
CHANNELS=['cell1','cell7','cell13','ibat_afe','temp1','temp2','temp3','ref2']
def require(ok,message):
    if not ok:raise ValueError(message)
def parse(line):
    body,crc=line.strip().rsplit(b'*',1)
    require(len(crc)==4 and binascii.crc_hqx(body,65535)==int(crc,16),'wire CRC')
    p=body.decode('ascii').split(',');require(p[1]==FW,'firmware identity')
    kind=p[0];require(kind in ('#G3Q','#G3L'),'report kind')
    fields=STATUS if kind=='#G3Q' else ROW
    require(len(p)==2+len(fields)+(48 if kind=='#G3L' else 0),'schema length')
    values=p[2:2+len(fields)]
    require(all(re.fullmatch(r'[0-9]+',x) and 0<=int(x)<=0xffffffff for x in values),'uint32 field')
    d=dict(zip(fields,map(int,values)));d['kind']=kind
    require(d['id']>0,'request id')
    if kind=='#G3Q':
        require(d['physical_valid']==0 and d['power_capable']==1,'calibration/capability')
        require(d['profile'] in POINTS and (d['ccr'],d['run_us'])==POINTS[d['profile']] and d['arr']==2000,'frozen point')
        require(d['phase']<=6 and d['core_state']<=4,'state')
    else:
        d['afe']=[]
        for i,ch in enumerate(CHANNELS):
            q=p[2+len(fields)+i*6:2+len(fields)+(i+1)*6]
            raw,start,end,status,hasraw=map(int,q[:5]);frame=bytes.fromhex(q[5])
            require(len(frame)==8 and 0<=raw<=65535 and hasraw in (0,1),'AFE fields')
            valid=hasraw==1 and not(status&383) and raw!=65535
            if valid:
                require(pec15(frame[:6])==int.from_bytes(frame[6:],'big'),'AFE PEC')
                index={4:1,5:2,7:2}.get(i,0)
                require(int.from_bytes(frame[2*index:2*index+2],'little')==raw,'AFE raw/frame')
            d['afe'].append(dict(channel=ch,raw=raw,start_ms=start,end_ms=end,status=status,raw_valid=valid,frame_hex=q[5]))
        require(max(d['vb_raw'],d['vs_raw'],d['vl_raw'])<=4095,'ADC2 range')
    return d
def frame(i,op,arg):
    b=f'G02,{i},{op},{arg}'.encode();return b+f'*{binascii.crc_hqx(b,65535):04X}\n'.encode()
class Session:
    def __init__(self,link,out):
        self.link=link;self.out=out;self.raw=(out/'serial.bin').open('xb');self.events=(out/'events.jsonl').open('x',encoding='utf-8')
        self.pending=b'';self.i=int(time.time()*1000)&0xffffffff;self.started=False;self.identified=False;self.last=None;self.reports=[]
    def send(self,op,arg=0):
        require(op in (40,41,42,43,45,49),'operation allowlist')
        if op in (41,49):
            require(self.identified and not self.started,'identify before single start')
            require(self.last['used']==self.last['owned']==self.last['faults']==self.last['phase']==self.last['bits']==0,'unused default-off')
            require(arg in POINTS,'point id');self.started=True
        self.i+=1;require(self.i<=0xffffffff,'id exhausted')
        wire=frame(self.i,op,arg);self.events.write(json.dumps(dict(monotonic=time.monotonic(),tx_attempt=wire.hex(),op=op,id=self.i))+'\n');self.events.flush()
        require(self.link.write(wire)==len(wire),'partial write; no replay');return self.i
    def receive(self,wanted,timeout=10,heartbeat=False):
        end=time.monotonic()+timeout;next_hb=time.monotonic()+.05
        while time.monotonic()<end:
            while b'\n' in self.pending:
                line,self.pending=self.pending.split(b'\n',1)
                if line.startswith(b'#BOOT,') and self.identified:raise RuntimeError('reset observed; no restart')
                if not line.startswith((b'#G3Q,',b'#G3L,')):continue
                d=parse(line);self.reports.append(d)
                self.events.write(json.dumps(dict(monotonic=time.monotonic(),report=d))+'\n');self.events.flush()
                if d['kind']=='#G3Q':self.last=d;self.identified=True
                if d['id']==wanted or (heartbeat and d['kind']=='#G3Q' and d['start_id']==wanted and d['phase']==6):return d
            if heartbeat and time.monotonic()>=next_hb:
                self.send(45);next_hb=time.monotonic()+.05
            data=self.link.read(max(1,min(self.link.in_waiting,4096)));self.raw.write(data);self.raw.flush();self.pending+=data
            require(len(self.pending)<8192,'oversize response')
        raise TimeoutError('No reply; start is never replayed')
    def request(self,op,arg=0):return self.receive(self.send(op,arg))
    def close(self):
        self.raw.close();self.events.close();self.link.close();(self.out/'reports.json').write_text(json.dumps(self.reports,indent=2),encoding='utf-8')
def derive(out,status,rows):
    require(len(rows)==status['rows'] and [x['seq'] for x in rows]==list(range(len(rows))),'capture completeness')
    records=[]
    for r in rows:
        a=r['afe'];valid=all(x['raw_valid'] for x in a[:4])
        record={k:v for k,v in r.items() if k not in ('afe','kind')}
        record.update(D_command=status['ccr']/status['arr'],D_register=r['ccr']/r['arr'],Vbat_nominal_V=sum(x['raw'] for x in a[:3])*.0001 if valid else '',
            Ibat_nominal_A=(a[3]['raw']-status['zero'])*.0001*1.3266666730244954 if valid and status['zero'] else '',
            Vload_measured_V='',Iload_measured_A='',Vload_model_V='',temperature_C='',physical_valid=0,
            sample_scope='transition' if r['begin_us']<status['pwm_off_us']<r['end_us'] else 'within_phase')
        for x in a:
            for k in ('raw','status','raw_valid','start_ms','end_ms','frame_hex'):record[x['channel']+'_'+k]=x[k]
        records.append(record)
    if records:
        with (out/'points.csv').open('x',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    events=[dict(event=n,us=status[k]) for n,k in [('relay_on','relay_on_us'),('pwm_on','pwm_on_us'),('pwm_off','pwm_off_us'),('relay_off','relay_off_us')]]
    with (out/'stop-events.csv').open('x',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=['event','us']);w.writeheader();w.writerows(events)
    active=[r for r in records if r['phase']==3 and r['sample_scope']=='within_phase' and r['Ibat_nominal_A']!='']
    passive=[r for r in records if r['phase']==2 and r['Ibat_nominal_A']!='']
    delta=(statistics.median(r['Ibat_nominal_A'] for r in active)-statistics.median(r['Ibat_nominal_A'] for r in passive)) if active and passive else None
    pwm_started=bool(status['pwm_on_us'])
    elapsed=(status['pwm_off_us']-status['pwm_on_us'])&0xffffffff
    coast=(status['relay_off_us']-status['pwm_off_us'])&0xffffffff
    timing_ok=pwm_started and status['run_us']-1000<=elapsed<=status['run_us']+500 and (not status['live'] or 20000<=coast<=20500)
    response=bool(active and delta is not None and delta<-.010 and statistics.median(r['Ibat_nominal_A'] for r in active)<-.050)
    return dict(samples=len(rows),active_complete_samples=len(active),
        stopped=status['bits']==0 and status['owned']==0 and status['restored']==1,
        software_pwm_us=elapsed if pwm_started else None,relay_hold_after_pwm_us=coast if status['live'] and pwm_started else None,timing_sequence_ok=timing_ok,
        pwm_increment_Ibat_nominal_A=delta,load_response_observed=response if status['live'] else None,
        actual_ccr_arr_constant=all(r['ccr']==status['ccr'] and r['arr']==status['arr'] for r in rows),
        real_power_command_sent=bool(status['live']),actual_pwm_started=pwm_started,faults=status['faults'],physical_valid=0,steady_state_claim=False)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',default='COM11');p.add_argument('--out',type=Path,required=True)
    p.add_argument('--mode',choices=['query','dry','live','read'],default='query');p.add_argument('--contract',type=Path)
    p.add_argument('--image',type=Path,required=True);p.add_argument('--sha256',required=True);p.add_argument('--profile',type=lambda x:int(x,0),default=PROFILE,choices=list(POINTS));a=p.parse_args()
    require(hashlib.sha256(a.image.read_bytes()).hexdigest()==a.sha256,'image hash')
    if a.mode=='live':
        require(a.contract is not None,'frozen source contract required');c=json.loads(a.contract.read_text(encoding='utf-8-sig'))
        for key in ('source_wiring_confirmed','source_settings_confirmed','source_cv_confirmed','no_real_cells','load_connected','charge_port_open','new_image_default_off_verified','dry_run_passed','source_paths_reviewed'):
            require(c.get(key) is True,'unconfirmed '+key)
        require(c['firmware_sha256']==a.sha256 and c['profile']==a.profile,'contract identity')
    a.out.mkdir(parents=True,exist_ok=False)
    manifest=dict(firmware=FW,image_sha256=a.sha256,mode=a.mode,profile=a.profile,physical_valid=0,created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),start_retries=0)
    if a.contract:manifest['contract_sha256']=hashlib.sha256(a.contract.read_bytes()).hexdigest()
    (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    import serial
    link=serial.Serial(port=None,baudrate=115200,timeout=.05,write_timeout=2);link.dtr=False;link.rts=False;link.port=a.port
    s=Session(link,a.out);result={}
    try:
        link.open();status=s.request(40);require(status['result']==0,'status failure')
        if a.mode in ('dry','live'):
            start=s.send(49 if a.mode=='live' else 41,a.profile)
            status=s.receive(start,heartbeat=POINTS[a.profile][1]>100000)
            require(status['result']==0 and status['start_id']==start and status['profile']==a.profile,'start not confirmed')
        if a.mode!='query':
            require(status['phase']==6 and status['used']==1 and status['owned']==0 and status['bits']==0,'not stopped/restored')
            rows=[s.request(42,i) for i in range(status['rows'])];require(all(x['result']==0 for x in rows),'record read failure')
            result=derive(a.out,status,rows)
            good=not status['faults'] and result['stopped'] and result['timing_sequence_ok'] and result['actual_ccr_arr_constant']
            if status['live']:good=good and result['load_response_observed']
            result['verdict']='pass' if good else 'fail'
        else:result=dict(verdict='pass',status=status,scope='identity/status only')
    except Exception as e:
        result.update(verdict='fail',error=repr(e))
        if s.started:
            try:result['stop_reply']=s.request(43)
            except Exception as stop:result['stop_uncertain']=repr(stop)
    finally:
        s.close();(a.out/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2));return int(result['verdict']!='pass')
if __name__=='__main__':raise SystemExit(main())
