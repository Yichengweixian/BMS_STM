from pathlib import Path
import csv,json,statistics,shutil,hashlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path('D:/ADMIN/Desktop/WEIJI/zonghe')
run=root/'evidence/runs/20261102-G03-discharge-d74-c1'
r4=root/'evidence/runs/20261102-G03-discharge-sprint-r4'
cross=root/'evidence/runs/20261102-G03-current-crosscheck-r1'
sha='001577eeccc6ab3d264283cb4d85be17e19051a08dccc2eb983f02fd9da2d4ab'
def readcsv(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def writecsv(p,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with p.open('x',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
def summarize(folder,firmware,vload=None,isource=None):
    rows=readcsv(folder/'points.csv');result=json.loads((folder/'result.json').read_text())
    active=[r for r in rows if r['phase']=='3' and r['sample_scope']=='within_phase']
    reports=json.loads((folder/'reports.json').read_text())
    status=next(r for r in reversed(reports) if r['kind']=='#G3Q' and r['phase']==6)
    med=lambda k:statistics.median(float(r[k]) for r in active)
    d=status['ccr']/status['arr'];tail=[r for r in active if float(r['begin_us'])>=status['pwm_off_us']-500000]
    return dict(run=str(folder.relative_to(root)),firmware=firmware,D=d,CCR=status['ccr'],ARR=status['arr'],
        requested_us=status['run_us'],actual_pwm_us=result['software_pwm_us'],relay_hold_us=result['relay_hold_after_pwm_us'],
        Ibat_AFE_nominal_A=med('Ibat_nominal_A'),Vbat_AFE_nominal_V=med('Vbat_nominal_V'),
        I_source_CH1_user_A=isource,I_source_CH2_user_A=isource,I_source_CH3_user_A=isource,
        Vload_DMM_user_V=vload,Iload_from_label33ohm_A=vload/33 if vload else None,
        Vload_ideal_CCM_V=med('Vbat_nominal_V')/d,Ibat_ideal_CCM_magnitude_A=med('Vbat_nominal_V')/(33*d*d),
        samples=result['samples'],active_samples=len(active),tail_samples=len(tail),
        tail_Ibat_min_A=min(float(r['Ibat_nominal_A']) for r in tail),tail_Ibat_max_A=max(float(r['Ibat_nominal_A']) for r in tail),
        temp1_median_raw=med('temp1_raw'),temp2_median_raw=med('temp2_raw'),temp3_median_raw=med('temp3_raw'),temperature_C=None,
        fault_bits=status['faults'],final_output_bits=status['bits'],restored=status['restored'],used=status['used'],verdict=result['verdict'],
        steady_state_claim=False,physical_calibration_valid=False,reference_recording='user display observation; not time synchronized'),rows,status

short,srows,sst=summarize(run/'live-d74-short-01','g03-power-d74-c1')
long,lrows,lst=summarize(run/'live-d74-long-01','g03-power-d74-c1',13.052,.512)
crossrow,_,_=summarize(cross/'live-d80-01','g03-power-points-r4',None,.433)
old90,_,_=summarize(r4/'live-d90-long-01','g03-power-points-r4',10.916)
old80,_,_=summarize(r4/'live-d80-long-01','g03-power-points-r4',12.152)
summary=[old90,old80,crossrow,short,long]
writecsv(run/'completed-points.csv',[short,long])
writecsv(run/'consolidated-points.csv',summary)
obs={'long_point':{'source':'user reply','PSU_CH1_CH2_CH3_A':[.512,.512,.512],'Vload_DMM_V':13.052,'other_observations_user_text':'其余无异常','stop_voltage_numeric_V':None,'no_CC_trip_or_anomaly_reported':True},'short_point':{'no_anomaly_user_confirmed':True},'final_three_sources_OFF_user_confirmed':True,'real_cells_remain_removed':True,'DMM_remains_DCV':True}
(run/'user-observations.json').write_text(json.dumps(obs,ensure_ascii=False,indent=2),encoding='utf-8')
direction={'from_run':crossrow['run'],'to_run':long['run'],'D_from':.8,'D_to':.74,'PSU_source_A_from':.433,'PSU_source_A_to':.512,'nominal_AFE_A_from':crossrow['Ibat_AFE_nominal_A'],'nominal_AFE_A_to':long['Ibat_AFE_nominal_A'],'source_discharge_magnitude_dI_dD':(.512-.433)/(.74-.8),'interpretation':'D decreases, discharge magnitude increases locally','scope':'same wiring/source settings; r4 to c1 exact-point whitelist extension, unchanged normal power path and thresholds; display readings not synchronized; not a global control model'}
(run/'local-direction.json').write_text(json.dumps(direction,ensure_ascii=False,indent=2),encoding='utf-8')
plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'font.size':10})
points=[long,old80,old90];xx=[p['D'] for p in points]
fig,ax=plt.subplots(1,2,figsize=(12,4.9),layout='constrained')
ax[0].plot(xx,[p['Vload_DMM_user_V'] for p in points],'o-',label='DMM负载电压（人工读数）')
ax[0].plot(xx,[p['Vload_ideal_CCM_V'] for p in points],'s--',color='#999',label='理想CCM（各点标称Vbat）')
ax[1].plot(xx,[-p['Ibat_AFE_nominal_A'] for p in points],'o-',label='AFE电池电流幅值（标称换算）')
ax[1].plot([.74,.8],[.512,.433],'D-',color='#d46618',label='三路源电流各路显示值（独立记录）')
ax[1].plot(xx,[p['Ibat_ideal_CCM_magnitude_A'] for p in points],'s--',color='#999',label='理想CCM（33Ω标签）')
ax[1].axhline(.55,ls=':',color='#a43333',label='保留0.550A退出设置')
ax[1].axhline(.5,ls=':',color='#579b50',label='课程电流范围下边界0.5A')
for p in points:ax[0].annotate(f"{p['Vload_DMM_user_V']:.3f}V",(p['D'],p['Vload_DMM_user_V']),xytext=(0,-18),textcoords='offset points',ha='center')
ax[1].annotate('0.512A',(.74,.512),xytext=(14,-28),textcoords='offset points')
for a in ax:a.set(xlabel='上管固定D',xlim=(.725,.915),xticks=[.74,.8,.9]);a.grid(alpha=.25);a.legend(fontsize=8)
ax[0].set_ylabel('负载端电压 / V');ax[0].set_ylim(10.6,14.15);ax[1].set_ylabel('电池/替代供电支路电流幅值 / A')
fig.suptitle('真实固定D有限窗口：D0.90/0.80为r4，D0.74为c1；各2秒，非长期热稳态')
fig.savefig(run/'dv-di.png',dpi=170);plt.close(fig)
fig,ax=plt.subplots(3,1,figsize=(11,7),sharex=True,layout='constrained')
t=[(float(r['begin_us'])-lst['pwm_on_us'])/1e6 for r in lrows]
ax[0].plot(t,[float(r['Ibat_nominal_A']) for r in lrows],'.-',ms=3)
ax[0].axhline(-.55,color='#a43333',ls=':',label='原退出设置−0.550A');ax[0].legend(fontsize=9);ax[0].set_ylabel('Ibat标称 / A')
ax[1].plot(t,[float(r['Vbat_nominal_V']) for r in lrows],'.-',ms=3);ax[1].set_ylabel('Vbat标称 / V')
ax[2].step(t,[bool(int(r['bits'])&1) for r in lrows],where='post',label='TIM1 MOE读回')
ax[2].step(t,[bool(int(r['bits'])&16) for r in lrows],where='post',label='放电继电器输出位');ax[2].set_ylabel('输出位 / 0或1');ax[2].set_xlabel('相对PWM开启时间 / s');ax[2].legend(fontsize=9)
for a in ax:
    a.axvspan(0,(lst['pwm_off_us']-lst['pwm_on_us'])/1e6,color='#dcecff',alpha=.5)
    a.axvline(0,color='#888',ls='--');a.axvline((lst['pwm_off_us']-lst['pwm_on_us'])/1e6,color='#888',ls='--');a.grid(alpha=.25)
fig.suptitle('D0.74：动作前、2秒PWM、自动停止与恢复\n寄存器/AFE记录；不等同于示波器测得的电气关断延时')
fig.savefig(run/'stop-and-recovery.png',dpi=170);plt.close(fig)

report=f'''# G03新增约0.5A固定D放电结果

验收日期2026-11-03，实测2026-11-02。保持三路限流电源代替实电池、33Ω/25W标签负载和原0.550A退出设置，完成固定D0.74短点及2秒点。2秒窗口中三路电源均显示0.512A，DMM负载电压13.052V，AFE电池电流中位数{long['Ibat_AFE_nominal_A']:.6f}A（标称换算）。自动截止与恢复通过。已取得约0.5A的功能展示点；未将它宣称为最终电流精度或长期热稳态验收。

## 已完成点

|工况|CCR/ARR|实际PWM软件窗口|AFE标称电池电流/A|电源各路显示/A|负载表测/V|结果|
|---|---|---|---:|---:|---:|---|
|原r4 D0.90|1800/2000|2.000072s|{old90['Ibat_AFE_nominal_A']:.6f}|未取得|10.916|通过、保留|
|原r4 D0.80|1600/2000|2.000072s|{old80['Ibat_AFE_nominal_A']:.6f}|未取得|12.152|通过、保留|
|r4 D0.80电流补测|1600/2000|2.000072s|{crossrow['Ibat_AFE_nominal_A']:.6f}|0.433|未取得|通过|
|c1 D0.74短点|1480/2000|{short['actual_pwm_us']/1e6:.6f}s|{short['Ibat_AFE_nominal_A']:.6f}|未取得|未取得|通过|
|c1 D0.74记录点|1480/2000|{long['actual_pwm_us']/1e6:.6f}s|{long['Ibat_AFE_nominal_A']:.6f}|0.512|13.052|通过|

负载电流13.052/33={13.052/33:.6f}A是电阻标签换算，不是电池电流；三路0.512A不相加。各电源显示是替代电芯供电支路读数，独立支持约0.5A输出，但没有同步采集或在此完成仪器校准。未用单点比例修改AFE系数。D0.80补测未读到电压，不用旧12.152V补填该run。

![D-V与D-I](dv-di.png)

同一接线与电源设置下，D0.80→0.74时电源各路显示0.433→0.512A，AFE标称电流也更负，支持局部D减小、放电幅值增大。原r4到c1仅扩展固定点白名单和身份，正常驱动/监测路径及阈值未改；不将局部趋势外推成整个范围已验证的模型。图中理论线为理想CCM模型，不填充未做点。

## 停止、恢复与质量

长点197条记录、95个完整PWM样本，最后0.5秒{long['tail_samples']}个完整样本，电流范围{long['tail_Ibat_min_A']:.6f}～{long['tail_Ibat_max_A']:.6f}A。软件PWM截止{long['actual_pwm_us']}us、随后继电器保持{long['relay_hold_us']}us；故障0，输出位0，资源恢复1，令牌已用1。用户报告其余无异常，随后明确确认三路OFF；最后串口状态独立核对一致。最后状态live=1表示该记录使用真实输出模式，不表示当前仍在输出。

温度GPIO2/3/4活动期中位原码分别{long['temp1_median_raw']:.0f}/{long['temp2_median_raw']:.0f}/{long['temp3_median_raw']:.0f}，Celsius留空。physical_valid=0表示物理标定未完成，不把它改成1。PA1不作唯一快速保护，ADC2负载电压未验证换算，不用于制造电压曲线。

![停止恢复](stop-and-recovery.png)

## 固件与冻结工况

实板身份g03-power-d74-c1，Release HEX SHA256 `{sha}`。Release构建0错误0警告；受影响端口12项（含D74固定CCR、截止、STOP、过流、CCR异常、心跳与防运行中改点）及主机13项通过，烧录读回通过，新镜像默认关闭和D74禁能核对通过。完整构建输入在build-source，构建清单在build/source-manifest.json；旧r4修改前文件在source-before。未提交修改和旧失败记录保留。

三路各3.500V、CC0.600A、OCP0.550A启用、OVP3.650V启用；CH1→左A/cell13，CH2→中B/cell7，CH3→右C/cell1，各黑端不互连，真实电池在板外，黄色口空，绿色33Ω接牢，原18V只按既有辅助/继电器供电使用。单节启动3.45～3.55V、运行3.30～3.65V，Ibat标称退出−0.550/+0.050A，基线和通路确认带均保持。

独立本地截止、STOP优先、数据失效关断、故障锁存、一次令牌、固定D和防重放保留。电源CC/OCP约束持续供能及锁断，延时未测；33Ω和短脉冲不被当成内部短路峰值上限。未建立电源输出电容及板内全部储能的量化界限，也未宣称周期级过流保护已验收。

## 本轮失败和差异记录

- new-image-dry-01：助手安排三路OFF，但禁能路径仍检查真实单节电压，读到近0V后退出；49条、实际继电器/PWM均未开启，faults=0x220008，保留fail。属于工况安排错误，未改阈值掩盖。
- new-image-dry-02：MCU未实际复位，主机在used1时拒绝启动，只发了状态查询；保留fail。
- 静态36条/0解析错误确认三节约3.5V后，一次ST-LINK复位生效，new-image-dry-03完成106条、100075us软件窗口、故障0、真实输出始终关闭。dry结果中的actual_pwm_started字段仅由软件时间戳推得，不能理解为物理PWM已开启。
- reset-before-short-01接口返回Error32，未重试复位；独立串口确认新启动、used0/faults0/bits0后才继续首个真实短点。该接口失败原样保留。
- 老师新上传DOCX与docs/course旧版本逐字节一致，SHA256均为5f8b027080aa93b1905be925cbd0828aafd45f769110e780513fd4c380ea4a72。没有新增充电上限或放宽电流依据。老师D0.758/0.5A是闭环例子，不冒充本项目固定D数据。

## 明日可展示及剩余差项

可展示D0.90、0.80、0.74三种固定D真实响应，以及D0.74约0.5A、2秒本地截止与恢复。D0.74是额外探索点，不替代课程D0.70。课程D0.70/0.60/0.50/0.40仍未执行；原10.5V/33Ω理想电池电流分别0.649/0.884/1.273/1.989A，与现有0.550A工况不相容，不直接提高阈值凑点。现场仅有33Ω时，六点不能在同一电压、同一负载下全部保持0.5～0.8A。

更高电流需新的有依据工况，低D还需母线电压/尖峰及负载范围依据。充电侧仍未接入：原实电池板外3.885/3.886/3.886V，与当前电压工况不相容；允许充电参数及实电池故障供能切断路径未确认。缺探头的物理波形、死区和电气关断延时仍缺测；不以这些缺项撤销本次有效功能点。不要求完整SOC或重做无关G01/G02。

数据入口：[本轮CSV](completed-points.csv)、[汇总CSV](consolidated-points.csv)、[现场操作](operation-guide.md)、[原r4报告](../20261102-G03-discharge-sprint-r4/report.md)、[扩点/充电约束核算](../20261102-G03-extension-readiness-r1/review.md)。
'''
(run/'report.md').write_text(report,encoding='utf-8')
guide=f'''# 当前c1固定D放电现场操作

当前实板g03-power-d74-c1，HEX SHA256 `{sha}`。本页适用于三路限流电源替代电池的已验证台架；不能装入3.885V实电池沿用本配置。历史r4操作指南和固件保留供复现；当前根目录主机工具已配套c1。

1. 断电接线：三路OFF，真实电池在板外；CH1→A左/cell13，CH2→B中/cell7，CH3→C右/cell1，各路红＋黑－，各黑端不互连。绿色33Ω负载接牢，黄色口空。DMM前面板INPUT HI/LO，DCV100V，跨负载，不改电流档。
2. 三路各3.500V、CC0.600A、OCP0.550A和OVP3.650V启用，独立模式。原18V辅助供电、串口及ST-LINK按原接法保留。打开三路时应约3.5V、空闲电流近0、无CC/跳闸。异常立即OFF，不自动重开。
3. 正常实验使用**运行档**（BOOT1=0/BOOT0=0）。需要重新烧录才切**烧录档**（BOOT1=1/BOOT0=0），此时三路必须OFF，烧录后必须读回核对；不能将烧录档当运行档。
4. 当前令牌已用，下一独立演示需明确复位再查询。RESET后如果仍used1，不继续发启动；查询结果是是否实际复位的依据。ST-LINK复位接口即使返回错误也不自动重试，独立核对身份和关闭状态。
5. 新烧录版本的必要禁能核对也需要电池替代输入3.5V有效，继电器和PWM仍不启用。本c1已取得new-image-dry-03通过记录，正常现场演示不需反复重做；失败01/02保留。
6. 在工程根目录PowerShell执行 `./scripts/g03/run_demo.ps1 -Mode Query -Port COM12` 仅查询。确认身份c1、phase0/faults0/used0/owned0/bits0后，已完成上述接线核对的操作者可执行 `./scripts/g03/run_demo.ps1 -Mode Live -Point D74 -Port COM12 -BenchReady`。脚本再核对默认关闭、c1禁能及同D短点记录，创建新目录，单次固定D0.74/2秒。不会自动RESET、扫点或重试。COM端口若变化先核实。
7. 记录窗口中三路各自A读数及DMM负载电压，不将三路电流相加。参考本次约0.512A、13.052V，属于实测参考而非保证值。需要提前STOP时采集进程Ctrl+C发送一次STOP；该主机路径已有离线检查，但未增加带载STOP电气延时验收。主机失联保留本地200ms心跳退出和总时限。
8. 正常结束应输出位0、faults0、owned0、restored1、used1。核对停止后显示及有无CC/跳闸；三路全部OFF收工。不用下一次成功覆盖旧失败。

固定点ID：D0.90短0x50393301/长0x50393303；D0.80短0x50393302/长0x50393304；D0.74短0x50393401/长0x50393402。当前通过的D0.74长点在live-d74-long-01，CCR1480/ARR2000在记录中固定。无PI或其他追踪反馈改D。
'''
(run/'operation-guide.md').write_text(guide,encoding='utf-8')
(run/'work-card.md').write_text('''# D0.74约0.5A固定占空比放电交付

本卡已完成：D0.80独立电源显示补测；c1源码/镜像构建与读回；受影响12项端口和13项主机检查；新镜像必要默认关闭/禁能；D0.74独立100ms与2秒真实点、停止恢复；CSV/曲线/理论对照/现场步骤。真实短点与长点verdict=pass，G03整体仍in_progress，阶段状态见STATUS。

证据范围：build/register_model/bench/user_display_observation。板端标称换算不等同精度验收，2秒不等同长期热稳态。原0.550A保护未改。所有失败、r4成果和原固件保留。详见report.md。
''',encoding='utf-8')
final=json.loads((run/'final-off-query-01/result.json').read_text())['status']
assert all(final[k]==0 for k in ('faults','owned','bits')) and final['restored']==final['used']==1
assert short['verdict']==long['verdict']=='pass' and .5<=.512<=.8
for rel in ('instructions/STATUS.md','instructions/RUNLOG.md','instructions/specs/hardware-profile.json'):
    p=run/'docs-before-final'/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/rel,p)
p=root/'instructions/specs/hardware-profile.json';hp=json.loads(p.read_text(encoding='utf-8-sig'))
hp['active_runtime']={'firmware':'g03-power-d74-c1','hex_sha256':sha,'run_id':run.name,'flashed_readback_verified':True,'runtime_verified':True,'last_point_D':.74,'last_point_CCR':1480,'last_point_ARR':2000,'last_point_us':2000000,'final_faults':0,'final_bits':0,'final_used':1,'restored':1,'sources':'all three OFF user confirmed','source_contract':'original 3.5V/CC0.6A/OCP0.55A/OVP3.65V unchanged; no real cells','report':str((run/'report.md').relative_to(root)),'completed_points':[short,long]}
p.write_text(json.dumps(hp,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=root/'instructions/STATUS.md';t=p.read_text(encoding='utf-8-sig');lines=t.splitlines()
for i,line in enumerate(lines):
    if line.startswith('日期：'):
        lines[i]='日期：2026-11-02。新增固定D0.74真实放电2秒：三路电源各0.512A，负载表测13.052V，AFE电池标称约−0.514A，停止恢复通过，原0.550A保护未改。实板g03-power-d74-c1，最终faults0/bits0/owned0/restored1/used1，用户确认三路OFF。原r4 D0.90/0.80成果保留；G03全项尚未完成。'
    elif line.startswith('当前交付：'):
        lines[i]='当前交付：[新增0.5A报告](../evidence/runs/20261102-G03-discharge-d74-c1/report.md)、[当前操作步骤](../evidence/runs/20261102-G03-discharge-d74-c1/operation-guide.md)、[汇总CSV](../evidence/runs/20261102-G03-discharge-d74-c1/consolidated-points.csv)。历史r4报告保留。CH1/A=cell13、CH2/B=cell7、CH3/C=cell1。'
    elif line.startswith('|G03 '):
        lines[i]='|G03 受限开环功率级|in_progress|null|固定D0.90/0.80/0.74各2s；新增D0.74源电流各0.512A、负载13.052V、自动停止恢复通过，阈值未改；课程D0.70及以下、电气波形/死区、精度/热稳态、充电侧仍缺|'
lines+=['','2026-11-02 D0.74补点交付：c1 Release 001577ee…，受影响端口12项、主机13项、构建0错0警告、烧录读回及默认关闭通过。真实100ms/2s分别100075/2000074us，最终输出0故障0资源恢复，三路OFF。禁能输入OFF的工况错误及未复位拒绝启动、一次复位接口Error32记录保留；新老师DOCX与原文档SHA完全相同。']
p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
with (root/'instructions/RUNLOG.md').open('a',encoding='utf-8') as f:
    f.write(f'\n\n2026-11-02 D0.74补点完成：c1 `{sha}`，烧录读回/运行身份通过，D74新禁能在恢复3.5V及实际复位后通过（失败01/主机拒绝02保留）。真实短点100075us、长点2000074us，197条/95完整活动样本，三路用户读0.512A、DMM13.052V，AFE标称中位{long["Ibat_AFE_nominal_A"]:.6f}A。自动停止及恢复通过，无CC/跳闸异常报告，最终三路OFF且bits0/faults0/owned0/restored1/used1。阈值未改；D0.74为额外探索点，不替代D0.70。新上传老师DOCX与原SHA一致。报告/CSV/曲线/操作步骤位于evidence/runs/{run.name}。\n')
for rel in ('scripts/g03/power_capture.py','scripts/g03/run_demo.ps1','scripts/g01/g01_capture.py'):
    p=run/'reproduction'/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/rel,p)
shutil.copy2(__file__,run/'finalize_d74.py')
manifest={str(p.relative_to(run)):hashlib.sha256(p.read_bytes()).hexdigest() for p in run.rglob('*') if p.is_file() and p.name!='delivery-manifest.json'}
(run/'delivery-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps({'report':str(run/'report.md'),'long_Ibat_nominal_A':long['Ibat_AFE_nominal_A'],'Iload_label_A':13.052/33,'files_hashed':len(manifest),'final_output_off':True},ensure_ascii=False))
