# BMS_EX · Keil（MDK-ARM）Debug / Release 双 target 配置说明

> 工程：`MDK-ARM/Appli/BMS_EX_Appli.uvprojx`，两个 target：`BMS_EX_Debug` / `BMS_EX_Release`
> 基准工程：`E:\workspace\MDKLED`（同芯片同板型，Debug/Release 都能跑，用它对齐配置）
> 本文记录 2026-10-22 实际调通的两套配置，以及踩过的坑。

---

## 1. 两套 target 的分工

| 项目 | BMS_EX_Debug | BMS_EX_Release |
|---|---|---|
| 运行方式 | **LRUN**：调试器下载到内部 SRAM 执行 | **XIP**：从 XSPI2 外部 flash 原地执行 |
| 代码位置 | `0x34000400`（内部 SRAM） | `0x70100400`（XSPI2 映射窗口） |
| Scatter | `stm32n647xx_LRUN_RAMxspi1.sct` | `stm32n647xx_ROMxspi2_RAMxspi1.sct` |
| **IROM1**（Options→Target） | `0x34000400` / `0x7FC00` | **`0x70100400` / `0x1EFFC00`** |
| IRAM1（Options→Target） | `0x34080000` / `0x180000` | `0x34080000` / `0x180000` |
| Define | `USE_HAL_DRIVER,STM32N647xx,DEBUG,USE_FULL_ASSERT` | `USE_HAL_DRIVER,STM32N647xx,NDEBUG` |
| Optimization | `-O1` | `-O3` |
| Update Target before Debugging | **0（必须）** | 1 |
| 烧录方式 | Keil Load（增量下载，**不写 flash**） | CubeProgrammer 写 `.hex`（或 `.bin` @ `0x70100400`） |
| XSPI / HyperRAM / NOR / 隔离配置 | **Appli 自己做**（`#ifdef DEBUG`） | **全部交给 FSBL**，Appli 一律跳过 |

一句话：**Debug 是"调试器把代码塞进 RAM 里跑"，Release 是"FSBL 把外部 flash 映射好、Appli 原地跑"**。
两者对地址、初始化职责的要求完全不同，不能靠复制 target 了事。

---

## 2. 必须改对的四项工程配置

### 2.1 Options for Target → Target → 片上存储

```
Debug  : IROM1 0x34000400  0x7FC00      IRAM1 0x34080000 0x180000
Release: IROM1 0x70100400  0x1EFFC00    IRAM1 0x34080000 0x180000
```

- **Release 的 IROM1 是最容易漏的一项**：从 Debug 复制 target 后，若还是 `0x34000400`，
  编译 0 error、Keil 也可能不报错，但镜像根本没进 XSPI2 flash（下载算法按这个范围找地址），
  复位后必然什么都不跑。本次"Debug 能跑、Release 烧完全黑"第一个根因就是它。
- 改完在 Keil 里重新打开工程确认一遍（直接改 `.uvprojx` 时 Keil 必须以关闭状态写入）。

### 2.2 Scatter 文件

| target | 文件 | 代码域 | 数据域 |
|---|---|---|---|
| Debug | `stm32n647xx_LRUN_RAMxspi1.sct` | 内部 SRAM `0x34000400` | 内部 SRAM `0x34080000` |
| Release | `stm32n647xx_ROMxspi2_RAMxspi1.sct` | XSPI2 `0x70100400` | 内部 SRAM `0x34080000` |

Release 这份的**四条硬约束**（本工程已按此改好）：

1. `RW_IRAM1` 必须落在内部 SRAM，且**不要**保留 CubeMX 默认的
   `RW_EXTRAM 0x90000000 { .ANY (+RW +ZI) }`。
   原因：这份 scatter 是给 `__main` 在 `main()` **之前**搬 RW、清 ZI 用的，
   那时 HyperRAM 是否已被 FSBL 映射是**运行期才知道的事**，把 `.data/.bss` 放过去等于
   把启动成败押在 FSBL 上（本工程 ZI 有 5KB，不是 MDKLED 那种 24 字节）。真要放，请显式用 `.EXTRAM` 段。
2. **body 里是字面地址，不跟 `#define` 走**：
   `RW_IRAM1 0x34080000 0x00080000` 与文件头 `#define __RAM_BASE/__RAM_SIZE` 必须**同步改**，
   只改宏等于没改。
3. 注释里**不要出现全角标点**（`：（）`），armclang 预处理会报 `-Wunicode-homoglyph`。
4. 堆 `ARM_LIB_HEAP` 用 `AlignExpr(+0,8)`，会跟随**前一个**区域；所以 `RW_EXTRAM` 不要留在
   `ARM_LIB_HEAP` 之前，否则堆被推到 HyperRAM 去。

### 2.3 C/C++ 与链接选项

```
Misc controls : --import_cmse_lib_out=../../Secure_nsclib/secure_nsclib.o --entry Reset_Handler
useUlib       : 0   （不启用 MicroLIB）
Include Paths : ..\..\Appli\Core\Inc;..\..\Secure_nsclib;..\..\Drivers\...;..\..\BSP;..\..\BSP\HyperRAM;..\..\BSP\NORFlash
```

`useUlib=0` 意味着 **`printf` 不可用**（走半主机 → 调试器外直接 HardFault/卡死），
串口输出统一用 `uart_printf()`。详见 §7。

### 2.4 Debug 页 / `setup.ini`

`MDK-ARM/Appli/setup.ini`（Debug 专用）：

```ini
LOAD $L@L.axf incremental
PC = _RDWORD(0x34000404);   // Reset_Handler of Appli (LRUN: vector table at 0x34000400)
```

- Debug 靠它把 PC 直接设到 Appli 的 `Reset_Handler`，**不经过 bootROM/FSBL**；
- 所以 Debug 能跑 **不能** 证明发布链路（flash + FSBL）是通的；
- Release target 的 "Update Target before Debugging" 要勾上（=1），Debug 必须取消（=0），
  否则调试时会把 RAM 里的东西往 flash 写。

---

## 3. 代码侧三条铁律（`Appli/Core/Src/main.c`）

### 3.1 向量表基址：两个 target 都要设

```c
{
  extern uint32_t Image$$ER_IROM1$$Base;
  SCB->VTOR = (uint32_t)&Image$$ER_IROM1$$Base;   /* Debug=0x34000400，Release=0x70100400 */
}
```

### 3.2 `#ifdef DEBUG` 只管"不该在 Release 里做的事"

```c
#ifdef DEBUG
  MX_XSPI1_Init();  MX_XSPI2_Init();  SystemIsolation_Config();
  HyperRAM_Init(...);  NORFlash_Init(...);
  HyperRAM_EnableMemoryMappedMode(...);  NORFlash_EnableMemoryMappedMode(...);
#endif
```

- Debug（LRUN，无 FSBL）：XSPI 时钟没配，必须自己 Init，否则 HyperRAM/NOR 不可用；
- Release（XIP）：Appli 本身就在 XSPI2 上取指，**重复 Init 会打断取指**；这些全归 FSBL。
- 注意：这段只在 Debug 里跑，**任何 Release 也需要的外设配置都不能放在里面**（见 3.3）。

### 3.3 GPDMA1 通道属性必须**无条件**设置 ← 本次"屏黑 + 串口无输出"的根因

```c
  /* USER CODE BEGIN 2，必须早于第一次 DMA 使用 */
  HAL_DMA_ConfigChannelAttributes(&handle_GPDMA1_Channel0,
      DMA_CHANNEL_SEC | DMA_CHANNEL_PRIV | DMA_CHANNEL_SRC_SEC | DMA_CHANNEL_DEST_SEC); /* I2C4-TX → OLED */
  HAL_DMA_ConfigChannelAttributes(&handle_GPDMA1_Channel1,
      DMA_CHANNEL_SEC | DMA_CHANNEL_PRIV | DMA_CHANNEL_SRC_SEC | DMA_CHANNEL_DEST_SEC); /* USART1-TX → 串口 */
```

- `SystemIsolation_Config()` 只在 Debug 分支里调用，它内部本来就设这两行；
  但 **OLED 刷新（I2C4-DMA）和 `uart_printf`（USART1-DMA）都走 GPDMA1**，
  Release 下没人设 → DMA 静默失败 → **屏全黑、串口一个字都不出**，而 CPU 其实还在正常跑。
- 提到 `USER CODE 2` 里无条件执行，与 Debug 分支重复调用是**幂等**的，安全。

---

## 4. 操作流程

### 4.1 Debug（LRUN）

1. Keil 选 `BMS_EX_Debug` → Build（`-O1`，`DEBUG` 已定义）。
2. Options 确认：Scatter = `stm32n647xx_LRUN_RAMxspi1.sct`、IROM1 = `0x34000400/0x7FC00`、
   **Update Target before Debugging 不勾**。
3. 点 **Download / Start Debug**：调试器按 `setup.ini` 增量下载 axf 并把 PC 设到 `0x34000404`。
4. 断电重启后程序**不会**继续跑（在 RAM 里），这是正常的。

### 4.2 Release（XIP）

1. Keil 选 `BMS_EX_Release` → Rebuild（`-O3`，`NDEBUG`）。
2. Options 确认：Scatter = `stm32n647xx_ROMxspi2_RAMxspi1.sct`、
   **IROM1 = `0x70100400 / 0x1EFFC00`**。
3. 烧录（任选一种，注意地址）：
   - **CubeProgrammer + `.hex`**：地址从文件里读（`0x70100400` 起），直接烧，最省事；
   - **CubeProgrammer + `.bin`**：**必须手动把起始地址填 `0x70100400`**，默认的 `0x08000000` 等于什么都没烧；
   - Keil 直接 Download：需要 IROM1 正确 + 下载算法覆盖 `0x70100400`，否则报 `No Algorithm found`。
4. 复位/上电，此时由板上 FSBL 引导（`0x70000000` 起）跳到 `0x70100400`。
5. 若改了 `.uvprojx` / `.sct`，Keil 里要 **File → Reload**（或关掉重开）后再编译。

---

## 5. 验收：编译完看 map 这几行（`BMS_EX_Release/BMS_EX_Release.map`）

```
Load Region LR_IROM1 (Base: 0x70100400, ...)                 ← 代码在 XIP 窗口
Execution Region RW_IRAM1 (Exec base: 0x34080000, ...)       ← 变量在内部 SRAM，不能是 0x90000000
Execution Region ARM_LIB_STACK (Exec base: 0x340FF7F8, ...)  ← 栈也在内部 SRAM
（不应存在 RW_EXTRAM 区域）
Image$$ER_IROM1$$Base = 0x70100400                           ← 与 VTOR 一致
Program Size: Code=... RW-data=... ZI-data=...
```

判断标准：**只要 map 里出现 `RW_EXTRAM (Exec base: 0x90000000` 且尺寸非 0，就说明数据落进了 HyperRAM**，
需要按 §2.2 改 scatter。

---

## 6. 症状 → 原因速查

| 症状 | 大概率原因 | 处理 |
|---|---|---|
| Release 编译 0 error，烧完上电**全黑无串口**，LED 一下都不闪 | IROM1 仍是 `0x34000400`，镜像没进 flash；或 `.bin` 起始地址没填 `0x70100400` | 改 IROM1（§2.1）、用 `.hex` 或填对地址 |
| 程序在跑（LED 心跳正常），但**屏黑 + 串口无输出** | GPDMA1 ch0/ch1 的 SEC/PRIV 没设（只在 Debug 分支里设过） | §3.3 无条件补两行 |
| 屏亮但字错位 / 全白 | 与 Release 无关，查 `OLED_DISPLAY_OFFSET(0xD3)`、`0xC8` 方向 | 见 `MEMORY.md` 的 OLED 章节 |
| 卡在某处不动，串口无输出 | `spi_WR_byte()` 用 `HAL_MAX_DELAY`，ADBMS1818 没接会**永久阻塞** | 先注释采样段；或给 SPI 加超时 |
| 串口输出是乱码 | 波特率：`uart_init()` 的参数被 `UNUSED`，真实值在 `MX_USART1_UART_Init()`（115200） | 改那里 |
| Debug 正常、Release 某些数值异常 | 时钟不同（Debug=复位默认，Release=FSBL 配的 PLL），手写的 `Delay_us` 循环会失准 | 用 `HAL_Delay` 代替 busy loop |

---

## 7. 本工程特有的坑（与 target 无关但常一起踩）

1. **不要用 `printf`**：`useUlib=0`（未启 MicroLIB），printf 走半主机 → 无调试器时 HardFault。
   统一用 `uart_printf()`（`vsnprintf` + DMA 发送，缓冲是 32 字节对齐的 static，启动 DMA 前会 `SCB_CleanDCache_by_Addr`）。
2. **ADBMS1818 的 SPI 用 `HAL_MAX_DELAY`**：芯片没接/没供电时，`BMS_ReadSample()` 会卡死，
   看起来像"程序停住"。排查时先注释掉采样调用。
3. **Keil 编辑器缓存**：外部改了 `main.c`/`.sct`/`.uvprojx` 后，Keil 里必须先 **File → Reload**，
   否则编辑器里旧内容一保存就把改动整文件覆盖（本项目已踩过一次）。
4. **手工命令行验证编译**（不用打开 Keil）：

```bash
armclang --target=arm-arm-none-eabi -mcpu=cortex-m55 -mfpu=fpv5-d16 -mfloat-abi=hard -xc -O3 -Wall -c \
  -DUSE_HAL_DRIVER -DSTM32N647xx -DNDEBUG '-D__HAL_RCC_RIFSC_CLK_ENABLE()=' \
  -I Appli/Core/Inc -I Secure_nsclib -I Drivers/STM32N6xx_HAL_Driver/Inc \
  -I Drivers/CMSIS/Device/ST/STM32N6xx/Include -I Drivers/CMSIS/Include \
  -I BSP -I BSP/HyperRAM -I BSP/NORFlash \
  Appli/Core/Src/main.c -o main.o
```

   - 必须加 `-D__HAL_RCC_RIFSC_CLK_ENABLE()=` 绕过一个 undeclared 报错（Keil 构建没这问题，是手工命令缺 define）；
   - Release 下应只剩 3 条 `unused function`（`MX_XSPI1_Init` / `MX_XSPI2_Init` / `SystemIsolation_Config`，
     因为 `#ifdef DEBUG` 段被裁掉），属正常。
   - `UV4.exe -b` 在 bash 里会 segfault，命令行构建请直接用 armclang/armlink。

---

## 8. 附录：无串口时的 LED 闪码定位法（**代码中已移除**，需要时按此临时加回）

`main.c` 里曾经有一组 `BMS_Blink()` 闪码，Release 调通后已删除（2026-10-22）。
以后遇到"上电没反应、串口也没输出"，再临时加回（约 10 行）即可，判读表如下：

| 闪几下 | 含义 |
|---|---|
| 0 | 没启动（FSBL/烧录地址/签名） |
| 1 下后停 | 卡在某个 `MX_*_Init()`（多半进了 `Error_Handler()`） |
| 2 下后停 | 卡在 `OLED_Init()` |
| 3 下后停 | 卡在 `uart_init()` |
| 4 下后停 | 卡在 ADBMS 采样（SPI 永久阻塞，见 §7.2） |
| 持续 1 下/秒 | 已进主循环（心跳） |

加回方式：`USER CODE 0` 里放一个 `static void BMS_Blink(uint8_t times)`（LED1=PF10，
`HAL_GPIO_WritePin` + `HAL_Delay(200)` 循环），在 `MX_GPIO_Init()` 之后、所有 `MX_*_Init()` 之后、
`OLED_Refresh()` 之后、`uart_init()` 之后各插一处，`while(1)` 里放心跳。
**注意**：`BMS_Blink` 依赖 `HAL_Delay`，只能放在 `MX_GPIO_Init()` 之后（之前 GPIO 时钟还没开）。

