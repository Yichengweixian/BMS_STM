from pathlib import Path
import shutil, subprocess, os, json, hashlib

base=Path(__file__).resolve().parent
root=Path('D:/ADMIN/Desktop/WEIJI/zonghe')
out=base/'d74-candidate-r1';out.mkdir(exist_ok=False)
w=out/'workspace';bsp=w/'BMS_EXv1.1/BMS_EX/BSP';test=w/'tests/g03'
shutil.copytree(root/'BMS_EXv1.1/BMS_EX/BSP',bsp)
test.mkdir(parents=True)
shutil.copytree(root/'tests/g03/power_port_fixture',test/'power_port_fixture')
shutil.copy2(root/'tests/g03/test_power_port.cpp',test/'test_power_port.cpp')
host=w/'scripts/g03';host.mkdir(parents=True)
shutil.copy2(root/'scripts/g03/power_capture.py',host/'power_capture.py')
shutil.copytree(root/'scripts/g01',w/'scripts/g01',ignore=shutil.ignore_patterns('__pycache__'))
shutil.copy2(root/'tests/g03/test_power_host.py',test/'test_power_host.py')
for name in ('g03_power_port.c','g03_power_profile.h','firmware_identity.h'):
    dest=out/'before'/name;dest.parent.mkdir(exist_ok=True);shutil.copy2(bsp/name,dest)
p=bsp/'g03_power_profile.h';t=p.read_text();t=t.replace('#define G3P_LONG_US', '#define G3P_D74_SHORT_ID 0x50393401U\n#define G3P_D74_LONG_ID 0x50393402U\n#define G3P_LONG_US');p.write_text(t)
p=bsp/'g03_power_port.c';t=p.read_text()
t=t.replace('||id==G3P_D80_LONG_ID;}','||id==G3P_D80_LONG_ID||id==G3P_D74_SHORT_ID||id==G3P_D74_LONG_ID;}')
t=t.replace('selected_ccr=(id==G3P_D80_SHORT_ID', 'selected_ccr=(id==G3P_D74_SHORT_ID||id==G3P_D74_LONG_ID)?1480U:(id==G3P_D80_SHORT_ID')
t=t.replace('selected_us=(id==G3P_D90_LONG_ID||id==G3P_D80_LONG_ID)', 'selected_us=(id==G3P_D90_LONG_ID||id==G3P_D80_LONG_ID||id==G3P_D74_LONG_ID)')
p.write_text(t)
p=bsp/'firmware_identity.h';p.write_text(p.read_text().replace('g03-power-points-r4','g03-power-d74-c1'))
p=host/'power_capture.py';t=p.read_text().replace("FW='g03-power-points-r4'", "FW='g03-power-d74-c1'")
t=t.replace('0x50393304:(1600,2000000)}','0x50393304:(1600,2000000),0x50393401:(1480,100000),0x50393402:(1480,2000000)}');p.write_text(t)
p=test/'test_power_port.cpp';t=p.read_text()
t=t.replace('int main(int argc,char**argv){','static_assert(G3P_DISCHARGE_MA==550 && G3P_CHARGE_MA==50 && G3P_CELL_LOW==33000 && G3P_CELL_HIGH==36500, "limits unchanged");\nint main(int argc,char**argv){')
t=t.replace('std::string name=argv[1];clock_read_latency=', 'std::string name=argv[1];bool d74=name.rfind("74_",0)==0;if(d74)name=name.substr(3);clock_read_latency=')
t=t.replace('keep_heartbeat=longer&&', 'if(d74)chosen=longer?G3P_D74_LONG_ID:G3P_D74_SHORT_ID;\n    keep_heartbeat=longer&&')
t=t.replace('until(3);assert(enable_count==(dry?0U:1U));', 'until(3);assert(enable_count==(dry?0U:1U));if(d74){status();assert(fields[9]==1480&&fields[10]==2000);if(!dry)assert((uint32_t)model_tim1.CCR2==1480);}')
t=t.replace('fields[8]==chosen&&fields[9]==1800','fields[8]==chosen&&fields[9]==(d74?1480:1800)');p.write_text(t)
cc=Path('D:/Program Files/JetBrains/CLion 2025.2.3/bin/mingw/bin/g++.exe')
env=os.environ.copy();env['PATH']=str(cc.parent)+os.pathsep+env.get('PATH','')
checks=out/'offline';checks.mkdir();commands=[]
def run(name,args):
    r=subprocess.run(list(map(str,args)),env=env,capture_output=True,timeout=60,cwd=out)
    (checks/(name+'.txt')).write_bytes(r.stdout+r.stderr)
    commands.append({'name':name,'argv':list(map(str,args)),'exit_code':r.returncode})
    (checks/'commands.json').write_text(json.dumps(commands,indent=2))
    if r.returncode:raise RuntimeError(name+': '+(r.stdout+r.stderr).decode(errors='replace'))
stub=test/'power_port_fixture'
run('compile',[cc,'-x','c++','-std=c++17','-O2','-Wall','-Werror','-Wno-missing-field-initializers','-Wno-misleading-indentation','-DG03_PWM_LIVE_BUILD=1','-DG3R_LIVE_PROFILE_VERIFIED=0','-I'+str(stub),'-I'+str(bsp),'-include',stub/'main.h',bsp/'g03_power_port.c',bsp/'pwm_oneshot.c',test/'test_power_port.cpp','-o',checks/'power.exe'])
cases=['normal','d80','long90','long80','74_normal','74_long90','74_dry','74_heartbeat_lost','74_stop','74_overcurrent','74_ccr','74_point_mutation']
for case in cases:run(case,[checks/'power.exe',case])
import sys
run('host',[sys.executable,test/'test_power_host.py'])
hashes={str(p.relative_to(w)):hashlib.sha256(p.read_bytes()).hexdigest() for p in w.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
(out/'source-manifest.json').write_text(json.dumps(hashes,indent=2))
(out/'result.json').write_text(json.dumps({'scope':'isolated candidate/register model/host tests','port_cases_passed':len(cases),'firmware_identity':'g03-power-d74-c1','protection_limits_unchanged':True,'hardware_access':False,'arm_image_built':False,'flashed':False,'physical_result':None},indent=2))
print(json.dumps({'path':str(out),'port_cases_passed':len(cases),'host':'pass','flashed':False}))

