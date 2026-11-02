# G01 电压取点与离线复算

本工具只做离线统计和电芯电压候选系数计算，不操作串口、不更改固件、不启动功率级。电流、温度实物标定按用户当前条件暂缓；温度继续保存原码、质量标志，不能把 `estimate` 当作校准温度。

## 原始数据检查

在项目根运行，输出必须是新文件：

```powershell
python scripts/g01/voltage_calibration.py inspect evidence/runs/<run>/capture --out evidence/runs/<run>/statistics.json
python scripts/g01/analyze_capture.py evidence/runs/<run>/capture --out evidence/runs/<run>/continuity.json
```

第一条先校验采集 manifest 中原始字节、事件、CSV 的 SHA256，再复核每条记录的串口校验、AFE PEC及状态语义。它输出所有9通道有效/无效计数、原码均值、样本标准差、极差，电芯另给名义电压统计。第二条补充序号缺口、重复、采样周期和不完整组。整段标准差可能包含漂移，不是测量准确度或仪器不确定度。无效样本保留计数，不填零或进入有效均值。

## 电压参考与候选拟合

复制 `scripts/g01/voltage-points.template.json` 到该次实验目录填写；capture 路径相对于这个 JSON。每个通道单独标定：至少3个不同参考电压的拟合点，另有未参与拟合的独立采样/参考点。每个点至少3条连续有效样本。**三节电池各测一次不等于同一通道的三个标定点。** 当前不要求用户为制造多个电压点而拆电池或启动充放电。

每点包含：

- `id`、`role`（fit / validation）、`channel`（cell1 / cell7 / cell13）。
- `capture`、`boot_id`、`seq_first` / `seq_last`：实际对应测量的稳定采样区间，回绕处拆开；有缺帧、重复、无效、过期或时间跳变时拒绝拟合。
- `reference_V`、`instrument_id`：独立参考读数及仪器身份。
- `mapping_evidence`：实物 A/B/C 对 AFE 通道的确认依据；不得按近似电压大小猜测。
- `reference_time_evidence`：参考时钟与采集时钟对齐的依据；仅有“差不多同时”不能完成此项。
- `reference_condition`：独立取点条件/会话的标识。不能把同一次稳定窗口随机拆成训练和验证，也不能只换标签绕过这一要求。
- `expanded_uncertainty_V`、`uncertainty_basis`：该点误差比较的合成扩展不确定度 U95 及计算依据，未知留 null。仪器规格最大允许误差不可直接填为 U95。

这些依据由实验执行者填写，程序检查字段存在，但不能自动证明接线、时间同步、独立性或仪器溯源真实。参考点计划冻结后运行：

```powershell
python scripts/g01/voltage_calibration.py fit evidence/runs/<run>/voltage-points.json --out evidence/runs/<run>/voltage-candidate.json
```

各点原码均值等权最小二乘拟合 `V = gain * raw + offset`；输出系数、拟合范围、逐点误差、波动、拟合/验证点 ID、固件与来源文件哈希。记录数不同不会让某一长窗口获得更多权重。拒绝混用不同固件、实物/模拟证据，拒绝重复或重叠窗口。拟合范围外的点不判通过；未覆盖区域不得外推使用。工具不处理温度传感器模型或两路电流系数。

只有填写已冻结 `tolerance_V` 和 `acceptance_basis`，并有 U95 时，才为范围内独立实物验证点给出 guard-band 比较：

- `abs(error) + U95 <= tolerance`：pass。
- `abs(error) - U95 > tolerance`：fail。
- 其他：inconclusive；缺少依据或模拟数据：null。

这仍是候选分析，`calibration_verified=false`、`formal_G01_verdict=null`；需人工审查参考质量、范围覆盖、模型适用性和独立验证后，另行发布校准版本。此工具没有自动写系数的接口。

## 当前实物限制

2026-10-31 用户确认目前只能测电压，无负载；电流/温度标定暂缓。A/B/C 最新手工值3.895/3.894/3.894V已保留，用户时间14:05:05/14:06:09/14:07:00与本次电脑记录13:52:18—13:53:48不对应，且实物位置到AFE通道仍未确认。不能拿这批数据生成正式系数。先前单体/GND测量支持电池串顺序C→B→A，但不等于AFE映射已验证。

现有 C.A5212 的4V档名义分辨率1mV，厂家准确度规格为±(0.2%读数+2字)，约3.9V时对应约±9.8mV的规格误差界，非已知U95。详情见仪器登记记录；数mV的表/板差异暂不能归因于板端偏差。后续只需电压可操作的测点和合适参考条件，电流夹具不阻塞此工具工作。

## 回归

`python scripts/g01/run_checks.py --out evidence/runs/<new-check-run>` 包含生产C故障注入、所有 `tests/g01/test_*.py`、36条模拟串口端到端回放。拟合测试数据为人工数学向量，不构成实物标定证据。
