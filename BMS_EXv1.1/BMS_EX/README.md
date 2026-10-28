# BMS_EX 工程模板 · 使用说明

> 适用对象：拿到本模板要做二次开发 / 实验的同学与同事
> 最后更新：2026-10-22（Debug + Release 双 target 均已上板验证）

---

## 0. 这个模板是什么（30 秒版）

| 项 | 内容 |
|---|---|
| MCU | **STM32N647X0HxQ**（Cortex-M55，VFBGA264） |
| 存储布局 | 代码跑在外部 **XSPI2 NOR（XIP）**，数据在**内部 SRAM**；**XSPI1 = HyperRAM** |
| 工程形态 | CubeMX 生成的 **Appli**（配 FSBL 使用，非裸机单镜像），Keil MDK 两个 target |
| 已实现 | OLED(SSD1306/I2C4)、串口(USART1 + DMA)、ADBMS1818 单体电压/电流/温度采样、按键扫描库、HyperRAM / NOR Flash BSP |
| 预留未做 | ADC 采集（只生成了配置壳）、继电器控制、按键业务联动、Flash 里的参数存储 |
| 验证状态 | Debug(LRUN) 与 Release(XIP) **都能跑**：OLED 显示 + 串口打印正常；采样代码就绪，需接 ADBMS1818 实测 |

---

## 1. 快速开始（三步）

**Step 1 打开工程**

```
MDK-ARM/Project.uvmpw  →  Appli/BMS_EX_Appli.uvprojx
```
首次打开请确认两个 target 都在：`BMS_EX_Debug` / `BMS_EX_Release`。
若上次是别人改过的工程，先 **Project → Rebuild all**（`.o` 可能是旧选项编的）。

**Step 2 跑 Debug（不用烧 flash，最快）**

1. 选 `BMS_EX_Debug`；
2. 检查 Options → Target：IROM1 = `0x34000400 / 0x7FC00`，**Update Target before Debugging 不勾**；
3. 点 **Download**（或 Start Debug）：调试器把 axf 增量下载到 SRAM，
   `Appli/setup.ini` 会自动把 PC 设到 `0x34000404`（Reset_Handler）；
4. 串口 115200 应看到 `BMS_EX UART ready, tick=... ms`。

> Debug 是在 RAM 里跑，**断电就没了**，这是正常的。

**Step 3 跑 Release（要进 flash）**

1. 选 `BMS_EX_Release`，Rebuild；
2. 检查 Options → Target：**IROM1 = `0x70100400 / 0x1EFFC00`**（这一项最容易漏，见 §6）；
3. 用 **STM32CubeProgrammer** 烧 `BMS_EX_Release\BMS_EX_Release.hex`
   （烧 `.bin` 时起始地址必须手填 `0x70100400`）；
4. 复位/上电，由板上 **FSBL** 引导跳转到 `0x70100400`。

---

## 2. 目录结构

```
BMS_EX/
├─ BMS_EX.ioc                 CubeMX 工程（引脚/外设的唯一来源）
├─ Appli/Core/
│  ├─ Inc/  main.h           引脚宏、HAL 配置
│  └─ Src/  main.c           初始化 + 用户代码（USER CODE 段）
│           stm32n6xx_it.c   中断入口（ADC/DMA/USART 等）
│           stm32n6xx_hal_msp.c  外设时钟与引脚（注释里有权威引脚表）
│           secure_nsc.c     CMSE 安全调用（配合 Secure_nsclib）
├─ BSP/                      手写驱动（与 CubeMX 无关）
│  ├─ oled_driver.c/.h        SSD1306 128x64，I2C4 + DMA 分块刷新
│  ├─ oled_font.c/.h          6x8 / 8x16 字库
│  ├─ uart.c/.h               USART1：DMA 发送 + IDLE 断帧接收
│  ├─ adbms1818.c/.h          ADBMS1818（18 节电池监视器）SPI5 驱动 + PEC
│  ├─ key.c/.h                按键扫描（短按/长按/双击/连发）
│  ├─ HyperRAM/               XSPI1 HyperRAM 驱动
│  └─ NORFlash/               XSPI2 NOR Flash 驱动（多型号）
├─ Drivers/                  STM32N6 HAL + CMSIS（本地化，不依赖外部路径）
├─ MDK-ARM/
│  ├─ Appli/BMS_EX_Appli.uvprojx      两个 target
│  ├─ Appli/*.sct                     Debug/Release 分散加载文件
│  ├─ Appli/setup.ini                 Debug 调试跳转脚本
│  └─ Keil_Debug_Release_配置说明.md   ← 改编译配置前必读
└─ Secure_nsclib/             CMSE veneer 库（secure_nsc.c 的产物）
```

---

## 3. 硬件资源（引脚分配）

以 `stm32n6xx_hal_msp.c` 的自动注释 + `main.h` 宏为准：

| 功能 | 信号 | 引脚 | 模式 | 备注 |
|---|---|---|---|---|
| 继电器 | `SWL_Relay` | **PG5** | 推挽输出 | 上电低 |
| 继电器 | `SWS_Relay` | **PB5** | 推挽输出 | 上电低；⚠ PB5 是 JTDO/TRACESWO，用 SWO 会冲突 |
| 串口 | `USART1_TX` | **PE5** | AF7 推挽 | 115200 8N1，TX 走 GPDMA1_Ch1 |
| 串口 | `USART1_RX` | **PE6** | AF7 推挽 | IDLE 断帧中断接收 |
| SPI5 | `SPI5_SCK` | **PE15** | AF5 推挽 | Mode 3、MSB、8bit、预分频 256 |
| SPI5 | `SPI5_MOSI` | **PH7** | AF5 推挽 | |
| SPI5 | `SPI5_MISO` | **PH8** | AF5 推挽 | |
| SPI5 | `ADBMS_CS` | **PH6** | 软件 GPIO | 默认高 |
| OLED | `I2C4_SCL` | **PC10** | AF4 开漏 | **必须外部上拉**，7bit 地址 0x3C |
| OLED | `I2C4_SDA` | **PC11** | AF4 开漏 | 刷新走 GPDMA1_Ch0，128B/块 |
| LED | `LED1` | **PF10** | 推挽输出 | 低电平点亮 |
| 按键 | KEY1/2/3 | **PF13 / PF14 / PF15** | 输入上拉 | 按下为低 |
| 功率 PWM | TIM1_CH2 / CH2N | **PA9 / PF7** | AF | PSC=0、ARR=1999、中心对齐；同时是 ADC 的 TRGO |
| 模拟 | VB_AD / I_AD / VS_AD / VL_AD | **PA0 / PA1 / PA2 / PA10** | 模拟 | 见 §7.6 |

**注意**：PA9 是 PWM 不是串口；PA10 是模拟输入 `VL_AD` 不是串口。串口只有 PE5/PE6。

---

## 4. 软件模块与 API

| 模块 | 关键 API | 说明 |
|---|---|---|
| OLED | `OLED_Init` / `OLED_Clear` / `OLED_ShowString(x,y,str,size)` / `OLED_ShowNum` / `OLED_Refresh` | 画进 `OLED_Buffer`，**必须再调 `OLED_Refresh()` 才上屏**；是叠加绘制，换内容前要先清 |
| UART | `uart_init(115200)` / `uart_printf` / `uart_send_string` / `uart_send_dma` / `uart_rx_data` / `uart_rx_restart` | `uart_printf` 是**同步**（等本帧发完）；接收用 IDLE 断帧，回调里必须 `uart_rx_restart()` |
| ADBMS1818 | `wakeup_sleep_cmd` / `ADBMS1818_EnableVREF2` / `ADBMS181x_read_reg` / `ADBMS181x_write_cmd` / `ADBMS_CalcPEC` / `ADBMS1818_SetCellDischarge` / `AutoBalance_Run` | 模板里 `main.c` 的 `BMS_ReadReg()` + `BMS_ReadSample()` 演示了"电压+电流+温度一次读完" |
| 按键 | `Key_Init(keys, n)` / `Key_RegisterCallback(cb)` / `Key_Scan()` | 需要在 10ms 周期任务里调 `Key_Scan()`；支持短按/长按/双击/连发 |
| HyperRAM | `HyperRAM_Init` / `HyperRAM_EnableMemoryMappedMode` | **只在 Debug 里调**（Release 由 FSBL 负责） |
| NOR Flash | `NORFlash_Init` / `NORFlash_EnableMemoryMappedMode` | 同上 |

---

## 5. 环境与工具版本

| 工具 | 版本（本工程实测可用） |
|---|---|
| Keil MDK (µVision) | **V5.42** |
| ARMCLANG | **V6.23** |
| Device Pack | `Keil.STM32N6xx_DFP` **1.2.0** |
| STM32CubeMX | **6.18.1**（`.ioc` 里记录） |
| STM32CubeProgrammer | 任意近期版本（Release 烧录用） |
| 调试器 | ST-LINK（SWD），或 ULINK |
| C 库 | **不启用 MicroLIB**（`useUlib=0`）→ 因此 **不能用 `printf`** |

---

## 6. 编译配置要求（两个 target）

| 项 | BMS_EX_Debug | BMS_EX_Release |
|---|---|---|
| 运行方式 | LRUN（调试器下载到 SRAM） | XIP（从 XSPI2 原地执行） |
| Scatter | `stm32n647xx_LRUN_RAMxspi1.sct` | `stm32n647xx_ROMxspi2_RAMxspi1.sct` |
| **IROM1** | `0x34000400 / 0x7FC00` | **`0x70100400 / 0x1EFFC00`** |
| IRAM1 | `0x34080000 / 0x180000` | `0x34080000 / 0x180000` |
| Define | `USE_HAL_DRIVER,STM32N647xx,DEBUG,USE_FULL_ASSERT` | `USE_HAL_DRIVER,STM32N647xx,NDEBUG` |
| Optimization | `-O1` | `-O3` |
| Update Target before Debugging | **不勾（0）** | 勾上（1） |
| 链接 Misc | `--import_cmse_lib_out=../../Secure_nsclib/secure_nsclib.o --entry Reset_Handler` | 同左 |
| 构建后 | `fromelf --bincombined` 生成 `.bin` | 同左 |
| 烧录 | Keil Load（不写 flash） | CubeProgrammer 写 `.hex`，或 `.bin`@`0x70100400` |

**Release 的三条硬要求**（详见 `MDK-ARM/Keil_Debug_Release_配置说明.md`）：

1. **IROM1 必须是 `0x70100400 / 0x1EFFC00`**。从 Debug 复制 target 后忘了改，会出现
   "编译 0 error、烧录无报错、上电全黑"；
2. **scatter 里 `.data/.bss` 必须落内部 SRAM**（`RW_IRAM1 0x34080000`），
   **删掉** CubeMX 默认的 `RW_EXTRAM 0x90000000 { .ANY (+RW +ZI) }`；
3. **scatter 的 region 行是字面地址，不跟 `#define` 走**；注释里别写全角标点（会报 `-Wunicode-homoglyph`）。

---

## 7. 代码约定（改代码前必读）

### 7.1 向量表自设
`main()` 开头用 `SCB->VTOR = &Image$$ER_IROM1$$Base;`（Debug=0x34000400，Release=0x70100400），
两个 target 都保留，别删。

### 7.2 `#ifdef DEBUG` 的边界
只有"Release 下不该做的事"放进去：`MX_XSPI1_Init` / `MX_XSPI2_Init` / `SystemIsolation_Config` /
`HyperRAM_*` / `NORFlash_*`。Release 下这些由 FSBL 完成，重复做会打断 XIP 取指。

### 7.3 GPDMA1 通道属性必须**无条件**设置
```c
HAL_DMA_ConfigChannelAttributes(&handle_GPDMA1_Channel0, SEC|PRIV|SRC_SEC|DEST_SEC); /* I2C4-TX → OLED */
HAL_DMA_ConfigChannelAttributes(&handle_GPDMA1_Channel1, SEC|PRIV|SRC_SEC|DEST_SEC); /* USART1-TX → 串口 */
```
放在 `USER CODE 2` 开头（第一次用 DMA 之前）。**这两句不能塞进 `#ifdef DEBUG`** ——
否则 Release 下屏幕全黑、串口一个字都不出（CPU 还在跑），这是本工程踩过的坑。

### 7.4 不要用 `printf`
未启 MicroLIB，`printf` 走半主机 → 无调试器时 HardFault/卡死。统一用 `uart_printf()`。

### 7.5 DMA 缓冲必须 32 字节对齐 + 清 Cache
N6 默认开 D-Cache。传给 DMA 的缓冲要 `__attribute__((aligned(32)))`，发送前 `SCB_CleanDCache_by_Addr()`。
（`uart.c` / `oled_driver.c` 里已按此实现，自己新加 DMA 时照做。）

### 7.6 ADC 目前是"空壳"
见 §12；要用 ADC 必须自己 `HAL_TIM_*_Start`（提供 TRGO）+ `HAL_ADC_Start*`，否则一帧都不会采。

### 7.7 ADBMS1818 四条
1. 每次读寄存器组都要校验 **PEC**；
2. **先发 `ADCV` 读电压，再发 `ADAX` 读 AUX**，顺序反了会把电压结果顶掉；
3. 转换等待用 `HAL_Delay(2)`，不要用 `BMS1818_Delay_us()`（那是按某档主频手调的循环，换主频就失准）；
4. `spi_WR_byte()` 的超时是 **`HAL_MAX_DELAY`**：ADBMS1818 没接/没供电时函数**永久阻塞**，
   现象像"程序卡死"，排查时先注释采样调用。

### 7.8 串口接收两件事
回调 `HAL_UARTEx_RxEventCallback()`（在 `main.c` 的 USER CODE 4）末尾必须调 `uart_rx_restart()`，
否则只能收一帧；回调在中断上下文，不能阻塞、不能打印。

### 7.9 Keil 编辑器缓存
外部（脚本/同事）改了 `main.c`、`.sct`、`.uvprojx` 后，Keil 里必须 **File → Reload**。
不 Reload 直接保存会把外部改动**整文件覆盖**（本工程已踩过一次）。

---

## 8. 启动链路

```
上电
 └─ bootROM（按 option byte/BOOT 引脚选启动介质）
     └─ FSBL（板上已烧，位于 0x70000000 起）：
          配时钟 / 配 XSPI2 memory-mapped / （若配置了）XSPI1 HyperRAM / RIF
          └─ 跳转 Appli @ 0x70100400（Release）
```

- **本工程不含 FSBL**，Release 能否启动取决于板上 FSBL；Debug 靠调试器 + `setup.ini` 绕过整条链路。
- 所以"**Debug 能跑**"不能证明发布链路通；"**Release 全黑**"也可能是 FSBL/烧录地址问题。

---

## 9. 上电/复位后的自检

| 观察点 | 正常表现 | 说明 |
|---|---|---|
| 串口 115200 | `BMS_EX UART ready, tick=... ms` | 串口回环：发什么回什么 |
| OLED | 第一行显示 **`BMS_EX`**（8x16） | 若全黑先查 I2C 上拉与 0x3C |
| 串口第二行 | `V1=.. V7=.. V13=.. I=.. A T1=.. T2=.. T3=..` | 需接 ADBMS1818；没接会卡在 SPI（见 §7.7） |
| LED1(PF10) | 模板不带心跳，常灭 | 需要心跳自己加，见 §12 |

**注意**：`BMS_ReadSample()` 在 `while(1)` 之前只跑一次；ADBMS 没接时可能卡在那里不往下走。

---

## 10. 常见问题速查

| 症状 | 原因 | 处理 |
|---|---|---|
| Release 编译过、上电无任何反应 | IROM1 还是 `0x34000400`；或 `.bin` 起始地址没填 | 见 §6 |
| 程序在跑但**屏黑 + 串口哑** | GPDMA1 通道 SEC/PRIV 没设 | 见 §7.3 |
| 串口有输出但乱码 | 波特率被改 / 时钟源变（CLKP） | 检查 `MX_USART1_UART_Init()` 与 `PeriphCommonClock_Config()` |
| 卡在某处不动 | ADBMS SPI `HAL_MAX_DELAY`（没接器件） | 注释采样，或给 SPI 加超时 |
| OLED 全黑 | 无外部上拉 / 地址不对 / 没 `OLED_Refresh()` | 先 probe 0x3C |
| OLED 字符错位 | `OLED_DISPLAY_OFFSET(0xD3)`、`0xC8` 方向 | 见 `MEMORY.md` 的 OLED 章节 |
| 数值偏大/偏小 12 倍 | Debug 与 Release 主频不同，手写 `Delay_us` 失准 | 改用 `HAL_Delay` |

---

## 11. 重新用 CubeMX 生成代码时（重要）

`.ioc` 是引脚/外设的唯一来源，但**生成会覆盖**一部分手工改动，重新 Generate 后逐项复查：

1. **scatter 文件**（`MDK-ARM/Appli/*.sct`）会被重新生成 → 必须重新删掉 `RW_EXTRAM { .ANY (+RW +ZI) }`、
   把 `RW_IRAM1` 改回 `0x34080000 / 0x00080000`（Release 与 Debug 各一份）；
2. **IROM1 不会被 CubeMX 改**，但**复制 target** 时最容易漏 → 每次新建 target 都核对 §6 表；
3. `main.c` 里所有**非 USER CODE 段**的手改会丢（目前手改都在 USER CODE 段内，安全）；
4. **ADC 过采样**：`.ioc` 是 `Ratio=2 + RightShift=1`，而生成出来的代码是 `Ratio=1 + 无右移`，
   两边不一致，Generate 后会变 → 先决定要哪个再改（见 §12）；
5. 生成后重新编译两个 target，确认 0 error（Release 允许 3 条 `MX_XSPI1_Init`/`MX_XSPI2_Init`/
   `SystemIsolation_Config` 的 unused-function 警告）。

---

## 12. 已知限制 / 待办（模板预留）

| 项 | 现状 | 要做的事 |
|---|---|---|
| **ADC** | 只有配置壳：从未 Start，ADC2 用 `DR` 模式 + `EOC_SEQ_CONV` 三路会互相覆盖，`I_AD`(PA1) 未进序列，没做自校准 | 改 `ADC_CONVERSIONDATA_DMA_CIRCULAR` + GPDMA，或每 rank 单次 EOC；补 `HAL_ADCEx_Calibration_Start` |
| **继电器** | 两个 GPIO 配好了，**没有任何控制逻辑** | 加驱动层（极性宏、上电默认态、充放电互锁、延时） |
| **按键** | `key.c` 已编译进工程，但没 `Key_Init`/`Key_Scan` | 建 10ms 周期任务调 `Key_Scan()`，注册回调 |
| **电流** | 遥测电流走 ADBMS1818 GPIO1；MCU 侧 `I_AD` 未接序列 | 二选一，别重复算 |
| **参数存储** | HyperRAM/NORFlash BSP 有，但没有"参数区"设计 | 需要掉电保存就自己规划扇区 |
| **心跳/诊断** | 模板不带 LED 闪码（已在 10-22 清掉） | 需要时按 `Keil_Debug_Release_配置说明.md` §8 临时加回 |

---

## 13. 相关文档

| 文档 | 内容 |
|---|---|
| `MDK-ARM/Keil_Debug_Release_配置说明.md` | 两个 target 的完整配置、烧录流程、map 验收、症状速查、闪码定位法 |
| `BMS_EX.ioc` | 引脚与外设的权威定义（改硬件先改这里） |
| `.workbuddy/memory/MEMORY.md` | 长期踩坑记录（OLED 偏移、I2C/SPI/DMA 细节、ADC 现状） |
