import sys,unittest,binascii,importlib.util
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
