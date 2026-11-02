import datetime,hashlib,json,shutil,subprocess
from pathlib import Path
root=Path(r'D:\ADMIN\Desktop\WEIJI\zonghe');stage=Path(__file__).parent
dest=stage/'final-delivery';dest.mkdir(exist_ok=False)
rp='evidence/runs/20261101-G03-relay-r2';run=root/rp
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
changes=[]
def write(rel,text):
    p=dest/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')
    changes.append(dict(path=rel,before_sha256=sha(root/rel) if (root/rel).exists() else None,after_sha256=sha(p)))
def copy(rel,source):
    p=dest/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,p)
    changes.append(dict(path=rel,before_sha256=sha(root/rel) if (root/rel).exists() else None,after_sha256=sha(p)))
live=read(run/'live-01/result.json');dry=read(run/'board-rehearsal-01/result.json');st=live['final']
metrics=read(run/'live-01/derived/metrics.json');g01=read(run/'g01-recovery-analysis.json')
fw=read(run/'conditions-ready.json')['firmware_sha256']
write(rp+'/first-experiment-report.md',f'''# G03 首次单次继电器实验报告

2026-11-01，g03-relay-r2，COM11。结论：**观察到响应并恢复**。真实启动命令仅发送一次，请求编号 {st['id']}；未自动重试，未启动 PWM、PI 或充电继电器。

## 结果与判读

|项目|实测结果|解释|
|---|---|---|
|数据完整性|102组，510条通道记录，全部raw_valid=1；CRC/AFE PEC及原码复算一致|50组基线、5组窗口阶段、47组恢复阶段；无序号缺失|
|完整窗口覆盖|4组|第5组跨撤销时刻，保留但不计入完整窗口样本|
|AFE动作前基线|8995—9005码，均值8998.64，固件中心8999，比较带±30码|规则为max(20,3×基线峰峰值)，未按结果放宽|
|AFE窗口内响应|6505—6507码；完整样本相对中心为−2494、−2493、−2492、−2494码|至少3个同方向越比较带，符合冻结响应判据|
|PG5命令区间|HAL tick 66035→66134；DWT复核98.528565ms|99ms调度截止，满足本次≤100ms软件命令期限；不是触点实测时长|
|停止原因|deadline，reason=1，faults=0|没有STOP或故障提前终止|
|AFE恢复|47个恢复阶段样本，8994—9005码；最后5个均在比较带内|首个恢复样本转换区间为撤销后21—27ms；不能据此给出电气关断时间|
|三路电芯原码最低值|cell1=38536；cell7=38543；cell13=38539|均处于冻结38365—39372码区间，动作后回升|
|输出与最终态|窗口记录bits=16，其他阶段0；DONE=5，live_used=1|PG5为唯一动作位；PB5、PWM引脚及TIM1功率输出禁能；最终再次查询为0|

三路电芯基线均值分别38866.82、38868.64、38870.96码，窗口最低值相对基线约下降331、326、332码；按AFE标称100µV/码约33mV，非经参考仪器校准的压降。AFE电流原码明显变化，辅助MCU电流在窗口阶段仅1259—1260码，未呈现相同幅度变化；MCU外部电流路径问题仍未闭合，不能代替AFE观测或用其推导零电流。

本次支持“三节电池、33Ω负载、充电口开路、仅PG5动作时，AFE及电芯出现相关响应，撤销后AFE回到基线范围”这一通路结论。电流绝对值、极性、触点开断、驱动波形和独立硬件保护仍无本次证据，physical_valid始终0。

## 固件与前置证据

Release HEX SHA256：`{fw}`。Debug HEX SHA256：`460c8e260582eb9bf7299f1c9662a5eb0f78db0e90181ae17e6dd5092e639b51`。Release构建0错0警告；Debug0错、原有EXTRAM警告1条。源码变更、构建日志及映像见[交付清单](artifact-manifest.json)、delivery-manifest.json、before/、source-after/和firmware/。

r2在ROM下载模式写入并读回验证；用户恢复BOOT1=0、BOOT0=0并RESET，COM11确认g03-relay-r2、初始IDLE且输出0。随后本镜像禁能演练得到102组有效数据、4组完整窗口样本、最长采集9ms、本地窗口98.53172ms、无故障/输出。禁能完成态保存后显式清除，再发送一次op32。冻结规则原件conditions-frozen.json保持不变，conditions-ready.json仅补充本镜像已通过的证据与就绪状态。

继电器核心、生产适配层、共享协议、SPI阻塞/过期、本地截止、STOP/PEC/缓存耗尽、互斥/重放、时间回绕等离线验证见relay-checks-02。结果复核时追加relay-checks-03，补充重复请求和RX溢出压力、采集期间不发送响应，以及跨时钟回绕的98/99ms期限断言；只改测试，生产固件保持不变。G01/G02受影响回归与板测的对应关系见[补测结果表](retest-matrix.md)。

## 采集性能与恢复

20ms为调度目标，本次实际各通道起始间隔为21ms；每组最长9ms。三路电芯各转换括号2ms，AFE电流括号6ms；MCU括号在1ms时间戳分辨率内显示0ms，不能解释为零耗时。基线标准差：AFE约2.398码，三路电芯约0.865、0.686、0.774码。最坏TIM2入口间隔1.00066ms。

结束后被动记录15秒：264条有效原码，29个完整九通道组，内部缺序/重复0，常规通道周期中位数500ms、最大501ms。最后一组只收到3个通道，末尾9字节截断单独保留，未作为有效零值。最终只发op30查询，保持DONE、live_used=1、faults=0、actual_bits=0；没有清除真实结果、重启或再次触发。

## 数据与结论字段

- [真实响应曲线](live-01/response.png)、[原码CSV](live-01/samples.csv)、[完整原始串口](live-01/serial.bin)、[收发事件](live-01/events.jsonl)。
- [派生指标](live-01/derived/metrics.json)、[GPIO命令及停止事件](live-01/derived/gpio-stop-events.json)、[独立标称换算CSV](live-01/derived/nominal.csv)。标称模型未进入物理有效列，未知物理值留空。
- [冻结工况表](conditions-table.md)、[运行前就绪证据](conditions-ready.json)、[最终状态](final-status-01/result.json)、[常规采集复算](g01-recovery-analysis.json)。

原始live-01/result.json保留主机通用verdict=inconclusive，同时analysis.conclusion=response_and_recovery。该工具对无故障的真实采集统一保留保守总判定；本报告在冻结的“单次通路响应并恢复”范围作出通过判断，另存trial-result.json，不改写原记录，也不将其提升为G03整体通过。G01/G02正式标定与电气验收、G03完整PWM开环仍保持未判定。
''')
write(rp+'/conditions-table.md',f'''# 本次冻结工况与停止办法

规则在首次真实触发前冻结，原始文件[conditions-frozen.json](conditions-frozen.json)；就绪证明[conditions-ready.json](conditions-ready.json)。本表是同一规则的阅读版，不改变阈值。

|项|冻结取值/操作|依据与适用范围|
|---|---|---|
|接线|三节真实电池；放电口33Ω标称负载；充电口开路|用户已确认，沿用原接线|
|固件|g03-relay-r2，Release SHA256 {fw}|写入后读回成功，正常BOOT身份确认|
|允许输出|仅PG5；每次启动最多一次显式真实请求|PB5、PWM引脚、TIM1功率输出保持禁能|
|采样|目标20ms，实际21ms；必需通道最大年龄40ms|r1禁能及r2禁能最长9ms，窗口内4组完整观测|
|基线|50个有效样本；峰峰值≤100码；中心为四舍五入均值|冻结的软件观察规则|
|启动漂移|AFE基线最小/最大均落在8958—9042码|r1实测8994—9006码，加±36码；3×实测峰峰值|
|电芯进入与退出|三路均处38365—39372码；任一路越界立即撤销|r1实测38865—38872码，加±500码工程观察余量；约±50mV标称，非厂家额定/硬限|
|比较带|±max(20,3×该次动作前基线峰峰值)码|r2真实动作前得到±30码；不重设动作后零点|
|命令期限|99ms调度截止，DWT复核不得超过100ms|TIM2独立1ms中断，IRQ不等待SPI或串口|
|响应与恢复|至少3组完整窗口样本同方向越带；恢复观察1000ms，最后5点有效且回带|原码判据，不宣称绝对电流标定|
|异常|STOP、数据失效/过期、超区、缓存耗尽、互锁/CPU/定时异常撤销PG5并锁存|清故障不启动；重复请求不重吸合或延时|
|实际停止|正常本地截止；必要时op34 STOP；撤销后不恢复或结果不明时现场断开电池供能|用户已确认可断开电池；主机不是本地计时/保护执行者|
|次数|只执行一次，禁止自动重试或自动增加PWM|本次已执行，live_used=1|

这些是本次短时探索的工程观察边界。制造商电芯硬限、实际电流标定、负载热状态与继电器电气关断未由本实验测定，hardware-profile中的未知物理额定值不填入这些观察阈值。停止与恢复证据只来自MCU命令记录和AFE样本。
''')
write(rp+'/retest-matrix.md','''# G01/G02 补测结果表

范围：在既有r4合格软件/禁能结果基础上，完成本次采集、调度、协议改动的受影响回归。原始r1表和失败记录保留；下表为本轮完成后的结果与尚缺条件。证据简称r1/r2分别指相邻20261101-G03-relay-r1与本目录。

|项目|既有证据|本轮补测证据与结果|完成条件/仍缺项目|
|---|---|---|---|
|G01转换完成与有效性|r4九通道记录及HAL检查|r1/g01-checks-03生产AFE路径验证通过，包含专用快速路径|完成软件检查；独立参考测量另列|
|G01错误传播|r4错误标志/原码分离|PEC、SPI/ADC错误、超时、过期、饱和及无原码用例通过|错误不得变成有效零；已完成软件条件|
|G01时间戳、序号、复算|r4回放与30秒记录|r1/g01-checks-03；r2两次102组原始帧CRC、AFE PEC、原码和seq复算一致|连续索引、通道起止与质量可追溯；完成|
|G01专用采集时长/间隔|原500ms常规采集不能覆盖窗口|r1及r2禁能实测：每组≤9ms，电芯2ms、AFE电流6ms，实际21ms节拍；完整窗口4组|窗口至少3组、采集≤20ms、年龄≤40ms；完成本次条件|
|G01基线噪声|r4静态原码|r2禁能AFE峰峰9码，三电芯5/3/2码；r2真实前AFE峰峰10码|metrics.json保留均值/标准差；无物理精度结论|
|G01常规采集恢复|r4已恢复|r1恢复266条，29完整组；r2恢复264条，29完整组；全raw有效，内部缺序/重复0|已完成；r1开头截断与r2结尾截断分开保留|
|G02启动/停止/锁存|r4的1秒/10秒、STOP/故障清除|r1/g02-checks-01及g02-board-01共13组板测通过；十秒计数999998、OVR/错误/迟到0|引脚禁能的软件与板测完成；电气关断另列|
|G02协议异常与重放|r4 CRC/id/异常帧|r1板测非法范围/未知命令、CRC/NaN/超长、分包粘包、冲突/旧id/重复、拥塞与断连期限通过|拒绝无副作用，不延长窗口；完成|
|资源互斥/清除不自启|r4合成G03/ADC|r1、r2生产集成模拟通过；r1禁能12点基线时重复请求+STOP，清除后IDLE/输出0|r1板测STOP在基线期；动作期STOP由生产代码模拟验证|
|复位默认禁能/身份|r4正常BOOT运行|r1及r2写入读回成功；r2恢复正常BOOT并RESET后IDLE、输出0、live_used=0|本轮正常复位证据完成；未新增断电冷启动测试|
|继电器本地期限/异常|新增功能|r1 relay-checks-04，r2 relay-checks-02/03：SPI阻塞、PEC/失效/过期、缓存、互锁、期限边界、时钟回绕、STOP、重复及RX压力通过|软件夹具通过；真实试验命令区间98.528565ms，不替代电气测量|
|新增改动对旧G03/ADC影响|r4实板合格用例|r1 g03-checks-01（含10000事件序列）、adc-checks-02及r2主机兼容检查通过|只回归受影响模块；生产身份变化和新基线检查已在r2核验|
|独立V/I/T物理标定|未完成|本轮不补伪数据；physical_valid=0|需要参考值、配对及实际标定，继续缺测|
|PWM/驱动/有效死区/电气关断|未完成|继电器单次只给本次响应证据|需要相应物理测量，G02/G03整体不据软件宣告通过|

软件验证、禁能板测与真实通路观察分别列证。relay-checks-03为实验后软件复核的补充，未改变已烧录固件和冻结条件。全部历史编译、栈异常、下载与早期实验失败均保留，未提交修改未重置。
''')
write(rp+'/work-card.md',f'''# G01/G02补测与G03首次单次继电器实验工作卡

日期：2026-11-01。status=complete（本轮任务），verdict=pass（仅首次通路响应并恢复），evidence_scope=static/build/simulation/bench。G01/G02/G03完整阶段验收仍为未判定。

本轮已完成无需现场仪器操作的G01/G02补测、独立单次状态机与主机工具、Debug/Release构建、烧录读回、r2正常BOOT身份及禁能演练，并执行一次真实PG5动作。结果为**观察到响应并恢复**：窗口内4组完整样本，AFE约下降2493码，撤销后回带；PG5命令窗口98.528565ms，最终输出0、故障0、live_used=1。没有PWM、PI或自动重试。

|交付|入口|
|---|---|
|首次实验结果与边界|[首次实验报告](first-experiment-report.md)|
|G01/G02补测与缺项|[补测结果表](retest-matrix.md)|
|冻结条件与停止办法|[工况表](conditions-table.md)、[原始冻结JSON](conditions-frozen.json)、[就绪证据](conditions-ready.json)|
|固件、源码和构建日志|[镜像哈希](artifact-manifest.json)、firmware/、source-after/、delivery-manifest.json|
|主机工具|[relay_capture.py](../../../..//scripts/g03/relay_capture.py)、[接口说明](../../../../instructions/specs/G03-relay-single.md)|
|真实原始数据/派生CSV/时间曲线/停止|[live-01](live-01/manifest.json)、[曲线](live-01/response.png)、[派生清单](live-01/derived/manifest.json)|
|禁能数据|[board-rehearsal-01](board-rehearsal-01/result.json)|
|结束后状态及常规采集|[最终查询](final-status-01/result.json)、[G01恢复分析](g01-recovery-analysis.json)|

Release SHA256 `{fw}`；Debug/Release都完成构建，Debug仅原有EXTRAM警告。首次r1下载失败与r2首次测试夹具失败原样保留；未覆盖原始运行结果。最终状态保留完成锁存，重连只查询/读取；下一步完整G03 PWM开环需单独安排，不属于本轮自动续跑范围。
'''.replace('../../../..//','../../../../'))
trial=dict(status='complete',verdict='pass',verdict_scope='this single relay path response and recovery only',evidence_scope=['static','build','simulation','bench'],conclusion='response_and_recovery',physical_valid=0,formal_G01_verdict=None,formal_G02_verdict=None,formal_G03_verdict=None,actual_trigger_count=1,firmware_sha256=fw,final_state=read(run/'final-status-01/result.json'),analysis=live['analysis'],raw_result_preserved=True)
write(rp+'/trial-result.json',json.dumps(trial,ensure_ascii=False,indent=2))
status='''# 当前状态

日期：2026-11-01。本表为正式阶段验收状态；本轮单次探索任务已完成，不能替代阶段整体验收。

|阶段|status|verdict|已有证据 / 剩余工作|
|---|---|---|---|
|G00 基线与硬件契约|in_progress|null|构建/烧录及历史冷启动基础项完成，三节14500、33Ω负载、充电口开路已登记；物理额定值、散热和仪器校准缺项保留|
|G01 测量与标定|in_progress|null|本轮有效性/完成/错误传播/时间戳/序号/复算与快速AFE时序补测完成；真实动作后264条有效原码、29完整组；物理V/I/T标定和MCU电流路径问题仍未闭合|
|G02 无功率PWM与时序|in_progress|null|受影响软件回归、13组禁能板测、STOP/锁存/协议异常/资源互斥完成；物理波形、有效死区与电气停止时间缺测|
|G03 受限开环功率级|in_progress|null|首次单次PG5探索已完成，观察到响应并恢复：命令98.528565ms，4组完整窗口观测，最终输出0/故障0；未执行PWM开环或PI，完整开环验收待推进|
|G04 PI恒流与故障退出|not_started|null|尚无闭环实物证据|
|G05 串口/上位机联调|in_progress|null|CRC/id/防重放、专用采集读回、停止与单次命令工具完成；真实恢复未确认先提示现场停止；完整功率业务仍未验收|
|G06 SOC基准与数据集|not_started|null|容量、初值、参考标签及独立验证尚待建立|
|G07 模型与端侧部署|not_started|null|无可验收数据集或模型产物|

实板当前运行g03-relay-r2，Release HEX SHA256为`'''+fw+'''`。已ROM模式写入并读回验证，用户恢复正常BOOT并RESET后串口确认身份。最终查询DONE=5、faults=0、actual_bits=0、live_used=1；完成结果保留，未重启、未清除真实结果或重复动作。物理量有效标志保持0。

本轮先完成r1禁能实测及G01/G02补测，再固定r2观察边界并验证本镜像禁能演练，最后执行一次真实命令。三路电芯与AFE均观察到相关响应，AFE恢复；软件窗口不是触点测量。未知制造商硬限和实际电流标定仍留空，观察区间仅属于本次工程探索。

本轮交付：[工作卡](../evidence/runs/20261101-G03-relay-r2/work-card.md)、[补测表](../evidence/runs/20261101-G03-relay-r2/retest-matrix.md)、[首次报告](../evidence/runs/20261101-G03-relay-r2/first-experiment-report.md)、[冻结工况](../evidence/runs/20261101-G03-relay-r2/conditions-table.md)。失败历史与已完成动作见RUNLOG和各run。r1恢复采集的截断位于开头；r2恢复采集为末尾9字节截断，均保留且不参与有效样本判定。

后续仍按[总推进计划](G03-无探头条件下的推进计划.md)推进独立的G03后续任务；本轮终点已到首次真实响应与分析，没有自动扩展到PWM或重复实验。
'''
write('instructions/STATUS.md',status)
log=(root/'instructions/RUNLOG.md').read_text(encoding='utf-8')
write('instructions/RUNLOG.md',log+f'''

## 2026-11-01 r2首次单次继电器响应与恢复

r2 Release `{fw}`在用户切换ROM下载模式后写入及读回成功，恢复正常BOOT/RESET后身份确认。r2禁能演练102组全部原码有效，完整窗口4组，最长采集9ms，软件窗口98.53172ms，输出0。规则保持冻结，在就绪文件中引用下载/禁能证据后仅发送一次真实op32，请求{st['id']}。

真实运行得到102组，AFE完整窗口样本相对基线−2492至−2494码，47个恢复阶段样本回带；三路电芯同步下降并回升。命令区间98.528565ms，deadline正常结束，无故障，最终输出0、live_used=1。判读“观察到响应并恢复”，只支持本次通路；未启用PWM/PI或重试。15秒常规采集恢复264条、29完整九通道组，内部缺序/重复0，尾部9字节截断保存。

补充复核通过串口重放/RX溢出压力及跨回绕期限测试，未修改生产固件；主机报告修正避免把动作前基线拒绝算作PG5高电平。原始通用verdict保留，单次观察结论另存trial-result.json。所有失败和原始数据未覆盖，STATUS已整理为当前状态。更正：r1的266条恢复采集为开头截断，并非末尾截断；r1旧r4补采179条与本轮r2恢复才有尾部截断。见evidence/runs/20261101-G03-relay-r2/first-experiment-report.md。
''')
hp=read(root/'instructions/specs/hardware-profile.json')
hp['g03_relay_exploratory_profile'].update(pulse_executed=True,trigger_count=1,firmware='g03-relay-r2',firmware_sha256=fw,evidence_run_id='20261101-G03-relay-r2',conclusion='response_and_recovery',final_output_bits=0,physical_current_calibrated=False,physical_valid=0)
hp['g03_relay_latest_result']=dict(firmware='g03-relay-r2',flashed_readback_verified=True,normal_boot_confirmed=True,disabled_capture_verified=True,physical_pulse_command_executed=True,contact_timing_measured=False,live_used=1,actual_bits=0,report=rp+'/first-experiment-report.md')
write('instructions/specs/hardware-profile.json',json.dumps(hp,ensure_ascii=False,indent=2)+'\n')
spec=(root/'instructions/specs/G03-relay-single.md').read_text(encoding='utf-8')
spec=spec.replace('# G03 单次继电器接口与记录（g03-relay-r1）','# G03 单次继电器接口与记录（g03-relay-r2）')
spec=spec.replace('对应总推进计划任务1—2。生产默认 `G3R_LIVE_PROFILE_VERIFIED=0`，只允许禁能演练；该构建不能置高PG5。两种Keil target始终关闭G02引脚输出门。','对应总推进计划任务1—2。r1构建的真实门为0；当前已冻结的r2构建为 `G3R_LIVE_PROFILE_VERIFIED=1`，只接受一次显式真实请求，复位不自动启动。两种Keil target始终关闭G02引脚输出门；本次真实动作已使用，live_used=1。')
spec=spec.replace('新固件身份为g03-relay-r1。','当前固件身份为g03-relay-r2；r1历史记录继续兼容。')
spec=spec.replace('当前草案电芯界限为缺失值，不能用于真实运行。','r1草案保留为历史；r2本次观察界限与依据见冻结工况表，不替代缺失的制造商物理额定值。')
spec+='\n\n本次已完成一次真实运行，结果见[首次报告](../../evidence/runs/20261101-G03-relay-r2/first-experiment-report.md)。重连只查询/读取，不能把清除结果或复位当作重复实验授权。原始结果中通用verdict与特定观察conclusion分开；阶段状态以STATUS为准。\n'
write('instructions/specs/G03-relay-single.md',spec)
nav=(root/'instructions/README.md').read_text(encoding='utf-8').replace('总计划任务1—2的详细方案，尚未实现或执行。','总计划任务1—2的详细方案；当前实现与首次探索结果见STATUS及对应工作卡。')
write('instructions/README.md',nav)
for name in ['work-card.md','retest-matrix.md']:
    rel='evidence/runs/20261101-G03-relay-r1/'+name
    original=(root/rel).read_text(encoding='utf-8')
    write(rel,'> 历史检查点：下文保留首次下载失败时的记录。后续已恢复下载并完成r1禁能板测；最新结果见[本轮完成工作卡](../20261101-G03-relay-r2/work-card.md)及[补测表](../20261101-G03-relay-r2/retest-matrix.md)。\n\n'+original+'\n\n续接证据：flash-romboot-*读回成功；board-rehearsal-01、g02-board-01和board-stop-replay-01通过；g01-recovery-01有效266条/29完整组，截断在开头。真实动作另由r2单独记录，r1仍全程禁能。\n')
for rel in ['tests/g03/test_relay_core.c','tests/g03/test_relay_port.c']:
    copy(rel,stage/rel)
checks=stage/rp/'relay-checks-03'
for p in checks.rglob('*'):
    if p.is_file():copy(rp+'/relay-checks-03/'+str(p.relative_to(checks)).replace('\\','/'),p)
for name in ['publish-host-fix.py','prepare-live.py','final-evidence.py','prepare-final-docs.py','download-r2.py']:
    copy(rp+'/procedure/'+name,stage/name)
# Render the established HTML from the updated Markdown in staging.
script=Path('instructions/validation/render_html.cjs');p=dest/script;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/script,p)
for rel in ['guide.md','specs/acceptance.md','specs/measurement.md','specs/data.md','MIGRATION.md','WORKFLOW.md','references/open-questions.md','references/source-map.md']:
    p=dest/'instructions'/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/'instructions'/rel,p)
proc=subprocess.run([r'D:\Program Files\nodejs\node.exe',str(dest/script)],capture_output=True)
(dest/'html-build.stdout').write_bytes(proc.stdout);(dest/'html-build.stderr').write_bytes(proc.stderr)
assert proc.returncode==0,proc.stderr
rel='instructions/BMS实施与验收指南.html'
changes.append(dict(path=rel,before_sha256=sha(root/rel),after_sha256=sha(dest/rel)))
(dest/'changes.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(staged_changes=len(changes),html_rendered=True,destination=str(dest)),ensure_ascii=False))
