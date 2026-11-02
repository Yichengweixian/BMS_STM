---
unit_id: G02-host-20261031
title: G02 上位机内部诊断与实板验证
requirement_ids: [G02.1, G02.2, G02.3, G02.5-software-review]
mode: exploratory
status: complete
verdict: null
evidence_scope: [static, build, simulation, bench, release_boot]
run_ids: [20261031-G02-host]
---

# G02 上位机内部诊断工作卡

本卡完成当前无需探头和硬件标定的实现、构建、部署与板内验证。用户已说明无法配合PWM测量，由上位机执行可完成的测试；不要求换电池、换三路源或拆电池测充电空载电压。原G02软件状态机/端口保持，增加串口传输和自动检查。阶段状态只维护在STATUS，本卡complete不表示G02电气验收通过。

## 实现与版本

- `g02-host-r1`增加G02_LinkRx/Task及UART错误同步；ISR仅入队，主循环校验CRC16、参数和递增请求id。最新完全重复请求不执行第二次，旧id和冲突拒绝；溢出/接收错误后重新找LF。
- 命令只有状态、内部采样、CCR、STOP、故障注入、CLEAR；两个target的G02_ALLOW_PIN_OUTPUT均关闭。采样期间不打印，停止后返回统计；默认启动仍执行G01。没有充放电或继电器操作。
- `scripts/g02/host_diagnostics.py`先核验响应版本及禁能gate，保存原始串口字节和收发事件；失败不自动重新启动，识别固件后出错尝试STOP。独立新目录保留每次运行。
- Release HEX SHA256：`ea05cc76e484a1afe60e3b61ff652668d3261e5a38355d83d34ba944044f70d1`。地址0x70100400；未改FSBL/OTP。完整固件归档firmware/，源码source-snapshot.zip及source-manifest.json，脚本/修改文件以delivery-manifest.json固定。

## 验证结果

| 项目 | 结果 | 证据 |
|---|---|---|
| 原生状态机/端口/串口生产代码 | 严格GCC编译；故障注入、CRC/分片/溢出/重放、STOP/锁存/清除/超时通过；C响应由Python解析交叉检查 | checks-final/ |
| G01回归 | 生产C测试、16项Python检查和合成回放通过 | g01-regression/ |
| Release/Debug构建 | Release 0错0警告；Debug 0错1条已有L6314W EXTRAM警告 | raw/BMS_EX_*.log、build-results.json |
| 烧录/读回 | 第3次CLI退出0，下载校验成功 | raw/flash-03.log、flash-result-03.json |
| 正常启动 | 用户正常BOOT复位后，上位机收到匹配g02-host-r1响应；非冷启动重复试验 | host-session-02/ |
| 1秒内部采样 | 更新/ADC各99996，OVR/ADC错误0，返回STOP且释放ADC | host-session-02/result.json |
| CCR及STOP | 请求1500，后续更新观察1500，写入1次；STOP清理完成 | 同上 |
| 故障锁存 | 注入fault32；再次START返回FAULTED；CLEAR仅回STOP | 同上 |
| 10秒内部采样 | CPU/TIM/ADC为800/400/64MHz；10000ms内更新/ADC各999998，OVR/ADC错误0，late_irqs0；终态STOP且释放ADC | 同上 |
| G01恢复 | 10秒采集177条已解析有效原码、19完整九通道组；各通道无缺序或重复。末尾89字节截断、1组不完整，记录器errors=1，保留未清洗 | g01-resume/、g01-resume-summary.json |

10秒窗口最大UPDATE间隔8000 CPU cycles，TIM ISR记录最大253 cycles，ADC ISR最大799 cycles；STOP软件区间365 cycles。这些数字仅包围代码标注区间，不含UART等待、IRQ入口前延迟、驱动传播和真实关断，不换算为物理停止保证。1秒窗口ADC ISR最大4106 cycles同样原样保留。

## 失败保留及解释

首次本机link编译CRC表达式有signedness警告，修复后严格测试通过；原log未覆盖。flash-01校验在0x701009EC出现一处不一致。flash-02日志显示下载校验成功，但其组合命令末尾复位失败；flash-result-02中的download_verified=false由当时“exit0且成功文本”复合逻辑生成，不否定日志中的读回成功。host-session-01无响应，未执行采样。用户随后说明此前未切BOOT；不能仅凭该说明断言首个校验差异的唯一根因。flash-03单独写入/校验成功（CLI exit0）；外层脚本终端GBK输出UnicodeEncodeError不影响已保存日志或读回结果。之后用户恢复正常BOOT复位，host-session-02通过。

## 结论边界及后续

本次证明新镜像能正常复位启动、上位机与MCU内部状态机/ADC同步采样链可运行，并能恢复常规采集。999998是软件服务计数；相对名义1000000的差异不能直接称为漏触发，也不能事后定为允许误差。窗口首尾相位及pending/在途转换需独立观测后才能判断；UIF可合并，计数相等不证明物理触发完整。

PA9/PF7、驱动与栅源实际波形、互补和死区、实际停止期限仍未测量；formal verdict保持null，不放行G03。三路普通直流源不作为充电吸收端。用户无法完成的探头/标定帮助登记为条件缺口，不反复提出同样要求；软件准备可独立继续。
