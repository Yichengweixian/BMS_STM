# 老师 HEX 的 PWM 与单次执行审查

日期：2026-11-01。只读静态分析；未访问串口、下载器或仪器，未修改当前源码，未执行 PWM。
目标 HEX：D:/ADMIN/Desktop/WEIJI/zonghe/firmware/prebuilt/BMS_Appli.hex
SHA-256：dd44fae11ed542ad6bcee45b35a13e93bd6632481b7d29662afda8ac7856be7f
反汇编来源：本轮 local-only/disassembly-v81m.txt；历史同源汇编用于初步定位，本轮重新从HEX校验解码。
二进制基址：0x70100400。按本地 ST HAL 的结构字段及实际寄存器访问交叉核对，不将字符串等同实现。
注意：本轮明确指定 armv8.1-m.main + force-thumb，将历史默认架构误显为stc的MVE存储正确解码为vstrw.32；涉及的常量池和四字结构布局另外直接读二进制复核。

## 1. 老师 TIM1 初始化确证

初始化在 main 内联区间 0x7010171a—0x701017d4；TIM1 handle=0x34000738，Instance=0x52000000。

|字段|老师 HEX|证据|
|---|---|---|
|PSC|0|literal 0x70101850 的四字为 00000000 00000020 000007cf 00000000，写 handle+4|
|CounterMode|CENTERALIGNED1 (0x20)|同上|
|ARR|1999 (0x7cf)|同上；与当前工程 2000 有差别|
|CKD|DIV1 (0)|同上|
|RCR|1|0x70101736 写 handle+20|
|ARPE|128|0x7010173a 写 handle+24|
|TRGO|UPDATE (0x20)|0x70101766—0x70101774|
|PWM 模式|PWM1 (0x60)|literal 0x70101860 四字为 00000060 000001f4 00000000 00000000|
|初始 CCR2|500|同上，只是初始化值，运行时会覆盖|
|主/互补极性|都 HIGH (0)|同上|
|OCIdleState|RESET (0)|sp+124=0|
|OCNIdleState|SET (512)|0x70101786/0x70101798；本地 HAL 定义 TIM_OCNIDLESTATE_SET=TIM_CR2_OIS1N|
|DeadTime|0|sp+136 起的 Break 结构首 16 字节全为0，DeadTime 位于+12|
|Break/Break2|均 DISABLE|Break 结构+16/+32=0|
|Break polarity|HIGH (0x2000)|literal 0x70101870|
|Break2 polarity|HIGH (0x02000000)|literal 0x70101880|
|AOE|ENABLE (0x4000)|0x701017ba/0x701017d2 写 sp+184，即 Break 结构+48|
|DeadTime preload|开启|0x701017a6 调0x70111d94，后者置 TIM1 DTR2+0x54 的0x20000|

HAL 例程身份交叉验证：
- 0x701117b8：HAL_TIM_Base_Init，对 handle+4 结构调用 TIM_Base_SetConfig 0x70111664。
- 0x7011181c：HAL_TIM_PWM_Init。
- 0x70111930：HAL_TIM_PWM_ConfigChannel；CH2分支0x701119b0调用0x70111880，写CCR2寄存器+0x38，并将idle位移到CH2。
- 0x70111cec：HAL_TIMEx_ConfigBreakDeadTime；明确从输入+12读DTG、从+48读AOE，并于0x70111d7e写BDTR+0x44。
- 0x70111d94：HAL_TIMEx_EnableDeadTimePreload。

频率不能从 HEX 本身宣布实测。若 TIM1 的实际时钟仍为当前实板确认的400MHz，则按中心对齐周期2×ARR计算，老师ARR1999对应约100050Hz；当前ARR2000对应100000Hz。这是时钟假设下的计算，不是老师镜像的实测波形。

## 2. 引脚及物理对应关系

PostInit 0x70102410—0x70102474：
- PF7：GPIO base=0x56021400，Pin=128，Mode=2 (AF_PP)，AF=1。
- PA9：GPIO base=0x56020000，Pin=512，Mode=2，AF=1。
结合本地器件复用表/现有 HAL_MspPostInit：PF7=TIM1_CH2N，PA9=TIM1_CH2。
这可以恢复 MCU 端输出配对，但 HEX 不包含 PCB 实际走线，因此不能据此宣布 PA9/PF7 分别接实物高侧或低侧，也不能恢复门极真实有效死区。

## 3. 启动与停止的已跟踪实现

0x70106fb0 是前台业务状态处理函数。已跟踪出：
1. 切换前调用停止0x70106d60，再设100ms等待截止（例如0x70106fd2、0x70106fe2—0x70106fec）。
2. state1在0x70107442等待上述期限，然后转state2。
3. state2完成电压/阈值等准备后使相应继电器GPIO有效：PB5路径0x7010742a—0x7010742e；PG5路径0x7010777a—0x7010777e。此后转state3并设置20ms等待（0x70107432—0x7010743e）。
4. state3于0x70107182等待结束，随后0x701071a6—0x701071c0取RAM地址0x340025a8的浮点 duty，乘1999.0（literal0x70107274）转整数写CCR2。0x701071d8将CNT写1999。
5. 0x701071f4/0x70107204启动两个ADC，然后0x7010720c调用主PWM Start（0x70111314跳转0x70111020），0x70107214调用互补PWM Start（0x70111a38）。这里是分开调用，两次HAL函数各会使能MOE/CEN。
6. 转state4并设置RAM 0x340025a4给出的等待值。不能把该等待误读成单次PWM截止：到期分支0x70107628—0x7010776e主要调整ADC并回到业务状态，没有在此分支调用PWM Stop。

因此：老师镜像包含前台的停机—等待—继电器—20ms—PWM启动时序，但不是可直接拿来替换当前单次实验程序的固定占空比一次性截止实现；CCR500仅初始化值。

普通停止0x70106d60：
- 0x70106d88、0x70106d92先写PB5=LOW、PG5=LOW。
- 0x70106d9c调用主PWM Stop（0x70111318跳转0x70111208）。
- 0x70106da4调用互补PWM Stop（0x70111b60）。
- 停两个ADC并恢复ADC2若干采样配置。

故障停止0x70106cf8：
- 0x70106d00/0x70106d0a先PB5/PG5低；
- 0x70106d12/0x70106d1a停止主/互补PWM；
- 0x70106d20/0x70106d26停两个ADC；
- 写若干锁存标志。
ADC watchdog回调0x7010119c中0x701011ca和0x701011e4均能进入0x70106cf8（具体电流阈值由电流审查分支另核对）。

停机GPIO调用顺序只能证明软件次序。触点释放、续流、MOS实际Vgs关断时间仍未知。AOE在初始化开启，且互补idle高，不能把老师参数整套复制并宣称比当前关断更可靠。

## 4. 当前源码可复用内容与最小实现变化

根：D:/ADMIN/Desktop/WEIJI/zonghe/BMS_EXv1.1/BMS_EX/

- Appli/Core/Src/main.c:639：当前TIM1 PSC0/CENTERALIGNED1/ARR2000/CKD1/RCR1；667初始CCR=G02_INITIAL_COMPARE=1000；668/669极性HIGH；671/672 idle全RESET；681 DTG0；682/686 Break禁用；690 AOE禁用。
- Appli/Core/Src/stm32n6xx_hal_msp.c:511：PA9=CH2、PF7=CH2N。
- BSP/g02_port.c:47：G02_EmergencyOff可复用为寄存器级紧急关闭：先清MOE|AOE、DIER、CEN、CCER，再把PA9/PF7改推挽LOW并拉低两继电器。
- BSP/g02_port.c:92：prepare有运行时钟与TIM配置核验、在ADC arm前进行UG、ADC独占。
- BSP/g02_port.c:152：enable在MOE=0时配置引脚，单次写CC2E|CC2NE，再CEN，最后MOE，可保留这种成对放行结构。
- BSP/g02_port.c:244：现有G02期限在主循环，不能用它充当主循环阻塞时仍可靠的带载截止。
- BSP/g03_relay_port.c:46、60：已有独立TIM2 1ms IRQ+DWT期限、IRQ间隔检查与本地过期判定；74用DWT补偿HAL tick延迟。可以作为新PWM执行适配器的截止实现基础，但它仍依赖CPU中断正常工作，不是独立硬件切断。
- BSP/g03_relay_port.c:118—121及141—144：每次启动只允许一个live动作，清结果不清live_used，可迁移到新适配器。
- BSP/g03_adc_port.c:70：已有ADC AWD/OVR中断立即执行EmergencyOff。现模块每SysTick软件触发，是禁能诊断，不能直接当100kHz快速电流采样。
- BSP/g02_link.c:48—60：已有CRC/递增id/重复请求幂等处理。当前串口无G02引脚输出命令（63—64），需新单次PWM命令与独立参数快照。
- BSP/g02_link.c:127、54：接收溢出/坏CRC当前丢弃并计数，不直接触发停机；新真实PWM策略若要求协议异常立即停，需增加对活动PWM session的fault路由（同时明确坏包和失联的策略）。
- Appli/Core/Src/stm32n6xx_it.c:79、95、111、127、143、159以及main.c:1124已将CPU异常接到G02_CPUFault；新适配器的锁存状态也应接入相同紧急出口。
- BSP/g03_relay_port.c:10、g03_adc_port.c:9均在G02_ALLOW_PIN_OUTPUT开启时#error。正确变更是隔离新真实PWM适配器和其target，不是删除这些诊断隔离条件。

最小新的代码范围：
1. 增加单次PWM core+port及冻结profile（固定CCR、DTG、限时、允许供能路径/限值身份；未知实物参数保持未就绪）。
2. 复用成对放行和EmergencyOff；有限期限放TIM2独立中断或另经验证的硬件截止，输出先关再后台清理；异常锁存，复位不自动运行，无循环重启。
3. 接入经确认的快速ADC/过流来源。保持ADC常开、合适的TIM同步触发、AWD中断紧急关闭、过期/OVR/IRQ迟到的故障出口。ADC AWD+ISR与独立比较器/Break不是同一保障层级。
4. 在本地模拟/寄存器替身中验证：恰好一次启动、边界截止、故障抢占、采样消失/OVR/越限、STOP、重复帧、未就绪拒绝、异常出口均为输出关闭。
5. 必要实物条件：PA9/PF7至高低侧对应、有效死区、快速电流真实路径或独立故障源、单次D/期限/供能限制。老师的DTG0和业务默认值不能补这些证据。

hardware-profile.json:31/32/35、41/42/45/47/50中的转换器电压/电流/源限流、允许D、有效死区、停止期限、点时长目前仍null。当前33Ω负载不约束半桥内部交越电流。

