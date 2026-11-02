"""G03 disabled MCU exercise. Reports contain synthetic sensors and shadow outputs."""
import argparse,binascii,csv,hashlib,json,re,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'g02'))
from host_diagnostics import frame
from extended_diagnostics import Session as BaseSession, require
FIELDS='id result state direction faults reason configured fixture ccr shadow_relays shadow_pwm actual_bits start_ms stop_ms heartbeat_ms transitions starts ticks max_tick_gap scenario synthetic power_capable'.split()

def parse(line):
    body,crc=line.rstrip(b'\r\n').rsplit(b'*',1)
    if not re.fullmatch(b'[0-9A-F]{4}',crc) or int(crc,16)!=binascii.crc_hqx(body,65535):raise ValueError('CRC')
    fields=body.decode('ascii').split(',')
    if len(fields)!=len(FIELDS)+2 or fields[0]!='#G03' or fields[1] not in ('g03-adc-r4','g03-relay-r1','g03-relay-r2'):raise ValueError('Firmware/schema')
    if any(not re.fullmatch('[0-9]+',x) or int(x)>0xffffffff for x in fields[2:]):raise ValueError('Range')
    return dict(zip(FIELDS,map(int,fields[2:])))

class Session(BaseSession):
    def send(self,op,arg=0):
        require(10<=op<=19,'G03 disabled operations only')
        require(self.counter<0xffffffff,'ID exhausted; no wrap')
        self.counter+=1;self.write(frame(self.counter,op,arg));return self.counter
    def receive(self,wanted,timeout=3):
        end=time.monotonic()+timeout
        while True:
            while b'\n' in self.pending:
                line,self.pending=self.pending.split(b'\n',1)
                if line.startswith(b'#BOOT,') and self.identified:raise RuntimeError('Device reboot; no replay')
                if not line.startswith(b'#G03,'):continue
                r=parse(line);self.reports.append(r);self.event(report=r)
                require((r['synthetic'],r['power_capable'],r['actual_bits'])==(1,0,0),'Unexpected output state/capability')
                if r['id']==wanted:return r
            require(len(self.pending)<=4096,'Oversized line')
            if time.monotonic()>=end:raise TimeoutError('No G03 response; no automatic retry')
            data=self.link.read(max(1,min(self.link.in_waiting,4096)));self.raw.write(data);self.pending+=data
    def finish(self):
        if self.link.is_open:self.link.close()
        self.raw.close();self.events.close()
        with (self.out/'reports.csv').open('x',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(self.reports)

def expect(r,code=0,state=None):
    require(r['result']==code,'Unexpected command result '+str(r))
    if state is not None:require(r['state']==state,'Unexpected state '+str(r))
    return r

def wait_state(s,state,seconds=2):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        r=s.request(10)
        if r['state']==state:return r
        if r['state']==6 and state!=6:raise RuntimeError('Unexpected fault '+str(r))
        time.sleep(.025)
    raise TimeoutError('Expected state '+str(state))

def suite(s,result):
    def passed(name):result['checks'].append(name);s.event(check_passed=name)
    expect(s.request(10),state=0);s.identified=True
    expect(s.request(18,1),4,0);expect(s.request(17,0));expect(s.request(11,500),2,0)
    expect(s.request(17,1));passed('power-rejected-unknown-config-rejected')
    start=expect(s.request(11,2000));r=wait_state(s,3)
    require(r['direction']==1 and r['shadow_relays']==1 and r['shadow_pwm']==1,'Charge shadow')
    expect(s.request(15));expect(s.request(19,1200));r=expect(s.request(19,1999),1)
    require(r['ccr']==1200,'Rejected compare mutated target')
    r=expect(s.request(12,100),3);require(r['direction']==1 and r['starts']==start['starts'],'Reversal restarted')
    expect(s.request(13));expect(s.request(13));r=wait_state(s,0)
    require(not r['shadow_pwm'] and not r['shadow_relays'] and r['reason']==2,'STOP sequence')
    passed('charge-compare-busy-reversal-stop')
    expect(s.request(12,500));r=wait_state(s,4)
    require(r['direction']==2 and r['shadow_relays']==2 and r['shadow_pwm']==1,'Discharge shadow')
    r=wait_state(s,0);require(r['reason']==1,'Duration did not stop')
    passed('discharge-duration-stop')

    cases=[(1,2),(2,4),(3,8),(4,16),(5,32),(6,64),(7,256),(8,1024),(9,512),(10,2)]
    for scenario,bit in cases:
        expect(s.request(16,0));expect(s.request(11,3000));wait_state(s,3)
        expect(s.request(16,scenario))
        if scenario==9:expect(s.request(13))
        r=wait_state(s,6);require(r['faults']&bit,'Wrong fault '+str(r))
        require(not r['shadow_pwm'] and not r['shadow_relays'],'Fault shadow still active')
        expect(s.request(12,200),5,6);expect(s.request(14),state=0)
    expect(s.request(16,0));passed('ten-sensor-interlock-decay-faults-latched')

    expect(s.request(12,4000));wait_state(s,4)
    for _ in range(5):time.sleep(.15);expect(s.request(15))
    require(expect(s.request(10))['state']==4,'Heartbeat failed to sustain')
    # Query/reconnect do not count as heartbeat or revive a timed-out run.
    s.link.close();s.event(host_handle='closed_without_STOP');time.sleep(1.1)
    s.link.open();s.event(host_handle='reopened_query_only');r=expect(s.request(10),state=6)
    require(r['faults']&128 and r['reason']==3,'MCU local communication timeout missing')
    expect(s.request(15),5,6);expect(s.request(14),state=0)
    passed('heartbeat-and-local-timeout-after-host-close')

    # Duplicate cached heartbeat must not extend the local lease.
    expect(s.request(11,3000));wait_state(s,3)
    hb=s.send(15);expect(s.receive(hb));time.sleep(.45)
    s.write(frame(hb,15,0));expect(s.receive(hb));time.sleep(.45)
    r=expect(s.request(10),state=6);require(r['faults']&128,'Duplicate heartbeat renewed lease')
    expect(s.request(14),state=0);passed('duplicate-heartbeat-does-not-renew')

    expect(s.request(16,1));expect(s.request(11,100),5,6);expect(s.request(14),state=0)
    expect(s.request(11,100),5,6);expect(s.request(16,0));expect(s.request(14),state=0)
    passed('clear-does-not-bypass-persistent-bad-input')
    expect(s.request(13));expect(s.request(19,1000));expect(s.request(17,0));expect(s.request(10),state=0)
    passed('final-stopped-unconfigured')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=False)
    import serial
    link=serial.Serial();link.port=a.port;link.baudrate=115200;link.timeout=.1;link.write_timeout=1;link.dtr=link.rts=False
    s=Session(link,out);result=dict(status='in_progress',verdict=None,evidence_scope=['bench'],checks=[],
        sensor_inputs='synthetic fixture only',physical_power_enabled=False,physical_waveforms_verified=False)
    try:
        link.open();suite(s,result);result.update(status='complete',software_checks='passed')
    except Exception as exc:
        result.update(software_checks='failed_or_unavailable',error=repr(exc))
        if s.identified:
            try:
                if not link.is_open:link.open()
                result['stop_after_error']=s.request(13)
            except Exception as stop_exc:result['stop_after_error']=repr(stop_exc)
    finally:
        s.finish();result['reports']=s.reports
        result['sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (out/'serial.bin',out/'events.jsonl',out/'reports.csv',Path(__file__))}
        (out/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='reports'},indent=2))
    return 0 if result.get('software_checks')=='passed' else 1

if __name__=='__main__':raise SystemExit(main())
