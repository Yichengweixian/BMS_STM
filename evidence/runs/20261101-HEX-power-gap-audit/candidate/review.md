# 独立代码复核：单次 PWM 控制核

日期：2026-11-01。复核者：current_feedback_audit（未编写控制核源码）。
范围：pwm_oneshot.c、pwm_oneshot.h、test_pwm_oneshot.c；static + host simulation。
结论：本轮发现的采样超时问题已修复并通过回归；在已声明的调用契约下，未发现其他阻断离线候选交付的问题。此结论不表示硬件适配完成或允许带电PWM。

## 首次发现与修复

首次审查发现 ADCISR 只检查新样本的时间，随后覆盖 last_adc_ms，可能让已经超期的采样链被晚到的新数据复活：

- t=20 ms启动，adc_max_age_ms=4，isr_max_gap_ms=2。
- 周期ISR在21、22、23 ms执行，没有新ADC。
- t=25 ms先执行ADCISR（新样本时间25），再执行周期ISR。
- 旧实现把last_adc_ms刷新为25，掩盖5 ms断采；周期ISR间隔2 ms未超过其阈值。

作者现已在 pwm_oneshot.c:127 检查旧last_adc_ms年龄，达到阈值时立即进入finish，先调用emergency_off并锁存ADC_STALE，不覆盖过期时间。新增 test_fresh_adc_cannot_revive_expired_chain（test_pwm_oneshot.c:194）按上述调用顺序复现，断言输出已关、故障锁存、last_adc_ms仍为20、没有再次enable。

复核者重新读取修复及测试，并运行当前test_pwm_oneshot.exe：退出码0，16组全部通过。复核者未重新编译该可执行文件；构建由作者执行，源文件哈希另附，防止将后续源码改动与本次审查混同。

## 其余复核项

- 前置缺项、非法CCR/DTG/时间/电流参数不会调用prepare或enable。
- 接受启动后，在任何硬件准备回调前消费used令牌；prepare或enable失败均关断，失败、ClearFault、Service及重新Init不能恢复已消费令牌。
- 冻结配置采用结构副本，运行期间没有修改CCR或profile的API；外部原profile修改不影响已接受快照。
- 时间差采用uint32减法，参数限制在半范围内，测试覆盖正常32位回绕；前提是调用契约规定的单调时钟和周期服务继续存在。
- 电流负限比较未对INT32_MIN做取负：允许的discharge_max_ma为正数，因此取负可表示；initial为空由短路表达式安全拒绝。
- 故障路径先emergency_off，再记录状态并推迟cleanup；部分enable失败也立即再次off。
- heartbeat和ADC超时均不允许晚到数据恢复已过期的链路。
- 调用者必须序列化所有API/回调，使用短临界区；回调不可重入。此实现本身不提供锁，也不适合直接由多个未协调ISR同时调用。
- 未实现真实STM32适配器、ADC标定/有效路径、驱动映射/死区、供能限制或硬件独立保护。文件已明确标记offline candidate，测试参数是合成夹具。

## 本次复核文件身份


- pwm_oneshot.c: 1a00264752c9de46c01670e13607c71d8ccdaa38e3c319b7eed94c7840c0e3b9
- pwm_oneshot.h: d81edab2032a7a3449a5dc0c50c6e30bcc1d83f00f0545643d8bcfbbbdc87cb8
- test_pwm_oneshot.c: 85c5d4cb506104c886d33d6e12e471e94d1d3fa8862babc11383216fcc7de498
- test_pwm_oneshot.exe: f196e71f5c847cb561ebf8f30e04721c7cb9b373d23f32d6aee857387d1283b5
