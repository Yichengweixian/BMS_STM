import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('capture',ROOT/'scripts/g01/g01_capture.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def line(**updates):
    row=dict(zip(m.FIELDS, ['M','0','current_mcu_adc1','1','2','0','2048','128','1',
                           '0.900000','','A','','0','','uncalibrated-v1','','']))
    row.update(updates)
    payload=','.join(row[k] for k in m.FIELDS[:-1]).encode('ascii')
    return payload+b',%04X\r\n'%m.pec15(payload)

class RecorderTests(unittest.TestCase):
    def test_known_pec(self): self.assertEqual(m.pec15(b'\x00\x01'),0x3d6e)
    def test_nominal_and_invalid(self):
        self.assertEqual(m.parse_line(line())['raw'],'2048')
        r=m.parse_line(line(raw='',status='452',raw_valid='0',sensor_V_nominal=''))
        self.assertEqual(r['raw'],'')
    def test_tamper_and_truncate(self):
        for data in (line().replace(b'2048',b'2049'),line()[:-8],b'garbage\n'):
            with self.assertRaises(ValueError):m.parse_line(data)
    def test_reject_semantic_conflicts(self):
        cases=[dict(status='130'),dict(physical_valid='1'),dict(physical_value='0'),
               dict(reference='1.0'),dict(sensor_V_nominal='nan'),dict(sensor_V_nominal='inf'),
               dict(raw='65536'),dict(raw=''),dict(age_ms='1001'),dict(unit='V'),
               dict(channel='unknown'),dict(cal_id='calibrated'),dict(estimate='nan'),
               dict(status='1152'),dict(start_ms='100',end_ms='1')]
        for case in cases:
            with self.subTest(case=case),self.assertRaises(ValueError):m.parse_line(line(**case))
    def test_bad_pec_retained(self):
        frame=b'\x28\x23\0\0\0\0'
        frame+=int(m.pec15(frame)^1).to_bytes(2,'big')
        r=m.parse_line(line(channel='current_afe_gpio1',raw='9000',status='130',raw_valid='0',sensor_V_nominal='',frame_hex=frame.hex()))
        self.assertEqual(r['raw'],'9000')
    def test_nominal_mcu_estimate_is_not_calibration(self):
        r=m.parse_line(line(estimate='-0.606185'))
        self.assertEqual(r['physical_valid'],'0')
        self.assertEqual(r['physical_value'],'')
    def test_gaps_reset_wrap(self):
        t=m.Tracker('test')
        t.feed(m.parse_line(line(seq='0',start_ms='4294967279',end_ms='4294967280')))
        events=t.feed(m.parse_line(line(seq='2',start_ms='15',end_ms='16')))
        self.assertTrue(any(e['event']=='sequence_gap' for e in events))
        self.assertTrue(any(e['event']=='tick_wrap' for e in events))
        events=t.feed(m.parse_line(line(seq='2',start_ms='15',end_ms='16')))
        self.assertTrue(any(e['event']=='duplicate' for e in events))
        events=t.feed(m.parse_line(line(seq='0',start_ms='1',end_ms='2')))
        self.assertTrue(any(e['event']=='inferred_reset_or_out_of_order' for e in events))
        self.assertEqual(t.boot_id,'test:1')
        self.assertTrue(any(e['event']=='incomplete_group' for e in t.finish_group()))
    def test_sequence_wrap_is_not_reset(self):
        t=m.Tracker('test')
        t.feed(m.parse_line(line(seq='4294967295')))
        events=t.feed(m.parse_line(line(seq='0',start_ms='500',end_ms='501')))
        self.assertFalse(any(e['event']=='inferred_reset_or_out_of_order' for e in events))

if __name__=='__main__':unittest.main(verbosity=2)
