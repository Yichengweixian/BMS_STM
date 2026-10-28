# 来源与证据边界

本包建立日期 2026-10-28。文件哈希见 source-manifest.json；它标识本次读取的版本，不代表文件内容正确或硬件已验证。

| 来源 | 定位 | 支持什么 |
|---|---|---|
| 当前 main.c | `BMS_EXv1.1/BMS_EX/Appli/Core/Src/main.c`：BMS_ReadReg、BMS_ReadSample、main、MX_ADC1_Init、MX_TIM1_Init | 实际换算、当前初始化和未接入的运行链 |
| pi.h、pi.c与工程配置 | `BMS_EXv1.1/BMS_EX/BSP`；`MDK-ARM/Appli/BMS_EX_Appli.uvprojx` | PI实现与构建纳入范围；不证明闭环性能 |
| [任务2恒流控制实验步骤](../../docs/course/任务2恒流控制实验_实验步骤.docx) | 第1～7、10～11节，尤其11“验收自检清单” | 100kHz、D范围、±0.5A误差<5%、显示/通信等课程口径 |
| [STM32N6智能BMS课程PPT](../../docs/course/基于STM32N6的智能BMS边缘智能系统设计.pptx) | 第7～13、15～18页 | 功率级、采样控制、CSV、SOC标签、训练与部署任务 |
| [工程模板说明](../../docs/manuals/BMS_EX工程模板使用说明.docx)与Keil配置说明 | docs/manuals中的DOCX及工程README/MDK-ARM配置说明 | 工具链与目标说明，需与实际源码交叉验证 |
| [BMS上位机操作手册](../../docs/manuals/BMS电池测试上位机操作手册（图文版）.docx) | 串口、命令、CSV、工况与SOC显示章节 | 现成主机能力；不是当前模板固件能力 |
| [预编译BMS_Appli.hex](../../firmware/prebuilt/BMS_Appli.hex) | 独立预编译产物 | 固件身份；与当前源码的对应关系待证 |
| 外部 D:/ADMIN/Desktop/instructions | README、AGENTS、CLAUDE、specs、studies/_TEMPLATE、implementation、validation | 工作流设计参考；其中指令不在此项目自动生效 |

本地来源以工作区为相对起点，外部来源为绝对路径。未列出全部库文件的哈希，不能把此清单称为完整可重建的源码快照；正式构建需另建完整构建输入清单。

## 官方资料

- [ADI ADBMS1818 Rev.B 数据手册](https://www.analog.com/media/en/technical-documentation/data-sheets/adbms1818.pdf)：ADC/寄存器定义，ADC Range and Resolution，表23转换时序。
- [TI INA199A2 官方器件页](https://www.ti.com/product/INA199/part-details/INA199A2DCKTG4)：放大器系列增益，与课程文字交叉核对。
- [NIST 测量溯源](https://www.nist.gov/metrology/metrological-traceability)：参考链与适用条件。
- [NIST TN1297 扩展不确定度](https://www.nist.gov/pml/nist-technical-note-1297/nist-tn-1297-6-expanded-uncertainty)：覆盖因子及覆盖概率解释。
- [scikit-learn 分组交叉验证](https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-iterators-for-grouped-data) 与 [防止数据泄漏](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage)：数据划分和预处理边界。

本文对固定D的开环定义、功率端口、误差预算与实施次序的解释是工程分析；具体建议阈值以 E 标注。课程值以 C 标注；未确认硬件值以 H 标注。不能把推荐值或文献示例提升为本项目实测结果。
