"""Host protocol and fail-closed capture checks. No hardware access."""
import binascii
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts/g03'))
import pwm_disabled as p


def wire(kind, values, firmware=p.FIRMWARE):
    fields = p.STATUS if kind == '#G3P' else p.TRACE
    body = ','.join([kind, firmware] + [str(values[key]) for key in fields]).encode('ascii')
    return body + ('*%04X\r\n' % binascii.crc_hqx(body, 65535)).encode('ascii')


def status(**extra):
    values = dict.fromkeys(p.STATUS, 0)
    values.update(id=101, restored=1, raw_min=4095, timer_hz=1000000,
                  tim_hz=400000000, adc_hz=64000000, arr=2000, ccr=1000)
    values.update(extra)
    return values


def finished(**extra):
    values = status(state=p.DONE, used=1, start_id=101, start_us=100, stop_us=100100,
                    now_us=100200, run_us=100000, sample_count=10000,
                    raw=1250, raw_min=1200, raw_max=1300, trace_written=2,
                    max_irq_gap_us=105, max_sample_gap_us=12)
    values.update(extra)
    return values


def trace(**extra):
    values = dict.fromkeys(p.TRACE, 0)
    values.update(id=101, seq=0, event=2, us=100, raw=1250, ccr=1000, phase=p.RUNNING)
    values.update(extra)
    return values


class Link:
    def __init__(self, replies=()):
        self.buffer = b''.join(replies)
        self.writes = []
        self.is_open = True
        self.partial = False

    @property
    def in_waiting(self):
        return len(self.buffer)

    def write(self, value):
        self.writes.append(value)
        return len(value) - int(self.partial)

    def read(self, count):
        result, self.buffer = self.buffer[:count], self.buffer[count:]
        return result

    def close(self):
        self.is_open = False


class Parser(unittest.TestCase):
    def test_exact_schema_and_internal_timer_allowed(self):
        self.assertEqual(len(p.STATUS), 33)
        decoded = p.parse(wire('#G3P', status(state=p.RUNNING, used=1, owned=1, timer_running=1)))
        self.assertEqual(decoded['actual_bits'], 0)
        self.assertEqual(decoded['timer_running'], 1)
        self.assertEqual(p.parse(wire('#G3E', trace(event=0)))['event'], 0)

    def test_crc_firmware_and_length_rejected(self):
        good = wire('#G3P', status())
        with self.assertRaisesRegex(ValueError, 'CRC'):
            p.parse(good.replace(b',101,', b',102,', 1))
        with self.assertRaisesRegex(ValueError, 'Firmware'):
            p.parse(wire('#G3P', status(), 'g03-relay-r2'))
        body = good.split(b'*')[0] + b',0'
        with self.assertRaisesRegex(ValueError, 'length'):
            p.parse(body + ('*%04X' % binascii.crc_hqx(body, 65535)).encode())

    def test_output_and_calibration_invariants(self):
        for key in ('actual_bits', 'power_capable', 'physical_valid'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                p.parse(wire('#G3P', status(**{key: 1})))
        with self.assertRaises(ValueError):
            p.parse(wire('#G3E', trace(actual_bits=16)))

    def test_bad_uint_and_quality_states(self):
        for change in (dict(raw=-1), dict(now_us=0x100000000), dict(used=2),
                       dict(state=5), dict(raw=4096), dict(state=p.RUNNING,used=0),
                       dict(sample_count=1, raw_min=20, raw_max=10)):
            with self.subTest(change=change), self.assertRaises(ValueError):
                p.parse(wire('#G3P', status(**change)))

    def test_invalid_raw_is_retained_with_flags(self):
        decoded = p.parse(wire('#G3E', trace(raw=4095, flags=4)))
        self.assertEqual((decoded['raw'], decoded['flags']), (4095, 4))


class Transport(unittest.TestCase):
    def session(self, replies=()):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        link = Link(replies)
        session = p.Session(link, Path(directory.name))
        session.counter = 100
        self.addCleanup(session.close)
        return session, link

    def test_split_send_receive_and_monotonic_ids(self):
        s, link = self.session([wire('#G3P', status(id=101)), wire('#G3P', finished(id=103))])
        p.ok(s.request(40))
        start_id = s.send(41,100000)
        stop_id = s.send(43)
        self.assertEqual((start_id,stop_id),(102,103))
        self.assertEqual(s.receive(stop_id)['id'],stop_id)
        self.assertEqual(len(link.writes),3)

    def test_consumed_token_blocks_restart_even_if_clear_idle(self):
        s, link = self.session([wire('#G3P', status(used=1))])
        p.ok(s.request(40))
        with self.assertRaisesRegex(ValueError, 'unused idle'):
            s.send(41,100000)
        self.assertEqual(len(link.writes),1)

    def test_partial_start_write_never_retries(self):
        s, link = self.session([wire('#G3P', status())])
        p.ok(s.request(40))
        link.partial = True
        with self.assertRaisesRegex(ValueError,'Short serial'):
            s.send(41,100000)
        link.partial = False
        with self.assertRaisesRegex(ValueError,'already attempted'):
            s.send(41,100000)
        self.assertEqual(len(link.writes),2)

    def test_start_timeout_does_not_retry(self):
        s, link = self.session([wire('#G3P', status())])
        p.ok(s.request(40))
        request_id=s.send(41,100000)
        with self.assertRaises(TimeoutError):
            s.receive(request_id, timeout=0)
        with self.assertRaisesRegex(ValueError,'already attempted'):
            s.send(41,100000)
        self.assertEqual(len(link.writes),2)

    def test_reset_after_identification_aborts(self):
        s, link = self.session([wire('#G3P', status())])
        p.ok(s.request(40))
        link.buffer=b'#BOOT,g03-pwm-disabled-r1\r\n'
        with self.assertRaisesRegex(RuntimeError,'reset'):
            s.request(40)
        with self.assertRaisesRegex(ValueError,'no retry'):
            s.send(41,100000)

    def test_operation_allowlist_and_counter_wrap(self):
        s, link = self.session()
        for op in (1,31,32,48,50):
            with self.assertRaises(ValueError):s.send(op)
        s.counter=0xffffffff
        with self.assertRaisesRegex(ValueError,'exhausted'):s.send(40)
        self.assertFalse(link.writes)

    def test_rejected_start_retains_preflight_trace_without_restart(self):
        failed=finished(state=p.FAULT,faults=1<<8,run_us=0,sample_count=0,trace_written=2)
        replies=[wire('#G3P',status(id=101)),wire('#G3P',status(id=102)),
                 wire('#G3P',dict(failed,id=103,result=6)),
                 wire('#G3P',dict(failed,id=104,result=0)),
                 wire('#G3P',dict(failed,id=105,result=0)),
                 wire('#G3E',trace(id=106,event=0,seq=0)),
                 wire('#G3E',trace(id=107,event=4,seq=1,flags=1<<8))]
        s,link=self.session(replies)
        result=p.capture(s,start=True)
        self.assertEqual(result['verdict'],'fail')
        self.assertIn('error',result)
        self.assertEqual(result['failure_analysis']['retained_preflight_records'],1)
        self.assertEqual([int(w.split(b',')[2]) for w in link.writes],[40,46,41,43,40,42,42])
        saved=json.loads((s.out/'trace.json').read_text())
        self.assertEqual([r['event'] for r in saved],[0,4])

    def test_failed_stop_reply_still_queries_retained_failure(self):
        failed=finished(state=p.FAULT,faults=1<<8,run_us=0,sample_count=0,trace_written=1)
        replies=[wire('#G3P',status(id=101)),wire('#G3P',status(id=102)),
                 wire('#G3P',dict(failed,id=103,result=5)),
                 wire('#G3P',dict(failed,id=105,result=0)),
                 wire('#G3E',trace(id=106,event=0,seq=0))]
        s,link=self.session(replies)
        request=s.request
        def interrupted(op,arg=0,timeout=8):
            if op==43:
                s.send(op,arg)
                raise TimeoutError('simulated lost STOP reply')
            return request(op,arg,timeout)
        s.request=interrupted
        result=p.capture(s,start=True)
        self.assertEqual(result['verdict'],'fail')
        self.assertIn('stop_error',result)
        self.assertEqual(result['failure_analysis']['retained_preflight_records'],1)
        self.assertEqual([int(w.split(b',')[2]) for w in link.writes],[40,46,41,43,40,42])


class Integrity(unittest.TestCase):
    def test_sequence_missing_duplicate_reordered(self):
        for rows in ([trace()], [trace(), trace()], [trace(seq=1), trace(seq=0)]):
            with self.subTest(rows=rows), self.assertRaisesRegex(ValueError,'Trace'):
                p.analyze(finished(),rows)

    def test_restoration_required_and_wrap_duration(self):
        rows=[trace(),trace(seq=1,event=3)]
        result=p.analyze(finished(start_us=0xfffffff0,stop_us=84),rows)
        self.assertEqual(result['observed_software_window_us'],100)
        for key,value in (('owned',1),('timer_running',1),('restored',0),('used',0)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                p.terminal(finished(**{key:value}))

    def test_failed_cleanup_trace_is_readable_and_explicitly_failed(self):
        rows=[trace(),trace(seq=1,event=3)]
        failed=finished(state=p.FAULT,faults=1<<8,owned=1,restored=0)
        self.assertFalse(p.analyze(failed,rows)['restoration_complete'])
        self.assertEqual(p.scenario_verdict(failed,0)['verdict'],'fail')

    def test_invalid_record_not_interpreted_as_zero(self):
        rows=[trace(raw=4095,flags=4),trace(seq=1,event=3)]
        result=p.analyze(finished(),rows)
        self.assertEqual(result['retained_invalid_sample_records'],1)
        self.assertEqual(rows[0]['raw'],4095)
        ordinary=[trace(flags=0x0f),trace(seq=1,event=3)]
        self.assertEqual(p.analyze(finished(),ordinary)['retained_invalid_sample_records'],0)

    def test_expected_fault_is_scoped_and_unrelated_fault_fails(self):
        self.assertEqual(p.scenario_verdict(finished(),0)['verdict'],'pass')
        self.assertEqual(p.scenario_verdict(finished(state=p.FAULT,faults=8),1)['verdict'],'pass')
        self.assertEqual(p.scenario_verdict(finished(state=p.FAULT,faults=8|128),1)['verdict'],'fail')
        self.assertEqual(p.scenario_verdict(finished(state=p.FAULT,faults=1<<16,trace_overflow=1),6)['verdict'],'pass')
        self.assertEqual(p.scenario_verdict(finished(state=p.FAULT,faults=32,sample_count=0),4)['verdict'],'pass')

    def test_normal_deadline_must_not_be_early_or_unbounded(self):
        self.assertEqual(p.scenario_verdict(finished(stop_us=100099),0)['verdict'],'fail')
        self.assertEqual(p.scenario_verdict(finished(stop_us=100305),0)['verdict'],'pass')
        self.assertEqual(p.scenario_verdict(finished(stop_us=100306),0)['verdict'],'fail')


if __name__=='__main__':
    unittest.main()
