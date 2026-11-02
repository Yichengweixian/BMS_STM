import sys,unittest,binascii
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/g03'))
import adc_diagnostics as a
def wire(body):
    b=body.encode();return b+b'*%04X\n'%binascii.crc_hqx(b,65535)
class Tests(unittest.TestCase):
    def test_status_and_signed_current(self):
        n=[0]*len(a.STATUS);n[2]=-1200
        r=a.parse(wire('#G3A,g03-relay-r2,'+','.join(map(str,n))))
        self.assertEqual(r['ua'],-1200);self.assertEqual(r['power_capable'],0)
    def test_corruption(self):
        b=wire('#G3A,g03-relay-r2,'+','.join(['0']*len(a.STATUS)))
        for v in [b[:-4],b.replace(b'g03-relay-',b'g03-bad-'),b.replace(b',0',b',1',1)]:
            with self.assertRaises(ValueError):a.parse(v)
    def test_diagnostic_aggregate(self):
        nums=[1,0,3,1,64,2048,2048,131072]+[0]*12+[2048]*64
        body='#G3D,g03-relay-r2,'+','.join(map(str,nums));r=a.parse(wire(body))
        self.assertEqual(len(r['samples']),64)
        nums[-1]=2049
        with self.assertRaises(ValueError):a.parse(wire('#G3D,g03-relay-r2,'+','.join(map(str,nums))))
    def test_unsigned_and_length(self):
        nums=[0]*len(a.STATUS);nums[0]=-1
        for n in (nums,nums[:-1]):
            with self.assertRaises(ValueError):a.parse(wire('#G3A,g03-relay-r2,'+','.join(map(str,n))))
if __name__=='__main__':unittest.main()
