# G01 软件采集与记录（g01-sw-r2 / g01-v1）

本次只实现 G01.1—G01.3 中不依赖参考仪器的部分。实际供电、探头/增益、接线、方向和精度仍以 [hardware-profile](hardware-profile.json) 的未确认字段为准；当前 Release r2 已烧录并完成实板连续原码采集验证；独立标定与准确性验证仍未执行。源码在 `BMS_EXv1.1/BMS_EX/BSP/measurement*.c` 和 `adbms_acquisition.c`，两个 Keil target 均纳入。

## 行为和边界

- 主循环每 500 ms 尝试一组采集（约 2 Hz）。ADC1 软件触发、12 bit、2 次过采样右移 1，结果尺度仍为 12 bit。ADC1 与 AFE 分开计时，一路故障不阻止另一路记录。它不是 PWM 同步的高速控制采样。
- ADC1 使用 `HAL_ADC_Start/PollForConversion/GetValue/Stop`，轮询限时 10 ms；内部 ADC 自校准暂未开启，完整外部链路标定待做。ADC2 保留原初始化但不启动，ADC2/Ioc 差异仍待后续所需电压通道任务处理。
- TIM1/TIM2 没有 Start 调用；继电器保持原初始化 LOW。新 AFE 驱动写 CFGA/CFGB 时将所有 DCC 清零。不据此宣称继电器物理开路已验证，也不改变硬件限值。
- AFE 单器件 SPI，每次传输限时 10 ms；配置读回检查长度约定与 PEC，参考启动等待 5 ms。转换前清结果寄存器，再发送 MD=2/ADCOPT=0 的转换命令，PLADC 保持 CS 低查询完成，整次转换限时 20 ms。清除后未转换的 0xffff 会被拒绝；读回错误只影响相关通道。
- 旧驱动仍供历史代码保留；主循环不再调用旧的填零换算函数。旧 UART 原样回显关闭，RX 只重启接收，防止中断回显插入 CSV。此版本未增加功率控制命令。
- OLED 仍显示 BMS_EX。500 ms 是尝试周期，不是精确定时或整周期平均；超出周期不追赶补采，主机检查序号与实际采样间隔。

## 通道字典

| channel | 输入 / 寄存器 | raw → 传感电压 | estimate 的意义 |
|---|---|---|---|
| cell1 | ADBMS C1 / RDCVA 第1码 | raw × 0.0001 V | 未校准电芯电压 |
| cell7 | ADBMS C7 / RDCVC 第1码 | 同上 | 同上 |
| cell13 | ADBMS C13 / RDCVE 第1码 | 同上 | 同上 |
| current_afe_gpio1 | AFE GPIO1 / RDAUXA 第1码 | 同上 | `(V-0.900)*1.3333 A`，继承示例，增益/零点/方向未确认 |
| temperature_gpio2 | GPIO2 / RDAUXA 第2码 | 同上 | PT1000 线性示例 |
| temperature_gpio3 | GPIO3 / RDAUXA 第3码 | 同上 | PT1000 线性示例 |
| temperature_gpio4 | GPIO4 / RDAUXB 第1码 | 同上 | PT1000 线性示例 |
| current_mcu_adc1 | PA1 / ADC1 INP1 | raw × 1.8 / 4096 V，1.8为资料标称 | 电流系数无独立依据，estimate 留空 |
| afe_vref2 | RDAUXB 第3码 | raw × 0.0001 V | 内部第二基准读数；不等于探头端激励实测 |

温度 estimate 使用 `R=9100*V/(3-V)`、`T=(R/1000-1)/0.00385`。实际传感器/拓扑未知，电压有效不代表温度模型正确。`V<=0` 或 `V>=2.999` 不执行分压换算。VREF2 同步记录仅作诊断，未自动替换为实际探头激励。两条电流方向均未实测；AFE estimate 正负只是示例代数方向，不是已确认的“充电为正”。

## CSV 协议

USART1 PE5 TX / PE6 RX，115200 8N1。开机发 `#BOOT`，开机及每20组发 `#META/#CONFIG/#FIELDS`，主机中途连接也能获取身份。`#META` 含固件版本、编译时间和标定身份；确切镜像 SHA256 由构建/烧录记录与记录器 manifest 关联，不能从 COM 口推断。

每通道一行，固定18列：

```text
type,seq,channel,start_ms,end_ms,age_ms,raw,status,raw_valid,sensor_V_nominal,estimate,unit,physical_value,physical_valid,reference,cal_id,frame_hex,wire_pec15
```

- `seq`：本轮尝试序号，9通道共用，32 bit。UART 丢失不回退序号。主机逐通道查丢失、重复、整组缺项。
- `start_ms/end_ms`：32 bit HAL tick、1 kHz；软件包围转换的起止窗口，非 UART 发送时间、非各 ADC 精确采样瞬间。未得到 raw 的记录标示失败尝试窗口。AFE 各 AUX 在同次顺序转换内，不声称与 MCU 同时采样。
- `age_ms`：开始格式化该行时距 end_ms 的无符号时间差；超过1000 ms 标过期。这是软件诊断阈值，非控制安全时限。
- `raw`：完整读回的码，即使坏 PEC 也保留供诊断；未得到完整传输或转换超时则空。`frame_hex` 保存 AFE 6数据字节＋2字节PEC，ADC1 无此字段。配置失败时不提供旧测量帧，状态记录失败原因。
- `raw_valid`：仅表示本版传输、转换、边界与时效检查通过。不是准确性认证，不能证明没有模拟前端限幅或接线错误。
- `sensor_V_nominal/estimate`：诊断派生值；有无效位时两者都空。即使有效也始终带 UNCALIBRATED。当前所有 `physical_value/reference` 均空、`physical_valid=0`、`cal_id=uncalibrated-v1`，不得拿 estimate 进入 PI/SOC。
- `wire_pec15`：最后一个逗号之前所有 ASCII 字节的 PEC15，4位十六进制；与 AFE 寄存器 PEC 分开，排除 CR/LF。记录器同时检查串口完整性及 AFE 原帧/原码一致性。

| status 位值 | 意义 |
|---|---|
| 1 | SPI传输 / ADC启动等 I/O 错误 |
| 2 | AFE PEC 错误 |
| 4 | SPI、AFE转换或ADC轮询超时 |
| 8 | 0xffff清除哨兵、ADC1码0/≥4095或温度分压边界；只是明确可判别的边界检查 |
| 16 | 过期 |
| 32 | AFE配置读回不一致 |
| 64 | MCU ADC错误，包括启动、轮询、溢出/其他HAL状态、停止失败 |
| 128 | 未标定；每一行都有 |
| 256 | 没有完整的新raw |

除128外任意置位都会使 `raw_valid=0`。有效零电流估算可以是0；通信错误不能伪装成0。未知的实物量程、温区、放大器限幅和开路诊断不能用软件码值检查替代，待 G01.4/G01.5 实测。

## 记录与复算

在项目根运行，目录必须是新目录，防止覆盖原始证据：

```powershell
python scripts/g01/g01_capture.py --port COM9 --seconds 60 --out evidence/runs/G01-capture-001
```

当前实板已运行 Release r2，最近串口为 COM9；旧 G00 的一次性文本不是此协议。实际 COM 号按当前枚举替换。记录器依赖 pyserial，仅打开接收，不发送命令、切换 BOOT 或复位。若确知烧录镜像可追加 `--firmware-sha256 <64位哈希>`，未知留空。Ctrl+C 会关闭端口并保存退出原因及文件哈希。

输出 `raw/serial.bin` 原字节、`raw/events.jsonl` 元信息/错误/丢帧、`derived/device.csv` 加主机时间和run/boot/stream身份的结构化数据、`manifest.json`。不会生成伪造的参考表读数；之后实物标定另建 `raw/reference.csv`，按独立参考和测点编号对齐。

boot_id 由主机 session UUID + 段号生成；收到 BOOT 标记后分段，缺标记但序号倒退则记“推断复位或乱序”，不混成连续积分数据。32 bit tick/seq 的正常回绕与回退分开处理；每次重连使用新session。采集开头/结尾的不完整帧和通道组如实记事件。

软件检查可重跑（输出目录同样需新建）：

```powershell
python scripts/g01/run_checks.py --out evidence/runs/G01-software-check-001
```

需要 GCC 和 Python。编译生产 C 代码＋测试 HAL，覆盖换算向量、PEC、SPI超时/部分读失败、配置不符、转换忙/超时/未更新、ADC错误和独立调度，再检查 Python 解析器、校验、缺帧、复位、时间回绕，最后回放真实 C 格式化器生成的模拟字节。所有此类输入明确为 simulation，不能替代板端连续运行与参考仪器标定。

## 依据

- [ADBMS1818 Rev.B](https://www.analog.com/media/en/technical-documentation/data-sheets/adbms1818.pdf)：第38页清除命令、第59页转换完成查询、第62页命令表、第65—66页寄存器映射。
- 工程自带 STM32N6 HAL：`HAL_ADC_Start/PollForConversion/GetValue/Stop`；Oversampling Ratio字段由驱动减1写寄存器，2次平均右移1未改变12bit原码尺度。
- [G01 提示词](../prompts/G01-measurement.md)、[验收 G01](acceptance.md)、[数据规范](data.md)。当前工作卡和本次实际检查在 `evidence/runs/20261031-G01-software/`。


## 2026-10-31 实板修正与验证

首版g01-sw-r1实际输出9通道记录，但8个AFE通道状态416（CONFIG＋NO_RAW＋UNCALIBRATED），ADC1有效；失败原始记录保留在 `evidence/runs/20261031-G01-board/capture-01`。

依据ADBMS1818 Table72：GPIO位写入控制下拉，读出反映输入逻辑电平；DTEN/MUTE是只读状态。r2比较CFGA第0字节只取REFON/ADCOPT(0x05)，CFGB第0字节只取DCC(0xf0)、第1字节排除MUTE(0x7f)，其余配置仍检查。模拟HAL已改成真实GPIO读写语义，并保留REFON、ADCOPT、DCC、FDRF不匹配的失败测试。

修复后的Release r2编译0错误0警告、烧录读回校验成功，用户恢复正常BOOT并RESET后显示BMS_EX；实际连续记录见 `evidence/runs/20261031-G01-board/capture-02`，统计见该run的 `result.json`。这是采集通路和协议验证，所有physical_value仍空、physical_valid仍0，不构成电流或温度标定。MCU名义1.8V换算不能用于判定其与AFE电流端电压一致，实际参考电压和通路需实测。


## 电压离线标定工具

新增哈希/协议复核、原码统计、电压候选拟合及独立点验证，见 [G01电压取点与复算](G01-voltage-tools.md)。工具不改变固件，电流和温度校准按用户当前条件暂缓。
