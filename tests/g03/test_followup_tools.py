import copy,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/g03'))
import pwm_point_plan as p
import compare_relay_runs as c

class Timing(unittest.TestCase):
    def test_dtg_boundaries(self):
        for code,ticks in [(0,0),(127,127),(128,128),(191,254),(192,256),(223,504),(224,512),(255,1008)]:self.assertEqual(p.deadtime_ticks(code),ticks)
        self.assertEqual(p.deadtime_code(318,400000000)['dtg'],128)
        self.assertEqual(p.deadtime_code(636,400000000)['dtg'],192)
        self.assertEqual(p.deadtime_code(1261,400000000)['dtg'],224)
        with self.assertRaises(ValueError):p.deadtime_code(2521,400000000)
    def test_round_up_all_ranges_and_ckd(self):
        for ckd in [1,2,4]:
            for ns in range(0,2520*ckd+1,7):
                v=p.deadtime_code(ns,400000000,ckd)
                self.assertGreaterEqual(v['represented_ns'],ns)
                if v['dtg']:self.assertLess(p.deadtime_ticks(v['dtg']-1)*2.5*ckd,ns)
    def test_fixed_duty_and_no_silent_rail(self):
        for duty,ccr in [('0.9',1800),('0.4',800),('0.50025',1001)]:
            v=p.fixed_point(duty);self.assertEqual(v['ccr'],ccr);self.assertEqual(v['center_aligned_frequency_Hz'],100000)
        for duty in ['0','1','nan','inf','0.00001']:
            with self.assertRaises((ValueError,OverflowError)):p.fixed_point(duty)
    def test_invalid_clock_does_not_wrap(self):
        for clock,ckd in [(0,1),(-1,1),(400000000,3)]:
            with self.assertRaises(ValueError):p.deadtime_code(100,clock,ckd)

class Comparison(unittest.TestCase):
    def test_duplicate_run_not_repeatability(self):
        with self.assertRaisesRegex(ValueError,'Duplicate'):c.compare(['same','same'])
    def test_no_run_is_not_pass(self):
        with self.assertRaisesRegex(ValueError,'No runs'):c.compare([])
    def test_condition_change_rejected(self):
        from unittest.mock import patch
        a=dict(rules=dict(cell_low=38365),request_id=1);b=dict(rules=dict(cell_low=38000),request_id=2)
        with patch.object(c,'summarize',side_effect=[a,b]):
            with self.assertRaisesRegex(ValueError,'conditions differ'):c.compare(['a','b'])
    def test_one_sample_study_remains_unjudged(self):
        from unittest.mock import patch
        r=dict(rules={},request_id=1,channels={'afe_current':{'delta_median':-2493}},analysis={'conclusion':'response_and_recovery','observation_ready':True},actual_bits_final=0,faults=0)
        with patch.object(c,'summarize',return_value=r):
            self.assertIsNone(c.compare(['a'])['verdict'])
if __name__=='__main__':unittest.main()
