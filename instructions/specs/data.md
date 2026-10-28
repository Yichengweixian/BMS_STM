# BMS 测量记录与 SOC 数据规范

版本：0.1；日期：2026-10-28；状态：执行规范草案，尚无硬件标定或采集结果。

每条测量、SOC标签和训练结果须能追溯到原始数据、硬件、固件和处理方法。“必须”是项目准入要求，不代表认证。量程、容限、温度、采样率、预热等未核定参数标为 `TBD`，不得提前声明精度。

## 1. 原始数据、标定和派生结果分开保存

每次实验使用唯一 `run_id`。文件先用CSV/JSON即可；不强制数据库。

```text
run_<id>/
  manifest.json
  raw/device.csv                 # 板端原始码、时间和状态
  raw/reference.csv              # 独立参考仪表读数
  raw/events.csv                 # 复位、命令、换向、故障、停止
  calibration/cal_<id>.json       # 系数、条件、来源和验证结论
  calibration/points.csv          # 拟合与独立验证记录
  derived/measurements.csv        # 换算、对齐后的物理量
  derived/soc_labels.csv          # SOC参考值及质量标志
  derived/processing.json         # 输入哈希、脚本/参数版本
  split_manifest.csv             # 分组及训练/验证/测试归属
```

- `raw` 保存实际收到的原始码和状态，完成采集后固定文件哈希；不得用清洗值覆盖。
- 原始帧可另存；记录协议/解码版本。改变标定或算法时生成新派生版本。
- 派生文件记录输入SHA256、标定ID、脚本版本、参数和生成时间。缺失时仅归档，不作正式结果。
- 共用标定/证书可引用，无需重复复制；目标须可获取并有哈希。

## 2. 两路电流分别标定，参考仪表独立记录

| 通道 ID | 测量路径 | 要保存的原始量 |
|---|---|---|
| `current_mcu_adc1` | 电流前端 → PA1/ADC1 | ADC码、采样/过采样配置、参考电压信息 |
| `current_afe_gpio1` | 电流前端 → ADBMS GPIO1/AUX | 寄存器码、转换模式、PEC与转换状态 |

两路各自建立 `I = a × raw + b` 或明确等价的模型，不能直接套用对方系数。ADBMS 的结果标度与 MCU 的 `VREF/满量程码` 换算不同。[ADI 数据表](https://www.analog.com/media/en/technical-documentation/data-sheets/adbms1818.pdf)

共用分流电阻或放大器时，两路可能一起偏。彼此一致只作诊断，不能代替外部参考；先核实器件型号与增益，再标定完整链路。

参考仪表记录型号、序列号、量程、分辨率、校准日期、证书/规格、滤波和不确定度。无有效校准依据时标 `reference_grade=spec_only` 或 `unknown`，限定结论。仪表已校准不自动证明整套结果可溯源。[NIST 溯源说明](https://www.nist.gov/metrology/metrological-traceability)

以下是建议取点，基准为**已确认且不饱和的工作范围**：

- 拟合点：0、±10%、±25%、±50%、±75%、±100%。
- 独立验证：重新采集零点、边界点，以及 ±15%、±40%、±65%、±90%；数据不参与拟合。
- 建议三轮，含升降扫、前后零点回测及温漂检查；稳定阈值写入计划。
- 同一窗口抽行不算独立验证；滤波相关样本不能按独立样本计算不确定度。

报告保存系数/单位、适用范围、点ID、残差、零漂、不确定度和结论。高 `R²`或静态验证不能证明快环正确。

## 3. 精度判定必须考虑参考误差

先确定 `MPE(I)`，建议用“绝对项+读数比例项”，照顾零点；数值待硬件和实验目标确认。

预算覆盖参考仪表、增益/零点/温漂、重复性、量化、标定残余误差及不同步。修正已知显著偏差，保留修正不确定度；共同参考/标定误差不能都当独立项。[NIST 合成不确定度](https://www.nist.gov/pml/nist-technical-note-1297/nist-tn-1297-5-combined-standard-uncertainty)

建议预先约定三态保护带规则，保存各验证点结果：

```text
e = I_DUT − I_reference
Ue = 本次误差比较的扩展不确定度
通过：     |e| + Ue ≤ MPE
不通过：   |e| − Ue > MPE
无法判定：其余情况
```

`Ue`不等于显示分辨率。`U=k×uc`须记录覆盖因子；`k=2`不总是严格95%覆盖。“无法判定”不得算作通过。

## 4. 时间、序号与有效性

每条采样的最小字段：

```text
run_id, boot_id, stream_id, seq, channel_id,
device_sample_ticks, host_rx_utc, raw_code,
status_bits, valid, invalid_reason
```

manifest保存时钟频率/位宽、时间戳含义与采样模式。建议另存 `host_rx_monotonic_ns`分析延迟；设备时间戳指采样/转换事件，不指串口发送。

- **积分用采样时间**：主机接收时间含串口缓存与调度抖动，不能代替采样间隔。主机 UTC 用于实验定位，不直接作为积分时钟。
- **通道分别计时**：记录AFE、MCU及参考仪表时间/窗口、对齐方法与不确定度。同帧不代表同时采样。
- **区分复位与回绕**：`boot_id + stream_id + seq` 标识样本。记录复位原因、计数器回绕、重复帧、丢帧和重新连接；不能把复位后的时间直接接在旧段后。
- **坏数据不作零**：PEC失败、超时、饱和、陈旧值、预热未完成均保留原始记录；派生量用空值/`null`和原因。有效零电流才写数值0。
- **复用旧值要标龄期**：若界面保留上一有效值，记录 `source_age_us`；不得把它当新采样参与积分。

### 一秒一个点，必须说明它是什么

| `value_kind` | 含义 | 可否代表整秒电荷 |
|---|---|---|
| `instantaneous_sample` | 每秒某一时刻的读数 | 不能直接假定；动态工况可能漏掉脉冲 |
| `interval_mean` | 明确时间区间内的平均电流 | 有完整有效覆盖和已知平均算法时，可乘该区间长度 |
| `interval_charge` | 区间内累积电荷 | 必须给单位、算法、校准版本和区间边界 |

均值/累积量补 `interval_start_ticks`、`interval_end_ticks`、`sample_count`、`invalid_count`；抽点须注明规则。低速显示不证明快环稳定，也不自动满足电荷积分要求。

## 5. SOC 标签的口径与不确定度

统一符号：**流向电池为正，充电为正、放电为负**。SOC保存为0～1；百分数仅作显示。`C_N` 单位Ah、`Δt`单位秒。

```text
q[k]   = q[k−1] + I_effective[k] × Δt[k] / 3600
SOC[k] = SOC0 + q[k] / C_N
```

`C_N`注明铭牌或已测容量。正式标签优先用对应电池、温度、倍率及截止条件下的已测容量，保存记录ID、日期和不确定度；不能为使终点归零而事后改容量。

`SOC0`记录锚定依据及不确定度，例如定义充电终止/静置条件后的满充锚点。单次端电压不等于精确SOC；OCV映射须匹配电池、温度和静置条件。

效率口径写进 `efficiency_model`。例如充电时使用 `I_effective=ηc·I`；放电是否取 `I` 或另设效率，取决于参考容量的定义。不得把容量测量中已体现的损失再次重复计算。效率取1可以作为明确标注、带适用范围的近似，不代表已测得100%效率。

### 参考SOC不能由同一误差自证

正式精度评价优先使用**独立校准的外部电流和已确认的计时基准**建立参考SOC，板载电流作为输入或待测对象。参考SOC也有不确定度，不称绝对真值。

若标签来自同一板载电流的安时积分，标记：

```text
label_source = same_sensor_coulomb_counting
label_grade = proxy
```

代理标签可用于原型；拟合误差小或同源积分一致都不证明真实SOC精度，共同偏置会同时污染输入和标签。

标签保存SOC值、有效性/等级/版本、初值锚点、容量记录、电流源、标定ID、效率模型和不确定度。

未知电流缺口不得按零积分。独立参考补齐须注明来源；否则评估误差界限，无法界定时暂停后续标签有效性，直到可信锚点。保留未裁剪SOC与越界标志，不用0～1裁剪隐藏漂移。

示例：1 Ah电池持续偏置1 mA，一小时累积0.1个百分点SOC偏差；不是允许指标。预算应包括零偏、增益、时钟、效率、初值和容量，共同偏置不能作为独立噪声平均掉。

相关项需保留协方差或采用有依据的保守界限，区分共同偏置、增益与重复性。[INL 原始研究](https://inldigitallibrary.inl.gov/content/uploads/50/2026/04/3394979.pdf)

## 6. 训练划分与泄漏防止

**课程口径：**材料要求8:2训练/验证。若按此执行，如实报告“训练集/验证集”，不要把用于调参的20%改名为独立测试集。

**工程建议：**条件允许时，按完整分组划分80%开发集、20%最终测试集；开发集内部再划分训练/验证或做分组交叉验证。最终测试集仅用于冻结方案后的评价。8:2是目标比例，不应为了凑行数而拆开完整循环或电池。

先分组，再生成滑动窗口。分组依据对应要回答的问题：

| 想证明的能力 | 隔离单位 |
|---|---|
| 同一电池后续循环表现 | 完整循环/运行，按时间保留后续循环 |
| 对新电池泛化 | `cell_id`，同一电池不得跨训练与测试 |
| 对新工况泛化 | 完整工况/协议族，另设留出评估 |
| 对温度或老化范围外推 | 留出对应条件，并明确外推范围 |

`cell_id+cycle_id`组合分组仍可能让同一电池跨集合，不能证明新电池泛化。只有一节电池不得宣称跨电池泛化。[分组验证说明](https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-iterators-for-grouped-data)

必须避免：

- 重叠滑动窗口、同一循环切片或同一文件副本进入不同集合。
- 用全数据拟合归一化、缺失值估计、特征选择或模型参数；这些仅在训练侧拟合。
- 用最终测试集调参、选模型或确定量化范围；量化代表数据从训练侧选。
- 用未来数据做居中滤波、用循环终点修正输入，再把结果称为在线推理表现。
- 把已知未来SOC、独立参考SOC、结束时刻等泄漏字段混入模型输入。

`split_manifest`保存 `dataset_version, cell_id, run_id, cycle_id, profile_id, split, split_reason`；另记种子、窗口、特征和预处理版本。按电池/循环/工况报告指标。[官方泄漏说明](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage)

## 7. 最小 manifest 示例

以下仅为字段示例；`TBD`/空值须在对应准入前补齐。

```json
{
  "schema_version": "bms-data-0.1",
  "run_id": "TBD",
  "cell_ids": ["TBD"],
  "board_id": "TBD",
  "hardware_revision": "TBD",
  "firmware_sha256": "TBD",
  "build_target": "TBD",
  "protocol_version": "TBD",
  "test_plan_id": "TBD",
  "profile_sha256": "TBD",
  "current_sign": "positive_into_battery",
  "units": {"current": "A", "voltage": "V", "temperature": "degC"},
  "clock": {"tick_hz": null, "timestamp_event": "TBD", "calibration": "TBD"},
  "sampling": {"value_kind": "TBD", "rate_hz": null, "filter": "TBD"},
  "calibration_ids": {"current_mcu_adc1": "TBD", "current_afe_gpio1": "TBD"},
  "reference": {"instrument_id": "TBD", "range": "TBD", "certificate_sha256": "TBD"},
  "soc": {"label_grade": "TBD", "anchor_id": "TBD", "capacity_record_id": "TBD", "efficiency_model": "TBD"},
  "acceptance_plan": "TBD",
  "raw_files_sha256": {},
  "processing_version": "TBD",
  "stop_reason": "TBD"
}
```

## 8. 数据准入与失效范围

1. **测量准入：**身份、符号、标定及独立验证完整，符合已确定容限；超出标定量程/温度的记录明确标为范围外。
2. **记录准入：**原始文件与哈希存在，时间/序号可解释，错误不作零，处理可重复。
3. **标签准入：**初值、容量、效率、参考链及缺口处理明确，标签等级和不确定度支持拟作的结论。
4. **训练准入：**分组隔离无泄漏，预处理仅训练拟合，验证/测试口径清楚。

单个通道失败只使该通道及依赖它的派生量失效，不删除整个原始文件。电流未知可能影响此后SOC；温度缺失可能只影响需要温度的特征或温度适用性判断。按依赖关系传播质量标志，写清剔除范围与原因。未过准入的数据可保留作调试证据，但不得混入正式精度评价而不标注。
