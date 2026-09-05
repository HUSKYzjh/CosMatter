# BiFeO₃ 实验指标与首批候选值

> 状态：2026-09-06 文献线索清单，`literature_mentioned`。本页中的数值来自原始论文页面、论文摘要或公开稿的首轮核对，尚未逐条完成 CosMatter Source Map 与人工数据复核，因此不是已接受材料事实，也不是 BiFeO₃ 的无条件“标准值”。

## 1. 为什么不能只存“指标—数值”

BiFeO₃（BFO）的实验结果强烈依赖样品形态、取向、外延应变、厚度、衬底、电极、缺陷、制备气氛、温度、频率和测量协议。同名指标只有在这些限定条件可比时才能放在同一组中。数据库的基本单元应是“某篇文献在某个样品和测量条件下报告的一次观测”，而不是一个覆盖所有 BFO 的平均值。

实验人员通常同时关心三类信息：

1. **样品是否可信**：相纯度、化学计量、杂相、晶粒/表面粗糙度、外延关系、厚度和应变是否被实际测量；
2. **功能响应有多大**：结构、铁电、介电、压电、磁性、光学、输运与疲劳等指标；
3. **数值能否比较和复现**：仪器与拟合定义、场强/频率/温度、回线是否饱和、误差、原始数据、对照样品和重复次数。

## 2. 建议优先收集的实验指标

| 优先级 | 指标族 | 主要指标 | 常用单位 | 最低限度的条件字段 |
|---|---|---|---|---|
| P0 | 结构与相 | 空间群、相分数、`a/b/c`、`c/a`、晶胞体积、应变、畴型/畴宽 | Å、%、nm | 样品形态、取向、衬底、厚度、温度、XRD/RSM/TEM/Raman 方法 |
| P0 | 铁电 | `P_s`、`P_r`、`2P_r`、`E_c`、`2E_c`、回线饱和性、保持与疲劳 | μC/cm²、kV/cm、cycle | 电极、测量方向、频率、最大电场、温度、漏电补偿方法 |
| P0 | 电输运 | 漏电流密度、体/畴壁电导、导电畴壁占比、开关电流、激活能、电阻开关比 | A/cm²、S/cm、%、eV、ratio | 偏压、几何、电极、气氛、温度、畴壁类型、扫描速率、统计畴壁数 |
| P0 | 相变 | 铁电、磁、有序—无序、绝缘—金属转变温度与滞后 | K、°C | 加热/冷却、速率、气氛、样品形态、判据和测试方法 |
| P1 | 介电与压电 | `εr`、`tanδ`、`d33`/有效 `d33`、场致应变 | —、%、pm/V | 频率、偏压、夹持状态、PFM/干涉法/宏观法、厚度与取向 |
| P1 | 磁性 | `T_N`、`M_s`、`M_r`、`H_c`、交换偏置、磁矩、螺旋周期 | K、emu/cm³、emu/g、Oe、nm | 场方向与范围、温度、基底/电极扣除、杂相检查、测量方法 |
| P1 | 光学与光伏 | 直接/间接带隙、吸收系数、折射率、`V_oc`、`J_sc`、响应度 | eV、cm⁻¹、V、A/cm² | Tauc/Kubelka–Munk 定义、波长/光强、器件几何、电极、畴结构 |
| P2 | 缺陷与化学 | Bi/Fe/O 化学计量、Fe²⁺/Fe³⁺/Fe⁴⁺、空位、缺陷浓度 | at.%、ratio、cm⁻³ | XPS/EELS/EDS 等方法、探测限、空间位置、退火气氛和充电校正 |
| P2 | 工艺与可复现性 | 生长温度、氧压、退火、沉积速率、靶材/前驱体、重复批次 | °C、Pa/mbar、nm/min | 设备、基底终止、冷却过程、批次数、参数容差 |

## 3. 首批候选观测值

下表的“值”仅描述对应来源中的具体报告。`≈`、范围、`2P_r` 与 `P_r` 等原始语义必须保留；不得为了得到整齐表格而擅自除以二、换成“典型值”或跨条件求平均。

| 指标 | 来源中报告的候选值 | 关键条件/定义 | 目前的比较结论 | 来源 |
|---|---:|---|---|---|
| 室温自发极化 | 50–60 μC/cm² | 外延约束 BFO 薄膜；结构分析为单斜而非块体菱方 | 只能作为该薄膜体系的报告值；不能直接解释为应变使极化提高，因为早期块体值受样品与回线饱和限制 | Wang 等，Science 2003，DOI [10.1126/science.1080615](https://doi.org/10.1126/science.1080615) |
| 铁电 α→β 转变 | 820–830 °C | 变温粉末中子衍射；`R3c`→`Pbnm`；两相共存且为一级转变 | 适合作为块体相变 P0 基准，并应保留升/降温与分解边界 | Arnold 等，PRL 2009，DOI [10.1103/PhysRevLett.102.027602](https://doi.org/10.1103/PhysRevLett.102.027602) |
| 高温 β/γ 相区 | β：820–925 °C；γ：925±5–933±5 °C | 薄膜、单晶和陶瓷的热分析、Raman、XRD、直流输运与光学联合实验 | 与 Arnold 等关于 925 °C 以上立方 γ 相的结果不一致，应作为显式反例组而非合并值 | Palai 等，PRB 2008，DOI [10.1103/PhysRevB.77.014110](https://doi.org/10.1103/PhysRevB.77.014110) |
| 强压缩下的四方度 | `c/a≈1.26` | 全应变薄膜，衬底失配覆盖约 −7% 到 +1%；高压缩区为 T-like 单斜相 | 需与 `c/a≈1.23` 的其他 T-like 报告按衬底、厚度与结构模型分组 | Sando 等，Nature Communications 2016，[原文](https://www.nature.com/articles/ncomms10718) |
| 应变相边界 | 约 −4.5% 压缩应变附近出现 R-like/T-like 共存 | 外延 BFO/LaAlO₃ 等体系；电场可驱动相互转换 | 是候选相边界，不是与厚度、温度无关的固定阈值 | Zeches 等，Science 2009，DOI [10.1126/science.1177046](https://doi.org/10.1126/science.1177046) |
| 导电畴壁占比 | 原始态 69%；淬火态 22%；时效态 59% | 多晶 BFO；PFM/c-AFM；每种状态约统计 200 个畴壁；占比按超过畴内背景的电流信号判定 | 这是按测试阈值定义的“导电畴壁比例”，不能写成 S/cm 电导率；热历史是必要限定字段 | Bencan 等，Nature Communications 2020，DOI [10.1038/s41467-020-15595-0](https://doi.org/10.1038/s41467-020-15595-0) |
| 直接压电系数 `d33` | 43±6 pC/N | 400 nm 商用 BFO/Pt 薄膜；对预写入相反极化区域做 DPFM 电荷积分；结果为两个扫描方向的平均 | 这是直接压电电荷系数，不能与 PFM 得到的有效 `pm/V` 响应静默合并 | Gómez 等，Nature Communications 2017，DOI [10.1038/s41467-017-01361-2](https://doi.org/10.1038/s41467-017-01361-2) |
| 单晶胞隧穿电致电阻 | 最高约 370% | 1 u.c. 四方 BFO/SrRuO₃/SrTiO₃(001)；室温垂直铁电隧道结 | `up to` 是器件与读出定义绑定的最大值；写入电压、读出偏压和高低阻定义仍需图级复核 | Wang 等，Nature Communications 2018，DOI [10.1038/s41467-018-05662-y](https://doi.org/10.1038/s41467-018-05662-y) |
| 畴壁内外 EELS 能量起始差 | 畴壁内 179.3 eV；相邻畴内 178.3 eV | 多晶 BFO 的 109° 头尾相接畴壁；STEM-EELS；O-K 与 Fe-L₃ 起始能量差 | 这是用于判断 Fe 氧化态的成对谱学观测，不是 Fe⁴⁺ 浓度或输运激活能 | Bencan 等，Nature Communications 2020，DOI [10.1038/s41467-020-15595-0](https://doi.org/10.1038/s41467-020-15595-0) |
| 畴壁 Bi 柱强度下降 | 约 20% | 同一原始态 109° 畴壁；定量 HAADF-STEM；畴壁内与相邻畴归一化比较 | 强度下降支持缺失 Bi 柱，但不能直接改写成 `20 at.%` Bi 空位浓度 | Bencan 等，Nature Communications 2020，DOI [10.1038/s41467-020-15595-0](https://doi.org/10.1038/s41467-020-15595-0) |
| 缺陷状态相关畴壁厚度 | 原始态约 6 个晶胞；淬火态约 3 个晶胞 | 两条不同的 109° 畴壁；按 Fe 位移偏离相邻畴的范围定义宽度 | 这是条件对比而非对同一畴壁的原位追踪，也不能在未确认晶格参数时擅自换算为 nm | Bencan 等，Nature Communications 2020，DOI [10.1038/s41467-020-15595-0](https://doi.org/10.1038/s41467-020-15595-0) |
| 厚度相关 `d33` | 约 46 pm/V（150 nm）降至约 8 pm/V（6 nm） | BFO/LSMO/(001)-SrTiO₃；PFM 定量；1–150 nm 系列，约 6 nm 以下未见清楚铁电畴 | 可用于检验厚度效应，但 PFM 有效系数不能与所有宏观 `d33` 无条件合并 | Chen 等，Physica B 2012，DOI [10.1016/j.physb.2012.03.010](https://doi.org/10.1016/j.physb.2012.03.010) |
| 薄膜直接带隙 | 2.7 eV | 两种 Bi/Fe 前驱体比例的溶液法 BFO 薄膜；UV–vis/Tauc | 在该样品与拟合定义下两组相同，不代表所有 BFO 形貌 | Role of Excess Bi，ACS Applied Energy Materials 2023，DOI [10.1021/acsaem.3c01926](https://doi.org/10.1021/acsaem.3c01926) |
| 纳米颗粒带隙 | 直接 2.17 eV；间接 1.84 eV | 生物模板 BFO 纳米颗粒；Kubelka–Munk 拟合；平均晶粒约 14.59 nm | 是 2.7 eV 薄膜值的条件反例；直接/间接定义必须分列 | J. Phys. Chem. C 2016，DOI [10.1021/acs.jpcc.6b08548](https://doi.org/10.1021/acs.jpcc.6b08548) |
| 光伏开路电压 | 最高约 50 V | BFO 薄膜，温度与电极—畴壁几何受控；异常光伏/体光伏讨论 | 器件几何和畴壁电导是必填条件，不能只存 `V_oc=50 V` | Yang 等，Nature Communications 2013，[原文](https://www.nature.com/articles/ncomms3835) |
| 畴壁电导调制 | 约 3 个数量级 | 拓扑限域 BFO 岛中固定位置畴壁，极化状态往返切换 | 记录为开关比及器件结构，不转换成绝对电导率 | Sharma 等，Nature Nanotechnology 2018，[原文](https://www.nature.com/articles/s41565-018-0204-1) |
| 薄膜螺旋周期 | 67.8±4.8 nm 与 69.7±5.3 nm | 不同外延薄膜，XRD 畴结构约束下的中子衍射线形提取 | 与常被引用的块体约 62 nm 分开，保留拟合不确定度 | Haykal 等，npj Quantum Materials 2019，[原文](https://www.nature.com/articles/s41535-019-0155-2) |
| 同一样品的铁电/介电/疲劳组合 | `2P_r≈210.7 μC/cm²`；`2E_c≈435 kV/cm`；`εr≈116.8`；`tanδ≈2.7% @1 kHz`；至 `10¹⁰` 次循环 | (111) 取向 BFO/LSMO/Pt/TiO₂/SiO₂/Si，RF 磁控溅射；疲劳场幅 300 kV/cm | 可作为“同一样品多指标联结”范例；文中 `M_s=89.5 emu/cm³` 主要来自 LSMO，不能误记成 BFO 本征磁化 | Ke 等，JES 2012，DOI [10.1149/2.018202jes](https://doi.org/10.1149/2.018202jes) |

## 4. 数据库存储约定

现有 `material_facts` 仍保存论文中经人工复核的材料事实；新增的指标采集不应绕过该门禁。每条实验观测至少映射为以下逻辑字段：

```json
{
  "indicator_id": "stable-local-id",
  "document_id": "frozen-document-id",
  "segment_id": "reviewed-source-map-segment",
  "category": "property",
  "name": "remanent_polarization_2pr",
  "reported_value": 210.7,
  "reported_unit": "uC/cm2",
  "value_semantics": "approximate",
  "uncertainty": null,
  "measurement_method": "ferroelectric_hysteresis_loop",
  "qualifiers": {
    "sample_form": "thin_film_heterostructure",
    "composition": "BiFeO3/La0.67Sr0.33MnO3",
    "orientation": "111_textured",
    "substrate": "Pt/TiO2/SiO2/Si(100)",
    "thickness": "not_checked",
    "strain": "not_checked",
    "temperature": "room_temperature",
    "frequency": "not_checked",
    "field_protocol": "not_checked",
    "electrode": "LSMO/Pt stack",
    "preparation": "off_axis_rf_sputtering",
    "measurement_geometry": "out_of_plane_not_checked"
  },
  "locator": "page/figure/table after human review",
  "source_quote_sha256": "filled by the reviewed Source Map workflow",
  "trust_status": "literature_mentioned_not_human_data_checked"
}
```

实现时应把 `reported_value`、误差和原始单位原样保留；规范化值作为另一个字段写入。`P_r` 与 `2P_r`、`E_c` 与 `2E_c`、`P_s` 与 `P_r`、直接与间接带隙、绝对 `d33` 与 PFM 有效响应必须使用不同的规范字段名，不允许静默换算。

### 4.1 已落地的机器可读工件

- `configs/bfo_p0_material_indicator_catalog.json`：冻结结构/相、铁电、输运和相变四个 P0 指标族，以及固定顺序的 12 个限定字段；`P_s`、`P_r`、`2P_r`、`E_c` 和 `2E_c` 使用不同 `indicator_id`。
- `configs/bfo_experimental_indicator_catalog_v2.json`：在完全保留 v1 P0 指标的基础上扩展为 9 个指标族和 P0/P1/P2 三层优先级，加入介电/压电、磁性、光学/光伏、缺陷化学与工艺复现指标。直接 `d33`、PFM 有效 `d33`、畴壁导电占比、绝对畴壁电导、EELS 能量差与缺陷浓度均为不同的规范字段。
- `configs/bfo_p0_source_candidate_matrix.json`：为极化、应变相边界、高温相变和畴壁输运各登记一条主证据路线、一条独立来源路线和一条条件反例路线，共 12 篇原始实验论文候选；同时保存作者组独立性、样品/方法边界和公开全文替代路线状态。
- `examples/frozen/bfo_p0_literature_observation_candidates.json`：把首批 P0 数值拆成逐观测记录。其中已经按原始态、淬火态和时效态分别登记 Bencan 等报告的导电畴壁占比 `69%`、`22%` 和 `59%`，并绑定各自热处理、c-AFM 偏压、扫描频率和统计口径；它们全部保持 `literature_mentioned + unreviewed + source_map_status=none`，只用于后续选文和人工核对。
- `examples/frozen/bfo_expanded_literature_observation_candidates_v2.json`：登记第一批 7 条扩展候选，包括直接 `d33=43±6 pC/N`、单晶胞隧穿电致电阻最高约 `370%`、畴壁内外 EELS `179.3/178.3 eV`、Bi 柱强度约降 `20%` 以及原始/淬火畴壁约 `6/3` 个晶胞。每条都包含 12 项条件、方法和不可越过的解释边界，仍未建立人工 Source Map。
- `src/cosmatter/material_indicator_registry.py`：无依赖校验器，拒绝缺字段、越级成熟度、伪造 Source Map 绑定、非法单位和不完整的范围/误差语义。
- `src/cosmatter/material_indicator_triage.py` 与 `tools/build_private_bfo_indicator_shortlist.py`：可对仓库外且哈希核验通过的整篇 MinerU Markdown 做确定性排序，不再受通用 48 段抽样限制；排序综合指标术语、数值/单位、测量条件、方法和限制语句，并对参考文献、引用型比较与非目标性质降权。每篇最多 2 段、全批最多 12 段；结果保留原文及双重哈希，只是私有导航候选，不是 Source Map 或证据。
- `src/cosmatter/material_indicator_draft.py` 与 `tools/draft_private_bfo_indicator_values.py`：可在明确外发授权下把上述受控片段逐批交给 `deepseek-v4-flash`，只接受与文献、片段、指标、允许单位及固定 12 项条件严格绑定的 JSON；输出不含引文，仍是未审核草案。单条非法事实按固定原因码拒绝；同文献同指标且数值语义完全相同的重复候选会合并，同时保留辅助片段哈希。
- `docs/templates/material_observation_registry.sql`：SQLite/PostgreSQL 兼容的关系数据库模板，分别保存指标定义、允许单位、必需条件、观测、12 项条件和 Source Map 审核状态；不保存 PDF、长引文、URL、凭据或本地路径。

这套格式不会替代现有 `material_facts`。候选观测只有在人工核对来源、数据和条件后，才可映射成正式材料事实；数据库中的候选信任状态也通过检查约束禁止升级为 `data_supported`。

2026-09-06 还对 Sciverse 做了一次不落正文的真实交叉检查：`semantic_search` 返回的相关命中没有 `is_content_accessible` 布尔值，但带有效 `doc_id`；随后用其中一个 `doc_id` 调用 `content` 成功返回 HTTP 200、4,000 字符和下一偏移量。由此验证当前适配器的判断是正确的：显式布尔值存在时服从它，不存在时可把有效 `doc_id` 视为可尝试的正文路由；是否真正可读仍以 `content` 调用结果为准。仓库只记录上述状态，不保存返回正文或 provider 文献 ID。

## 5. 分层证明标准

| 层级 | 本路线的验收条件 |
|---|---|
| 文献提及 | DOI/文献身份已核对，数值只作为候选；允许缺少 Source Map，不进入材料结论 |
| 有数据支撑 | 人工核对图/表/正文定位、数值、单位、误差和全部关键条件；至少一条 `human_reviewed` Source Map |
| 可复现 | 在上一层基础上，样品、工艺、测量协议和数据处理足以重做；原始数据状态明确；预先定义容差 |
| 已经复现 | 独立样品或运行按预定义容差完成比较，记录独立运行 ID、成功/失败/不确定结论并经人工审核 |

同一指标形成稳健结论前，至少需要两个独立来源组，并主动保留一个不同条件或相反结果。只有“有数据支撑”及以上观测才能进入数值比较；条件缺失时状态必须是“不可直接比较”，而不是取平均值。

## 6. 下一批执行顺序

1. **已完成**：冻结 P0 指标名、单位语义与 12 个限定字段，覆盖相变、结构、极化和输运，并建立候选观测校验器和关系数据库模板。
2. **进行中**：四个核心比较问题已经各有两条独立原始实验路线和一条条件反例；继续把同一覆盖扩展到其余 P0 指标，以及 v2 新增的介电/压电、磁性、光学/光伏、缺陷和工艺指标。优先使用公开论文、作者稿或校园账号本地核对，不在仓库保存受限全文。
3. **已完成**：对 Lebeugle 2007、Teague 1970、Zeches 2009、Sando 2016、Arnold 2009 与 Bencan 2020 的六条公开 PDF 路线完成文件签名、私有 MinerU 解析和 Markdown 哈希核验，生成 6 个私有未审核候选池与 6 份空白 Source Map 选择模板。5 个长文池各含 48 个确定性全文分层片段，2 页 Teague 文献含 26 个片段；模板均为全未选状态。公开仓库只登记 `private_mineru_review_pool_ready`，不保存该批次的直接 PDF URL、PDF、Markdown、候选片段、提供方任务 ID 或私有路径。
4. **已完成技术定位和模型草案、待数据复核**：确定性指标排序已从六篇哈希核验 Markdown 各选出 2 段，共 12 段；四个问题均有命中。受控 `deepseek-v4-flash` 重跑完成 12 个逐段批次，严格校验后得到 16 条去重候选、合并 4 条重复观测、0 条结构拒绝。该输出仍为 `untrusted_llm_private_indicator_value_draft_not_source_map_or_evidence`；逐篇图表定位、数值语义、误差、方法与限定条件仍须核对，且不得写入 `material_facts`。
5. 先按“样品形态 → 相/取向 → 测量定义 → 条件”分组，再运行跨文献比较；不生成跨组平均值。
6. 前端只展示通过相应门禁的数值，并同时显示样品、方法、条件完整度和证据成熟度；候选值保留“待复核”标识。

本批次还复现并修复了 MinerU v4 的签名上传兼容问题：高级 HTTP 客户端会为字节正文隐式加入 `Content-Type`，从而使对象存储的规范请求与签名不一致并统一返回 403。当前批处理器改用只发送 `Content-Length` 的精确 HTTPS PUT；回归测试固定验证不加入 `Content-Type` 或 `Accept-Encoding`。修复后同一批次 6/6 上传、解析与 Markdown 获取成功。

后续批次可用同一离线入口生成审阅池；三个输入路径都必须位于仓库和 `runs` 目录之外，输出目录必须尚不存在：

```powershell
.\.venv\Scripts\python.exe tools\prepare_private_mineru_review_pools.py `
  --manifest <private-markdown-manifest.json> `
  --markdown-root <private-markdown-directory> `
  --output <new-private-review-directory> `
  --mission-id <bounded-mission-id>
```

命令要求清单中的每项均已下载，逐文件复算 Markdown SHA-256，拒绝路径逃逸、重复文献 ID、重复正文或部分完成批次；它只生成最多 48 段的私有候选池和全未选模板。

指标定向 shortlist 可以使用同一私有索引，也可以直接读取哈希核验清单，对整篇 Markdown 排序；输入和输出都必须位于仓库和 `runs` 之外：

```powershell
.\.venv\Scripts\python.exe tools\build_private_bfo_indicator_shortlist.py `
  --manifest <private-markdown-manifest.json> `
  --markdown-root <private-markdown-directory> `
  --output <new-private-indicator-shortlist.json>
```

2026-09-07 的真实运行先复现了超时、空响应与非完整 JSON，并均安全关闭；随后通过逐片段请求、禁用推理态空正文、明确 JSON 数字字段和局部事实拒绝完成受控重跑。最终私有汇总为 6 篇、12 个输入绑定、16 条去重候选、4 条重复合并、0 条结构拒绝，覆盖 `820–830 °C` 相变、`R3c/Pbnm/Cc`、导电畴壁占比 `69%/22%/59%`、极化 `3.5/60/100 μC/cm²`、外延失配范围、`c/a≈1.26` 及 `1.07→1.27` 等待核指标。所有数值仍是模型生成的私有核对线索；未建立人工 Source Map，也未升级证据成熟度。
