# 单次固定 PWM 离线候选控制核

这是本次新写的 HAL 无关 C 实现，供审查和后续接入。它不是老师原始源码，没有 MCU 硬件适配器，没有加入 Keil 工程，不能直接烧录运行功率。测试中的占空比、死区编码、期限和电流数值全是合成夹具，不是建议用于当前电路的参数。

## 已实现与验证

- 零初始化对象在 Init 时执行关闭；未提交完整 profile 不放行。
- profile 要求实际电流反馈路径、电流方向/比例与可观测保护窗口、驱动映射、有效死区、供能边界、停止路径、冻结工况均有对应证据身份；缺任一项拒绝启动。这里的 CURRENT_BOUND 是保护范围证明，不要求 G01 正式精度标定全部完成。标志仅表达已有事实，不是修改几个布尔值就能取得实物依据。
- 检查 ARR/CCR 整数范围与已验证 CCR 区间、非零 8 位 DTG、正电流限值、启动电流窗、所有时间间隔小于 2^31 ms。ISR 最大间隔不大于单点期限、ADC 新鲜度窗和心跳窗。
- 接受启动后、调用硬件 prepare 前，消耗本次启动的唯一令牌。prepare/enable 失败也消耗；完成、故障、ClearFault、Service、重复 Init 都不能恢复。没有运行时改 CCR 的 API，调用方修改原 profile 不影响内部冻结副本。
- 由独立定时器 IRQ 调用 PeriodicISR；期限、ADC 数据年龄、心跳及 ISR 间隔在此检查。停止不需要主循环 Service。时间采用 uint32 无符号差，覆盖跨 0 回绕；所有输入时间必须同源，并且真实两次检查不能跨越半个计时范围。
- ADCISR 收到两向超流、无效样本、OVR 或过期/未来时间戳，立即关闭并锁存。重复旧样本保留实际采样时间，不能伪装成新数据；新样本若在原采样链已经超期后才到达，也不能抢在周期 ISR 之前刷新时间并复活该链。
- STOP、协议异常、外部保护错误都进入同一关闭和故障锁存出口。
- emergency_off 先于状态后处理及前台清理；prepare、enable_pair、after_off 回调失败均保持关闭。定时器正常截止的 DONE 结果也不允许重启。

本次实际使用 GCC 13.1.0 编译并运行 16 组测试，编译选项包含 `-Wall -Wextra -Werror -Wconversion -Wshadow -pedantic -O2`。复现：

```powershell
powershell.exe -NoProfile -File .\build.ps1
```

`build.ps1` 仅构建和运行主机模拟程序，输出 `test-results.txt`、`validation.json` 和 `.exe`。不会调用串口、ST-Link 或烧录程序。若编译器位置不同可传 `-Compiler`。

## 接入契约

所有 core API、ADC ISR、周期 ISR、串口命令与回调必须由同一个短临界区串行化；禁止回调重入。对象声明为静态零初始化，Init 每次 MCU 启动仅调用一次。不要 memcpy/memset 已初始化对象或直接写内部状态来“清一次性锁”。一次性令牌只覆盖本次 MCU 启动；硬件复位后依然必须等待新的显式请求，绝不能自动启动。

`now_ms` 必须来自同一单调、自然回绕的硬件计时基准，并在主循环或低优先级 IRQ 延迟时继续推进。不能在临界区中依赖一个需要被屏蔽 SysTick ISR 才能递增的时钟来证明回调有界。也不能直接使用 DWT->CYCCNT / cycles_per_ms：CYCCNT 自身回绕后，商不是自然 uint32 毫秒回绕。应使用满足契约的独立计时器，或经过正确回绕扩展与并发验证的计时实现。周期 IRQ 本身必须由独立于主循环的定时器驱动，并有实际优先级/最长关中断/最坏延迟依据。

此版 API 的时间分辨率是毫秒。停止判定可能比请求时刻迟一个周期 IRQ 间隔，再叠加实际 ISR/关断回调延迟及时间量化影响，`run_ms` 不是严格的最大电气通电时长。若工况要求微秒界限，应将接口和相应测试改为 1MHz 时间基，或使用经验证的硬件截止。未来 port 不能把以 us 冻结的硬限向上取整为 ms 来放宽约束，必须给量化和最坏响应预留预算。

快速过流不能等待毫秒周期 Tick：ADC AWD 或独立故障 IRQ 应直接执行紧急关闭，并调用 `PWM_OneShot_Trip(..., PWM_F_OVERCURRENT)`（若状态已损坏则只执行关闭）。ADCISR 的每次样本检查是补充；AWD 阈值配置、真实响应速度和 IRQ 延迟仍要由硬件适配器验证。

回调契约：

|回调|必须完成的动作|
|---|---|
|emergency_off|寄存器级幂等关闭，两路 PWM 同时禁止，清除可能自动重新断言输出的控制；按照实际续流/继电器路径处理关断；初始化前、ISR 和 CPU 故障中均可调用|
|prepare|输出保持关闭；独占 ADC/TIM，写入并回读固定 CCR/DTG/极性；验证时钟；配置快速采样及过流出口；在 enable 前启用周期截止 IRQ；任一失配返回0|
|enable_pair|在所有保护已就绪后成对放行，失败或部分使能返回0；不能更改冻结 CCR|
|after_off|可选，仅在已经关闭的前台 Service 中做有界清理/向日志队列复制结果；不能使能、重试或重置令牌|

回调不得等待 HAL 轮询、SPI、串口或打印，不得在里面执行长计算。异常回调返回时 core 立即调用 emergency_off，但无法制止一个永不返回的回调。因此这仍是 CPU 软件保护；需要独立硬件过流/截止的工况，必须另接比较器/驱动关断/定时器 Break 等已经确认的路径。

推荐适配现有工程的位置（目前只列接入点，没有修改它们）：

- `BSP/g02_port.c:G02_EmergencyOff`：已有清 MOE|AOE、CCER、CEN 和引脚低电平的关闭基础。实际继电器和续流次序需按板证据审查。
- `BSP/g02_port.c:prepare/enable`：复用运行时钟核验、ADC 所有权、先 UG 后 arm、成对 CC2E/CC2NE 最后 MOE 的流程；不要直接使用其主循环期限。
- `BSP/g03_relay_port.c:G03_RelayTickIRQ`：当前 TIM2 1ms IRQ 和 DWT 计时是周期截止的接入基础；新会话必须与继电器测试互斥。
- `BSP/g03_adc_port.c:G03_ADC_IRQHandler`：已有 AWD/OVR 紧急关闭模式，但该文件是禁能诊断并且当前1ms软件触发；新的带载适配器需按实际快速采样目标单独实现。
- `BSP/g02_link.c`：保留 CRC、请求编号和防重复；增加单次 PWM 命令，并将运行期间所选协议异常、STOP、失联路由到 core。收到请求不得自动重试。
- CPU fault handlers 和 `Error_Handler`：先直接执行 emergency_off，再在可行时登记故障，不依赖日志或 HAL 成功返回。

准备调用形态如下，所有 profile 字段来自已冻结的实物证据，不提供一份含猜测数值的板级初始化器：

```c
static PWMOneShot shot; /* zero initialized */
/* startup, with a real adapter: PWM_OneShot_Init(&shot, &ops, ctx); */
/* explicit validated request: PWM_OneShot_Start(&shot, &profile, &fresh_sample); */
/* dedicated timer IRQ:       PWM_OneShot_PeriodicISR(&shot); */
/* real ADC completion/OVR:   PWM_OneShot_ADCISR(&shot, &sample); */
/* foreground after OFF:      PWM_OneShot_Service(&shot); */
```

## 本板仍待提供的输入

真实 profile 目前未生成，启动条件继续不成立：PA1 电流传递关系或经确认的替代快速反馈；方向/比例/可观测窗口与过流阈值；PA9/PF7 到高低侧的实际映射及 AF/驱动关断极性；有效死区及对应非零 DTG；允许的 CCR 区间、单次期限、供能限制；电气停止时延和续流/继电器顺序。老师 HEX 的 DTG=0、默认 CCR、业务延时均不能自动成为这些值。

当前 core 采取“经确认电流反馈+ADC判据”的接口。若最终走独立硬件过流保护路线，必须在适配器契约、故障输入、自检和相应事实条件中明确建模；不能把未知电流标为有效来绕过前置检查。

所有主机测试只证明 C 状态机和替身回调行为，不证明 STM32 中断延迟、ADC 物理响应、PWM Vgs 波形、电气关断时间或硬件保护有效性。周期检查的真实关闭时刻还受 IRQ 最坏延迟与关闭回调时延影响，应纳入硬期限预算；绝不能把 `run_ms` 当成已经证明的电气截止时间。
