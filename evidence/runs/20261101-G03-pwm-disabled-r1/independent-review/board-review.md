截至 `resource-recovery-01` 完成，本次单次 PWM **禁能版本的 15 项板测及受影响资源恢复均有合格记录**。此结论覆盖内部定时、ADC、软件关断、防重放和资源复用；不包含真实 PWM 功率输出、驱动波形、有效死区或物理电流标定。

烧录 Release HEX SHA256 为 `9126778404c6f9a9890ab729522f7fbd9fe7fe0a380436694494ebecde81f9fb`，`flash-01` 写入校验通过，运行身份为 `g03-pwm-disabled-r1`。独立只读复核了 147 个归档文件哈希、3,116 条串口回复的 CRC/身份/禁能字段，并将原始回复与派生记录逐项比较，均一致；当前 core/port 源码哈希与构建清单一致。复核数据见同目录 `board-review-data.json`，脚本为 `review_board_evidence.py`，均未访问硬件。

| 板测项目 | 实测结果 | 证据含义 |
|---|---|---|
| normal / sample-6p5 | 核心窗口 100,002 / 100,001 µs，各 9,999 次采样；最大样本间隔 10 µs | 两种采样周期下均完成本地截止；不证明原码已物理校准 |
| ADC stale / invalid | 故障位精确为 `0x8` / `0x4`；窗口 7,101 / 5,002 µs；stale 时末样本年龄 2,099 µs | 过期与无效记录触发锁存，不被当作有效零值 |
| FIFO OVR / AWD low / AWD high | 故障位 `0x10` / `0x20` / `0x20`；off 快照分别带真实 ADC OVR / AWD 标志 | 真实外设标志触发软件关断。AWD 两组运行采样数为 0，保留为故障停止而非零电流 |
| cache-full / heartbeat-expiry | `0x10000` / `0x40`，窗口 4,455 / 20,001 µs；缓存保留 512 条，包括各 1 条 off、fault、restore | 缓存耗尽与心跳期限均能停止，并保留终止证据 |
| explicit-stop | 故障 `0x1`，窗口 25,990 µs | 显式 STOP 早于 200,000 µs 的本地期限 |
| foreground-stall | 窗口 100,001 µs，前台 cleanup 比 stop 晚 177,986 µs | 截止不依赖主循环恢复或主机继续发送 |
| bad-crc / rx-pressure / conflicting-start | 故障均为 `0x2`，窗口 25,990 / 39,987 / 25,990 µs；冲突回复码为 8 | 协议异常锁存并撤销内部触发 |
| duplicate-start | 窗口 200,001 µs，start/off 事件各 1 条 | 重复帧未重启、未延长窗口 |

全部 15 项终态均为 `owned=0, restored=1, actual_bits=0, timer_running=0`；所有保存的输出快照均为 0。每项均保留 64 条 preflight 原码，单次令牌在结束及清故障之后仍为 `used=1`；两次显式“已消耗令牌再次启动”负测均返回 4，原 start/stop 时间和记录数未改变。正常完成后的 clear 返回 BAD_ARGUMENT，故障态 clear 返回 OK，二者都没有自动启动。

`board-suite-01/08-cache-full` 的 ST-Link reset Error32 是**准备失败记录**：没有发送 start，也没有本次采样。该 suite 的总结果保持 fail。随后 `reset-failure-query-01` 只读确认新启动的 `used=0` 默认禁能态，再由主流程明确建立独立 `board-suite-02` 继续余下 8 项；首项复用已确认 boot，不把失败当作成功或自动重试。最终组合结果为 suite01 前 7 项加 suite02 全部 8 项通过。

`resource-recovery-01` 补齐了本次受影响路径：

- G01 连续保存 15.047 s 原始串口数据，30 个完整组、270 条记录，9 路各 30 条全有效，无序号缺口或解析错误，最大间隔 500 ms。三路电芯转换括号最大 3 ms，AFE 电流最大 6 ms；原码和标称换算继续分离，`physical_valid=0`，标定未改。
- G02 1,000 ms 禁能采样有 99,997 次更新和 99,997 次转换完成，OVR、ADC errors、late IRQ 均为 0，结束释放 ADC。
- relay DRY 完成 102 组，50 组基线，动作观察窗口内 4 组有效记录；采集最大 9 ms、间隔最大 21 ms、恢复计数 48。`live=live_gate=live_used=0`，全部 GPIO 输出快照为 0，未真实吸合继电器。
- 最终 PWM 结果仍保留原请求，`used=1, owned=0, restored=1`；G02 空闲、无故障，输出快照为 0。

本轮所需板测已补齐，无需扩大硬件测试范围。TIM2 的 PSC/ARR 没有协议读回字段，因此板上 DRY 只能证明共享计时路径功能恢复；精确寄存器恢复、回绕、preflight 协议中止、cleanup 失败后的保留所有权及记录读取，由已通过的真实 port 寄存器模型覆盖，不能改写为板上直接测量。

报告中的核心 stop 时间与寄存器 off 事件必须区分：normal 的事件跨度为 100,002 µs，sample-6p5 和 foreground-stall 为 100,003 µs。100 ms 是本轮软件判定期限，实测包含数微秒事件偏差；这些禁能记录不能表述为“物理功率严格不超过 100 ms”。PWM 引脚实际波形、驱动极性、有效死区、电气关断时间以及 PA1 电流物理校准继续保留缺测，真实放电仍需单独准入。

主流程后续只需将本复核、时间曲线和汇总报告归档，并更新工作卡、STATUS、RUNLOG；不覆盖 reset 失败记录。证据主目录：`D:\ADMIN\Desktop\WEIJI\zonghe\evidence\runs\20261101-G03-pwm-disabled-r1`。
