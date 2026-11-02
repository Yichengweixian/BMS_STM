"""Disabled real ADC diagnostic, shadow scan and watchdog-window exercise.
No command in this tool can enable PWM/relays. Thresholds are test values.
"""
import argparse,binascii,csv,hashlib,json,re,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'g02'))
from host_diagnostics import frame
from extended_diagnostics import Session as BaseSession,require
STATUS=('id result ua state faults configured profile selfcal count raw zero_mcode limit_ma low high ccr step '
        'written overwritten probe owns_adc actual_bits power_capable physical_valid hw_low hw_high trip_ms '
        'trip_cycles off_cycles cfgr1 cfgr2 calfact reason start_ms last_ms heartbeat_ms duration_ms').split()
TRACE='id result seq ms cycles raw ua ccr event faults'.split()
DIAG='id result profile selfcal count minimum maximum sum'.split()
REGS='cfgr1 cfgr2 calfact difsel gcomp ofr1 sqr1 smpr1 pcsel cr common_ccr gpioa_moder'.split()
def parse(line):
    body,crc=line.rstrip(b'\r\n').rsplit(b'*',1)
    if not re.fullmatch(b'[0-9A-F]{4}',crc) or int(crc,16)!=binascii.crc_hqx(body,65535):raise ValueError('CRC')
    v=body.decode('ascii').split(',');kind=v[0]
    if v[1] not in ('g03-adc-r4','g03-relay-r1','g03-relay-r2') or kind not in ('#G3A','#G3D','#G3T'):raise ValueError('Identity/schema')
    if any(not re.fullmatch('-?[0-9]+',x) or not -2147483648<=int(x)<=0xffffffff for x in v[2:]):raise ValueError('Range')
    nums=list(map(int,v[2:]));fields={'#G3A':STATUS,'#G3T':TRACE,'#G3D':DIAG+REGS}[kind]
    if kind!='#G3D' and len(nums)!=len(fields):raise ValueError('Length')
    if kind=='#G3D' and (len(nums)<len(fields) or nums[4] not in (0,64) or len(nums)!=len(fields)+nums[4]):raise ValueError('Diagnostic length')
    r=dict(zip(fields,nums));r['kind']=kind
    if any(r[k]<0 for k in fields if k!='ua'):raise ValueError('Unsigned field')
    if kind=='#G3D':
        r['samples']=nums[len(fields):]
        if r['count'] and (any(not 0<=x<=4095 for x in r['samples']) or
                min(r['samples'])!=r['minimum'] or max(r['samples'])!=r['maximum'] or sum(r['samples'])!=r['sum']):raise ValueError('Diagnostic aggregate mismatch')
    return r
class Session(BaseSession):
    def send(self,op,arg=0):
        require(20<=op<=29,'Only disabled ADC commands')
        require(self.counter<0xffffffff,'ID exhausted')
        self.counter+=1;self.write(frame(self.counter,op,arg));return self.counter
    def receive(self,wanted,timeout=3):
        end=time.monotonic()+timeout
        while True:
            while b'\n' in self.pending:
                line,self.pending=self.pending.split(b'\n',1)
                if line.startswith(b'#BOOT,') and self.identified:raise RuntimeError('Reboot; no replay')
                if not line.startswith((b'#G3A,',b'#G3D,',b'#G3T,')):continue
                r=parse(line);self.reports.append(r);self.event(report=r)
                if r['kind']=='#G3A':require((r['actual_bits'],r['power_capable'],r['physical_valid'])==(0,0,0),'Output/calibration invariant')
                if r['id']==wanted:return r
            require(len(self.pending)<=4096,'Unterminated report')
            if time.monotonic()>=end:raise TimeoutError('ADC report timeout; no automatic replay')
            data=self.link.read(max(1,min(self.link.in_waiting,4096)));self.raw.write(data);self.pending+=data
    def finish(self):
        if self.link.is_open:self.link.close()
        self.raw.close();self.events.close()
        (self.out/'reports.json').write_text(json.dumps(self.reports,indent=2))
def ok(r,code=0):require(r['result']==code,'Command failed '+str(r));return r
def dump(s,out,label):
    r=ok(s.request(20));require(r['state']!=1 and r['owns_adc']==0,'Trace must be stable')
    rows=[ok(s.request(28,i)) for i in range(r['overwritten'],r['written'])]
    with (out/(label+'-trace.csv')).open('x',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=TRACE,extrasaction='ignore');w.writeheader();w.writerows(rows)
    require([x['seq'] for x in rows]==list(range(r['overwritten'],r['written'])),'Trace gap')
    return r,rows
def suite(s,result):
    r=ok(s.request(20));require(r['state']==0 and not r['owns_adc'],'Require idle initial board')
    s.identified=True
    profiles=[ok(s.request(21,i)) for i in range(6)]
    result['diagnostics']=profiles
    for p in profiles:require(p['count']==64,'No diagnostic raw samples')
    means=[x['sum']/64 for x in profiles]
    result['adc_comparison']={'means':means,'os2_to_osoff_before_cal':means[0]/means[1],
        'selfcal_change_codes':means[2]-means[1],'os2_to_osoff_after_cal':means[3]/means[2],
        'calibration_executed':profiles[-1]['selfcal']==1,
        'note':'Compare within one boot; selfcal state reveals whether first pair was already calibrated. No external reference.'}
    require(profiles[-1]['selfcal']==1,'Internal self-calibration failed')
    result['stable_tail']=[dict(profile=p['profile'],minimum=min(p['samples'][16:]),maximum=max(p['samples'][16:]),mean=sum(p['samples'][16:])/48) for p in profiles]
    ok(s.request(22));before=ok(s.request(20));ok(s.request(23,2000),1)
    require(ok(s.request(20))['limit_ma']==before['limit_ma'],'Rejected threshold mutated config')
    result['checks'].append('six-profiles-stable-tail-and-rail-threshold-rejection')
    ok(s.request(24,1000))
    for _ in range(5):time.sleep(.12);ok(s.request(25))
    time.sleep(.4);r,rows=dump(s,s.out,'scan')
    require(r['state']==0 and r['reason']==1 and r['count']>0 and not r['faults'],'Scan did not complete')
    require({x['ccr'] for x in rows if x['event'] in (1,3)}=={1800,1700,1600,1500,1400},'Missing shadow points')
    require(r['overwritten']==0,'Scan trace overwritten')
    result['scan_preflight']=ok(s.request(21,6))
    result['checks'].append('five-shadow-points-real-ADC-local-duration-trace')
    for side in (1,2):
        ok(s.request(27));ok(s.request(21,5));ok(s.request(22));ok(s.request(29,side))
        time.sleep(.08);r,rows=dump(s,s.out,'awd-'+str(side))
        require(r['state']==2 and r['faults']&32 and r['probe']==side,'Real ADC watchdog event missing')
        require(any(x['event']==5 and x['faults']&32 for x in rows),'Missing watchdog trace')
        result['awd_'+str(side)+'_preflight']=ok(s.request(21,6))
        ok(s.request(24,1000),5)
    result['checks'].append('both-real-ADC-watchdog-windows-latched-no-power')
    ok(s.request(27));ok(s.request(21,5));ok(s.request(22));ok(s.request(24,2000))
    s.link.close();s.event(host_handle='closed_no_STOP');time.sleep(1.0);s.link.open()
    r,rows=dump(s,s.out,'link-timeout')
    require(r['state']==2 and r['faults']&8,'Local link timeout missing')
    result['checks'].append('local-timeout-with-host-closed')
    ok(s.request(27));ok(s.request(21,5));ok(s.request(22));ok(s.request(24,2000))
    hb=s.send(25);initial=ok(s.receive(hb));time.sleep(.45)
    s.write(frame(hb,25,0));repeated=ok(s.receive(hb))
    require(repeated['heartbeat_ms']==initial['heartbeat_ms'],'Replay extended heartbeat')
    time.sleep(.45);r,rows=dump(s,s.out,'duplicate-heartbeat')
    require(r['state']==2 and r['faults']&8,'Replayed heartbeat prevented timeout')
    result['checks'].append('replayed-heartbeat-does-not-renew')
    ok(s.request(27));ok(s.request(21,5));ok(s.request(22));ok(s.request(24,2000));ok(s.request(26))
    r,rows=dump(s,s.out,'explicit-stop');require(r['reason']==2 and r['state']==0,'STOP missing')
    ok(s.request(27));r=ok(s.request(20));require(r['configured']==r['owns_adc']==r['state']==0,'Final not released')
    result['checks'].append('stop-cleanup-unconfigured')
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=False)
    import serial
    link=serial.Serial();link.port=a.port;link.baudrate=115200;link.timeout=.05;link.write_timeout=1;link.dtr=link.rts=False
    s=Session(link,out);result=dict(evidence_scope=['bench'],checks=[],power_enabled=False,physical_calibration_verified=False)
    try:link.open();suite(s,result);result['checks_status']='passed'
    except Exception as e:
        result.update(checks_status='failed_or_unavailable',error=repr(e))
        if s.identified:
            try:
                if not link.is_open:link.open()
                result['stop_after_error']=s.request(26)
                result['diagnostic_after_error']=s.request(21,6)
                result['fault_trace_status'],_=dump(s,out,'failed')
            except Exception as stop:result['stop_after_error']=repr(stop)
    finally:
        s.finish();result['sha256']={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in out.iterdir() if x.is_file()}
        (out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
    return 0 if result['checks_status']=='passed' else 1
if __name__=='__main__':raise SystemExit(main())
