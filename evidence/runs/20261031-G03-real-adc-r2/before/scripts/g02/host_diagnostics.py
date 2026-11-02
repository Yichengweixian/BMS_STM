"""G02 internal-only diagnostics. Never sends pin-output or relay commands."""
import argparse
import binascii
import json
import re
from pathlib import Path
import time

FIELDS = 'id result start_id state faults owns_adc cpu_hz tim_hz adc_hz start_ms stop_ms updates completions overruns adc_errors gap_max_cycles tim_isr_max_cycles adc_isr_max_cycles late_irqs ccr_writes ccr_requested ccr_observed stop_software_cycles bad_frames rx_errors pins_gate'.split()

def frame(request_id, op, arg=0):
    if any(type(x) is not int or x < 0 or x > 0xffffffff for x in (request_id,op,arg)) or request_id == 0:
        raise ValueError('uint32 request fields; request id must be nonzero')
    body = ('G02,%d,%d,%d' % (request_id,op,arg)).encode('ascii')
    return body + ('*%04X\n' % binascii.crc_hqx(body,65535)).encode('ascii')

def parse(line):
    body, check = line.rstrip(b'\r\n').rsplit(b'*',1)
    if not re.fullmatch(b'[0-9A-F]{4}',check) or int(check,16)!=binascii.crc_hqx(body,65535): raise ValueError('CRC')
    parts=body.decode('ascii').split(',')
    if parts[0]!='#G02' or parts[1] not in ('g02-host-r1','g02-host-r2','g03-adc-r1') or len(parts)!=len(FIELDS)+2: raise ValueError('schema/firmware')
    if any(not re.fullmatch('[0-9]+',x) for x in parts[2:]): raise ValueError('unsigned decimal fields')
    values=[int(x) for x in parts[2:]]
    if any(x<0 or x>0xffffffff for x in values): raise ValueError('range')
    return dict(firmware=parts[1],**dict(zip(FIELDS,values)))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=False)
    import serial
    link=serial.Serial();link.port=a.port;link.baudrate=115200;link.timeout=0.1;link.dtr=link.rts=False
    reports=[];request_id=int(time.time()*1000) & 0xffffffff;identified=False
    raw=(out/'serial.bin').open('xb');events=(out/'events.jsonl').open('x',encoding='utf-8')
    def log(**data): events.write(json.dumps(dict(monotonic=time.monotonic(),**data))+'\n');events.flush()
    def send(op,arg=0):
        nonlocal request_id
        request_id+=1;wire=frame(request_id,op,arg);link.write(wire);log(tx_hex=wire.hex(),id=request_id,op=op,arg=arg);return request_id
    pending=b''
    def receive(wanted,seconds=3):
        nonlocal pending
        until=time.monotonic()+seconds
        while time.monotonic()<until:
            data=link.read(max(1,min(link.in_waiting,4096)));raw.write(data);pending+=data
            while b'\n' in pending:
                line,pending=pending.split(b'\n',1)
                if line.startswith(b'#BOOT,') and identified:raise RuntimeError('Device reboot; no automatic restart')
                if not line.startswith(b'#G02,'):continue
                r=parse(line);log(report=r);reports.append(r)
                if r['pins_gate']!=0:raise RuntimeError('Unexpected output-capable firmware')
                if r['id']==wanted:return r
            if len(pending)>4096:raise RuntimeError('Unterminated oversized response')
        raise TimeoutError('No matching G02 response; no automatic command retry')
    def clean(r):
        assert r['result']==0 and r['state']==0 and r['faults']==0 and r['owns_adc']==0,r
    result=dict(scope=['bench'],verdict=None,status='in_progress',checks=[],hardware_waveforms_verified=False)
    try:
        link.open();clean(receive(send(0)));identified=True
        clean(receive(send(4)))
        r=receive(send(1,1000),4);clean(r);assert r['updates']>0 and r['completions']>0;r['test']='sample-1s'
        result['checks'].append('sample-1s')
        start=send(1,10000);time.sleep(.25);send(5,1500);time.sleep(.25)
        r=receive(send(2));clean(r);assert r['start_id']==start and r['ccr_writes']==1 and r['ccr_observed']==1500;r['test']='compare-stop'
        result['checks'].append('compare-stop')
        send(1,10000);time.sleep(.25);r=receive(send(3));assert r['state']==3 and r['faults']&32;r['test']='fault'
        r=receive(send(1,1000));assert r['result']==5 and r['state']==3;r['test']='latched-reject'
        clean(receive(send(4)));clean(receive(send(0)));result['checks'].append('fault-latch-clear')
        r=receive(send(1,10000),13);clean(r);assert r['updates']>0 and r['completions']>0;r['test']='sample-10s'
        assert r['overruns']==0 and r['adc_errors']==0;r['elapsed_ms']=(r['stop_ms']-r['start_ms'])&0xffffffff
        result['checks'].append('sample-10s');result['status']='complete';result['software_checks']='passed'
    except Exception as exc:
        result.update(status='in_progress',software_checks='failed_or_unavailable',error=str(exc))
        if identified:
            try:result['stop_after_error']=receive(send(2))
            except Exception as stop_exc:result['stop_after_error']=str(stop_exc)
    finally:
        if link.is_open:link.close()
        raw.close();events.close();result['reports']=reports
        import hashlib
        result['sha256']={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in (out/'serial.bin',out/'events.jsonl')}
        (out/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2));return 0 if result.get('software_checks')=='passed' else 1

if __name__=='__main__':raise SystemExit(main())
