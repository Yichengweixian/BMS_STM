"""Automated internal-only board checks; no power command exists in this tool."""
import argparse
import binascii
import csv
import hashlib
import json
from pathlib import Path
import time
from host_diagnostics import frame, parse, FIELDS


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def clean(r, code=0):
    require(r['result']==code and r['state']==0 and r['faults']==0 and r['owns_adc']==0,
            'Unexpected stopped result: '+str(r))


class Session:
    def __init__(self, link, out):
        self.link=link
        self.out=out
        self.raw=(out/'serial.bin').open('xb')
        self.events=(out/'events.jsonl').open('x',encoding='utf-8')
        self.pending=b''
        self.identified=False
        self.counter=int(time.time()*1000)&0xffffffff
        self.reports=[]

    def event(self, **data):
        self.events.write(json.dumps(dict(monotonic=time.monotonic(),**data))+'\n')
        self.events.flush()

    def write(self, wire):
        require(self.link.write(wire)==len(wire),'Short serial write')
        self.event(tx_hex=wire.hex())

    def send(self, op, arg=0):
        # Permit only diagnostic operations (99 is an intentionally invalid command).
        require(op in (0,1,2,3,4,5,99),'Not a diagnostic operation')
        require(self.counter<0xffffffff,'Request id exhausted; no wrap/replay')
        self.counter+=1
        self.write(frame(self.counter,op,arg))
        return self.counter

    def receive(self, wanted, timeout=3):
        end=time.monotonic()+timeout
        while True:
            while b'\n' in self.pending:
                line,self.pending=self.pending.split(b'\n',1)
                if line.startswith(b'#BOOT,') and self.identified:
                    raise RuntimeError('Device reset; no automatic restart')
                if not line.startswith(b'#G02,'):
                    continue
                r=parse(line)
                self.event(report=r)
                self.reports.append(r)
                require(r['firmware'] in ('g02-host-r2','g03-adc-r4','g03-relay-r1','g03-relay-r2') and r['pins_gate']==0,
                        'Require fixed r2 firmware with pin output disabled')
                if r['id']==wanted:
                    return r
            require(len(self.pending)<=4096,'Oversized unterminated response')
            if time.monotonic()>=end:
                raise TimeoutError('No matching response; commands are not retried')
            data=self.link.read(max(1,min(self.link.in_waiting,4096)))
            self.raw.write(data)
            self.pending+=data

    def request(self, op, arg=0, timeout=3):
        return self.receive(self.send(op,arg),timeout)

    def finish(self):
        if self.link.is_open:
            self.link.close()
        self.raw.close()
        self.events.close()
        with (self.out/'reports.csv').open('x',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=['firmware']+FIELDS)
            w.writeheader()
            w.writerows(self.reports)


def check_sample(r, start_id, duration):
    clean(r)
    require(r['start_id']==start_id,'Unexpected sampling session')
    require(r['updates']>0 and r['completions']>0,'No serviced sampling events')
    require(r['overruns']==0 and r['adc_errors']==0,'Sampling errors')
    require((r['stop_ms']-r['start_ms'])&0xffffffff >= duration,'Early automatic stop')
    require((r['cpu_hz'],r['tim_hz'],r['adc_hz'])==(800000000,400000000,64000000),'Clock mismatch')


def suite(s, result):
    def passed(name):
        result['checks'].append(name)
        s.event(check_passed=name)
    clean(s.request(0))
    s.identified=True
    start=s.send(1,200)
    base=s.receive(start)
    check_sample(base,start,200)
    passed('identify-and-sample')

    # A rejected stopped-state compare must not leak into the next START.
    clean(s.request(5,1999),2)
    start=s.send(1,200)
    r=s.receive(start)
    check_sample(r,start,200)
    require(r['ccr_requested']==base['ccr_requested'],'Rejected CCR changed next start')
    passed('rejected-compare-has-no-side-effect')
    previous=r.copy()
    s.write(frame(start,1,200))
    clean(s.receive(start))
    require(s.reports[-1]['start_ms']==previous['start_ms'],'Repeated request restarted')
    s.write(frame(start,1,201));clean(s.receive(start),8)
    s.write(frame(start-1,1,200));clean(s.receive(start-1),7)
    passed('duplicate-conflict-stale')

    for op,arg in ((1,0),(1,10001),(5,0),(5,2000),(99,0),(2,1),(4,1)):
        clean(s.request(op,arg),1)
    passed('range-and-unknown-rejection')
    before=s.request(0)
    malformed=[b'G02,1,1,NaN',b'G02,1,1,Inf',b'G02,1,1,-1',
               b'G02,1,1,4294967296',b'G02,1,1',b'G02,0,1,10',b'x'*80]
    for body in malformed:
        s.write(body+('*%04X\n'%binascii.crc_hqx(body,65535)).encode())
        time.sleep(.15)
    s.write(b'G02,1,1,10*FFFF\n')
    time.sleep(.15)
    r=s.request(0);clean(r)
    require(r['bad_frames']>=before['bad_frames']+len(malformed)+1,'Bad frames not accounted')
    require(r['start_ms']==previous['start_ms'],'Malformed input started sampling')
    passed('malformed-crc-numeric-overlong')

    s.counter+=1
    wire=frame(s.counter,0)
    s.write(wire[:7]);time.sleep(.03);s.write(wire[7:]);clean(s.receive(s.counter))
    s.counter+=1
    s.write(b'bad\n'+frame(s.counter,0));clean(s.receive(s.counter))
    passed('fragment-and-concatenation')

    start=s.send(1,1000);time.sleep(.15)
    busy=s.send(1,1)
    r=s.receive(busy,3);clean(r,3)
    require(r['start_id']==start and ((r['stop_ms']-r['start_ms'])&0xffffffff)>=1000,
            'BUSY start replaced active window')
    passed('busy-start-preserves-window')

    for compare in (1,1000,1999):
        start=s.send(1,700);time.sleep(.15)
        r=s.receive(s.send(5,compare),3)
        check_sample(r,start,700)
        require(r['ccr_writes']==1 and r['ccr_observed']==compare,'CCR observation mismatch')
    passed('internal-ccr-boundary-scan')

    start=s.send(1,10000);time.sleep(.2)
    r=s.request(2);clean(r)
    require(r['start_id']==start and ((r['stop_ms']-r['start_ms'])&0xffffffff)<10000,'STOP did not shorten window')
    clean(s.request(2))
    passed('stop-and-repeated-stop')
    s.send(1,10000);time.sleep(.2)
    r=s.request(3)
    require(r['result']==0 and r['state']==3 and r['faults']==32 and r['owns_adc']==0,'Fault cleanup failed')
    r=s.request(1,200)
    require(r['result']==5 and r['state']==3,'Fault did not reject START')
    clean(s.request(4));clean(s.request(0))
    passed('fault-latch-clear')

    # Close the host handle without STOP. This tests autonomous window expiry,
    # not physical USB removal or a firmware communication-loss watchdog.
    start=s.send(1,1000)
    s.link.flush();time.sleep(.15)
    s.link.close();s.event(host_handle='closed_without_STOP')
    time.sleep(1.3)
    s.link.open();s.event(host_handle='reopened_without_replay')
    r=s.request(0);check_sample(r,start,1000)
    clean(s.request(0))
    passed('host-close-expiry-reconnect-no-replay')

    start=s.send(1,1000)
    for _ in range(20):
        time.sleep(.02)
        last=s.send(99)
    r=s.receive(last,3);clean(r,1)
    require(r['start_id']==start and r['overruns']==0 and r['adc_errors']==0,'Traffic disturbed sampling')
    passed('bounded-command-traffic')
    for _ in range(3):
        start=s.send(1,10000)
        check_sample(s.receive(start,13),start,10000)
    passed('three-10s-windows')
    clean(s.request(2))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=False)
    import serial
    link=serial.Serial();link.port=a.port;link.baudrate=115200;link.timeout=.1
    link.write_timeout=1;link.dtr=link.rts=False
    s=Session(link,out)
    result=dict(status='in_progress',verdict=None,evidence_scope=['bench'],checks=[],
                physical_waveforms_verified=False,physical_disconnect_tested=False)
    try:
        link.open();suite(s,result)
        result.update(status='complete',software_checks='passed')
    except Exception as exc:
        result.update(software_checks='failed_or_unavailable',error=repr(exc))
        if s.identified:
            try:
                if not link.is_open:link.open()
                result['stop_after_error']=s.request(2)
            except Exception as stop_error:result['stop_after_error']=repr(stop_error)
    finally:
        s.finish()
        result['reports']=s.reports
        result['sha256']={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in
                          (out/'serial.bin',out/'events.jsonl',out/'reports.csv',Path(__file__))}
        (out/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='reports'},indent=2))
    return 0 if result.get('software_checks')=='passed' else 1


if __name__=='__main__':raise SystemExit(main())
