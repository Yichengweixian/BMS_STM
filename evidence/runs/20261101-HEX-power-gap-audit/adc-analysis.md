# 老师 HEX：ADC、电流反馈与 AWD 关断链恢复

日期：2026-11-01。范围：static；没有访问串口、烧录或启动功率输出。

来源为 `D:/ADMIN/Desktop/WEIJI/zonghe/firmware/prebuilt/BMS_Appli.hex`，SHA256 `dd44fae11ed542ad6bcee45b35a13e93bd6632481b7d29662afda8ac7856be7f`。分析使用已校验的 `prebuilt.bin`（base `0x70100400`）及全文 Thumb 汇编。以下函数名为按 HAL 寄存器行为推定的分析名称，不是恢复的原始符号。

## 1. 电流工作通道仍为 PA1 / ADC1 CH1

这不是“老师使用另一个电流引脚”的证据。必须区分启动默认初始化与进入充放电时的动态重配置：

| 路径 | 地址证据 | 恢复结果 |
|---|---|---|
| ADC1句柄 | main `0x701015bc..0x70101604`，常量 `0x70101898/189c` | handle `0x34000a18`，instance `0x50022000` |
| ADC2句柄 | main `0x7010164e..0x7010169c`，常量 `0x701018a0/18a4` | handle `0x340009b8`，instance `0x50022100` |
| ADC1默认规则序列 | `0x70101622..0x7010163a`，常量 `0x70101820` = [11,6,3,0x3ff] | CH11、rank1、11.5周期、单端 |
| ADC2默认规则序列 | `0x701016a6..0x701016ea` | CH0/rank1，CH14/rank2，CH11/rank3；11.5周期 |
| 工作模式的ADC1配置 | `0x70105bb8..0x70105c18`，常量 `0x70105d00` = [1,6,2,0x3ff] | CH1/rank1、CH0/rank2；6.5周期、单端 |
| 工作模式的序列长度 | `0x70105c4c..0x70105c56` | `ADC1->SQR1 = (SQR1 & ~15) | 1`，两个规则转换 |
| 工作模式 ADC2 | `0x70105d2c..0x70105d92` | 可按模式选定一个电压通道；6.5周期，规则长度1 |

ADC1启动默认CH11用于电压/待机路径，不能据此把当前MCU电流通道从CH1改成CH11。电流控制模式调用 `0x70105bb8` 的调用点至少包括 `0x701073b6, 0x7010753a, 0x701076d0, 0x70107846, 0x7010795a`。

### MSP 与引脚

`HAL_ADC_Init` 分析函数 `0x701081a4` 在句柄未初始化时于 `0x701081e0` 调用 MSP `0x70101f6c`。

- ADC1 分支：`0x70101fd2..0x70101ff4`，GPIOA地址 `0x56020000`，Pin mask `0x403` = PA0、PA1、PA10；Mode=3（模拟），Pull=0。
- ADC2 分支：`0x70102040..0x70102062`，GPIOA Pin mask `0x407`，即另含PA2；同为模拟/无上下拉。
- `0x70101ffc..0x70102004` 设置并启用 IRQ46，即 ADC1_2，中断优先级参数0/0。
- `0x70101f9e..0x70101fac` 以及 ADC2对应分支选择ADC外设时钟源0x10（CLKP），divider=1。

与当前源码的物理引脚选择一致。HEX里没有发现另一个电流输入通道来解释当前PA1不响应；仍需区分I_AD与I_ADA实际连线，以及继电器支路和PWM功率支路。

## 2. 触发、过采样与读取链

老师两个ADC初始化句柄的关键参数：

- Resolution=0，即12位；GainCompensation=0。
- ADC1 ScanConvMode=0、NbrOfConversion=1；ADC2 ScanConvMode=1、NbrOfConversion=3。
- EOCSelection=8，序列结束。
- LowPowerAutoWait=0、ContinuousConvMode=0、DiscontinuousConvMode=0。
- ExternalTrigConv=0x480（TIM1_TRGO），ExternalTrigConvEdge=0x400（上升沿）。
- ConversionDataManagement=0（DR）、Overrun=0（保留）、LeftBitShift=0。
- OversamplingMode=1、Ratio=2、RightBitShift=0x20（右移1），TriggeredMode=0、OversamplingStopReset=1。
- 数据证据在 `0x701015bc..0x70101604`、`0x7010164e..0x7010169c`；四字常量块 `0x70101800,1810,1830`。

这里存在结构布局陷阱：老师GCC产物的 FunctionalState 为短枚举布局，不能拿当前Keil句柄结构偏移盲写二进制。上述字段已同时与 `0x701081a4` 内实际寄存器更新行为交叉核对。

规则转换完成回调分析函数为 `0x701010bc`：

1. 检查传入句柄 Instance == `0x50022000`（ADC1）；ADC2自身完成回调不执行控制器。
2. `0x701010ce` 调用 `0x701083f0`（读取DR），保存第一个值到 `0x3400050c`。
3. `0x701010dc` 再读同一ADC1 DR，保存到 `0x3400050a`。
4. 查询ADC2状态，有数据时于 `0x7010113e` 读ADC2 DR，保存到 `0x34000508`。
5. 读取模式，`0x7010111a` 调用控制计算 `0x70102f98`，首参数是ADC1第一次读取值。
6. 结果有效时在 `0x70101120..0x70101134` 将浮点占空比乘常量转换为整数，写TIM1偏移0x38，即CCR2。

结合工作序列及 STM32N6 ADC 的 preserved-mode FIFO，代码意图是第一参数取CH1电流，第二参数取CH0电池电压。成立条件是FIFO按该序列对齐且没有未处理的溢出/旧数据；不能仅按两次DR读取就宣布实际数据身份无条件正确。该证据支持老师选用ADC1 CH1作为实时控制输入，AFE不是此回调的实时输入。N6的FIFO依据及错误处理边界见 verification-notes.md。

## 3. ADC内部自校准与外部零点估计

main于 `0x70101d3e` 调用 `0x70104ab0`：

- `0x70104ace` 对ADC1、`0x70104ade` 对ADC2调用 `0x701090c4`，参数0x3ff对应单端ADC自校准。
- AFE零点为5次采样均值；只在0.75..约1.05V内接受，否则记录提示并保留旧默认值。
- `0x70104bba` 以参数1调用 `0x70104a2c`，临时把ADC1配置成CH1单次软件采样、6.5周期。
- `0x70104bcc..0x70104bea` 最多循环5次 Start/Poll/GetValue/Stop，成功样本转换为 `code * float32(1.8/4095)` 后求均值。
- `0x70104bee` 以参数11恢复ADC1 CH11；`0x70104c0e..0x70104c18` 恢复触发选择字段。
- 接受范围也是0.75..约1.05V；MCU零点保存 `0x34000058`，AFE零点 `0x3400005c`。
- 两路零点差值超过10mV会提示传感器未稳定或通道故障，不会证明二者物理上已连通。

当前PA1约1232–1272码按此标称LSB只有约0.542–0.559V，落在老师零点接受范围外。因此“照搬老师校零”也不能把这条物理输入自动修复；保留0.9V只维持默认软件参数，不能当作路径确认。

## 4. AWD 配置：八次连续越界过滤，依赖CPU中断

电流模式配置函数 `0x70105bb8` 在 `0x70105c1a..0x70105cc0` 构造AWD：

```c
// 逻辑重建；不是可直接烧录的源码。
K = 1.3266666730244954;
lsb = float32(1.8 / 4095);
high = truncate(clamp((zero_mcu_V + limit_A / K) / lsb, 0, 4095));
low  = truncate(clamp((zero_mcu_V - limit_A / K) / lsb, 0, 4095));
watchdog = AWD1;                 // 编码0x7dc00000
mode = SINGLE_REG;              // 编码0x00c00000
channel = ADC_CHANNEL_1;
ITMode = ENABLE;
FilteringConfig = 0xe0000000;   // ADC_AWD_FILTERING_8SAMPLES
HAL_ADC_AnalogWDGConfig(adc1, ...);
```

过滤字段证据 `0x70105ca8, 0x70105cbe`。电压通道的AWD配置 `0x70105d98..0x70105dba` 也使用相同八次过滤。

不能把“AWD硬件判窗”写成“CPU无关硬件关断”。该链需要ADC样本、八次过滤条件、NVIC/CPU及软件回调。具体电气延迟尚未实测；不将100kHz倒数或过滤次数直接冒充总关断时间。

## 5. 从中断向量到实际关断的完整调用链

向量表 `0x70100400 + 4*(16+46)` 内容为 `0x701025f1`，去Thumb位后：

```
ADC1_2 IRQ handler 0x701025f0
  -> HAL_ADC_IRQHandler(ADC1) 0x701083f8
  -> HAL_ADC_IRQHandler(ADC2) 0x701083f8

HAL ADC handler:
  EOC/EOS路径 0x70108472 -> conversion callback 0x701010bc
  AWD1路径 0x70108576   -> AWD callback        0x7010119c
```

AWD回调 `0x7010119c`：

- 先取活动模式 `0x340025cc`（getter `0x70106054`）。
- 若 `0x340025b1 != 0`（getter `0x70107808`，切换/过渡状态标志），直接返回。
- ADC1事件且模式非0：写故障代码5到 `0x340025ca`（setter `0x701060c8`），调用关断 `0x70106cf8`。
- ADC2事件：模式1/3写故障1；模式2写故障3；同样调用关断。
- 最后向ADC ISR写0x80清AWD1标志。

关断 `0x70106cf8` 的顺序：

1. `0x70106d00`：GPIOB pin0x20写低，即PB5充电继电器命令撤销。
2. `0x70106d0a`：GPIOG pin0x20写低，即PG5放电继电器命令撤销。
3. `0x70106d12`：TIM1 CH2 stop，调用 `0x70111318 -> 0x70111208`，清CC2E。
4. `0x70106d1a`：TIM1 CH2N stop，调用 `0x70111b60`，清CC2NE；无其他通道运行时清MOE/CEN。
5. `0x70106d20/6d26`：停止ADC1、ADC2，调用 `0x70108f9c`。
6. 设置两个软件标志并将活动模式 `0x340025cc` 清0。

HAL_PWM_Stop实现没有直接以最先清MOE作为统一原子动作；主/互补输出按HAL调用依次撤销。当前 `G02_EmergencyOff` 的先清MOE并锁存、再处理外围资源的结构更适合构建明确的紧急停机路径，仍需测量输出至驱动/MOS的效果。

老师HAL IRQ会先处理完成回调，再处理AWD1；若同次EOC/AWD都挂起，可先执行浮点控制并更新CCR2，再进入AWD关断。若追求快速保护，候选实现应在IRQ入口先检查AWD/OVR并清MOE，不复制这个处理顺序。

## 6. 对用户当前缺口的直接结论

1. **不存在已经查到的“换一个ADC电流通道”修复。** 老师的实时电流仍是PA1/CH1。可移植的是TIM1同步采样、ADC自校准、6.5周期配置及明确的序列数据读取；这些不能替代模拟路径确认。
2. **老师HEX没有提供已核实的独立硬件过流关断路径。** 恢复到的是AWD1 + 8样本过滤 + CPU回调 + HAL关断，并有过渡期屏蔽分支。当前无响应的ADC输入也无法仅靠开启AWD变成有效电流保护。
3. **可将原码窗口、先关MOE、故障锁存、数据失效、单点本地截止完成为禁能候选。** 物理输入验证前不能宣称其过流功能可用；PWM驱动死区和供能约束还需要其他证据。

源码对照位置：当前 `main.c:276`、`g03_adc_port.c:70`、`g02_port.c:47`，路径均在 `D:/ADMIN/Desktop/WEIJI/zonghe/BMS_EXv1.1/BMS_EX`。

