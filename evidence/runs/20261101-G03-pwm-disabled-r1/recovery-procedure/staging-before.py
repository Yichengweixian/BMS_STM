"""Post-PWM recovery checks on g03-pwm-disabled-r1, without reset or power output.

One Serial instance owns the port for the whole run. Operations are allowlisted:
40/42 PWM query/read, optional explicit 44 fault clear, 0/1/2 G02 query/internal
sample/STOP, 30/31/34/36 relay query/DRY/STOP/read. Never sends PWM start (41),
relay live (32), compare, reset, or download. Starts are never retried.

Default invocation prints the plan without serial access; --execute runs it.
Sequence: check stopped/restored/used PWM -> G01 raw 15 seconds ->
G02 1000 ms internal sampling -> relay DRY -> final disabled status checks.
Existing fault/relay results are not silently cleared or overwritten. To clear a
known PWM fault, supply its exact decimal/0x mask with --clear-pwm-fault; the
script saves all its trace records first, verifies owned=0/restored=1, then
checks that the one-shot token remains consumed after clear.

Old G02/relay host parsers reject the new firmware label. This script accepts
only the new label with the unchanged exact schemas, CRC, and zero-output
invariants. G01 parsing is reused unchanged; no physical calibration is changed.
There are no TIM2 PSC/ARR readback fields in the wire protocol: relay DRY proves
functional reuse only, while exact PSC/ARR restoration belongs to the offline
register fixture. A successful run is not physical PWM or relay acceptance.
"""
import argparse
import binascii
import csv
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parent / 'workspace'


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


g01 = load('recovery_g01', 'scripts/g01/g01_capture.py')
g02 = load('recovery_g02', 'scripts/g02/host_diagnostics.py')
pwm = load('recovery_pwm', 'scripts/g03/pwm_disabled.py')
relay = load('recovery_relay', 'scripts/g03/relay_capture.py')
FIRMWARE = 'g03-pwm-disabled-r1'
ALLOWED = {0, 1, 2, 30, 31, 34, 36, 40, 42, 44}
EXPECTED_KIND = {0: '#G02', 1: '#G02', 2: '#G02', 30: '#G3R',
                 31: '#G3R', 34: '#G3R', 36: '#G3S', 40: '#G3P',
                 42: '#G3E', 44: '#G3P'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    require(re.fullmatch('[0-9]+', value) is not None, 'unsigned decimal field')
    result = int(value)
    require(result <= 0xffffffff, 'uint32 field range')
    return result


def parse_report(line):
    if line.startswith((b'#G3P,', b'#G3E,')):
        return pwm.parse(line)
    body, checksum = line.rstrip(b'\r\n').rsplit(b'*', 1)
    require(re.fullmatch(b'[0-9A-F]{4}', checksum) is not None, 'CRC encoding')
    require(int(checksum, 16) == binascii.crc_hqx(body, 65535), 'CRC mismatch')
    fields = body.decode('ascii').split(',')
    require(len(fields) >= 2 and fields[1] == FIRMWARE, 'firmware identity')
    kind, values = fields[0], fields[2:]
    if kind in ('#G02', '#G3R'):
        names = g02.FIELDS if kind == '#G02' else relay.STATUS
        require(len(values) == len(names), 'status length')
        result = dict(zip(names, map(number, values)))
        if kind == '#G02':
            require(result['pins_gate'] == 0, 'G02 output gate')
        else:
            require(all(result[key] == 0 for key in
                        ('live', 'actual_bits', 'live_gate', 'live_used', 'physical_valid')),
                    'relay disabled-output/calibration invariant')
    elif kind == '#G3S':
        require(len(values) == 37, 'relay sample length')
        result = dict(zip('id result seq phase at_ms done_ms bits'.split(),
                          map(number, values[:7])))
        require(result['bits'] == 0, 'relay trace output invariant')
        result['samples'] = []
        for index, channel in enumerate(relay.CHANNELS):
            data = values[7 + index * 6:13 + index * 6]
            sample = dict(zip('start_ms end_ms raw status raw_valid'.split(),
                              map(number, data[:5])))
            require(re.fullmatch('[0-9A-F]{16}', data[5]) is not None, 'raw frame')
            require(sample['raw'] <= 65535 and sample['raw_valid'] in (0, 1), 'sample range')
            require(sample['status'] & 128 and sample['status'] & ~511 == 0,
                    'uncalibrated quality flags')
            require(bool(sample['raw_valid']) == (not bool(sample['status'] & g01.INVALID_MASK)),
                    'raw validity/quality conflict')
            require(((sample['end_ms'] - sample['start_ms']) & 0xffffffff) <= 1000,
                    'conversion bracket')
            if index < 4 and sample['raw_valid']:
                frame = bytes.fromhex(data[5])
                require(g01.pec15(frame[:6]) == int.from_bytes(frame[6:], 'big') and
                        int.from_bytes(frame[:2], 'little') == sample['raw'], 'AFE PEC/raw mismatch')
            sample.update(channel=channel, frame_hex=data[5])
            result['samples'].append(sample)
    else:
        raise ValueError('report schema')
    require(result['id'] != 0, 'zero reply ID')
    result.update(kind=kind, firmware=FIRMWARE)
    return result


def summarize_g01(rows, parse_errors=0):
    groups, summary = {}, {}
    for row in rows:
        groups.setdefault(int(row['seq']), set()).add(row['channel'])
    sequence_order = list(groups)
    interior_missing = {str(seq): sorted(set(g01.CHANNELS) - groups[seq])
                        for seq in sequence_order[1:-1] if len(groups[seq]) != len(g01.CHANNELS)}
    anomalies = []
    for channel in g01.CHANNELS:
        data = [row for row in rows if row['channel'] == channel]
        valid = [int(row['raw']) for row in data if row['raw_valid'] == '1']
        periods = []
        for left, right in zip(data, data[1:]):
            step = (int(right['seq']) - int(left['seq'])) & 0xffffffff
            period = (int(right['end_ms']) - int(left['end_ms'])) & 0xffffffff
            periods.append(period)
            if step != 1 or period > 1000:
                anomalies.append(dict(channel=channel, seq_step=step, period_ms=period))
        summary[channel] = dict(records=len(data), valid=len(valid), invalid=len(data) - len(valid),
                                raw_min=min(valid, default=None), raw_max=max(valid, default=None),
                                raw_mean=statistics.mean(valid) if valid else None,
                                raw_noise_pstdev=statistics.pstdev(valid) if valid else None,
                                conversion_max_ms=max(((int(r['end_ms']) - int(r['start_ms'])) &
                                                       0xffffffff for r in data), default=None),
                                age_max_ms=max((int(r['age_ms']) for r in data), default=None),
                                sample_gap_max_ms=max(periods, default=None))
    passed = (parse_errors == 0 and not anomalies and not interior_missing and
              all(value['valid'] >= 2 and value['invalid'] == 0 for value in summary.values()))
    return dict(verdict='pass' if passed else 'fail', channels=summary,
                rows=len(rows), parse_errors=parse_errors, sequence_or_gap_anomalies=anomalies,
                incomplete_interior_groups=interior_missing,
                complete_groups=sum(len(channels) == len(g01.CHANNELS) for channels in groups.values()),
                edge_groups_may_be_partial=True, physical_valid=0, calibration_changed=False,
                acceptance='15 s; each existing channel >=2 valid rows; no interior gaps, '
                           'duplicates, invalid rows or gap > existing 1000 ms stale limit')


class Session:
    def __init__(self, link, out, first_id, clock=time.monotonic):
        self.link, self.out, self.clock = link, Path(out), clock
        self.counter = first_id - 1
        self.raw = (self.out / 'serial.bin').open('xb')
        self.events = (self.out / 'events.jsonl').open('x', encoding='utf-8')
        self.device_file = (self.out / 'g01.csv').open('x', encoding='utf-8', newline='')
        self.device = csv.DictWriter(self.device_file, fieldnames=['phase', 'host_monotonic'] + g01.FIELDS)
        self.device.writeheader()
        self.pending, self.reports, self.rows = b'', {}, []
        self.phase, self.identified, self.first_line = 'identify', False, True
        self.parse_errors, self.active, self.g01_raw = 0, None, None
        self.start_attempts = set()

    def event(self, **data):
        self.events.write(json.dumps(dict(host_monotonic=self.clock(), phase=self.phase, **data)) + '\n')
        self.events.flush()

    def pump(self):
        data = self.link.read(max(1, min(self.link.in_waiting, 4096)))
        self.raw.write(data)
        self.raw.flush()
        if self.g01_raw is not None:
            self.g01_raw.write(data)
        self.pending += data
        while b'\n' in self.pending:
            line, self.pending = self.pending.split(b'\n', 1)
            first, self.first_line = self.first_line, False
            if line.startswith(b'#BOOT,') and self.identified:
                self.event(event='unexpected_reset', line_hex=line.hex())
                raise RuntimeError('Reset detected; no replay or restart')
            if line.startswith((b'#G02,', b'#G3R,', b'#G3S,', b'#G3P,', b'#G3E,')):
                report = parse_report(line)
                self.event(report=report)
                require(report['id'] not in self.reports, 'duplicate report ID')
                self.reports[report['id']] = report
            elif line.startswith(b'M,'):
                try:
                    row = g01.parse_line(line)
                except (ValueError, UnicodeError, OverflowError) as error:
                    self.parse_errors += 1
                    self.event(event='g01_parse_error', reason=str(error), line_hex=line.hex())
                    continue
                item = dict(phase=self.phase, host_monotonic=self.clock(), **row)
                self.rows.append(item)
                self.device.writerow(item)
            elif line.startswith(b'#'):
                self.event(event='metadata', line=line.decode('ascii', errors='replace'))
            elif first:
                self.event(event='leading_stream_fragment', line_hex=line.hex())
            elif line.strip():
                self.event(event='unknown_serial_line', line_hex=line.hex())
                raise ValueError('Unknown serial line')
        require(len(self.pending) <= 4096, 'oversized unterminated serial line')

    def request(self, op, arg=0, timeout=8):
        require(op in ALLOWED, 'recovery operation allowlist')
        require(type(arg) is int and 0 <= arg <= 0xffffffff, 'argument uint32')
        if op not in (1, 36, 42):
            require(arg == 0, 'zero argument required')
        if op == 1:
            require(arg == 1000, 'only fixed 1000 ms internal sample is allowed')
        if op in (1, 31):
            require(self.identified and op not in self.start_attempts, 'start already attempted or unidentified')
            self.start_attempts.add(op)  # includes partial write/timeout; never retry
            self.active = op
        require(0 <= self.counter < 0xffffffff, 'request ID exhaustion; no wrap')
        self.counter += 1
        wire = g02.frame(self.counter, op, arg)
        self.event(tx_attempt_hex=wire.hex(), id=self.counter, op=op, arg=arg)
        count = self.link.write(wire)
        self.event(tx_hex=wire.hex(), bytes_written=count, id=self.counter, op=op, arg=arg)
        require(count == len(wire), 'short write; no retry')
        until = self.clock() + timeout
        while self.counter not in self.reports:
            if self.clock() >= until:
                raise TimeoutError('Missing response; no command retry')
            self.pump()
        result = self.reports[self.counter]
        require(result['result'] == 0, 'command rejected: ' + str(result))
        require(result['kind'] == EXPECTED_KIND[op], 'response kind mismatch')
        if op in (1, 31, 2, 34):
            self.active = None
        return result

    def capture_g01(self):
        self.phase = 'g01-15s'
        before = self.parse_errors
        started = self.clock()
        self.event(event='g01_capture_begin', requested_seconds=15)
        with (self.out / 'g01-15s-serial.bin').open('xb') as raw:
            self.g01_raw = raw
            try:
                while self.clock() - started < 15:
                    self.pump()
            finally:
                self.g01_raw = None
        result = summarize_g01([r for r in self.rows if r['phase'] == self.phase], self.parse_errors - before)
        result.update(host_elapsed_seconds=self.clock() - started, requested_seconds=15)
        self.event(event='g01_capture_end', result=result)
        return result

    def close(self):
        try:
            if self.link.is_open:
                self.link.close()
        finally:
            if self.pending:
                self.event(event='partial_tail', line_hex=self.pending.hex())
            self.raw.close()
            self.events.close()
            self.device_file.close()
            (self.out / 'reports.json').write_text(json.dumps(list(self.reports.values()), indent=2), encoding='utf-8')


def stopped_pwm(report):
    require(report['state'] in (pwm.IDLE, pwm.DONE, pwm.FAULT) and report['used'] == 1,
            'require a previously attempted, stopped PWM rehearsal')
    require(report['owned'] == report['timer_running'] == report['actual_bits'] == 0 and
            report['restored'] == 1, 'PWM resources not restored; do not continue')


def g02_clean(report):
    require(report['state'] == report['faults'] == report['owns_adc'] == 0, 'G02 not idle/released')


def run_sequence(session, result, clear_mask=None):
    initial = session.request(40)
    session.identified = True
    result['initial_pwm'] = initial
    stopped_pwm(initial)
    if initial['faults']:
        require(clear_mask is not None and clear_mask == initial['faults'],
                'PWM fault blocks other sessions; exact --clear-pwm-fault mask required for explicit clear')
        trace = [session.request(42, index) for index in range(initial['trace_written'])]
        require([row['seq'] for row in trace] == list(range(initial['trace_written'])), 'PWM trace sequence')
        (session.out / 'pwm-before-explicit-clear.json').write_text(json.dumps(trace, indent=2), encoding='utf-8')
        result['explicit_clear'] = session.request(44)
        stopped_pwm(result['explicit_clear'])
        require(result['explicit_clear']['state'] == pwm.IDLE and result['explicit_clear']['faults'] == 0,
                'explicit clear failed or restarted')
    else:
        require(clear_mask is None, 'clear mask supplied but current fault mask is zero')
    result['g01'] = session.capture_g01()
    require(result['g01']['verdict'] == 'pass', 'G01 recovery checks failed')

    session.phase = 'g02-internal-1s'
    result['g02_before'] = session.request(0)
    g02_clean(result['g02_before'])
    result['g02_sample'] = sample = session.request(1, 1000, timeout=5)
    g02_clean(sample)
    require(sample['start_id'] == sample['id'] and sample['updates'] > 0 and sample['completions'] > 0,
            'G02 internal trigger/completion unavailable')
    require(sample['overruns'] == sample['adc_errors'] == 0, 'G02 ADC error/overrun')
    require(sample['bad_frames'] == result['g02_before']['bad_frames'] and
            sample['rx_errors'] == result['g02_before']['rx_errors'], 'new protocol errors')
    require(((sample['stop_ms'] - sample['start_ms']) & 0xffffffff) >= 1000,
            'G02 internal session ended before the requested window')
    result['pwm_after_g02'] = session.request(40)
    stopped_pwm(result['pwm_after_g02'])

    session.phase = 'relay-dry'
    result['relay_before'] = before = session.request(30)
    require(before['state'] == before['faults'] == before['written'] == 0,
            'relay already has a session/result; no automatic clear or overwrite')
    result['relay_final'] = status = session.request(31, timeout=8)
    require(status['state'] in (5, 6), 'relay DRY did not reach a terminal state')
    rows = [session.request(36, index) for index in range(status['written'])]
    (session.out / 'relay-dry-samples.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
    require([row['seq'] for row in rows] == list(range(status['written'])), 'relay sequence gap')
    with (session.out / 'relay-dry-samples.csv').open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames='seq phase at_ms done_ms bits channel start_ms end_ms raw status raw_valid frame_hex'.split())
        writer.writeheader()
        for row in rows:
            for measurement in row['samples']:
                writer.writerow(dict((key, row[key]) for key in ('seq', 'phase', 'at_ms', 'done_ms', 'bits')) | measurement)
    result['relay_analysis'] = relay.analyze(status, rows)
    result['relay_resource_reuse'] = dict(
        functional_reuse_passed=result['relay_analysis']['observation_ready'],
        direct_tim2_psc_arr_readback=False,
        note='DRY reuses restored TIM2 and checks its deadline path; no PSC/ARR fields exist on wire. '
             'Exact register restore is covered by the offline production-port fixture.')
    require(result['relay_analysis']['observation_ready'], 'relay DRY timing/data recovery failed')
    session.phase = 'final'
    result['final_pwm'] = session.request(40)
    stopped_pwm(result['final_pwm'])
    result['final_g02'] = session.request(0)
    g02_clean(result['final_g02'])
    result.update(verdict='pass', conclusion='affected_software_resource_recovery_only')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', help='Run the disabled recovery sequence; default only prints plan')
    parser.add_argument('--port', default='COM11')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--firmware-sha256')
    parser.add_argument('--first-request-id', type=int, default=None)
    parser.add_argument('--clear-pwm-fault', type=lambda value: int(value, 0), default=None,
                        help='Explicit clear of this exact existing fault mask, after snapshot; no reset/restart')
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps(dict(mode='plan', serial_opened=False, firmware=FIRMWARE,
                              sequence=['op40: stopped/used/restored PWM',
                                        'optional exact-mask clear: op42 snapshot then op44',
                                        'G01 read-only 15 s raw capture',
                                        'G02 op0 then op1(1000 ms) internal sample',
                                        'relay op30 then op31 DRY and op36 readback',
                                        'op40/op0 final released and disabled checks'],
                              allowed_ops=sorted(ALLOWED), no_reset_or_flash=True,
                              tim2_register_readback_available=False,
                              execute_requires=['--execute', '--out NEW_DIRECTORY', '--firmware-sha256 IMAGE_HASH']), indent=2))
        return 0
    require(args.out is not None and args.firmware_sha256 is not None,
            '--execute requires --out and --firmware-sha256')
    require(re.fullmatch('[0-9a-fA-F]{64}', args.firmware_sha256) is not None, 'image SHA256 format')
    first = args.first_request_id if args.first_request_id is not None else (int(time.time() * 1000) & 0xffffffff)
    require(1 <= first <= 0xffffffff - 1024, 'first ID needs space for records; do not wrap')
    require(args.clear_pwm_fault is None or 0 < args.clear_pwm_fault <= 0xffffffff, 'clear mask')
    args.out.mkdir(parents=True, exist_ok=False)
    sources = [Path(__file__), ROOT / 'scripts/g01/g01_capture.py', ROOT / 'scripts/g02/host_diagnostics.py',
               ROOT / 'scripts/g03/pwm_disabled.py', ROOT / 'scripts/g03/relay_capture.py']
    manifest = dict(schema='post-pwm-disabled-recovery-v1', firmware=FIRMWARE,
                    firmware_sha256=args.firmware_sha256.lower(), image_hash_is_caller_supplied=True,
                    port=args.port, baud=115200, first_request_id=first,
                    started_utc=dt.datetime.now(dt.timezone.utc).isoformat(), evidence_scope=['bench'],
                    physical_valid=0, physical_calibration_changed=False, power_output_requested=False,
                    reset_or_flash_performed=False, allowed_ops=sorted(ALLOWED),
                    explicit_clear_mask=args.clear_pwm_fault,
                    source_sha256={str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources})
    (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    result = dict(verdict='fail', scope='post-PWM G01/G02/relay DRY software resource recovery',
                  physical_output_tested=False, physical_valid=0)
    # Serial is imported/opened only when explicitly running this CLI.
    import serial
    link = serial.Serial()
    link.port, link.baudrate, link.timeout, link.write_timeout = args.port, 115200, .05, 1
    link.dtr = link.rts = False
    session = Session(link, args.out, first)
    try:
        link.open()
        run_sequence(session, result, args.clear_pwm_fault)
    except (Exception, KeyboardInterrupt) as error:
        result['error'] = repr(error)
        # One STOP for an uncertain disabled start; no retry, clear or restart.
        if session.identified and session.active is not None:
            operation = 2 if session.active == 1 else 34
            try:
                result['stop_after_error'] = session.request(operation)
            except Exception as stop_error:
                result['stop_error'] = repr(stop_error)
    finally:
        session.close()
        result['start_attempts'] = sorted(session.start_attempts)
        result['ended_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
        result['sha256'] = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                            for path in args.out.iterdir() if path.is_file()}
        (args.out / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
    return 0 if result['verdict'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
