import sys,unittest,binascii,importlib.util,tempfile
from pathlib import Path
root=Path('D:/ADMIN/Desktop/WEIJI/zonghe')
sys.path.insert(0,str(root/'scripts/g01'))
tool=Path(__file__).resolve().parents[2]/'scripts/g03/power_capture.py'
spec=importlib.util.spec_from_file_location('power_capture',tool);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def wire(fields):
    b=','.join(map(str,fields)).encode();return b+f'*{binascii.crc_hqx(b,65535):04X}'.encode()
def status():
    x={k:0 for k in m.STATUS};x.update(id=1,profile=m.PROFILE,ccr=1800,arr=2000,run_us=100000,power_capable=1)
    return ['#G3Q',m.FW]+[x[k] for k in m.STATUS]
class Tests(unittest.TestCase):
    def outcome(self,coast=20001,active_raw=6000):
        rows=[]
        for seq,(phase,raw) in enumerate([(2,6600),(3,active_raw)]):
            d={k:0 for k in m.ROW};d.update(id=1,seq=seq,phase=phase,ccr=1800,arr=2000,begin_us=1100000+seq*40000,end_us=1110000+seq*40000)
            d['afe']=[dict(channel=ch,raw=35000 if i<3 else (raw if i==3 else 3200),raw_valid=True,status=0,start_ms=0,end_ms=1,frame_hex='00'*8) for i,ch in enumerate(m.CHANNELS)]
            rows.append(d)
        s=dict(ccr=1800,arr=2000,run_us=100000,rows=2,zero=9000,pwm_on_us=1115000,pwm_off_us=1215073,relay_on_us=1010000,relay_off_us=1215073+coast,bits=0,owned=0,restored=1,live=1,faults=0)
        with tempfile.TemporaryDirectory() as folder:return m.derive(Path(folder),s,rows)
    def test_complete_outcome(self):
        d=self.outcome();self.assertTrue(d['timing_sequence_ok'] and d['load_response_observed'])
    def test_early_relay_off_fails(self):self.assertFalse(self.outcome(coast=1)['timing_sequence_ok'])
    def test_no_load_does_not_pass(self):self.assertFalse(self.outcome(active_raw=9000)['load_response_observed'])
    def test_allowed_profiles(self):
        for profile,(ccr,us) in m.POINTS.items():
            a=status();a[2+m.STATUS.index('profile')]=profile;a[2+m.STATUS.index('ccr')]=ccr;a[2+m.STATUS.index('run_us')]=us
            self.assertEqual(m.parse(wire(a))['ccr'],ccr)
    def test_unknown_profile(self):
        a=status();a[2+m.STATUS.index('profile')]=123
        with self.assertRaises(ValueError):m.parse(wire(a))
    def test_status(self):self.assertEqual(m.parse(wire(status()))['bits'],0)
    def test_identity(self):
        a=status();a[1]='g03-pwm-disabled-r1'
        with self.assertRaises(ValueError):m.parse(wire(a))
    def test_crc(self):
        with self.assertRaises(ValueError):m.parse(wire(status())[:-1]+b'X')
    def test_duty_is_frozen(self):
        a=status();a[2+m.STATUS.index('ccr')]=1600
        with self.assertRaises(ValueError):m.parse(wire(a))
    def test_physical_valid(self):
        a=status();a[2+m.STATUS.index('physical_valid')]=1
        with self.assertRaises(ValueError):m.parse(wire(a))
    def test_afe_valid_and_corruption(self):
        d={k:0 for k in m.ROW};d.update(id=1,ccr=1800,arr=2000)
        a=['#G3L',m.FW]+[d[k] for k in m.ROW]
        for i in range(8):
            raw=35000 if i<3 else 9000;f=raw.to_bytes(2,'little')*3;f+=m.pec15(f).to_bytes(2,'big')
            a.extend([raw,0,1,0,1,f.hex()])
        self.assertTrue(all(x['raw_valid'] for x in m.parse(wire(a))['afe']))
        a[-1]='00'*8
        with self.assertRaises(ValueError):m.parse(wire(a))
    def test_missing_does_not_become_valid_zero(self):
        d={k:0 for k in m.ROW};d.update(id=1,ccr=1800,arr=2000)
        a=['#G3L',m.FW]+[d[k] for k in m.ROW]+[0,0,1,1,0,'00'*8]*8
        self.assertFalse(any(x['raw_valid'] for x in m.parse(wire(a))['afe']))
if __name__=='__main__':unittest.main()
