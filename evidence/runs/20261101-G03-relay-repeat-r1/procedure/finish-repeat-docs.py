import datetime,hashlib,json,shutil,subprocess
from pathlib import Path
root=Path(r'D:\ADMIN\Desktop\WEIJI\zonghe');stage=Path(__file__).parent
rp='evidence/runs/20261101-G03-relay-repeat-r1';run=root/rp
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
comparison=read(run/'comparison/comparison.json');final=read(run/'final-status/result.json')
assert comparison['run_count']==3 and comparison['all_response_and_recovery']
assert final['actual_bits']==final['faults']==0
dest=stage/'documentation';dest.mkdir(exist_ok=False);changes=[]
def write(rel,body):
    p=dest/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(body,encoding='utf-8')
    changes.append(dict(path=rel,before_sha256=sha(root/rel) if (root/rel).exists() else None,after_sha256=sha(p)))
write(rp+'/work-card.md','''# G03 同工况重复性与PWM单点准备

日期：2026-11-01。任务3及任务4的同工况短时记录：status=complete，verdict=pass（仅三次响应方向和恢复一致性）。任务5的参数计算/条件核对：已交付；真实PWM执行与完整G03验收仍未完成。

本次追加两次独立PG5命令，与此前首次实验合计三次。使用同一g03-relay-r2镜像、三节电池/33Ω负载/充电口开路，以及完全相同的100ms上限、采集和退出规则。每次先确认初始禁能，再独立显式触发；无自动循环、无异常重试、无PWM/PI。

|记录|请求id|PG5软件命令ms|完整窗口样本|AFE中位变化（码）|MCU中位变化（码）|恢复/故障|
|---|---|---|---|---|---|---|
|首次live-01|2520201630|98.528565|4|−2492.5|+0.5|已恢复 / 0|
|第二次repeat-02|2521445083|98.530290|4|−2493.0|−1.0|已恢复 / 0|
|第三次repeat-03|2521666429|98.530300|4|−2491.0|0.0|已恢复 / 0|

AFE变化按“完整窗口中位数−动作前50点中位数”复算，三次差幅为2码，仅描述这三次数据的离散程度，不宣称电流准确度或大样本重复性指标。每次均有102组有效采集，最后5个AFE样本回到各自冻结比较带，三路电芯同步下降并回升。MCU通道未跟随明显的AFE变化，不能作为已验证的快速电流保护输入。其基线开始处的暂态原样保留，没有删掉后冒充完整低噪声基线。

## 启动异常与当前档位

当前应保持运行档BOOT1=0、BOOT0=0。第二次记录前，用户按RESET后COM11状态请求超时，5秒被动监听也没有字节；SWD只读得到VTOR=0x18000000，CFSR/HFSR=0，未进入r2应用。没有发送真实触发。一次Hot Plug软件复位后恢复r2、IDLE、输出0及live_used=0，再执行第二次。

第二次已保存并复算恢复后，为第三次另行执行一次显式软件复位，确认IDLE后单独发送一次新请求。不是重放第二次命令，也没有自动复位/循环脚本。手动复位未进入应用的根因仍未确认，不能将软件复位恢复算作新一轮冷启动通过。所有无响应及启动寄存器记录保留。

最终查询仍为DONE=5、faults=0、actual_bits=0、live_used=1。第三次结果保持锁存，本轮未重新烧录或改变固件、阈值、脉冲长度。

## 交付与下一项

- [三次对照指标](comparison/comparison.json)、[对照CSV](comparison/comparison.csv)、[时间对齐曲线](comparison/aligned-responses.png)。
- [第二次原始结果](repeat-02/result.json)、[第三次原始结果](repeat-03/result.json)；各自含manifest、serial.bin、events.jsonl、samples.json/CSV、response.png及derived中的标称换算/停止事件/哈希。
- [冻结规则](conditions-frozen.json)、conditions-ready-02/03.json、[最终查询](final-status/result.json)。
- [PWM准备分析](pwm-preparation.md)、[机器可读缺项](pwm-readiness.json)、[软件交付与8项验证](software-delivery/manifest.json)。
- [比较工具](../../../scripts/g03/compare_relay_runs.py)、[PWM时序工具](../../../scripts/g03/pwm_point_plan.py)、[绘图工具](../../../scripts/g03/plot_relay_comparison.py)。

下一项优先定位PA1电流反馈路径或落实独立的快速过流保护，并确认驱动映射、有效死区和输入能量约束，再接真实PWM执行适配层。当前不会因继电器重复成功就把PWM门打开。任务4的更长记录也未执行，原33Ω/25W标签不作为已核验的连续散热能力。
''')
write(rp+'/pwm-preparation.md','''# G03 PWM单点准备：已落实部分与剩余条件

本轮已交付可执行的离线时序/CCR计算与条件核对工具，8项测试通过。现有固件保持g03-relay-r2，PWM没有启动；没有为尚缺实物依据的参数填写默认起点。

## 已核对到实际代码和数据

|项|当前事实|下一步需要落实的内容|
|---|---|---|
|定时器|TIM1时钟400MHz，PSC=0，中心对齐ARR=2000，对应100kHz；RCR=1|继承已测时钟/更新证据，真实启动前核验寄存器与构建身份|
|固定D|课程0.90→0.40对应CCR1800→800；已有禁能固定CCR和状态机|该序列是课程点，不是本板已批准的实物扫描范围；真实起点仍为null|
|死区|main.c配置DeadTime=0，DTR2预装载开启|确认PA9/PF7到实际驱动高/低侧的映射、MOS及有效关断余量，再设置有依据的非零死区并回读|
|Break|Break/Break2都关闭，自动输出恢复关闭|先确定故障源、有效电平及物理连接，不能仅打开BKE就声称有硬件过流保护|
|快速电流路径|源码I_AD=PA1、ADC1_INP1；三次实际MCU中位变化+0.5/−1/0码，AFE约−2492码|定位PA1是否接到同一电流信号、输入是否受连接/工作模式影响；修改换算系数不能产生缺失的物理响应|
|现有真实ADC模块|g03_adc_port.c为禁能诊断，编译检查禁止打开输出门|可沿用其采样/失效测试，但不能直接当成带载执行适配器|
|输入能量与退出|三节真实电池；转换器峰值电流/电压、供能源电流约束、允许D/时长仍无实物依据|33Ω外部负载不能限制内部半桥交越电流；需要对应供能路径/保护条件，而不只是缩短串口命令|

AFE当前21ms实际采样周期可观察趋势，不能替代100kHz功率切换的快速过流路径。GPIO撤销与AFE恢复只给出本次低速观测，不给出Vgs交越、触点或微秒级停止证据。

## 本轮实现

`pwm_point_plan.py`计算中心对齐频率、请求D到整数CCR的量化值，以及STM32N6四段DTG编码。死区计算向上取整到可表示值，越界拒绝，不会截断或回绕为0；支持CKD=1/2/4。计算器不选定本板安全死区，不包含串口/寄存器写入。`--root <工程> --comparison <comparison.json> --out <新json>`会读取实际源码和hardware-profile，输出明确缺项，当前power_ready=false。

测试覆盖四段DTG边界、全部区间向上量化、时钟/CKD非法值、CCR量化到边界、重复数据不能算独立运行、冻结条件变化不能混合判定、单次数据不宣称重复性通过。已有固件构建与板测证据沿用，无新固件因此不重复构建/烧录。

参数编码依据为工程内ST提供的stm32n6xx_ll_tim.h中`__LL_TIM_CALC_DEADTIME`四段范围及CMSIS的8位DTG定义；参考[ST RM0486](https://www.st.com/resource/en/reference_manual/dm00769900.pdf)。已核对[EGMICRO产品页](https://www.egmicro.com/products/filter_drive?category_id=28&lang=en)对EG3112高有效HIN/LIN、闭锁及死区功能的说明；这些是器件资料，不能确认本板实际器件、接线或有效死区。PWM的剩余问题是上表具体路径与条件，不是要求用户重新做一整套无关的软件检查。
''')
m=read(run/'manifest.json');m.update(status='complete',verdict='pass',verdict_scope='same-condition relay direction/recovery only',evidence_scope=['static','simulation','bench'],actual_new_triggers=2,total_independent_triggers=3,report='work-card.md',pwm_power_executed=False,pwm_ready=False,physical_valid=0,formal_G03_verdict=None)
write(rp+'/manifest.json',json.dumps(m,ensure_ascii=False,indent=2))
status=(root/'instructions/STATUS.md').read_text(encoding='utf-8')
status=status.replace('日期：2026-11-01。本表为正式阶段验收状态；本轮单次探索任务已完成，不能替代阶段整体验收。','日期：2026-11-01。本表为正式阶段验收状态；同工况三次继电器探索已完成，PWM单点准备与具体缺项另行记录。')
status=status.replace('首次单次PG5探索已完成，观察到响应并恢复：命令98.528565ms，4组完整窗口观测，最终输出0/故障0；未执行PWM开环或PI，完整开环验收待推进','三次独立PG5同工况观察均响应并恢复，命令98.528565—98.530300ms，每次4组完整窗口样本，最终输出0/故障0；已交付PWM参数工具，实际PWM因反馈/死区/保护及输入约束尚未落实而未执行')
status=status.replace('完成结果保留，未重启、未清除真实结果或重复动作。','第三次完成结果保留，当前运行档；此前通过独立软件复位准备新一轮单次入口，每次均单独请求，不自动循环。')
status=status.replace('本轮先完成r1禁能实测及G01/G02补测，再固定r2观察边界并验证本镜像禁能演练，最后执行一次真实命令。','此前完成r1禁能实测及G01/G02补测，固定r2观察边界并完成首次真实命令；用户继续G03后，沿用同一条件追加两次独立记录。')
status=status.replace('后续仍按[总推进计划](G03-无探头条件下的推进计划.md)推进独立的G03后续任务；本轮终点已到首次真实响应与分析，没有自动扩展到PWM或重复实验。','最新交付：[重复性工作卡](../'+rp+'/work-card.md)、[三次曲线](../'+rp+'/comparison/aligned-responses.png)、[PWM准备](../'+rp+'/pwm-preparation.md)。AFE三次中位响应−2492.5/−2493/−2491码；MCU为+0.5/−1/0码，不能作为已验证的快速反馈。手动RESET后曾停留ROM且串口无响应，软件复位恢复；该启动问题保留，未新增冷启动通过结论。下一项优先落实PA1反馈或独立快速过流路径、驱动死区及供能约束，再接真实PWM适配器。')
write('instructions/STATUS.md',status)
log=(root/'instructions/RUNLOG.md').read_text(encoding='utf-8')
write('instructions/RUNLOG.md',log+'''\n\n## 2026-11-01 G03三次同工况重复性与PWM准备

用户要求继续G03，按总计划任务3固定两次追加记录，沿用r2固件和全部退出条件。第二次前手动RESET后UART无响应，5秒被动监听0字节；Hot Plug只读VTOR=0x18000000，CFSR/HFSR=0。未发真实启动；一次软件复位恢复应用、默认禁能和未使用单次状态。第二次完成并复算恢复后，第三次通过另一次显式软件复位准备，单独发送新请求。无自动重放、循环或延长。

三次命令98.528565/98.530290/98.530300ms，各有4组完整窗口样本，AFE中位变化−2492.5/−2493/−2491码，均恢复且故障0；MCU变化仅+0.5/−1/0码。新增比较与时序工具，8项针对性测试通过，原始/派生数据、时间对齐曲线和启动异常日志已归档。PWM源码DeadTime=0、Break禁用，快速反馈实际响应及输入约束未落实；只完成软件参数准备，未打开PWM门或改动固件。最终DONE、live_used=1、输出0。见evidence/runs/20261101-G03-relay-repeat-r1/work-card.md。
''')
hp=read(root/'instructions/specs/hardware-profile.json')
hp['g03_relay_repeatability']=dict(run_id=run.name,new_triggers=2,total_triggers=3,firmware='g03-relay-r2',conditions_unchanged=True,afe_delta_median_codes=[-2492.5,-2493,-2491],mcu_delta_median_codes=[.5,-1,0],all_recovered=True,final_output_bits=0,physical_valid=0,report=rp+'/work-card.md')
hp['g03_relay_latest_result'].update(report=rp+'/work-card.md',latest_trial='repeat-03',total_independent_trials=3)
hp['g03_pwm_preparation']=dict(power_ready=False,pwm_executed=False,current_feedback_path_verified=False,programmed_deadtime=0,break_enabled=False,evidence=rp+'/pwm-readiness.json',physical_limits_unchanged=True)
write('instructions/specs/hardware-profile.json',json.dumps(hp,ensure_ascii=False,indent=2)+'\n')
for item in changes:
    current=root/item['path'];assert (sha(current) if current.exists() else None)==item['before_sha256']
history=run/'documentation-delivery';history.mkdir(exist_ok=False)
for item in changes:
    p=root/item['path']
    if p.exists():
        old=history/'before'/item['path'];old.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,old)
    p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dest/item['path'],p)
    assert sha(p)==item['after_sha256']
html=root/'instructions/BMS实施与验收指南.html';old=history/'before/instructions/BMS实施与验收指南.html';old.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(html,old)
r=subprocess.run([r'D:\Program Files\nodejs\node.exe',str(root/'instructions/validation/render_html.cjs')],capture_output=True)
(history/'html.stdout').write_bytes(r.stdout);(history/'html.stderr').write_bytes(r.stderr);assert r.returncode==0
changes.append(dict(path='instructions/BMS实施与验收指南.html',before_sha256=sha(old),after_sha256=sha(html)))
(history/'manifest.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2),encoding='utf-8')
for name in ['finish-repeat-docs.py','finalize-repeat-data.py']:shutil.copy2(stage/name,run/'procedure'/name)
production=read(root/'evidence/runs/20261101-G03-relay-r2/production-source-manifest.json')
for item in production['files']:assert sha(root/item['path'])==item['sha256'],item['path']
for trial in ['repeat-02','repeat-03']:
    r=read(run/trial/'result.json')
    for n,digest in r['sha256'].items():assert sha(run/trial/n)==digest,n
verify=dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),production_source_files_unchanged=len(production['files']),new_actual_triggers=2,total_independent_trials=3,all_recorded_raw_hashes_match=True,final_output_bits=0,formal_G03_verdict=None)
(history/'verification.json').write_text(json.dumps(verify,indent=2),encoding='utf-8')
inventory={str(p.relative_to(run)).replace('\\','/'):sha(p) for p in run.rglob('*') if p.is_file() and 'documentation-delivery/before/' not in str(p.relative_to(run)).replace('\\','/')}
(history/'inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(verify,indent=2))
