# TIM1 / ADC 独立核验

日期：2026-11-01。范围：老师 HEX 的静态汇编、本地 STM32N6 HAL/CMSIS、ST 官方 RM0486 Rev 4。没有连接硬件或执行固件。

## 结论

1. **TIM1 中心对齐计数的完整周期是 `2 × ARR` 个计数时钟。** 对 `PSC=0, ARR=1999`，`f_PWM = f_TIM / 3998`，不能使用 `f_TIM / 4000`。若另有证据确认 `f_TIM=200 MHz`，理论载波为约 `50,025.013 Hz`，不是精确 50 kHz。此处没有独立证明老师固件的最终 TIM1 内核时钟数值。
2. **`RCR=1` 对应每两个计数端点、即每个完整中心对齐 PWM 周期一次更新。** 当 TRGO 选择 UPDATE 且没有额外 UG/从模式更新、UDIS 禁止等因素时，稳定更新/TRGO 频率等于载波频率。RCR 不把 PWM 载波再除以二。CMS=1 控制输出比较标志在哪个计数方向置位，不把更新事件限定为一个方向。
3. **`0x480` 确实是 STM32N6 的 TIM1_TRGO 触发宏。** `EXTSEL=4` 的移位编码为 `0x80`；`0x400` 为上升沿 EXTEN。HAL 初始化会分别取触发源掩码和 `ExternalTrigConvEdge`，并非把宏的所有位原样当作 EXTSEL。
4. **STM32N6 ADC 在 `OVRMOD=0` 时有 8 级 FIFO，两次DR访问可以依序取出两个转换结果。** 仅在 `OVRMOD=1` 时 FIFO 被禁用并保留最新转换值。老师回调还有根据 EOC 排空 FIFO 的循环，不能仅凭同地址读取就认定是重复采样错误。
5. **正常序列下“两读”有硬件依据；异常后样本完整性仍需单独处理。** OVR 表示已有结果丢失，清 OVR 不会找回数据或自动证明 rank/周期重新对齐。静态代码中可确认存在清 OVR 后继续进入控制计算的路径；“已经发生错误采样/必然 rank 错位”则没有运行证据。

## 定时器依据与相位

RM0486 Rev 4 §53.3.4，纸面页 2499-2500：上数取 `0..ARR-1`，随后下数取 `ARR..1`，再回到零。因此每周期一共 `ARR + ARR` 个 tick，`f_CNT=f_TIM/(PSC+1)`。

§53.3.5，页 2504-2505：RCR 每遇溢出或下溢减一次，每 `RCR+1` 个端点生成更新。奇数 RCR 的更新落在峰端还是谷端，取决于 RCR 写入和计数启动顺序。不能仅凭 `center-aligned1 + RCR1` 声称 ADC 必定在某一个固定端点采样；还要核对 UG、CEN、RCR 的顺序。软件 UG 产生的初始化更新也不能当成稳定周期中的一个样本。

本地 `stm32n6xx_hal_tim.h:65` 的 `RepetitionCounter` 注释也明确中心对齐模式按半周期计数。

## ADC 触发源和 CKPER 是不同配置

本地定义链：

- `stm32n6xx_hal_adc.h:575`：`ADC_EXTERNALTRIG_T1_TRGO` 引用 LL 宏。
- `stm32n6xx_ll_adc.h:1039`：`ADC_CFGR1_EXTSEL_2 | ADC_REG_TRIG_EXT_EDGE_DEFAULT`。
- `stm32n647xx.h:5212` 起：EXTSEL 在 bit 5，掩码 `0x3e0`，`EXTSEL_2=0x80`。
- 同文件 `5221` 起：EXTEN 在 bit 10，rising=`0x400`。
- `stm32n6xx_hal_adc.c:540`：源字段按 EXTSEL 掩码取值，另外合入 `ExternalTrigConvEdge`。

因此 `0x480` 表示“由 TIM1_TRGO 上升沿启动”，**不表示 ADC 转换时钟来自 TIM1，更不表示 CKPER 的频率**。RM0486 §32.4.3，页 1472，区分 ADC 寄存器访问的 AHB 时钟和独立 ADC 内核时钟。异步时钟域还可能引入触发同步不确定性；TRGO 周期不等于转换用时。

N6 的 ADC 分频属于 RCC。`stm32n6xx_hal_adc.h:73` 明确提示与一些其他 ADC IP 不同，不能寻找 `hadc.Init.ClockPrescaler`。RCC 中需要同时核对 `AdcClockSelection`、`AdcDivider`；CLKP/CKPER 上游由 `CkperClockSelection` 决定。本地源码模板选 CLKP，并把 CKPER 源设为 HSI，但模板配置不能替代对老师二进制最终时钟的核验。

## FIFO 对两读和异常的正确解释

RM0486 Rev 4 的直接依据：

|位置|核实内容|
|---|---|
|§32.4.23-24，页 1493|EOC 表示可读数据；FIFO 未空时 EOC 再次置位；EOS 表示最后一个序列转换完成|
|§32.4.26，页 1496|`OVRMOD=0` 时 ADC_DR 有 8 级 FIFO|
|§32.4.26，页 1501|FIFO 满时 OVR；preserved 模式丢弃新数据，OVR 保持时后续结果也被丢弃；CPU 可以继续读取排空|
|同节页 1501|`OVRMOD=1` 关闭 FIFO，DR 被最新结果覆盖|

老师二进制中的可定位事实：

- `0x701010ce` 和 `0x701010dc` 两次调用 `0x701083f0`。
- `0x701083f0` 取 `hadc->Instance`；`0x701083f2` 从偏移 `0x40` 读取，即 ADC_DR。FIFO 语义来自硬件，不在 HAL 读函数里体现。
- ADC1 初始化 `0x701015f0` 将零写入 handle 偏移 `0x30/0x34`，对应 ConversionDataManagement/Overrun；因此正常配置是 DR 管理、preserved FIFO。动态 ADC 配置需要结合实际路径的序列长度确认 rank 数量。
- `0x70101158..0x70101162`、`0x7010116e..0x70101178` 检查 ISR.EOC 并至多执行 8 次 DR 读取，符合排空 8 深 FIFO 的实现。
- `0x701010fa..0x70101102` 在 ADC2 路径检查 ISR.OVR 并写 `0x10` 清标志，随后 `0x70101104` 继续获取数据、`0x7010111a` 进入控制计算。这个局部路径没有先把该次样本标为无效或退出控制。

在“FIFO 开始为空、两 rank 都完成、无溢出、读取期间没有插入别的消费者”的条件下，EOS 后两读可以正确取出 rank 1、rank 2。上述 FIFO 机制已消除仅凭同地址读两次提出的错误诊断。

尚需区分的异常风险是：FIFO 溢出、延迟导致的旧序列积压、排空过程中又有新转换到来，可能造成数据丢失、样本跨周期或 rank 边界错位。清标志/排空能帮助恢复，但没有独立的序列边界确认时不能视为完整性证明。是否实际触发、是否被其他中断/故障处理覆盖，需要进一步控制流或运行证据；这里不宣布老师固件必然存在该故障。

如要重建可靠版本，异常恢复应把当前批次判无效、计数并记录 OVR，重新建立序列边界后才允许进入控制；正常 FIFO 路径不必因为“两次 DR 读”本身被改掉。

## 来源和可复查产物

- ST 官方下载：[RM0486](https://www.st.com.cn/resource/en/reference_manual/dm00769900.pdf)。本轮取得 **Rev 4，4669 页**，SHA-256 `83cb7e9c7f784a4c5dbbedec428adf58d2cbac8cd802d11e2cdc4d504cceaa86`。不要把搜索缓存中的 Rev 2 页码混入本报告。
- 下载原件和抽取文本留在本机分析目录 `C:/Users/ADMIN/.codex/visualizations/2026/10/31/01a190f7-17b3-7453-a3ab-b4c2e18cd61a/hex-reverse-20261101/scripts/RM0486.pdf`（同目录 `RM0486-adc.txt`、`RM0486-tim.txt`）。本文只概括核验结论，完整表述以手册为准；归档项目不重复复制整本手册。
- 本地 HAL 根：`D:\ADMIN\Desktop\WEIJI\zonghe\BMS_EXv1.1\BMS_EX\Drivers\STM32N6xx_HAL_Driver`。
- 汇编证据：本轮 `local-only/disassembly-v81m.txt`，使用 `-m armv8.1-m.main -M force-thumb` 正确解码MVE；关键摘录随本报告归档。
