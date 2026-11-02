import binascii,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/g03'))
from disabled_diagnostics import Session,parse,FIELDS
def reply(**values):
    d=dict.fromkeys(FIELDS,0);d.update(id=1,synthetic=1);d.update(values)
    body=('#G03,g03-adc-r3,'+','.join(str(d[x]) for x in FIELDS)).encode()
    return body+('*%04X\n'%binascii.crc_hqx(body,65535)).encode()
class Link:
    def __init__(self,parts):self.parts=list(parts);self.is_open=True;self.writes=[]
    @property
    def in_waiting(self):return len(self.parts[0]) if self.parts else 0
    def read(self,n):return self.parts.pop(0) if self.parts else b''
    def write(self,b):self.writes.append(b);return len(b)
    def close(self):self.is_open=False
class TestHost(unittest.TestCase):
    def session(self,parts):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        s=Session(Link(parts),Path(temp.name));self.addCleanup(s.finish);return s
    def test_crc_numeric_schema(self):
        self.assertEqual(parse(reply())['synthetic'],1)
        for b in (reply().replace(b'*',b'*0'),reply(state='NaN'),reply(state=-1),reply(state=2**32)):
            with self.assertRaises(ValueError):parse(b)
    def test_fragment_and_metadata(self):
        b=b'#META,x\n'+reply();s=self.session([b[:7],b[7:11],b[11:]])
        self.assertEqual(s.receive(1,.1)['id'],1)
    def test_fail_closed_on_capability_or_real_output(self):
        for fields in ({'actual_bits':1},{'power_capable':1},{'synthetic':0}):
            s=self.session([reply(**fields)])
            with self.assertRaises(RuntimeError):s.receive(1,.1)
            self.assertFalse(s.link.writes)
    def test_reboot_no_replay(self):
        s=self.session([b'#BOOT,new\n']);s.identified=True
        with self.assertRaises(RuntimeError):s.receive(1,.1)
        self.assertFalse(s.link.writes)
    def test_timeout_and_id_exhaustion(self):
        s=self.session([])
        with self.assertRaises(TimeoutError):s.receive(1,.001)
        s.counter=0xffffffff
        with self.assertRaises(RuntimeError):s.send(11,100)
        self.assertFalse(s.link.writes)
if __name__=='__main__':unittest.main()
