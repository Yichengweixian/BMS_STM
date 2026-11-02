from pathlib import Path
import csv, json, hashlib, shutil

ROOT = Path('D:/ADMIN/Desktop/WEIJI/zonghe')
OUT = ROOT/'evidence/runs/20261102-G03-extension-readiness-r1'
OUT.mkdir(exist_ok=False)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
protected = [ROOT/'evidence/runs/20261102-G03-discharge-sprint-r4'/p for p in ('report.md','completed-points.csv','delivery-manifest.json')]
protected += [ROOT/'BMS_EXv1.1/BMS_EX/BSP'/p for p in ('g03_power_port.c','g03_power_profile.h','firmware_identity.h')]
before = {str(p.relative_to(ROOT)):sha(p) for p in protected}
rows=[]
for label, vin in [('three_limited_sources',10.5),('user_real_cells_sum',3.885+3.886+3.886)]:
    for d in (.9,.8,.75,.7,.6,.5,.4):
        vout=vin/d
        rows.append(dict(scenario=label,Vbat_input_V=vin,D=d,CCR_if_ARR2000=round(d*2000),
            Vload_ideal_CCM_V=vout,Iload_ideal_CCM_A=vout/33,
            Ibat_discharge_magnitude_ideal_CCM_A=vin/(33*d*d),Pload_ideal_W=vout*vout/33,
            R_for_ideal_Ibat_0p6A_ohm=vin/(.6*d*d),
            provenance='model only; ideal CCM, R label 33 ohm; not measured or allowed operating points'))
with (OUT/'operating-point-calculations.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
assert abs(rows[0]['Ibat_discharge_magnitude_ideal_CCM_A']-10.5/(33*.9**2))<1e-12
assert all(abs(r['Vbat_input_V']*r['Ibat_discharge_magnitude_ideal_CCM_A']-r['Pload_ideal_W'])<1e-10 for r in rows)
report='''# 0.5～0.8A扩点与实电池充电复核

2026-11-02。证据范围为静态源码审核、既有实测复算、理想模型及用户现状。没有新硬件动作、没有烧录、没有调整保护阈值。实板仍为g03-power-points-r4；三路电源最后确认OFF。原r4两点及失败历史保留。

## 已确认与结论

用户现场只有33Ω/25W负载；没有额外负载。原三节14500电池在板外测得3.885、3.886、3.886V，合计11.657V，极差1mV；未给出每节身份/位置、品牌、充电规格或外观检查结论，不推定已经完成这些检查。已有标签Li-ion、3.7V、800mAh沿用，800mAh不是允许充电电流。

目前不能直接装回实电池开始充电或继续沿用放电工况。r4只接通PG5放电继电器，PB5充电继电器始终关闭；独立检查正向电流超过50mA退出。启动单节范围3.45～3.55V，运行范围3.30～3.65V，三节现电压均不相容。原三路CC/OCP在实电池供能时不再构成电池支路限流。

## 放电0.5～0.8A与其余D点

本项目电流目标按电池端Ibat处理：课程电流给定/反馈也是该端口。既有负载端电流0.331/0.368A为DMM电压除33Ω标签值，不是电池电流。

|上管D|10.5V、33Ω理想Ibat幅值/A|11.657V实电池电压、33Ω理想Ibat幅值/A|判断|
|---|---:|---:|---|
|0.90|0.393|0.436|已有模拟电池实测点，非0.5A达标点|
|0.80|0.497|0.552|已有模拟电池实测标称0.4444A；不能按理想值声称达到0.5A|
|0.70|0.649|0.721|可能满足电流目标，但超过现有0.550A保护工况|
|0.60|0.884|0.981|两工况理想电流均超过0.8A|
|0.50|1.273|1.413|两工况均不在本次允许范围|
|0.40|1.989|2.208|两工况均不在本次允许范围，另有母线电压问题|

公式：Vload=Vbat/D，Iload=Vbat/(R D)，|Ibat|=Vbat/(R D²)，理想CCM/无损耗。不能将模型外推填入实测CSV。实际损耗、导通压降、DCM、采样误差都会改变结果。

同一电池电压和33Ω下，D0.40与0.90的理想电池电流比为5.0625，不可能让所有六点同时落在0.5～0.8A（范围比1.6）。换实电池不解决此矛盾。若保持原电流边界并扩展低D，需更大阻值或降低输入电压，并对新工况分别记录；降低三路电压会触发当前3.30V下限，不能悄悄改动。更换负载时，当前200～450mA的被动通路确认带也需按新负载重算，不可直接删除负载检查。不同负载的点不能拼成一条固定负载特性。

最近的候选是保持原供电和33Ω，增加固定D0.75/CCR1500：从既有D0.80标称0.444433A按1/D²局部外推约0.5057A；但10.5V理想模型给0.5657A，已经超过0.550A，二者不是误差上下界，故不能保证不触发保护或已经达标。需要独立电池支路电流参考，再决定是否冻结单独候选版本；目前未加入固件白名单、未执行。

UDP3305S本体容量不构成0.8A的主要缺项，CH1/2额定0～30V/5A，CH3额定0～6V/3A。更大功率电源不是当前必需采购。当前缺的是已验证的电流测量与该电流下的功率级/保护工况，不是把OCP从0.550A直接调大。

课程列SiZ998DT，Vishay数据手册VDS绝对最大值30V；这不是整板允许工作母线值，也未新增实装型号确认。D0.40时10.5V输入理想输出26.25V；实电池当前11.657V则29.1425V，满电电压若更高还会继续升高。没有尖峰/实际电容耐压依据时不能靠25W电阻额定值宣告该点可用。

## 充电侧具体缺项与现有设备调整

1. 电芯资料及本次电芯状态：已有标签与本次三节静态电压，不重复索取这些资料；仍需该型号允许充电电压/电流，以及实物外观和温度情况。三节均衡不说明能够承受0.5～0.8A。首次小电流功能点也需要有依据的停止电压，不直接套用通用4.2V或按800mAh反推倍率。
2. 电池自身故障供能路径：确认原电芯/板上是否已有独立过流切断及其适用范围；若没有，需要电池支路限流/保护器件或具备双向限流的电池模拟器。充电源CC只约束源端持续供能，不能截断电池向故障桥臂放电；保险丝本身也不能等同于已知瞬时峰值限制。PA1仍不得担任唯一快速保护。
3. 充电电源可复用现有UDP3305S的CH1或CH2。未来改线必须先三路OFF并断开板上18V、USB/ST-LINK可能供能，撤除电池座三对模拟电池线，再安装确认可用的实电池；原电池座上的普通电源不可与实电池并联，也不能拿来吸收充电。黄色口由单路限流源供电，极性按既有板照/端子标识核对；绿色负载在充电工况断开。此处是待实施接线差异，不是立即上电步骤，数值待充电工况冻结。
4. 同板课程15V/1A是源端例子，不是实电池允许电流。当前11.657V串电压下，理想Buck平衡D约11.657/15=0.7771；D0.90对应13.5V理想平均驱动电压，不能照搬放电起始D。电池是低阻电压源，固定D的充电电流不能用33Ω公式计算，须核算电感电流变化及供能约束。源端Ibus也不能冒充Ibat。
5. 软件由我独立处理：单独充电适配工况，需要方向互锁、充电前检查、正向电流监督、逐节电压退出、独立截止、STOP/数据失效关断和故障锁存。沿用已验证单次核心；不启用PI，不改原r4结果。不在缺少电芯上限/保护路径时生成貌似可执行的充电配置。
6. 独立电流参考可使用现有DMM6500；切换到串联电流测量前需全断电，且明确所测电池支路和表压降。当前仍保持负载两端的DCV接法，不能就地切到电流档。USB数据线不是物理充电前提，只影响能否自动同步记录；可人工记录，但不能冒充同步曲线或快速保护测量。

以上只阻塞依赖这些事实的新增功率动作，不撤销已通过D0.90/0.80结果，不要求完整原理图、整套G01标定或完整SOC。

## 来源

- [已有r4报告](../20261102-G03-discharge-sprint-r4/report.md)、[实测CSV](../20261102-G03-discharge-sprint-r4/completed-points.csv)。
- [当前硬件档案](../../../instructions/specs/hardware-profile.json)、[G03验收要求](../../../instructions/specs/acceptance.md)。课程任务2提取段落79～83、244、307、407、563：拓扑、源端示例、教师闭环例子和电池电流给定范围。教师闭环D不算本项目固定D点。
- [UNI-T UDP3305S规格](https://uni-trendus.com/products/udp3305s)。
- [Vishay SiZ998DT数据手册](https://www.vishay.com/docs/62979/siz998dt.pdf)。
'''
(OUT/'review.md').write_text(report,encoding='utf-8')
(OUT/'work-card.md').write_text('''# G03扩点及充电准备工作卡

任务：解释现有33Ω与三路电源能否达到电池端0.5～0.8A，核查能否直接改实电池充电。

本卡进展：已完成静态复核、14个理论工况复算、原r4保护兼容性审核及实电池电压登记；新增硬件试验未执行，结果null。阶段状态见STATUS。

证据范围：static/model/user_report。不是新增PWM通过记录。

完成物：[复核报告](review.md)、[数值CSV](operating-point-calculations.csv)、[保存校验](result.json)。原固件、源码、两个通过点和失败run均未修改。下一物理动作所需事实见报告逐项说明。
''',encoding='utf-8')
paths=['instructions/STATUS.md','instructions/RUNLOG.md','instructions/specs/hardware-profile.json']
for rel in paths:
    dest=OUT/'before'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,dest)
p=ROOT/'instructions/specs/hardware-profile.json'
profile=json.loads(p.read_text(encoding='utf-8-sig'))
profile['g03_extension_readiness_20261102']={
 'scope':'static/model/user_report; no new power commands',
 'available_loads':[{'ohm_label':33,'W_label':25}], 'extra_loads_available':False,
 'real_cells_off_board_voltage_user_V':[3.885,3.886,3.886], 'voltage_mapping_to_A_B_C':None,
 'cell_manufacturer_charge_limits':None,'cell_visual_thermal_check_result':None,
 'real_cells_installation_authorized_for_this_profile':False,
 'runtime_firmware_unchanged':'g03-power-points-r4','protection_limits_changed':False,
 'report':'evidence/runs/20261102-G03-extension-readiness-r1/review.md'}
p.write_text(json.dumps(profile,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=ROOT/'instructions/STATUS.md';t=p.read_text(encoding='utf-8-sig')
note='\n扩点/充电准备复核（2026-11-02）：现场仅33Ω负载；原电芯板外3.885/3.886/3.886V，不符合r4启动/运行电压范围。原两点继续有效；未放宽阈值、未换接电池、未新增充电结果。[具体差项与数值核算](../evidence/runs/20261102-G03-extension-readiness-r1/review.md)。\n'
p.write_text(t.replace('\n## 历史过程记录',note+'\n## 历史过程记录',1),encoding='utf-8')
p=ROOT/'instructions/RUNLOG.md'
with p.open('a',encoding='utf-8') as f:
    f.write('\n\n2026-11-02 G03扩点/充电静态复核：用户仅有33Ω/25W，板外电芯3.885/3.886/3.886V，合计11.657V。生成14工况模型CSV、源/负载调整及充电缺项报告；r4仅放电、单节启动3.45～3.55V/运行3.30～3.65V与当前实电池不相容。没有新硬件动作、没有阈值修改；通过点与失败历史保留。见evidence/runs/20261102-G03-extension-readiness-r1/review.md。\n')
after={str(p.relative_to(ROOT)):sha(p) for p in protected}
assert before==after
result={'scope':'static/model; no hardware access','calculated_rows':len(rows),'power_balance_checks':'pass',
 'protected_artifacts_unchanged':before==after,'protected_hashes':after,'new_physical_result':None,
 'runtime_changed':False,'thresholds_changed':False}
(OUT/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
shutil.copy2(__file__,OUT/'reproduce_audit.py')
(OUT/'manifest.json').write_text(json.dumps({str(p.relative_to(OUT)):sha(p) for p in OUT.rglob('*') if p.is_file()},indent=2),encoding='utf-8')
print(json.dumps({'out':str(OUT),'rows':len(rows),'preserved':before==after},ensure_ascii=False))
