from pathlib import Path
import hashlib,json
ROOT=Path(r'D:\ADMIN\Desktop\WEIJI\zonghe')
STAGE=Path(__file__).parent
RUN=ROOT/'evidence/runs/20261101-G03-current-path-r1'
a=json.loads((RUN/'derived/analysis.json').read_text())
documents=STAGE/'documents';documents.mkdir(exist_ok=True)
report='''# G03 MCU电流输入交叉检查

本次完成7组禁能ADC诊断，共448个原码，原寄存器与ADC状态恢复核对通过；第三次继电器实验的DONE状态、单次已使用标志、102组缓存及接通/撤销时间保留。固件仍为g03-relay-r2，未下载、复位或发送新的功率启动命令。

诊断执行结论为pass；MCU电流输入问题的根因判定为inconclusive。所有数据physical_valid=0，不能据此宣布G01或G03正式验收通过。

## 动作与证据

- 入口为COM11的op20状态、op21/profile0禁能64点诊断和op30继电器状态，仅这三种请求，共7次诊断。
- ADC1保持12位、单端、OS2右移1和未新增自校准状态。通过SWD HOTPLUG暂停CPU，在ADC禁用且无转换时临时切换SQR1/PCSEL/SMPR1/SMPR2/CCR；每次写入逐项读回。只为内部VREF通道临时启用VREFEN，未启用VREFBUF输出、未写OTP。
- PA1为CH1，PA0/PA10/PA2分别为CH0/CH11/CH14。引脚对应关系见[ST DS14791引脚表](https://www.st.com/resource/en/datasheet/stm32n647a0.pdf)，工程main.h/MSP定义分别为I_AD/VB_AD/VL_AD/VS_AD；软件标签不能证明实物模拟节点已连接。
- 每组保留全部64点。后48点统计仅用于描述稳定尾段，前16点未删除；分通道覆盖期间的常规遥测不作为电流记录使用。诊断报文没有逐点硬件时间戳，因此图的横轴使用样本序号，不冒充采样时间曲线。
- 所有输入配置恢复到保存值后，再读取原PA1配置。额外只读确认PWR.SVMCR3.ASV=1，PA0/1/2/10均模拟模式、无上下拉，TIM1.CEN=0、CCER=0、MOE=0，PB5/PG5输出命令为低。

## 原码结果

|输入/配置|采样周期数|首点|后48点中位数|后48点范围|
|---|---:|---:|---:|---|
'''
names={'current-before':'PA1 原配置','input-0':'PA0 / VB_AD标签','input-11':'PA10 / VL_AD标签','input-14':'PA2 / VS_AD标签','internal-vref':'片内VREF / CH17','current-long':'PA1 长采样','restored-current':'PA1 恢复原配置'}
for g in a['groups']:
    report+=f"|{names[g['label']]}|{g['sampling_cycles']}|{g['first']}|{g['tail_median']:g}|{g['tail_min']}—{g['tail_max']}|\n"
report+='''
PA1短采样→长采样→恢复短采样的尾段中位数为1272→1232→1271码。该结果支持继续调查采集配置对外部输入读数的影响；各组顺序采集、没有独立模拟参考，不能把40码差异归因于某个确定的电阻、断线或芯片故障，也不能当成真实电流变化。

片内参考与外部通道的读数有区别，排除了“诊断接口始终返回同一固定值”这一现象；它没有证明外部电流传递关系正确。现有源代码、引脚模式、模拟供电有效位和通道寄存器检查未发现可据此修复的通道号错误。当前不修改换算比例或真实保护限值。

课件第7页的原始电流图只展示R1分流器、U5与I_ADA输出，未给出I_ADA到PA1/I_AD之间的完整连接。照片也不足以确认同一节点，因此hardware-profile中的mcu_and_afe_current_same_node仍为null。前次三次继电器记录的MCU变化+0.5/−1/0码仍是“未观察到相应变化”，不改写成已证明断路。

## 本次交付与后续入口

- [原始运行清单](manifest.json)、[采集及恢复结果](result.json)、[复算指标](derived/analysis.json)、[全部原码CSV](derived/samples.csv)、[汇总CSV](derived/summary.csv)、[曲线](derived/adc-input-comparison.png)。各串口子目录保留serial.bin、events.jsonl和原始解析记录，swd目录保留全部命令、stdout/stderr。
- [诊断过程](procedure/probe_current_path.py)、[只读配置核对](procedure/inspect_restored.py)、[离线分析](procedure/analyze_current_path.py)、[绘图](procedure/plot_current_path.py)。硬件脚本限定本次固件和DONE/live_used=1入口，不应直接用作下一版通用功率工具。
- [原构建与固件身份](../20261101-G03-relay-r2/production-source-manifest.json)：本次171份生产源文件及Release HEX哈希与该清单一致，未改固件，因此沿用已有Debug/Release构建和烧录证据。

下一项需要明确I_ADA至PA1的实际连接、输入调理与电流路径。用户已明确没有完整原理图，本轮不要求小焊点测量。需要获得板厂的连接资料或由具备条件的实验人员确认这条路径；不能靠将采样延长或改系数宣布反馈可用。真实PWM继续依赖反馈路径、有效死区和供能/退出条件。已有PWM参数计算和禁能状态机成果保留。

当前保持运行档（BOOT1=0、BOOT0=0），无须切换下载档；本轮没有改变BOOT设置。最终输出禁能、故障0，第三次继电器结果仍可查询读取。
'''
(documents/'work-card.md').write_text(report,encoding='utf-8')
status=(ROOT/'instructions/STATUS.md').read_text(encoding='utf-8')
status=status.replace('MCU电流路径问题仍未闭合','MCU电流路径问题仍未闭合；追加448点禁能输入交叉检查并恢复寄存器')
status=status.replace('最新交付：[重复性工作卡]','此前交付：[重复性工作卡]')
status+='''

最新禁能诊断：[MCU电流输入工作卡](../evidence/runs/20261101-G03-current-path-r1/work-card.md)。7组448点完成并核对原始CRC/聚合值，PA1原采样/长采样/恢复后的尾段中位数1272/1232/1271码；模拟供电有效位、模拟引脚模式和通道配置读回符合源码，寄存器与ADC状态全部恢复，第三次继电器记录保留，输出0。静态检查未定位I_ADA至PA1的实际连接或传递关系，根因仍inconclusive，真实PWM未执行；用户确认没有完整原理图，需要板厂资料或具备条件的路径确认，不以修改系数替代。
'''
log=(ROOT/'instructions/RUNLOG.md').read_text(encoding='utf-8')+'''

## 2026-11-01 G03 MCU电流输入禁能交叉检查

用户要求继续。沿用g03-relay-r2，先核对DONE/live_used=1/输出0，再使用现有op21/profile0和SWD临时ADC复用配置，比较PA1、PA0、PA10、PA2及片内VREF。共7组448点，全程无下载、复位、继电器/PWM启动、自校准或物理换算修改。寄存器按原值逐项恢复并读回，原ADC配置状态与第三次继电器结果保持。

PA1短采样/长采样/恢复短采样的后48点中位数1272/1232/1271码，片内参考1823码；所有原码及启动收敛保留。只读确认ASV=1、PA0/1/2/10模拟无上下拉、TIM1功率输出和PB5/PG5禁能。源代码与通道映射未发现确定错误，完整模拟连接仍未确认，根因判读inconclusive；用户确认没有完整原理图，不要求用户测小焊点。未把缺少负载响应解释成零电流或断路。生产171份文件及原Release镜像哈希不变。见evidence/runs/20261101-G03-current-path-r1/work-card.md。
'''
hp=json.loads((ROOT/'instructions/specs/hardware-profile.json').read_text(encoding='utf-8'))
assert hp['mcu_and_afe_current_same_node'] is None
hp['g03_current_input_diagnostic']={
 'run_id':RUN.name,'firmware':'g03-relay-r2','groups':7,'raw_samples':448,
 'power_start_commands':0,'registers_restored':True,'relay_result_preserved':True,
 'pa1_tail_median_codes_short_long_restored':[1272,1232,1271],
 'adc_supply_valid_bit_set':True,'input_pin_modes_verified':True,
 'root_cause_confirmed':False,'verdict':'inconclusive','physical_valid':0,
 'complete_schematic_available_per_user':False,
 'physical_limits_unchanged':True,'report':'evidence/runs/'+RUN.name+'/work-card.md'}
changes={'instructions/STATUS.md':status,'instructions/RUNLOG.md':log,
         'instructions/specs/hardware-profile.json':json.dumps(hp,ensure_ascii=False,indent=2)+'\n'}
manifest={}
for name,content in changes.items():
    dst=documents/name;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_text(content,encoding='utf-8')
    manifest[name]={'before_sha256':hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),
                    'after_sha256':hashlib.sha256(dst.read_bytes()).hexdigest()}
(documents/'change-manifest.json').write_text(json.dumps(manifest,indent=2))
print('Prepared work card and 3 tracked documentation updates; root unchanged')
