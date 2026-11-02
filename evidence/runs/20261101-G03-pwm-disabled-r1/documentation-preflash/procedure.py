from pathlib import Path
import json,shutil,hashlib,datetime
S=Path(__file__).parent;R=Path(r'D:\ADMIN\Desktop\WEIJI\zonghe');E=R/'evidence/runs/20261101-G03-pwm-disabled-r1'
out=E/'documentation-preflash';out.mkdir(exist_ok=False)
for rel in ('instructions/STATUS.md','instructions/RUNLOG.md','instructions/specs/hardware-profile.json'):
    p=out/'before'/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(R/rel,p)
status=R/'instructions/STATUS.md'
s=status.read_text(encoding='utf-8');anchor='实板当前运行g03-relay-r2'
note='''新增单次 PWM 禁能 target 已接入并完成双构建：`g03-pwm-disabled-r1`，Release HEX SHA256 `9126778404c6f9a9890ab729522f7fbd9fe7fe0a380436694494ebecde81f9fb`。核心21组、port寄存器模型15组、主机19项及受影响ADC/继电器回归通过；Release 0错0警告，Debug仅原有EXTRAM警告。下载、运行身份和板测尚待执行；本次固定所有功率引脚及PB5/PG5禁能，内部TIM1触发不等于PWM引脚输出。见[禁能工作卡](../evidence/runs/20261101-G03-pwm-disabled-r1/work-card.md)。

'''
assert anchor in s;s=s.replace(anchor,note+anchor,1);status.write_text(s,encoding='utf-8')
p=R/'instructions/RUNLOG.md'
with p.open('a',encoding='utf-8') as f:f.write('''

## 2026-11-01 — 单次PWM禁能接入与双构建

- 用户授权接入、构建、下载及禁能板测。新增独立BMS_PWM_Disabled_Debug/Release，功率门编译关闭，旧target与镜像保留；实际工程修改前171份生产文件与r2基线逐项哈希相同，新快照176份。
- 使用TIM2 1MHz微秒时间基及独立100us IRQ；固定shadow CCR，ADC持续使能、真实TIM1触发、AWD/OVR先寄存器关闭、一次令牌、协议错误/STOP/缓存故障锁存。新增采集预备期与清理失败记录处理，保留ADC/TIM2共享资源恢复。
- 核心21组、生产port寄存器模型15组、主机19项，以及受影响旧ADC/继电器回归通过。Release0错0警告，Debug0错/已有EXTRAM警告1。Release SHA256为9126778404c6f9a9890ab729522f7fbd9fe7fe0a380436694494ebecde81f9fb。
- 已读取老师HEX baseline-plan及r2候选，采用显式死区来源；EG3112资料支持内置死区，DTG0不单独否决。CH1、持续ADEN、TIM1触发及6.5/11.5周期对照纳入禁能方案。未刷老师HEX，未确认实物测流传递或电气死区。
- 下载及板测待用户按现有流程切到BOOT1=1/BOOT0=0并RESET后执行，当前无新硬件结果。离线结果不替代板测，physical_valid=0，禁能夹具参数不写成真实电气限值。证据：evidence/runs/20261101-G03-pwm-disabled-r1。
''')
p=R/'instructions/specs/hardware-profile.json';h=json.loads(p.read_text(encoding='utf-8'))
h['g03_pwm_disabled_integration']=dict(run_id=E.name,firmware='g03-pwm-disabled-r1',release_hex_sha256='9126778404c6f9a9890ab729522f7fbd9fe7fe0a380436694494ebecde81f9fb',software_validation='pass',flashed_readback_verified=None,bench_verdict=None,power_capable=False,physical_valid=0,physical_limits_unchanged=True,physical_driver_identity_confirmed=False,report='evidence/runs/'+E.name+'/work-card.md')
p.write_text(json.dumps(h,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
shutil.copy2(S/'bench_pwm_disabled.py',R/'scripts/g03/bench_pwm_disabled.py')
shutil.copy2(S/'bench_pwm_disabled.py',E/'preparation/bench_pwm_disabled.py')
shutil.copy2(S/'flash_disabled.py',E/'preparation/flash_disabled.py')
shutil.copy2(Path(__file__),out/'procedure.py')
(out/'manifest.json').write_text(json.dumps(dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope=['static','build','simulation'],hardware_actions=False,files=[dict(path=x,sha256=hashlib.sha256((R/x).read_bytes()).hexdigest()) for x in ('instructions/STATUS.md','instructions/RUNLOG.md','instructions/specs/hardware-profile.json','scripts/g03/bench_pwm_disabled.py')]),indent=2),encoding='utf-8')
print('Preflash documentation and reviewed disabled bench procedure published; hardware verdicts remain null.')
