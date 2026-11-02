"""G01 read-only serial recorder / replay. Python 3.8+, pyserial for live capture.
Raw bytes are never cleaned; decoded rows and errors are separate artifacts.
"""
import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
from pathlib import Path
import time
import uuid

FIELDS = ('type seq channel start_ms end_ms age_ms raw status raw_valid '
          'sensor_V_nominal estimate unit physical_value physical_valid reference '
          'cal_id frame_hex wire_pec15').split()
CHANNELS = ('cell1', 'cell7', 'cell13', 'current_afe_gpio1', 'temperature_gpio2',
            'temperature_gpio3', 'temperature_gpio4', 'current_mcu_adc1', 'afe_vref2')
INVALID_MASK = 383  # all v1 flags except UNCALIBRATED=128

def pec15(data):
    rem = 16
    for byte in data:
        rem ^= byte << 7
        for _ in range(8):
            rem = ((rem << 1) ^ (0x4599 if rem & 0x4000 else 0)) & 0xffff
    return (rem << 1) & 0xffff

def parse_line(line):
    """Strict schema and integrity validation; invalid measurements remain rows."""
    text = line.decode('ascii').rstrip('\r\n')
    payload, check = text.rsplit(',', 1)
    if len(check) != 4 or pec15(payload.encode('ascii')) != int(check, 16):
        raise ValueError('wire checksum')
    values = next(csv.reader([text]))
    if len(values) != len(FIELDS):
        raise ValueError('column count')
    row = dict(zip(FIELDS, values))
    if row['type'] != 'M' or row['channel'] not in CHANNELS:
        raise ValueError('unknown type/channel')
    if row['cal_id'] != 'uncalibrated-v1':
        raise ValueError('unsupported calibration identity')
    for key in ('seq', 'start_ms', 'end_ms', 'age_ms', 'status'):
        if not row[key].isdigit() or not 0 <= int(row[key]) <= 0xffffffff:
            raise ValueError('invalid ' + key)
    status = int(row['status'])
    if status & ~511 or not status & 128:
        raise ValueError('unknown/missing quality flag')
    if row['raw_valid'] not in ('0', '1') or row['physical_valid'] != '0':
        raise ValueError('validity field')
    if row['physical_value'] or row['reference']:
        raise ValueError('uncalibrated stream cannot supply physical/reference truth')
    if row['raw'] and (not row['raw'].isdigit() or not 0 <= int(row['raw']) <= 65535):
        raise ValueError('raw range')
    if bool(status & 256) != (row['raw'] == ''):
        raise ValueError('raw presence flag')
    if (row['raw_valid'] == '1') != (not (status & INVALID_MASK)):
        raise ValueError('status/validity conflict')
    if (int(row['age_ms']) > 1000) != bool(status & 16):
        raise ValueError('age/stale conflict')
    if ((int(row['end_ms'])-int(row['start_ms'])) & 0xffffffff) > 1000:
        raise ValueError('invalid conversion time window')
    for key in ('sensor_V_nominal', 'estimate'):
        if row[key] and not math.isfinite(float(row[key])):
            raise ValueError('non-finite ' + key)
        if row['raw_valid'] == '0' and row[key]:
            raise ValueError('invalid sample has derived value')
    if row['raw_valid'] == '1' and not row['sensor_V_nominal']:
        raise ValueError('valid raw without sensor voltage')
    ch = row['channel']
    expected_unit = 'A' if ch.startswith('current') else 'degC' if ch.startswith('temperature') else 'V'
    if row['unit'] != expected_unit:
        raise ValueError('unit')
    if ch == 'current_mcu_adc1' and row['frame_hex']:
        raise ValueError('MCU source cannot supply AFE frame')
    # A nominal MCU current estimate is allowed; physical/reference truth stays
    # forbidden above. Model provenance is carried in the session #CONFIG.
    if row['frame_hex']:
        frame = bytes.fromhex(row['frame_hex'])
        if len(frame) != 8 or ch == 'current_mcu_adc1':
            raise ValueError('AFE frame size/source')
        bad_pec = pec15(frame[:6]) != int.from_bytes(frame[6:], 'big')
        if bad_pec != bool(status & 2):
            raise ValueError('AFE PEC flag')
        index = {'temperature_gpio2': 1, 'temperature_gpio3': 2, 'afe_vref2': 2}.get(ch, 0)
        if int.from_bytes(frame[2*index:2*index+2], 'little') != int(row['raw']):
            raise ValueError('raw/frame mismatch')
    elif ch != 'current_mcu_adc1' and row['raw']:
        raise ValueError('AFE raw without received frame')
    return row

class Tracker:
    """Host boot segments, per-channel sequence gaps, uint32 wrap and reset events."""
    def __init__(self, session):
        self.session = session
        self.segment = 0
        self.last = {}
        self.group = None
        self.seen = set()

    @property
    def boot_id(self):
        return '{}:{}'.format(self.session, self.segment)

    def finish_group(self):
        if self.group is not None:
            missing = sorted(set(CHANNELS) - self.seen)
            self.group = None
            self.seen = set()
            if missing:
                return [{'event': 'incomplete_group', 'missing_channels': missing}]
        return []

    def reset(self, reason):
        events = self.finish_group()
        if self.last:
            self.segment += 1
        self.last.clear()
        return events + [{'event': reason, 'boot_id': self.boot_id}]

    def feed(self, row):
        events = []
        ch, seq, end = row['channel'], int(row['seq']), int(row['end_ms'])
        prev = self.last.get(ch)
        if prev:
            step = (seq-prev[0]) & 0xffffffff
            if step >= 0x80000000:
                events += self.reset('inferred_reset_or_out_of_order')
                prev = None
            elif step == 0:
                events.append({'event': 'duplicate', 'channel': ch, 'seq': seq})
            elif step > 1:
                events.append({'event': 'sequence_gap', 'channel': ch, 'missing': step-1})
        if prev:
            delta = (end-prev[1]) & 0xffffffff
            if delta >= 0x80000000:
                events.append({'event': 'time_reversal', 'channel': ch})
            elif end < prev[1]:
                events.append({'event': 'tick_wrap', 'channel': ch})
            if delta > 1000 and delta < 0x80000000:
                events.append({'event': 'sampling_gap', 'channel': ch, 'elapsed_ms': delta})
        if self.group != seq:
            events += self.finish_group()
            self.group = seq
        self.seen.add(ch)
        self.last[ch] = (seq, end)
        return events

def capture(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    (out/'raw').mkdir()
    (out/'derived').mkdir()
    session = uuid.uuid4().hex
    tracker = Tracker(session)
    source = None
    manifest = dict(schema='g01-recorder-v1', session=session, evidence_scope='simulation' if args.replay else 'bench',
                    source=str(args.replay or args.port), simulated=bool(args.replay), baud=115200,
                    started_utc=dt.datetime.now(dt.timezone.utc).isoformat(), physical_calibration_verified=False,
                    firmware_sha256=args.firmware_sha256, verdict=None, rows=0, errors=0,
                    tick_hz=1000, tick_bits=32, sample_time='conversion bracket; not UART transmit time',
                    boot_id_policy='host session:segment; reconnect starts a new session', metadata=[])
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    reason='completed'
    try:
        if args.replay:
            source = open(args.replay, 'rb')
        else:
            import serial
            source = serial.Serial()
            source.port, source.baudrate, source.timeout = args.port, 115200, 0.2
            source.dtr = source.rts = False
            source.open()  # no writes, commands, reset or buffer flush
        with (out/'raw/serial.bin').open('xb') as raw, (out/'raw/events.jsonl').open('x', encoding='utf-8') as events, \
             (out/'derived/device.csv').open('x', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=['run_id','boot_id','stream_id','host_rx_utc','host_rx_monotonic_ns']+FIELDS)
            writer.writeheader()
            started=time.monotonic()
            pending=b''
            def event(item, stamp):
                item.update(host_rx_utc=stamp, boot_id=tracker.boot_id)
                events.write(json.dumps(item, ensure_ascii=False)+'\n')
            while args.replay or time.monotonic()-started < args.seconds:
                chunk=source.read(1 if not args.replay else 4096)
                if not chunk:
                    if args.replay: break
                    continue
                raw.write(chunk)
                pending+=chunk
                while b'\n' in pending:
                    line,pending=pending.split(b'\n',1)
                    line+=b'\n'
                    stamp=dt.datetime.now(dt.timezone.utc).isoformat()
                    if line.startswith(b'#'):
                        msg=line.decode('ascii', errors='replace').strip()
                        if line.startswith(b'#BOOT,'):
                            for item in tracker.reset('boot_marker'): event(item,stamp)
                        if line.startswith((b'#META,',b'#CONFIG,')) and msg not in manifest['metadata']:
                            manifest['metadata'].append(msg)
                        event({'event':'device_metadata','text':msg},stamp)
                        continue
                    try:
                        row=parse_line(line)
                    except (ValueError, UnicodeError, OverflowError) as err:
                        manifest['errors']+=1
                        event({'event':'parse_error','reason':str(err),'line_hex':line.hex()},stamp)
                        continue
                    for item in tracker.feed(row): event(item,stamp)
                    row.update(run_id=out.name, boot_id=tracker.boot_id,stream_id='g01-v1',host_rx_utc=stamp,host_rx_monotonic_ns=time.monotonic_ns())
                    writer.writerow(row)
                    manifest['rows']+=1
                if len(pending)>4096:
                    event({'event':'overlong_unterminated_line','bytes':len(pending)},dt.datetime.now(dt.timezone.utc).isoformat())
                    manifest['errors']+=1
                    pending=b''
            stamp=dt.datetime.now(dt.timezone.utc).isoformat()
            for item in tracker.finish_group(): event(item,stamp)
            if pending:
                event({'event':'partial_tail','bytes':len(pending)},stamp)
                manifest['errors']+=1
    except KeyboardInterrupt:
        reason='user_interrupted'
    except Exception as err:
        reason='error: '+str(err)
        raise
    finally:
        if source is not None: source.close()
        manifest.update(exit_reason=reason, ended_utc=dt.datetime.now(dt.timezone.utc).isoformat())
        manifest['sha256']={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in out.rglob('*') if p.is_file() and p.name!='manifest.json'}
        manifest['recorder_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps({'out':str(out),'rows':manifest['rows'],'errors':manifest['errors'],'exit_reason':reason}))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    source=parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--port')
    source.add_argument('--replay',type=Path,help='offline/simulated bytes; never hardware acceptance')
    parser.add_argument('--out',required=True,help='new directory; refuses to overwrite raw data')
    parser.add_argument('--seconds',type=float,default=60)
    parser.add_argument('--firmware-sha256',help='hash of actual flashed image, not inferred from port')
    args=parser.parse_args()
    if args.seconds<=0: parser.error('--seconds must be positive')
    if args.firmware_sha256 and (len(args.firmware_sha256)!=64 or any(c not in '0123456789abcdefABCDEF' for c in args.firmware_sha256)):
        parser.error('--firmware-sha256 must be 64 hex characters')
    capture(args)
