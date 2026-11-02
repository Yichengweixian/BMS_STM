from pathlib import Path
import json,hashlib,datetime,shutil,csv

S=Path(__file__).parent;R=Path(r'D:\ADMIN\Desktop\WEIJI\zonghe');E=R/'evidence/runs/20261101-G03-pwm-disabled-r1'
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
cases=[];failures=[]
for suite in ('board-suite-01','board-suite-02'):
    for p in sorted((E/suite).glob('*/result.json')):
        d=read(p)
        if d['verdict']!='pass':failures.append(dict(path=p.relative_to(E).as_posix(),error=d.get('error')));continue
        t=d['terminal_status'];f=d['final']
        assert t['actual_bits']==t['timer_running']==t['owned']==0 and t['restored']==1
        assert f['used']==1 and f['faults']==f['actual_bits']==f['owned']==0
        cases.append(dict(case=d['case'],run_us=t['run_us'],elapsed_us=(t['stop_us']-t['start_us'])&0xffffffff,
             sample_count=t['sample_count'],retained_records=t['trace_written'],fault_mask=t['faults'],
             sample_gap_max_us=t['max_sample_gap_us'],irq_gap_max_us=t['max_irq_gap_us'],
             request_id=d['start_request_id'],outputs=0,restored=True,path=p.relative_to(E).as_posix()))
assert len(cases)==15 and len({x['case'] for x in cases})==15
assert len(failures)==1 and 'reset failed' in failures[0]['error']
flash=read(E/'flash-01/result.json');boot=read(E/'boot-query-01/result.json');recovery=read(E/'resource-recovery-01/result.json')
assert flash['verdict']=='pass' and flash['exit_code']==0 and recovery['verdict']=='pass'
assert 'Download verified successfully' in (E/'flash-01/stdout.txt').read_bytes().decode(errors='replace')
assert boot['initial']['firmware']=='g03-pwm-disabled-r1' and boot['initial']['used']==0
source=read(E/'production-source-manifest.json')
assert all(sha(R/x['path'])==x['sha256'] for x in source['files'])
out=E/'documentation-final';out.mkdir(exist_ok=False)
for rel in ('instructions/STATUS.md','instructions/RUNLOG.md','instructions/specs/hardware-profile.json'):
    dest=out/'before'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(R/rel,dest)
for name in ('manifest.json','work-card.md'):shutil.copy2(E/name,out/('before-'+name))
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
summary=dict(status='complete',verdict='pass',scope='single PWM disabled integration/build/flash/bench only',
     evidence_scope=['static','build','simulation','bench'],completed_utc=now,firmware_identity='g03-pwm-disabled-r1',
     release_sha256=flash['firmware_sha256'],flash_readback_verified=True,normal_boot_serial_identity_verified=True,
     cold_power_cycle_tested=False,disabled_cases_passed=15,cases=cases,preserved_failures=failures,
     recovery_verdict='pass',g01_rows=recovery['g01']['rows'],g01_complete_groups=recovery['g01']['complete_groups'],
     g02_completions=recovery['g02_sample']['completions'],relay_dry_groups=recovery['relay_final']['written'],
     final_pwm=recovery['final_pwm'],physical_valid=0,real_pwm_or_relay_command_sent=False,
     limits=['IRQ observation times are not hardware conversion timestamps','Raw fast records are decimated; sample_count counts every completed ISR sample',
             'Software deadline does not establish electrical shutdown time','Board driver/current transfer function remains unverified',
             'ST-LINK software reset API error retained despite subsequent successful default-state query'])
save(E/'result.json',summary)
with (E/'disabled-cases.csv').open('x',newline='',encoding='utf-8') as f:
    writer=csv.DictWriter(f,fieldnames=list(cases[0]));writer.writeheader();writer.writerows(cases)
names={'normal':'正常11.5周期','sample-6p5':'对照6.5周期','adc-stale':'停止触发/样本过期','adc-invalid':'无效样本','fifo-overrun':'真实FIFO溢出','awd-low':'AWD低侧越窗','awd-high':'AWD高侧越窗','cache-full':'缓存耗尽','heartbeat-expiry':'心跳过期','explicit-stop':'STOP','foreground-stall':'前台阻塞250ms','bad-crc':'错误CRC','rx-pressure':'串口压力','duplicate-start':'相同请求重放','conflicting-start':'同ID参数冲突'}
rows='\n'.join('|'+ '|'.join(map(str,[names[x['case']],x['elapsed_us'],x['sample_count'],x['fault_mask'],x['retained_records'],'通过']))+'|' for x in cases)
report=f'''# 单次 PWM 禁能版本接入、下载与板测报告

2026-11-01。已完成独立禁能 target 接入、Debug/Release 构建、Flash 写入读回、正常 BOOT 身份核对、15 个禁能场景和共享资源恢复检查。没有发送真实 PWM 或继电器放电命令。G03 正式功率阶段仍单独验收。

## 固件与实现

运行身份 `g03-pwm-disabled-r1`；Release HEX SHA256 `{flash['firmware_sha256']}`。Debug 0 错、已有 EXTRAM 警告 1 条；Release 0 错 0 警告。176 份生产源文件与快照逐项一致；原有未提交修改、旧 target 和历史镜像保留。核心21组、生产port寄存器模型15组、主机19项及受影响ADC/继电器回归通过。

独立 TIM2 1MHz、100us 周期 IRQ 管理单次期限；固定 shadow CCR，不允许重复启动/延长。TIM1 只产生内部 TRGO，PA9/PF7 保持 GPIO 禁能，MOE/CCER 及 PB5/PG5 不允许开启。AWD/OVR 先寄存器关闭再记故障；STOP、数据失效、协议异常、缓冲耗尽进入锁存出口。清故障不恢复一次令牌。ADC/TIM2 保存和恢复纳入互斥。

参数固定在 manifest：TIM1 400MHz、ADC 64MHz、ARR2000、shadow CCR1000；普通窗口100ms，协议试验窗口200ms；样本最大年龄2000us、IRQ间隔阈值500us。DTG0与DRIVER来源、verified_facts及标称电流限值仅是不可开输出的逻辑夹具，未变成实物限值。

## 禁能板测

|场景|观察窗口 us|ADC完成次数|终止故障掩码|保留轨迹行|结果|
|---|---:|---:|---:|---:|---|
{rows}

所有完成组输出位0、timer_running0、owned0、restored1；新请求再次启动及清故障后再次启动均被拒绝。重复请求只有一次开始/关闭事件，200001us结束，未延长。前台阻塞250ms时仍在100001us截止，清理和回复晚177986us发生，说明该软件截止不依赖主循环或主机读回。AWD两侧均保留硬件AWD标志，FIFO注入保留真实OVR标志；不是用伪造0电流代替错误。

普通11.5周期及6.5周期各完成9999次采样，最大IRQ观察采样间隔10us；核心停止时间戳分别为100002/100001us。按轨迹开始事件至寄存器关闭事件复算，普通组为100002us、6.5周期与前台阻塞组均为100003us；停止时间戳采集与关闭回调的先后造成这一差别。保留64点预备原码、首64点快速原码，之后每100次完成保留一条及全部关键事件。**sample_count是全部完成计数，trace不是完整100kHz原码流。** 时间来自IRQ观察，不是硬件转换起止时间；微秒计时结果不代表功率引脚或MOS电气关闭延时，也不宣称物理通电严格小于等于100ms。

## 资源恢复

G01 15秒记录{recovery['g01']['rows']}条、{recovery['g01']['complete_groups']}个完整九通道组，全有效、无内部缺序/重复或CRC错误。电芯转换记录最长3ms，AFE电流最长6ms；常规组间隔500ms。MCU常规采集原码986—991，只保留原码/标称量，不称已标定电流。

G02内部采样1秒更新/完成均{recovery['g02_sample']['completions']}，OVR、ADC错误和迟到计数0。relay DRY完成{recovery['relay_final']['written']}组、4个窗口样本，最长采集9ms、最大开始间隔21ms，软件窗口98.5330475ms；所有PG5记录为0。此项证明共享ADC/TIM2功能可复用，未通过线协议直接读回TIM2 PSC/ARR；精确寄存器恢复依据离线fixture及代码检查。

最终PWM为IDLE、used1、faults0、owned0、timer_running0、actual_bits0；继电器DRY已完成、live_gate0、live_used0。当前为正常运行档 BOOT1=0/BOOT0=0，不需再切换。

## 保留的异常

首轮第8组开始前，ST-LINK软件复位返回“Unable to run MCU / Error code 32”，未发送启动。原 `board-suite-01` 仍为fail，前7组结果有效。独立COM11查询确认新固件默认IDLE、used0、输出0；经记录后，`board-suite-02` 的首项沿用该启动状态、不重复复位，其余独立场景按固定计划执行。两轮共取得15项通过；没有将复位接口失败改写成成功。未增加断电冷启动结论。

烧录CLI退出0且原始日志明确 `Download verified successfully`。包装脚本在回显已保存日志时遇GBK编码异常；写入/校验均先完成，未重复刷写，说明单独保留在 `flash-01/wrapper-note.json`。

## 老师HEX带来的新信息

已核对[baseline-plan](../20261101-HEX-baseline-followup/baseline-plan.md)，采用r2显式死区来源：课程和EG3112资料支持内部死区，不能仅凭DTG0否定原方案，也无需完整原理图才能完成禁能接入。

老师工作电流仍为PA1/ADC1 CH1，TIM1_TRGO、6.5周期、OS2右移1；本次两种采样时间的真实内部触发均正常，无需换成启动时的CH11。当前原码仍不支持确认实际电流传递关系。本次没有刷老师HEX；其原版STOP对照仍可作为后续独立排查方式。

老师初始化CCR500会被闭环覆盖，不能作为固定D依据；`stream stop`仅停数据，功率停止路径是`bms mode stop`。AWD经CPU中断关闭，也不等于独立BKIN保护。详见[HEX补充分析](preparation/hex-followup.md)和[采样对照](analysis/adc-comparison.md)。

## 可执行范围

本次交付已满足单次PWM禁能版本的接入、双构建、下载与板测要求。物理有效标志保持0；本轮未验证测流路径随PWM支路电流的响应、实装驱动/引脚对应、电气非交叠及关断时间，也未定义真实PWM工况的固定D和最长通电时间。真实PWM需据本次路径与选定有限工况落实这些事实；不要求先补齐完整原理图或G01全部精度验收。

入口：`scripts/g03/pwm_disabled.py`；完整禁能场景：`scripts/g03/bench_pwm_disabled.py`；恢复检查：`scripts/g03/post_pwm_recovery.py`。重连默认仅查询/读回；原始串口、请求、CRC记录、样本CSV、停止事件各自保存在每组目录。清令牌仅靠独立复位，清故障不启动。
'''
(E/'report.md').write_text(report,encoding='utf-8')
m=read(E/'manifest.json');m.update(status='complete',verdict='pass',flash_verdict='pass',bench_verdict='pass',evidence_scope=summary['evidence_scope'],completed_utc=now,report='report.md',disabled_cases_passed=15,preserved_failed_reset='board-suite-01/08-cache-full/reset.json',physical_power_stage_verdict=None)
save(E/'manifest.json',m)
p=E/'work-card.md';text=p.read_text(encoding='utf-8');text=text.replace('当前下载与板测结果尚未产生，manifest 中保持 null。阶段进度统一维护于 instructions/STATUS.md。','下载读回、正常BOOT身份核对、15项禁能板测及G01/G02/relay DRY恢复已完成；判定与原始异常分别保留。见[最终报告](report.md)、[结果清单](result.json)和[场景CSV](disabled-cases.csv)。阶段进度统一维护于 instructions/STATUS.md。');p.write_text(text,encoding='utf-8')
p=R/'instructions/STATUS.md';text=p.read_text(encoding='utf-8')
text=text.replace('同工况三次继电器探索已完成，PWM单点准备与具体缺项另行记录。','同工况三次继电器探索及单次PWM禁能接入/板测已完成，真实PWM工况仍单独推进。')
start=text.index('新增单次 PWM 禁能 target 已接入');end=text.index('此前完成r1禁能实测',start)
text=text[:start]+f'''当前实板正常运行 `g03-pwm-disabled-r1`，Release HEX SHA256为`{flash['firmware_sha256']}`。ROM下载写入/读回成功，用户恢复BOOT1=0/BOOT0=0并RESET后COM11核对默认禁能及身份。单次PWM禁能15项全部取得通过结果，G01恢复270条/30完整组，G02 1秒更新/完成99997无错误，relay DRY102组。最终PWM IDLE、used1、faults0、owned0、timer_running0、actual_bits0；物理量有效标志保持0。本版不能开启真实PWM或继电器。

核心21组、port寄存器模型15组、主机19项及受影响旧回归通过；Release0错0警告、Debug原有EXTRAM警告1。一次软件复位接口Error32保留，独立串口证实默认启动后继续未执行场景，无复位/启动自动重试。详见[禁能工作卡](../evidence/runs/20261101-G03-pwm-disabled-r1/work-card.md)、[最终报告](../evidence/runs/20261101-G03-pwm-disabled-r1/report.md)。未新增断电冷启动或电气关断结论。

历史真实继电器镜像 `g03-relay-r2` / `8ff78e03997c4a5facd8f6feade09024fdd4721a3f0e32fc3531312bf1598c49` 与三次观察数据保留。此版下载后不再把旧固件的live_used状态当作当前运行状态。

'''+text[end:]
text=text.replace('STOP/锁存/协议异常/资源互斥完成；物理波形','STOP/锁存/协议异常/资源互斥完成；新增单次PWM禁能15项及采集恢复通过；物理波形')
text=text.replace('已交付PWM参数工具，实际PWM因反馈/死区/保护及输入约束尚未落实而未执行','单次PWM禁能接入/双构建/读回/15项板测已完成，实际PWM工况的路径与驱动/停止依据仍待落实')
text=text.replace('下一项优先落实PA1反馈或独立快速过流路径、驱动死区及供能约束，再接真实PWM适配器。','禁能适配器已接入；下一项落实本次PWM路径的反馈或快速保护、实装驱动及有限工况，随后接真实输出版本。EG3112资料支持内部死区，DTG0不单独否决，不要求完整原理图作为禁能工作的前提。')
p.write_text(text,encoding='utf-8')
p=R/'instructions/RUNLOG.md'
with p.open('a',encoding='utf-8') as f:f.write(f'''

## 2026-11-01 — 单次PWM禁能下载与15项板测完成

用户切换ROM模式后一次写入/读回校验通过，Release SHA256 `{flash['firmware_sha256']}`；包装脚本回显GBK编码异常发生于校验后，原始stdout/退出0保留，无重复刷写。用户恢复正常BOOT/RESET后新身份及默认输出0确认。

禁能15项全部取得通过：两种采样时间、断采/无效/FIFO溢出、双侧AWD、缓存耗尽、心跳、STOP、前台阻塞、CRC/RX压力、重复和冲突请求。普通窗口100002/100001us，各9999完成，最大观察采样间隔10us；前台阻塞250ms仍100001us截止；重复请求200001us一次结束。全部输出0、资源已恢复、清故障后令牌仍已消费。

suite01第8项复位API Error32未发送start，原fail保留；独立只读查询证实已进入默认unused状态，suite02首项沿用该启动、不重复复位，其余独立场景完成。不是把失败改判，未新增冷启动通过。

恢复验证G01 15秒270有效条/30完整九通道组，G02 1秒99997更新/完成且无OVR/错误，relay DRY102组/4窗口样本、最长采集9ms。最终PWM IDLE/used1/owned0/faults0/输出0，正常运行档，真实功率门关闭。报告：evidence/runs/20261101-G03-pwm-disabled-r1/report.md。IRQ时间和抽取原码的边界明确，physical_valid=0，物理额定/标定未改。
''')
p=R/'instructions/specs/hardware-profile.json';h=read(p)
h['g03_pwm_disabled_integration'].update(flashed_readback_verified=True,normal_boot_serial_identity_verified=True,bench_verdict='pass',disabled_cases_passed=15,resource_recovery_verified=True,final_actual_bits=0,final_once_token_used=1,cold_power_cycle_tested=False,report='evidence/runs/'+E.name+'/report.md',preserved_reset_api_failure='evidence/runs/'+E.name+'/board-suite-01/08-cache-full/reset.json')
h['g03_pwm_preparation'].update(disabled_adapter_integrated=True,disabled_bench_verified=True,latest_disabled_evidence='evidence/runs/'+E.name+'/report.md')
save(p,h);shutil.copy2(Path(__file__),out/'procedure.py')
save(out/'manifest.json',dict(completed_utc=now,source_files_verified=len(source['files']),hardware_commands_executed=False,report_sha256=sha(E/'report.md')))
print(json.dumps(dict(disabled_cases=15,recovery='pass',report=str(E/'report.md'),source_files_verified=len(source['files']))))
