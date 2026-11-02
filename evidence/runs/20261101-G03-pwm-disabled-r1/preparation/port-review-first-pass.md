# 新禁能PWM port首轮只读审查

2026-11-01。范围为staging的g03_pwm_port.c及微秒版pwm_oneshot.c；不检查尚在接入中的main/link是否已引用，不访问硬件，不修改port。root在同步修改，下述结论针对阅读到的初稿/随后局部更新，修复后需复查对应路径。

## 必须处理的具体问题

1. **ADC IER的运行中写入不符合N6寄存器契约。** 初稿emergency_off先写ADC1->IER=0，再置ADSTP；scenario3在ADSTART仍为1时清EOCIE/EOSIE。RM0486 Rev4 §32.6.2 p1540—1541要求这些IER位只能在ADSTART=0时写，AWD位还要求JADSTART=0。不能以写入语句存在推断中断已被屏蔽。建议独占期间先寄存器关闭功率/触发、屏蔽NVIC ADC中断、发ADSTP而不等待；前台完成停止后再清IER并按保存值恢复NVIC。OVR注入可以在ADC IRQ中有界跳过DR消费，等待真实OVR；不要依靠非法IER写入制造断采。

2. **在资源取得前失败会留下无法清除的pending_cleanup。** preflight的时钟/输出检查失败返回时owned仍0；调用方Trip设pending_cleanup=1，Task因!owned直接返回。之后ClearFault会因pending_cleanup一直返回BUSY。未占资源时也需执行core Service（只调用空after_off即可），或在这一失败分支完成服务。此问题可用时钟不匹配的stub验证，无需板上改变时钟。

3. **共享TIM2不能只保留自由运行后直接交还。** 初稿把ARR改为0xffffffff并说继电器start会自行初始化，实际RelayCommand只设置CNT/SR/DIER/CR1，PSC/ARR只在RelayInit设置。后续继电器演练会丢失原1ms UPDATE截止。已看到root加入TIM2保存/恢复和停止时钟快照，方向正确；应确认失败清理也执行相同恢复，且不通过再次RelayInit清掉原继电器结果。收归TIM2前关闭/清理旧UIE及pending状态；恢复后新port报告使用自己的快照，不混用恢复后的CNT。

## 采样记录语义需说明

ADCIRQ的stamp=TIM2->CNT是IRQ服务时刻，当前传入core的PWMSample.at_us并非硬件采样起止时刻。单rank且第二次EOC未置位可以拒绝积压，但不能把服务时间严格当作采样时间。禁能报告应写明timestamp_basis=adc_irq_service，记录触发周期、CNT/方向及可验证的最大延迟界限；若要按实际获取时间计算新鲜度，使用硬件触发/捕获时间或保守的时间下界。此处不要求为禁能测试额外做物理标定。

## 已确认合理的部分

- 独立编译门要求G02引脚与继电器真实门均关闭；enable仅设置TIM1 CEN，没有MOE、CCER、AF或继电器置高路径。bits把内部CEN与输出位分开，符合禁能TRGO用途。
- TIM1先停机、MMS=ENABLE下UG预装载，之后切UPDATE并arm ADC，避免把准备UG当作运行采样；CH1单rank、OS2右移1，保持ADC使能等待连续硬件触发。
- HAL等待在前台preflight/Task，core prepare/enable保持寄存器操作；core在prepare前消耗一次令牌，故障/完成/clear不重新发放。
- TIM2 1MHz uint32微秒计数可自然回绕，core差值比较及小于半范围条件仍适用；周期100us、迟到阈值500us是本次禁能夹具，不冒充电气硬截止。
- AWD/OVR分支先调用关闭再处理core/数据。单rank在读DR后发现仍有EOC则拒绝采样，避免把队列中旧结果当成新序列；仍须板测确认持续触发下的FIFO/ISR行为。
- 已看到恢复失败锁存且不无限自动重试cleanup的修订；共享资源释放应只发生在完整恢复验证通过后。

## 最小后续回归

只需针对新增接入：资源取得前失败→Service→Clear；前台准备/清理HAL失败→输出禁能且所有权不误释放；TIM2原PSC/ARR/DIER/CR1和ADC配置恢复；真实AWD/OVR处理次序；本地截止在前台停顿时继续；FIFO旧数据拒绝及记录时间语义。主机core已有边界/一次性/回绕测试可沿用本次微秒版新构建结果，不再重复旧HEX逆向或旧六模式全套。

寄存器来源：[ST RM0486](https://www.st.com.cn/resource/en/reference_manual/dm00769900.pdf)，本地已核对Rev4抽取文本RM0486-adc.txt的§32.6.2和§32.4.26；本次以本地官方文档内容核对，没有采用社区推断。

## 接入复查（2026-11-01）

已继续只读复查最新port、main/link及G02/G03/relay/ADC互斥挂钩。前三项已落实修复：关断使用NVIC mask+ADSTP，真实OVR演练在5ms时屏蔽ADC NVIC 200us后恢复；未owned仍调用Service；保存/恢复TIM2寄存器并冻结本次计时快照。额外的request_used令牌在preflight前消耗，失败不会获得第二次请求机会。ADC优先路由、TIM2优先路由、前台cleanup和常规测量禁入均已接入。TIM2 NVIC实际保持与relay初始化一致的enable/priority0，不应声称已经通用保存恢复所有NVIC状态。

复查提出两处接入问题：

- preflight的64次采样期间owned=1但shot仍IDLE，core ProtocolError原本忽略这段时间的UART RX错误。已看到最新Stop/ProtocolFault对owned+IDLE直接Trip的修订，因此后续Start会因fault拒绝触发。提前结束preflight循环只影响失败返回速度，不再作为阻塞。
- cleanup失败保持owned时，ReportReady已允许状态回报，但op42与G3E分支仍要求!owned，导致保留的原始rows不能读取。建议用ReportReady和终态判断允许只读，所有权继续锁住资源，避免失败记录只有汇总而没有原始数据。该条已反馈root，待对应条件修订。

本轮没有运行测试或硬件操作。除上述失败记录读取条件外，未发现另一个确定的禁能构建/下载阻塞。此结论只覆盖静态接入审查，需结合独立集成测试和完整Keil镜像构建；ADC stamp应明确为IRQ服务观察时刻，不宣称逐点转换起点或物理电流。
