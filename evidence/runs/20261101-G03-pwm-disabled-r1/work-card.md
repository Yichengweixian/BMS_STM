# G03 单次 PWM 禁能接入与板测

本次只运行定时器与真实 ADC，PA9/PF7 保持 GPIO 禁能，TIM1 MOE/CCER 和 PB5/PG5 均不允许开启。新增独立 Debug/Release target，原继电器 target 和镜像保留。

## 已完成的软件检查

微秒计时核心 21 组、实际 port 寄存器模型 15 组、主机 19 项及受影响继电器/ADC 回归通过。模型验证不代替板测。Release 0 错 0 警告；Debug 0 错、原有 EXTRAM 警告 1 条。完整源码、镜像和哈希见 production-source-manifest.json。

## 固定的禁能验证

运行身份 g03-pwm-disabled-r1；单次令牌；本地 TIM2 1MHz、100us IRQ 截止。普通演练 100ms，协议停止试验 200ms；样本年龄阈值 2000us，IRQ 最大间隔阈值 500us。阈值属于禁能软件夹具，不是电气通电限值。比较 ADC CH1 的 11.5 和老师 HEX 的 6.5 周期，保存预备 64 点、快速开头、抽取记录及全部停止事件。

每个已列场景仅一次独立软件复位和一次启动；失败立即记录并停止本轮，不重试或自动放宽判据。覆盖正常截止、采样过期/无效/FIFO溢出、双侧 AWD、缓存耗尽、心跳、STOP、前台阻塞、协议错误与请求重复/冲突。下载必须读回验证，正常 BOOT 后先确认身份和所有输出为0。

## 证据边界

fast ADC 时间是 IRQ 观察时间，不冒充硬件转换起止时间。physical_valid 恒0。fixture 的 verified_facts 和标称 mA 限值只测试关闭输出后的逻辑，不是实物证据。未使用老师 HEX 刷写，不执行真实 PWM/继电器放电；老师资料新增信息见 preparation/hex-followup.md。

下载读回、正常BOOT身份核对、15项禁能板测及G01/G02/relay DRY恢复已完成；判定与原始异常分别保留。见[最终报告](report.md)、[结果清单](result.json)和[场景CSV](disabled-cases.csv)。阶段进度统一维护于 instructions/STATUS.md。
