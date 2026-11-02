"""Capture one disabled PWM rehearsal, or query/read an existing result.

Outputs must remain disabled in every response. This program never resets,
flashes, enables a physical output, or retries a start request. The firmware
hash is a caller-supplied image identity; the wire firmware label is checked
separately and does not independently prove the supplied image hash.
"""
import argparse
import binascii
import csv
import hashlib
import json
from pathlib import Path
import re
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'g02'))
from host_diagnostics import frame

FIRMWARE = 'g03-pwm-disabled-r1'
STATUS = ('id result state faults used owned scenario start_id start_us stop_us '
          'now_us run_us sample_count raw raw_min raw_max last_sample_us '
          'max_sample_gap_us max_irq_gap_us irq_count trace_written trace_overflow '
          'tim_hz adc_hz timer_hz arr ccr dtg actual_bits timer_running restored '
          'power_capable physical_valid').split()
TRACE = 'id result seq event us raw flags ccr cnt phase actual_bits'.split()
IDLE, PREPARING, RUNNING, DONE, FAULT = range(5)
ALLOWED_OPS = {40, 41, 42, 43, 44, 45, 46, 47, 49}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def parse(line):
    """Verify the exact schema, CRC and disabled-output invariants."""
    try:
        body, crc = line.rstrip(b'\r\n').rsplit(b'*', 1)
    except ValueError as exc:
        raise ValueError('Missing CRC') from exc
    require(re.fullmatch(b'[0-9A-F]{4}', crc) is not None, 'CRC encoding')
    require(int(crc, 16) == binascii.crc_hqx(body, 65535), 'CRC mismatch')
    parts = body.decode('ascii').split(',')
    require(len(parts) >= 2 and parts[1] == FIRMWARE, 'Firmware identity')
    kind = parts[0]
    require(kind in ('#G3P', '#G3E'), 'Report kind')
    fields = STATUS if kind == '#G3P' else TRACE
    require(len(parts) == len(fields) + 2, 'Report length')
    require(all(re.fullmatch('[0-9]+', value) for value in parts[2:]), 'Unsigned fields')
    numbers = list(map(int, parts[2:]))
    require(all(value <= 0xffffffff for value in numbers), 'uint32 field range')
    report = dict(zip(fields, numbers))
    report.update(kind=kind, firmware=FIRMWARE)
    require(report['id'] != 0, 'Zero reply request ID')
    require(report['actual_bits'] == 0, 'Physical output invariant')
    require(report['raw'] <= 4095, '12-bit raw field')
    if kind == '#G3P':
        require(report['state'] <= FAULT, 'State range')
        for key in ('used', 'owned', 'timer_running', 'restored'):
            require(report[key] in (0, 1), 'Boolean field: ' + key)
        require(report['power_capable'] == report['physical_valid'] == 0,
                'Power/calibration invariant')
        require(report['raw_min'] <= 4095 and report['raw_max'] <= 4095,
                '12-bit extrema')
        if report['sample_count']:
            require(report['raw_min'] <= report['raw_max'], 'Raw extrema order')
        if report['state'] in (RUNNING, DONE):
            require(report['used'] == 1, 'Running/completed token must be consumed')
    elif report['result'] == 0:
        require(0 <= report['event'] <= 5, 'Trace event range')
    return report


def ok(report, expected=0):
    require(report['result'] == expected, 'Rejected command: ' + str(report))
    return report


class Session:
    """One owner of the link; start uncertainty is retained until close.

    send() and receive() are separate because firmware defers replies while a
    run is active. Test drivers may send STOP/heartbeat after send(41, ...),
    then receive the later command's response. There is no resend helper.
    """
    def __init__(self, link, out):
        self.link, self.out = link, Path(out)
        self.raw = (self.out / 'serial.bin').open('xb')
        self.events = (self.out / 'events.jsonl').open('x', encoding='utf-8')
        self.pending = b''
        self.counter = int(time.time() * 1000) & 0xffffffff
        self.identified = False
        self.start_sent = False
        self.reset_seen = False
        self.last_status = None
        self.reports = []
        self.sent = {}
        self.closed = False

    def event(self, **values):
        self.events.write(json.dumps(dict(host_monotonic=time.monotonic(), **values)) + '\n')
        self.events.flush()

    def send(self, op, arg=0):
        require(op in ALLOWED_OPS, 'Disabled PWM operation allowlist')
        require(type(arg) is int and 0 <= arg <= 0xffffffff, 'Argument uint32')
        if op in (40, 43, 44, 45, 49):
            require(arg == 0, 'Operation requires argument zero')
        if op == 47:
            require(1 <= arg <= 300000, 'Foreground stall range')
        if op == 41:
            require(1000 <= arg <= 200000, 'Rehearsal duration range')
            require(self.identified and self.last_status is not None,
                    'Identify the disabled firmware before starting')
            require(not self.start_sent and not self.reset_seen, 'Start already attempted; no retry')
            status = self.last_status
            require(status['state'] == IDLE and status['used'] == status['owned'] ==
                    status['faults'] == status['timer_running'] == 0,
                    'Require unused idle board; no automatic clear or reset')
        require(self.counter < 0xffffffff, 'Request ID exhausted; do not wrap')
        self.counter += 1
        request_id = self.counter
        wire = frame(request_id, op, arg)
        # Consume before write: partial delivery or a write exception is uncertain.
        if op == 41:
            self.start_sent = True
        self.sent[request_id] = (op, arg)
        self.event(tx_attempt_hex=wire.hex(), id=request_id, op=op, arg=arg)
        written = self.link.write(wire)
        self.event(tx_hex=wire.hex(), id=request_id, op=op, arg=arg, bytes_written=written)
        require(written == len(wire), 'Short serial write; command will not be replayed')
        return request_id

    def receive(self, wanted, timeout=8):
        require(wanted in self.sent, 'Unknown request ID')
        until = time.monotonic() + timeout
        while True:
            while b'\n' in self.pending:
                line, self.pending = self.pending.split(b'\n', 1)
                if line.startswith(b'#BOOT,') and self.identified:
                    self.reset_seen = True
                    raise RuntimeError('Device reset; do not replay or restart')
                if not line.startswith((b'#G3P,', b'#G3E,')):
                    continue
                report = parse(line)
                self.reports.append(report)
                self.event(report=report)
                if report['kind'] == '#G3P':
                    self.last_status = report
                    self.identified = True
                if report['id'] == wanted:
                    op = self.sent[wanted][0]
                    if report['result'] == 0:
                        require(report['kind'] == ('#G3E' if op == 42 else '#G3P'),
                                'Response kind does not match request')
                    return report
            require(len(self.pending) <= 4096, 'Unterminated oversized report')
            if time.monotonic() >= until:
                raise TimeoutError('No matching response; command will not be replayed')
            data = self.link.read(max(1, min(self.link.in_waiting, 4096)))
            self.raw.write(data)
            self.raw.flush()
            self.pending += data

    def request(self, op, arg=0, timeout=8):
        return self.receive(self.send(op, arg), timeout)

    def close(self):
        if self.closed:
            return
        try:
            if self.link.is_open:
                self.link.close()
        finally:
            self.raw.close()
            self.events.close()
            (self.out / 'reports.json').write_text(json.dumps(self.reports, indent=2), encoding='utf-8')
            self.closed = True

    finish = close


def readable_terminal(status):
    require(status['state'] in (DONE, FAULT), 'Terminal result not reached')
    require(status['used'] == 1, 'Terminal run token not consumed')
    require(status['timer_running'] == status['actual_bits'] == 0,
            'Stopped result still runs timer/output')
    require(not status['owned'] or status['state'] == FAULT,
            'Only a latched cleanup failure may retain ownership for stable trace readout')


def terminal(status):
    readable_terminal(status)
    require(status['owned'] == 0, 'Stopped result still owns resources')
    require(status['restored'] == 1, 'Original ADC/TIM configuration not restored')


def read_records(session, status):
    readable_terminal(status)
    rows = [ok(session.request(42, index)) for index in range(status['trace_written'])]
    require([row['seq'] for row in rows] == list(range(status['trace_written'])),
            'Trace gap, duplicate or out-of-order record')
    return rows


def analyze(status, rows):
    """Data integrity and observed software timing, never physical power timing."""
    readable_terminal(status)
    require(len(rows) == status['trace_written'], 'Trace count mismatch')
    require([row['seq'] for row in rows] == list(range(len(rows))),
            'Trace gap, duplicate or out-of-order record')
    require(all(row['actual_bits'] == 0 for row in rows), 'Output recorded in trace')
    elapsed = (status['stop_us'] - status['start_us']) & 0xffffffff
    require(elapsed < 0x80000000, 'Ambiguous stop time or clock ordering')
    samples = [row for row in rows if row['event'] == 2]
    preflight = [row for row in rows if row['event'] == 0]
    return dict(conclusion='completed_disabled' if status['state'] == DONE and not status['faults']
                else 'fault_latched_disabled',
                observed_software_window_us=elapsed, requested_window_us=status['run_us'],
                deadline_difference_us=elapsed-status['run_us'],
                retained_sample_records=len(samples),
                retained_preflight_records=len(preflight),
                retained_invalid_sample_records=sum(bool(row['flags'] & 0x90) or row['raw'] in (0,4095)
                                                    for row in samples),
                total_adc_samples=status['sample_count'], trace_overflow=status['trace_overflow'],
                max_sample_gap_us=status['max_sample_gap_us'],
                max_irq_gap_us=status['max_irq_gap_us'],
                stop_events=[row for row in rows if row['event'] in (3, 4)],
                restoration_complete=bool(status['restored'] and not status['owned']),
                physical_valid=0, physical_output_tested=False,
                note='Trace is decimated; event2 flags are ADC ISR bits (EOC/EOS are normal). '
                     'Raw/flags retained, no missing sample inferred as zero.')


def scenario_verdict(status, scenario):
    """Only the selected disabled fixture outcome; no physical safety claim."""
    require(scenario in range(9), 'Unknown disabled scenario')
    expected = {0: 0, 1: 1 << 3, 2: 1 << 2, 3: 1 << 4, 4: 1 << 5,
                5: 1 << 5, 6: 1 << 16, 7: 1 << 6, 8: 0}[scenario]
    expected_state = FAULT if expected else DONE
    elapsed = (status['stop_us'] - status['start_us']) & 0xffffffff
    deadline_ok = (status['run_us'] <= elapsed <=
                   status['run_us'] + 100 + status['max_irq_gap_us'])
    passed = (status['state'] == expected_state and status['faults'] == expected and
              status['owned'] == 0 and status['restored'] == 1 and
              (status['sample_count'] > 0 or scenario in (4, 5)) and
              (bool(status['trace_overflow']) == (scenario == 6)) and
              (expected != 0 or deadline_ok))
    return dict(expected_fault_mask=expected, expected_state=expected_state,
                observed_deadline_within_period_and_measured_gap=deadline_ok if not expected else None,
                verdict='pass' if passed else 'fail', scope='selected_disabled_scenario_only')


def capture(session, *, start=False, run_us=100000, scenario=0):
    result = dict(evidence_scope=['bench'], mode='disabled_pwm', trigger_sent=False, verdict=None)
    rows = []
    try:
        status = ok(session.request(40))
        result['initial'] = status
        if start:
            require(status['state'] == IDLE and not status['used'] and not status['owned'] and
                    not status['faults'] and not status['timer_running'], 'Unused idle board required')
            ok(session.request(46, scenario))
            # Set uncertainty flag before attempting start, including write failures.
            result['trigger_sent'] = True
            start_id = session.send(41, run_us)
            result['start_request_id'] = start_id
            status = ok(session.receive(start_id))
            require(status['start_id'] == start_id, 'Run/request identity mismatch')
        result['final'] = status
        if status['state'] in (DONE, FAULT):
            rows = read_records(session, status)
            result['analysis'] = analyze(status, rows)
            if start:
                result['scenario_check'] = scenario_verdict(status, scenario)
                result['verdict'] = result['scenario_check']['verdict']
            if not result['analysis']['restoration_complete']:
                result['verdict'] = 'fail'
                result['cleanup_error'] = 'Stable failed trace retained; resource restoration incomplete'
        elif start:
            raise ValueError('Rehearsal did not finish')
        result['data_integrity'] = 'pass'
    except Exception as error:
        result['error'] = repr(error)
        result['verdict'] = 'fail'
        if session.identified:
            try:
                result['stop_after_error'] = session.request(43)
            except Exception as stop_error:
                result['stop_error'] = repr(stop_error)
            # A rejected start may already have retained preflight observations.
            # Query once after the single STOP attempt, even if its reply failed;
            # terminal readback is idempotent and never retries the start.
            try:
                failure_status = ok(session.request(40))
                result['status_after_error'] = failure_status
                if (not rows and failure_status['used'] and
                        failure_status['state'] in (DONE, FAULT)):
                    rows = read_records(session, failure_status)
                    result['failure_analysis'] = analyze(failure_status, rows)
            except Exception as read_error:
                result['failure_read_error'] = repr(read_error)
    finally:
        result['start_attempted_in_session'] = session.start_sent
        session.close()
        (session.out / 'trace.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
        with (session.out / 'trace.csv').open('x', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=['firmware', 'kind'] + TRACE)
            writer.writeheader()
            writer.writerows(rows)
        result['sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in session.out.iterdir() if p.is_file()}
        (session.out / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--firmware-sha256', required=True)
    parser.add_argument('--start', action='store_true', help='one explicit disabled rehearsal; no retry')
    parser.add_argument('--run-us', type=int, default=100000)
    parser.add_argument('--scenario', type=int, default=0)
    args = parser.parse_args()
    if not re.fullmatch('[0-9a-fA-F]{64}', args.firmware_sha256):
        parser.error('--firmware-sha256 must contain 64 hex digits')
    if not 1000 <= args.run_us <= 200000 or args.scenario not in range(9):
        parser.error('Invalid rehearsal duration or scenario')
    if not args.start and args.scenario:
        parser.error('--scenario requires --start; reconnect defaults to query/read only')
    args.out.mkdir(parents=True, exist_ok=False)
    manifest = dict(firmware=FIRMWARE, firmware_sha256=args.firmware_sha256.lower(),
                    mode='disabled_pwm', explicit_start=args.start, run_us=args.run_us,
                    scenario=args.scenario, power_capable=0, physical_valid=0,
                    tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    reset_or_flash_performed=False)
    (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    import serial
    link = serial.Serial()
    link.port, link.baudrate = args.port, 115200
    link.timeout, link.write_timeout = .05, 1
    link.dtr = link.rts = False
    session = Session(link, args.out)
    try:
        link.open()
    except Exception:
        session.close()
        raise
    result = capture(session, start=args.start, run_us=args.run_us, scenario=args.scenario)
    print(json.dumps(result, indent=2))
    return 1 if 'error' in result or result.get('verdict') == 'fail' else 0


if __name__ == '__main__':
    raise SystemExit(main())
