# 关键过程记录

## 2026-10-28 · 规范适配

- 类型：documentation / static review。
- 输入：当前 BMS 工程、课程资料、外部 `D:/ADMIN/Desktop/instructions` 工作流模板、官方芯片与测量参考资料。
- 动作：建立 BMS 分层解释、G00—G07 验收草案、迁移说明、工作卡和运行/标定模板，记录待确认参数。
- 范围：新建当前项目内 `BMS执行规范`；未修改固件或外部 instructions；未烧录、未运行功率实验、未产生训练数据。
- 结论：可供下一阶段准备和审阅；全部硬件验收 verdict 仍为 null。结构检查以 validation/structure-report.json 的实际结果为准。

## 2026-10-28 · 目录整理与规范采用

- 来源：用户要求“整理项目文件夹，然后把新的instruction改了放到对应目录下面”。
- 目录：原 `BMS执行规范/` 改为 `instructions/`；课程、手册、阅读指南分别归档到 `docs/`；现成HEX到 `firmware/prebuilt/`；上位机、Flash加载器与安装包到 `tools/`。
- 入口：项目根新增README导航及AGENTS执行入口；流程采用，E类建议阈值仍待具体正式实验冻结。
- 保留：Keil工程 `BMS_EXv1.1/` 原路径与内容；外部旧instructions；所有原始压缩包与固件。旧说明及来源快照保存在 references/history。Office临时锁文件由Office管理。
- 追溯：references/layout-migration.json 记录路径映射、13份移动文件的前后哈希及432份Keil文件基线；validation/layout-report.json给出最终一致性与链接检查结果。
- 实验状态：没有构建、烧录、台架或模型实验；G00仍in_progress/null，其余阶段不变。

## 2026-10-28 · GitHub 初始同步准备

- 用户指定目标：`https://github.com/Yichengweixian/BMS_STM`；开始时远端为空，默认分支main。
- 本地建立Git仓库、origin、忽略规则与Git LFS；压缩包通过LFS传输，源码和资料保持原有内容。
- 文档适配：项目内部HTML文件链接改用相对路径；保留外部参考与历史快照的原始语义。
- 范围：仅版本管理与同步，不编译、安装、烧录或启动硬件实验。实际远端完成状态以Git提交和远端分支核对为准。

## 2026-10-28 · 配套工具改为仅本地

- 用户要求从仓库移除配套工具、安装程序和全部RAR/ZIP等压缩包，保留本地文件。
- 通过Git取消跟踪`tools/`中的5个压缩包及`firmware/prebuilt/BMS_Appli.hex`，不删除本地文件；移除当前LFS匹配规则并补充大小写兼容的忽略规则。
- 源码、工程配置、开发规范和说明文档继续保留。更新根AGENTS与README，避免后续重新上传工具包。
- 范围为当前分支的后续提交，不重写已发布历史；初始提交和GitHub端旧LFS对象仍可能保留原记录。
- 无软件卸载、固件构建或硬件实验；实验状态不变。

## 2026-10-30 · 当前基础源码烧录

- 安装用户提供的 MX25UM25645G_ATK-CNN647B.FLM 至 Keil；解压配套 CubeProgrammer stldr。
- 用户切换开发启动模式后识别 STM32N647。ST-Link V2J37S7 未升级。
- BMS_EX_Release 构建 0 错误、0 警告；SWD 100 kHz Under Reset 写入 0x70100400，Download verified successfully。
- 首次 HotPlug 擦除失败与成功重试日志均保留于 evidence/runs/20261030-basic-flash；镜像 SHA256 与工作卡同目录。
- 证据范围 build、bench；独立启动正在等待实物确认，未进行测量/功率级验收。

- 后续启动确认：BOOTSR 实测 0x3，用户反向切换两个 BOOT 开关并复位后确认 OLED 显示 BMS_EX；Flash 复位启动已跑通。最终纠正开关后的全断电重启未另行观察。保存复用脚本 tools/flash-loaders/flash-current-release.ps1，已检查语法。


## 2026-10-30 · G00 软件基线核验

- 当前源码/配置快照、Git差异、工具哈希、材料清单和双target干净构建归档于 evidence/runs/20261030-G00-baseline。
- Release 0错误0警告，HEX与实际烧录镜像完全一致；Debug 0错误1条空EXTRAM警告，已分析并记录外部堆依赖。源码未修改。
- ADC2 ioc/源码差异、PI旧接口、默认输出/停止设计、实物资料适配均已登记。
- G00整体尚未宣告通过：等待冷启动重复记录、串口通路与实物登记。

- G00启动复测：用户确认完全断电重启3次均显示BMS_EX，已逐次登记为用户报告证据。Keil型号STM32N647X0HxQ与实测STM32N647对应；不据此推断板卡版本、供电和仪器。最新串口枚举仍只有蓝牙COM3–COM8，基础UART实测待接入。

## 2026-10-31 · 分阶段提示词

- 按用户要求新增 prompts/README.md 与 G00—G07 八份独立提示词；每阶段细分五个子任务，允许按范围实施或复核。
- 通用要求集中在 prompts/README.md，阶段文件引用现有验收、数据和硬件规范，不复制数值阈值或维护第二套阶段状态。
- 新增根 README 与规范 README 的导航。提示词要求核对已有工作卡和实际代码，复用有效证据，明确离线/台架及正式验收边界。
- 本次为提示词与入口文档变更，没有执行固件构建、烧录或硬件实验，不改变阶段验收状态。

## 2026-10-31 · G00 串口 USB 识别排查

- 用户报告独立 CH340 模块，换数据线直连电脑并断开所有板侧杜邦线后，仍为 VID_0000/PID_0002、设备描述符请求失败、Code 43，未生成串口。
- 已存在 CH341 驱动文件与驱动仓库记录。指定设备的软件重启被 Windows 拒绝访问，未执行成功。
- 当前 Release HEX 哈希仍与已烧录基线一致。串口测试尚未执行，等待可正常枚举的模块；原三次冷启动结果保留。证据：evidence/runs/20261031-G00-uart。

- CH340恢复：用户再次换线后识别为USB-SERIAL CH340(COM10)，VID_1A86/PID_7523，状态OK。115200/8N1成功打开，被动接收2秒0字节，未发送数据。USB/驱动通路恢复，等待接线确认后进行板端日志/回显测试；G00尚未整体通过。

- 照片补充：核心板丝印CNN647B、AFE丝印ADBMS1818可见。用户只展示底板/核心板，CH340可能为板载接口，先前按独立模块理解的接线隔离证据不能当作已验证物理事实。
- 例程确认USART1 PE5/PE6、115200/8N1；说明书关于ST-Link提供串口的描述与实物CH340枚举不一致。COM10短帧回显收到非匹配字节，未通过；保持原固件，抓取复位启动数据定位。

- G00基础UART通过：RST后COM10以115200/8N1捕获两次BMS_EX UART ready与测量文本；3组短帧逐字节回显一致。证据见evidence/runs/20261031-G00-uart。应用代码未改动，测量数据未标定。G00总体硬件契约待实物登记。


## 2026-10-31 G00硬件资料审查

- 对照课件、任务2步骤、模板说明、现成上位机说明和当前源码，补齐已确认身份、软件配置、资料标称以及冲突来源。
- profile_id=cnn647b-bms-baseline-20261031-r1；实测值和硬限没有从示例自动填充。未改固件或执行功率动作。
- 实物供电/电池/负载/仪器仍需用户只看标签确认；分流器、增益和传感器属于后续测量前核对。G00整体保持in_progress/null。
- 记录及参数变更前后快照：evidence/runs/20261031-G00-hardware-audit。

- 全板照片补充：实装3节14500标签Li-ion电芯（3.7V、800mAh标签值），金色铝壳外接电阻可见但参数不清。电源可能12V仅用户未确认估计，不填实际值；当前无万用表。照片原件和参数快照已归档。

- 用户确认外接电阻标签25W33ΩJ，已登记33Ω/25W/±5%标称规格；未执行功率测试。


## 2026-10-31 G01 软件采集、记录及异常处理

按用户指定范围完成G01.1—G01.3软件部分：ADC1软件触发、500ms周期原码流、AFE配置/PEC/转换完成与有界超时、无效值传播；独立记录器保留原字节及复位/丢帧事件。Release最终0错误0警告；Debug0错误、1个原有.EXTRAM警告。原生C故障注入、7项Python测试及36行/9通道端到端模拟回放通过。安装当前用户pyserial3.5供记录器使用。未烧录新镜像，未取得板端新版本数据；仪表标定与独立验证待补。证据范围static/build/simulation，正式G01 verdict=null。详见 [工作卡](../evidence/runs/20261031-G01-software/work-card.md) 和 [采集说明](specs/G01-software.md)。


## 2026-10-31 G01 Release实板验证及GPIO读回修复

用户授权下载并采9通道。首版r1烧录校验后发现AFE CONFIG误判，原始756条失败记录保留。按手册修正GPIO位读写语义比较，补充只读状态/真实配置错误回归；r2 Release0错误0警告，Debug仅原有1警告。r2烧录读回成功，正常BOOT复位显示BMS_EX，COM9实采71.603秒、144完整组/1296条，9通道原码全有效，无PEC/串口校验/序号丢失。仍为未标定数据，G01正式判定null。见 [实板工作卡](../evidence/runs/20261031-G01-board/work-card.md)。


## 2026-10-31 实物仪器型号补充

用户提供照片确认 Chauvin Arnoux C.A 5212 万用表与 UNI-T MSO3034HD 示波器可用；示波器面板350MHz/2.5GSa/s/12bit登记为标称。更新hardware-profile与当前STATUS，原照片及旧profile保存在evidence/runs/20261031-instrument-registration。序列号、校准/精度依据、参考量程和示波器探头仍未知；没有新增板卡测量或精度结论。


## 2026-10-31 G01 首组实物电压参考

用户报告A=3.896V、B/C=3.895V，各3次一致；原始转录/参考CSV已归档。COM9五分钟窗口取得593完整组/5337条，9通道原码全有效。核对C.A5212中文厂家手册14/15页及来源哈希。A/B/C与AFE通道、参考精确时间均未确认，所有可能对照差约2.35—4.91mV；未拟合或写入补偿，正式G01仍null。见 evidence/runs/20261031-G01-voltage-reference-01/work-card.md。


## 2026-10-31 G01 供电实测及无编号反馈

用户报告圆孔适配器实测18V、另一未知测点3V、充电源未接、电池座无编号。更新硬件profile，旧12V猜测仅存历史；15V/1A保留课程输入示例，未定为电池电流限值。复查课件第7页嵌入电路图补充A1/A2及NTC/PT1000资料冲突。下一步待各电芯负极对GND电位，未启用功率级。详见 evidence/runs/20261031-G01-supply-observation-01/review.md。


## 2026-10-31 G01 电池串位置测量

用户报告A/B/C负极对板上GND为7.77/3.895/0.000V，结合单体电压支持低到高C→B→A，已登记profile；AFE实际接线映射仍为空。请求查找明确电流采样测试点，未令用户探测芯片细脚或改变功率接线。未拟合、未写系数。证据：evidence/runs/20261031-G01-cell-position-01/review.md。


## 2026-10-31 G01 电流采样区域定位

用户未找到信号标识，提供整板照片。对照课件U5/C24及源码PA1定位U5候选区域；实际型号、方向及可测焊点未知，未给出猜测性引脚测量指令。核对TI INA199条件引脚表，保存原照片与放大观察图。见 evidence/runs/20261031-G01-current-location-01/review.md。


## 2026-10-31 G01 改用整链参考标定

用户提出将总误差合并到易操作位置进行标定。执行方式改为外部同物理量参考与串口原码直接拟合；暂停U5细脚探测要求，两路电流独立系数。确认接线与范围后采零点/多点及独立验证；不使用DC-DC另一侧表显电流代替电池侧参考，不将稳定性当准确性。未改固件、未写系数、未启动功率级。见specs/measurement.md当前执行方式及evidence/runs/20261031-G01-system-calibration-method。


## 2026-10-31 G01 外部串表接法核对

从课件标注照片确认黄色充电输入、绿色负载接口，均不能直接代替电池侧参考。所需断点为电池侧同分流器支路；照片中电池座直接上板，无已确认可拔总正极线。保存条件接线图与表笔极性（充电正：红板侧、黑电池正侧），询问有无专用夹具/已引出测试线，未进行改接或功率动作。见evidence/runs/20261031-G01-series-meter-wiring-01/wiring-review.md。


## 2026-10-31 G01 现有线材与新增细节照片核对

确认P_VS充电/P_LOAD放电丝印、R1位置与015标记；用户仅有普通表笔/鳄鱼夹等，无已识别串联夹具。未找到可安全指定的电池支路断点，转由实验室确认并提供绝缘串联转接。保留实物照片和前版硬件登记；无改接或功率动作。见evidence/runs/20261031-G01-series-fixture-review-02/review.md。


## 2026-10-31 G01 电压优先与上位机工具完成

按用户要求暂缓电流/温度实物标定。新增电压统计、候选拟合及独立验证工具和未填实测值模板；16项Python测试、生产C故障注入及36条合成回放通过。串口重采90秒、177完整组/1603条，九通道原码有效，首尾2项错误保留。登记无负载A/B/C=3.895/3.894/3.894V及用户读数基本稳定的补充，作为近3.9V工作点核对；未假定时钟同步或AFE物理映射，未写校准系数。固件/BOOT/功率状态未改。证据：evidence/runs/20261031-G01-VT-followup-01/work-card.md。

## 2026-10-31 G01 电压模拟源登记与多点方案准备

据用户照片登记UNI-T UDP3305S；核对官方独立输出/通道隔离说明，记录CH1远端接线与三对夹具未知。准备空电池座替代激励、单路变化辨识、3点拟合及2个独立验证点的待执行工作卡。所有参考读数、映射、系数与验收结果留空；未改变固件、BOOT或操作电源，电流/温度仍暂缓。见 evidence/runs/20261031-G01-voltage-source-preparation-01/work-card.md。


## 2026-10-31 G01 三路模拟源设置与取点表

用户确认CH1/A、CH2/B、CH3/C及真实电池移除、原约18V板供电保留、充电与负载端空。归档两张照片；识别CH3仍预设5V/3A且三路Off。准备各路3.9V/50mA初始设置、3.2/3.6/3.9V拟合、重新采集3.8/3.4V验证及端点回测；实际映射/参考/系数均留空，AFE供电条件待核实。未操作电源或固件。见 evidence/runs/20261031-G01-voltage-source-settings-02/work-card.md。

随后最新照片三路改为3.5V/0.5A、仍Off；OVP3.5V未启用/OCP1A启用。登记为设置，不作为实测；已说明完整单点需独立表读数与板端raw配对。


## 2026-10-31 G01 load-connected observation

User reports load is now connected but no current observed. Updated current setup; previous load-empty confirmation is historical. Rechecked r2 source: measurement-only loop, relays LOW, no PWM start or charge/discharge commands. COM9 read attempt failed with Windows error 31; zero records captured. No firmware or power-output changes. Evidence: evidence/runs/20261031-G01-source-current-check-01/.


## 2026-10-31 G01 COM9重采及标定暂缓

COM9恢复后只接收记录60秒，1071条/119完整组，哈希/协议/PEC与连续性复核通过。前79组约3.5V，后段下降至近零，不将整段均值用于标定。用户要求电压、电流以后统一标定，本轮停止追加取点，无参考配对或系数发布；温度继续暂缓。固件、功率控制未变。见 evidence/runs/20261031-G01-source-capture-01/work-card.md。


## 2026-10-31 G02 默认禁能诊断、停止和时序观测

按阶段提示推进G02.1—G02.3：核对N6 TIMG时钟与100kHz推导，50%比较值改为1000，显式公共时钟配置；新增两阶段启动、直接硬停、故障锁存、ADC独占/恢复、TIM/ADC服务计数、overrun/缺完成退出和128项内存trace。Release/Debug均默认禁止引脚输出、无自动启动；异常处理接入撤销输出。运行中拒绝重复START保持原期限，下降方向重启先退出中心对齐再复位DIR。

10组生产状态机测试、两种引脚门控分支的生产端口寄存器/HAL模拟通过；G01原生故障注入、16项Python检查、36条/9通道回放通过。最终Release 0错误0警告（exit 0），Debug 0错误、原有L6314W EXTRAM警告1个（exit 1）。首轮沙箱链接器启动失败、检查报告相对路径错误均保留，修正后重跑存证。

实际工程在WEIJI/zonghe，聊天旧目录不存在；使用临时副本实现/构建，按文件哈希检查后回写。源码/候选镜像身份、修改前文件、工作卡、配置推导和待执行波形矩阵保存在evidence/runs/20261031-G02-software。未烧录、未操作串口/下载器或开启功率路径，硬件未知限值未填猜测值；G02正式verdict=null，G03未放行。


## 2026-10-31 G02 Release烧录

用户授权后写入g02-sw-r1，CubeProgrammer退出0、读回校验成功。COM9尚未观察到新固件身份，0条记录/0完整组；启动确认待用户反馈。未启用PWM/继电器，未采集示波器波形。证据：evidence/runs/20261031-G02-board。


## 2026-10-31 G02启动确认与电源用途澄清

用户确认正常BOOT复位显示BMS_EX；COM9重采60秒确认fw=g02-sw-r1，1071条/119完整组，解析错误0；全部已记录raw有效=True。三路直流源是此前电压模拟激励，不用于承受充电回灌；当前继续G02无功率测试准备。PWM波形和停止期限仍未测。见evidence/runs/20261031-G02-board。
