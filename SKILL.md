---
name: understand-gourmet-video-5.3-flash
description: "5.3-Flash 专用的离线美食视频语料理解流水线。完整输入视频/真实帧与 ASR，分阶段生成视觉证据账本、关键反应窗口、标准 A1–A15/B1–B7 Markdown 与结构化 JSON，并通过独立闸门验收。触发词：/understand-gourmet-video-5.3-flash、5.3-Flash视频理解、5.3-Flash美食视频理解"
argument-hint: "[语料目录路径]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, AskUserQuestion
# 本 skill 是主 skill 的完整独立分支；仅此分支适配 5.3-Flash。
---

# 5.3-Flash 离线美食视频语料批量理解

> **定位**：`understand-gourmet-video` 的 5.3-Flash 专用完整分支。独立执行、独立安装、独立验证，不依赖主 Skill 目录。
> **版本边界**：主 Skill 已锁定。5.3-Flash 的 prompt、阶段拆分、脚本与闸门只在本目录迭代；通用协议确需升级时，再对两个 Skill 分别修改和回归。
> **交付边界**：流程到标准 Markdown/JSON、双轨验收、合并整理与交付检查为止，不负责跨期蒸馏。

---

## Flash.2 目标：超过 0011–0030 的专业视频理解器

本分支不再以“写了多少 `[画面]`”为目标，而以**视频独有事实的机会覆盖、硬事实准确率和判断贡献**为目标。必须同时运行：

- 空间流：shot、构图、光线、色彩、景深、环境、食物形态；
- 时间流：动作边界、人物/物体运动、摄影机运动、FACS-lite 微反应；
- 声音流：对白/环境/餐具/烹饪/咀嚼/音乐/音效及声画关系；
- 剪辑流：shot boundary、时长、转场、空间/时间/节奏/图形关系。

完整规则见 `references/audiovisual-coding-framework.md` 和 `references/visual-observation-taxonomy.json`。抽样固定为全片 2fps、判断窗口 8fps/连续视频、面部清晰的微反应窗口目标 25fps（最低 15fps）。专业编码完整留在 ledger，A1 只投影与判断、表达、情境有关的高价值内容。

**超过基线的判据**：0011–0030 的不可丢视觉事实不回归，并在食物形态、动作/微反应、镜头/剪辑、声音/声画四类上增加可核验证据；OCR、对象分类、术语数量和全文字数均不算胜出。金标及门槛见 `references/visual-golden-v2.json`。

## 5.3-Flash 强制执行契约（接手前先读）

前序多模型实跑的失败不是内容不够长，而是**输入和产物协议失效**：部分调用只收到 ASR，却声称 `reviewed_frames`；部分产物漂移成“深度理解”自由文章或缺少 JSON。以下规则优先于历史说明：

1. **模型名不等于视觉输入。** 每期先用 `scripts/prepare_visual_assets.py` 建 `run-manifests/5.3-flash/{编号}.json`；没有实际视频/图片输入，所有段只能是 `audio_only`。
2. **阶段隔离且由状态机强制。** shot ledger → visual ledger → reaction windows → sound/edit ledger → assembly → 标准 JSON/Markdown；每阶段先过 `scripts/check_stage.py`，缺文件或 schema 不合格不得继续。
3. **结构不可自由选择。** 探店产物必须是 A1–A15/B1–B7 + C 区及 `data/5.3-flash/{编号}.json`；禁止 Mermaid、深度理解文章、人格侧写、星级和自由章节。
4. **视觉证据不可由 ASR 反推。** 单帧只支持静态事实；连续动作、表情变化和镜头关系必须有连续视频或 4–8fps 密帧。
5. **A9–A11 必须扫描但允许不可观察。** 证据不足写 `not_observable_from_sampled_frames`，不得为填满模板而编造。
6. **高召回不等于重复。** OCR 与口播相同不算视觉语义增量；人物/餐具/食物分类只进 raw detector 层。

阶段 prompt：

- `references/audiovisual-coding-framework.md`
- `references/visual-ledger-prompt.md`
- `references/reaction-window-prompt.md`
- `references/sound-edit-prompt.md`
- `references/assembly-prompt.md`
- `references/visual-positive-negative-examples.md`
- `references/visual-golden-v2.json`

## 丰富性优先迭代（当前最高优先级，接手前先读）

2026-08-27 对比实跑产物后确认：0011–0030 的视听观察、判断过程、方法论线索与表达DNA显著丰富于后续的安全收紧批次。**本 skill 的第一目标重新确认为高召回理解：最低不得低于 0011–0030 的丰富度，并应继续增强。**

### 不可违反的方向

1. **严格禁止恢复 V5.2。** V5.2 是低召回失败版本，不得作为架构基线，也不得以换名方式重新引入其“紧缩 JSON / 默认留空”路线。
2. **丰富性高于安全性。** 不确定信息采用保留、分层、竞争解释和下游隔离，不以删除、默认留空或抬高提取门槛换取零 BLOCK。
3. **前置理解不是摘要。** 除完整原话和逐段画面，还须重建本期判断过程：预期、刺激、信息获取、反应序列、比较、推理、复核、修正、结论和行动。
4. **电影学只服务判断还原。** 分析镜头内部行动、镜头关系、声画关系、反应序列、判断弧线和意义主体；不做摄影审美评论。
5. **安全闸门与丰富性审计分开。** `validate_corpus.py` 检查事实/结构；`audit_richness.py` 诊断遗漏。零 BLOCK 但内容薄，仍是失败产物。

### 新增高召回结构

- A9 镜头与声画关系
- A10 反应序列与可观察机会
- A11 专家/言语/剪辑三种注意力
- A12 判断弧线
- A13 本期判断事件
- A14 比较、转折与言行张力
- A15 本期推理链
- B3 六环节机会扫描
- B4 表达DNA素材
- B5 原始感官措辞
- B6 品味谱系与个人经验
- B7 开放解释与竞争性解释

完整定义见 `references/understand-prompt.md`、`references/output-schema.md`；验收见 `references/richness-rubric.md`。

## v4.7：视觉声明必须形成跨层证据链

2026-08-31 对新版 0001–0010 回归发现：0002–0010 的 JSON 大量声明 `reviewed_frames` / `frame_sequence`，但 Markdown A1 没有 `[画面]` 客观观察，旧闸门仍签发零 BLOCK。Prompt 已写清要求，失效点是脚本没有交叉检查。

本轮补齐：

- `VISUAL_STATUS_NO_MD_BASIS`（BLOCK）：逐段核对 JSON reviewed 声明与 A1 的同源视觉观察；`audio_only` 不得出现视觉事实。
- `FRAME_SEQ_NO_MD_OBSERVATION`（BLOCK）：`frame_sequence` 至少两个真实帧端点，并在对应 A1 时间窗留下引用同源帧的客观观察。
- `RICH_VISUAL_LINES_ZERO` / `RICH_VISUAL_MD_COVERAGE_LOW`（WARN）：揭示“JSON 很满、Markdown 视觉为零/过低”的影子层分裂。
- 每条新规则均进入 `--selftest`；旧产物没有新视觉契约时维持兼容，不因升级被 BLOCK。

**诚实边界**：这些规则只能证明声明、资产和跨层留痕一致，不能证明模型真的读取过图片或描述语义真实。模型输出的帧清单只是可审计声明；若执行环境可提供不可由模型改写的工具访问日志，以工具日志为准。语义真实性由校准批与放量批的独立原帧抽检兜底。

## v4 变更摘要（历史安全机制，仍有效但不得压过丰富性）

v3 把约束从 prompt 搬进了脚本，方向是对的。但对 10 份 v2 产出实跑后发现：
**风险跟着搬了家——从「模型说谎」变成「校验器说谎」，而后者更隐蔽。**

闸门报出 419 条问题，看起来很勤奋。实际上：

| v3 的失效 | 后果 |
|---|---|
| `check_candidate_patterns` 读 `p['statement']`，而 schema/prompt 用 `pattern` | **`B1_FORBIDDEN_PHRASE` 一次都没运行过**——而"从单期偷渡稳定偏好"是 B1 唯一要防的事 |
| `build_gate()` 不输出 `validated_at` | 合并准入要求它非空 ⇒ **零 BLOCK 的记录也进不了下游**，死循环 |
| `md_allowed_h3` 只有探店那套 | 表态类按自己的 prompt 写就必吃 5 个 `MD_H3_DIVERGED`，**无论怎么改都过不了** |
| 脚本要求 `sample_count==1`，schema 说 3-4 可填 medium 且示例写 4 | 文档与校验直接对立，模型怎么填都挨一刀 |
| `enums.json` 注释承诺"ASR 纠正后的值也算博主说过"，脚本没实现 | 0001「剪发→碱发」已纠错，6 处 `TECH_TERM_NOT_SPOKEN` 全误报，连纠错表自己那行都被拦 |
| `TS_DUPLICATE` 只比较区间字符串 | 文档承诺"不重叠"，部分重叠（00:32-01:15 vs 01:00-01:40）查不出——实测漏了 8 处 |
| SKILL.md 承诺"自动回修"是三大手段之一 | 该功能不存在，全靠人工 |

所以 v4 的主题是**让校验器自己也可被验证**：

| 变更 | 文件 | 要点 |
|------|------|------|
| **新增 `--selftest`** | `validate_corpus.py` | 每条规则各配 should-fail 样本（v4 首版 30 条，现 48 条） + 探店/表态两份 should-pass 基准。**这是本次最重要的改动**——没有它，"规则存在但不生效"只是从 prompt 层搬到脚本层 |
| **新增 `--fix-safe`** | `validate_corpus.py` | 零语义判断的机械回修（括号→`tag_qualifier`、组合枚举→`both`、v4 新字段补 null）。实测 10 期可自动修 142 项 |
| 修 `pattern`/`statement` 键名 | `validate_corpus.py` | 两者都认，以 `pattern` 为正名。B1 禁用词检查**首次真正生效** |
| `build_gate` 补 `validated_at`/`validator_version` | `validate_corpus.py` | 解开合并死循环。新增 `--date` 指定日期 |
| 表态类独立白名单 | `enums.json` | `md_allowed_h3_statement`；`B1_NO_JSON` 不再对表态类报 |
| **新增 `### A7 无反应自检`/`### A8 镜头时长分配`** | `enums.json` | v2 的模板分裂不是"写错了"，是这两块内容**没有合法位置**。给了编号，占用 A3/A4 才成为真错误 |
| ASR「纠正后」值并入可溯源语料 | `validate_corpus.py` | 按表头定位列（实跑是 5 列，模板是 4 列）。消掉 6 处 `TECH_TERM_NOT_SPOKEN` 误报 |
| `sample_count` 拆为 `video_count` + `within_video_sample_count` | schema | 前者恒 1（防抖阈值关心的），后者记本期几道菜支撑。消掉文档与校验的对立 |
| `QUOTE_ELIDED`（WARN）从 `QUOTE_NOT_IN_TRANSCRIPT` 分出 | `validate_corpus.py` | 逗号级分句全部可溯源 ⇒ 只是漏标省略号，词汇指纹完好。实测 10 条里 2 条属此类 |
| `TS_OVERLAP` 按秒做区间交集 | `validate_corpus.py` | 重叠过半 BLOCK、少量 WARN。实测新发现 8 处 |
| `sentiment_dish` 统一为六级 | `enums.json` | 加回 `有保留`。五级/六级的刻意区分是最高产的枚举错误（46 条里 7 条），而 schema 从未说明为何要有这个差异 |
| 标签词典 38 → 57 个 | `tag-dictionary.json` | 10 期撞出 37 种词典外标签，多数是合理新概念。闭词典太小 ⇒ 模型自创 ⇒ 更乱 |
| 逃生口允许带前缀 | `tag-dictionary.json` | `味道-其他-味儿浓` 现在合法——模型在保留统计轴，这个直觉是对的 |

### v4.1 补修（评审发现的内部不一致，全部已核实存在）

v4 落地后的评审又找出 8 处真实问题。**它们全都属于同一类：
文档说了一件事，脚本做的是另一件事**——正是 v4 想根治的病，只是位置更深。

| 问题 | 表现 | 修法 |
|---|---|---|
| `sentiment` 五级/六级冲突 | enums/schema 已统一六级，`understand-prompt.md:560,572` 仍写五级——**同一文件 L699 与 L560 自相矛盾** | 统一为六级 |
| schema 示例照抄即 BLOCK | `candidate_patterns` 示例缺 `source_type`，而闸门强制非空。实测复现 `ENUM_NULL` | 示例补 `source_type`/`scope`/`scope_quote`，并规定 `model_inference` 不进 B1 |
| **D10 scope 后门** | `d10_ordering.scope` 完全没被校验，`"scope": "本帮菜普遍如此"` 一路畅通 | 新增 `D10_SCOPE_NOT_THIS_SERVING`，钉死 `this_serving` |
| schema 示例教错写法 | `d2_ingredient` 示例仍是"碱发过度产生异味"+"碱发能让海参涨发变大"——把推测写成确定因果、把行业常识包装成博主判断 | 重写示例 |
| `scope_quote` 只查非空 | docstring 写着"须能在转写稿命中"，实现只判空——编一句"他们家每次都这样"就能给升级背书 | 新增 `SCOPE_QUOTE_NOT_IN_TRANSCRIPT` |
| B1 md/json 不逐条比对 | 文档承诺"检查两边数量是否一致"，实际只在键缺失时报 WARN | 新增 `B1_COUNT_MISMATCH`（两种 md 写法都认）|
| `tag_qualifier` 值域无校验 | 词典只许 4 个值，`--fix-safe` 却主动写 `原括注：面包`——**schema 说不允许、脚本却在写** | 正式承认该过渡形态，新增 3 个 WARN 码 |
| 逃生口过宽 | `口感-其他-这个东西真好吃啊我简直了` 能通过 | 限 2-12 字、禁括号换行 |

修的过程中又发现**一个 v4 自己没抓到的死检查**：B1 区正则的边界
`(?=\n###|\n##|\Z)` 里，`\n###` 会匹配到 `\n#### 候选规律` 的前三个 `#`，
导致 B1 区内容恒为空字符串——**md 侧的 `B1_FORBIDDEN_PHRASE` 一直是死的**。
和 v3 的 `statement`/`pattern` 是同一类错误：正则的 off-by-one 不会报错，
它只会让检查静静地什么都不查。这也说明 `--selftest` 的 should-pass 基准
同样重要——正是基准样本冒出一个不该有的 WARN 才暴露了它。

**新检查上线即战果**：`B1_COUNT_MISMATCH` 在 10 期语料里抓出
**30 条候选规律只写在 md、json 里一条都没有**——这批数据若按 v3 合并，
30 条单期猜测会带着"已确认规律"的身份进入下游画像。

规则数 30 → 38，两份基准仍零 BLOCK。

### v4.6：`values_triggered` 的同款漏洞，以及探店 B2 根本没进 json

外部审计指出 `values_triggered[].source_type` 的约束**四处文档互相矛盾**，
而脚本只做全局枚举校验，因此 `model_inference` 会通过。核实全部成立：

| 位置 | 原文 |
|---|---|
| `output-schema.md:661` | 允许 `model_inference` |
| `understand-prompt-statement.md:133` | 允许 `model_inference` |
| `understand-prompt.md` B2 | **只允许** 两个 blogger_* |
| `output-schema.md:41`（同一文件内）| "不得进入 candidate_patterns、**价值观**与跨期统计" |

他们的风险判断也对，而且我认为**比 B1 更该优先修**：红线按防抖阈值
「≥1次明确表态+行为一致」**单期即可确认**——它没有 `not_stable_rule` 免责声明，
也不需要跨期验证。B1 的猜测下游至少知道要再验；红线的猜测会直接成为
专家画像里的"他绝不接受 X"。已加 `VALUES_MODEL_INFERENCE`。

**顺着查下去发现一个他们没提、但更严重的问题**：
探店 prompt 的 B2「价值观与红线」**没有任何 json 对应字段**——
`values_triggered` 原先只存在于表态类 schema。于是探店的 B2 只写在 md 里，
下游只读 json 就全丢了。**这与 v3 时 B1 的失效方式一模一样**
（当时 30 条候选规律静默消失），只是 B1 后来有了 `B1_COUNT_MISMATCH` 保护，
B2 从头到尾没人看。

新检查一上线就抓出：**10 期里 7 期共 18 条价值观/红线只写在 md**。

修法：
- `enums.json` 新增 `source_type_blogger_only` 作单一事实源，B1 与 values 共用
- 四处文档统一为"只接受 blogger_explicit / blogger_hypothesis"
- 探店 schema 与 prompt 都补 `values_triggered`，新增 `B2_NO_JSON` / `B2_COUNT_MISMATCH`

> **这轮的教训**：v4.5 刚修完 B1 的收窄枚举，同一个模式在 `values_triggered`
> 上原封不动地又存在一遍——**修了一处没去搜同类**。
> 以后发现"文档约束比枚举窄"这类问题，应当立刻全量搜一遍还有哪些字段同病，
> 而不是只修被指出的那一个。同理，B1 补了 md/json 对齐检查时，
> 就该顺手问一句"B2、B3 有没有同样的洞"——答案是有。

规则数 48 → 50。

### v4.5：B1 收窄枚举没被强制 + 自检的覆盖盲区

外部审计（只读 skill、不看产出）找出一个 BLOCK 级漏洞和几处一致性问题，全部核实成立。

**★ 必修：`candidate_patterns[].source_type` 是收窄枚举，但闸门按全局枚举验。**
schema 与 prompt 都写明"`model_inference` 不进 B1"，而 `check_enums` 只验它是否
属于全局 `source_type`——全局枚举本身含 `model_inference`。于是这条一路放行：

```json
{"pattern": "模型推测他通常更重视食材新鲜度", "source_type": "model_inference",
 "video_count": 1, "confidence": "low", "not_stable_rule": true}
```

模型自己的猜测以"可跨期归并的候选规律"身份进入下游，**正好违背 B1 的设立目的**。
已加 `B1_MODEL_INFERENCE`。这是"约束写在文档里、枚举校验够不着"的典型：
**凡是某字段的合法取值比全局枚举更窄，就必须单独写一条检查**——
`chk(val, key, where)` 那套通用枚举校验天然只认全局闭集。

其余：

| 问题 | 修法 |
|---|---|
| `dimension_events[].scope_quote` 被强制但**未写进 schema** | schema 的 B 档字段表 + A2 事件模板都补上该列。严格照 schema 写的人原先只能从报错里得知需要它 |
| 表态类基准样本仍写 `processing_status: 完整` | 改 `完成待修订`。不影响零 BLOCK 判定，但基准就该是规范写法的范本 |
| 禁用词子串匹配重复计数（`核心标尺` 同时命中 `标尺`）| 新增 `forbidden_hits()`，最长词优先去重。不漏检，但问题总数不再虚高 |
| WARN 规则几乎没有回归保护 | 补 `B1_NO_JSON` / `DERIVED_NO_BASIS` / `REACT_ALL_EXPLICIT` 三条断言（审计点名的优先项）|
| `sentiment_dish` 与 `assessment_dimension` 靠人记得保持一致 | 加载期断言两者相等，不等则直接退出。五级/六级分叉不会再静默回归 |
| `merge-guide` 准入未显式排除 `无关`/`失败` | 加 `content_type` 白名单。准入是不可逆的信息固化，多一道成本为零 |
| SKILL.md 写"30 条规则"而实际已 48 条 | 改为不写死数字——**要看的是「0 条未生效」，不是 N** |

**顺带修了自检框架自身的一个脆弱点**：某条变异函数误返回了 `dict.pop()` 的结果
（list）而非 md 文本，整轮自检直接崩在 `write()` 上——只看到一个 TypeError，
看不出是哪条坏了。现在会定位到具体规则并继续跑完其余。
**测试框架本身也需要容错**，否则它在最需要它的时候（有人改坏了东西）失灵。

规则数 43 → 48。

### v4.4：三个语义盲点（外部评审发现，全部核实成立）

重跑后的评审抽样读了正文，指出了三处**闸门报"通过"而内容实际有问题**的地方。
逐条复核后全部成立，而且比报告说的更严重——它们互相成链：

| 盲点 | 表现 | 为什么闸门没抓到 |
|---|---|---|
| **B1 禁用词差一个字就绕过** | 实跑写的是「核心标尺」「核心评价指标」「具有稳定性」「参照标尺」「坐标系」，禁用表只有「的标尺」 | 闭集列举式检查的固有弱点：列了 12 个词，模型用第 13 个 |
| **`[推断]` 行是无条件豁免通道** | 标上 `[推断]` 就什么都能写。0001 L32「微甜、香油重为**本帮菜典型特征**」——这是模型的餐饮知识，不是本期博主说的任何话 | TECH 检查见到 `[推断]` 直接 `continue` |
| **★ C 区纠错是洗白通道** | 0001 写 `剪发 → 碱发/化学发制`，于是「碱发」被注册进可溯源语料，**全份正文再怎么用都不会被 TECH_TERM 拦** | v4 为修 ASR 误报，把「纠正后」值并入可溯源语料——修对了一半，却没同时强制"纠正后必须唯一确定" |

第三条最值得记：**v4 的修复自己造出了一个新漏洞。**
"纠正后必须唯一确定"这条规则在 `understand-prompt.md` 写了三处、SKILL.md 写了一处，
**从来没有被强制过**。于是一个多值纠错就能给任意工艺术语发一张通行证。
0001 的「碱发」正是这样一路畅通的——它不是没被检查，是**检查在源头就被喂了假数据**。

对策：

| 变更 | 要点 |
|---|---|
| 禁用表 12 → 24 项 | 补「标尺」「核心标尺」「核心评价指标」「坐标系」「具有稳定性」「表现稳定」「稳定偏好」「一贯」「判断体系」等。实测立刻抓出 **12 处**漏网 |
| 新增 `INFERENCE_IS_INDUSTRY_KNOWLEDGE` | `[推断]` 行禁用「典型特征/标准做法/通常/众所周知」等行业常识指纹。推断的依据只能是本期语音画面，不能是模型先验 |
| 新增 `TECH_TERM_INFERENCE_UNHEDGED` | `[推断]` 不再无条件豁免：出现工艺词时必须同时划清界限（明写"博主未说过"或加"可能/疑似"）。0007 L131 是合规范本——它明写"不得将模型的化学知识署名给博主" |
| **新增 `ASR_CORRECTION_NOT_UNIQUE`** | C 区「纠正后」给多值且含工艺术语 ⇒ BLOCK（堵洗白通道）；其余多值 ⇒ WARN。括注里的存疑说明（`存疑保留（可能为红曲汤/红酱油汤底）`）不算多值——那是诚实标注，正是 prompt 要求的做法 |

规则数 40 → 43。问题总数 119 → 141（不是变差，是**原先漏掉的被看见了**）。

> **方法论教训**：`--selftest` 防的是"规则没运行"，v4.2 的 `TS_OVERLAP` 教的是
> "规则运行了但判据对错了对象"，这一轮教的是第三种——
> **规则和判据都对，但输入数据在上游就被污染了**。
> 检查链上任何一环能被产出物自己改写（这里是 C 区纠错表），
> 整条链的结论就不可信。凡是"产出物参与定义自己的校验基准"的地方，
> 都要专门问一句：**它能不能借此给自己发通行证？**

重跑一轮后做了归因分析：130 条问题里，**38% 是 skill 缺陷**（模型无从合规），
59% 是"规则已写明但没做到"。而后者**超过一半聚集在 2 份文件**
（0001+0003 = 40 条），其余 8 份平均 4.6 条。

决定性证据是**同一次运行内部的分裂**——同一模型、同一规则、同一次连续运行：

| 编号 | 含括号标签 | 用了 v4 新标签 | 用了 `tag_qualifier` |
|---|---|---|---|
| 0003 | **10** | 0 | 0 道菜 |
| 0006 | 0 | 5 | 3 道菜 |
| 0009 | 0 | 3 | 3 道菜 |

0006 写出 `['口感-酥脆','口感-干硬'] + {'口感-酥脆':'过度'}`（完全正确），
0003 写出 `['口感-软烂(九分烂)','味道-辣(微辣)'] + {}`（v3 老习惯，零采用）。
**同一能力、同一规则、结果两极 ⇒ 病因是执行一致性，不是能力上限。**

三项对策：

| 改动 | 文件 | 要点 |
|---|---|---|
| **`processing_status` / `quality_gate` 移出输出契约** | prompt + schema | 生成时固定 `完成待修订`、不输出 `quality_gate`。新增 `GATE_SELF_REPORTED` 拦残留的自我声明；`--write-gate` 改为**单向裁决**（零 BLOCK 升 `完整`，有 BLOCK 降 `完成待修订`），不看它原来写的是什么 |
| **补闭集缺口** | `enums.json` / `tag-dictionary.json` | `cuisine` 补 11 项 + `其他` 逃生口——0003 是湖北菜、0008 是小吃综合，**v4 闭集里都没有且无逃生口，模型填什么都是 BLOCK**。标签补 `香气-青花椒香`/`香气-发酵香` |
| **`QUOTE_COMPOSITE` 默认静默** | `validate_corpus.py` | 拼接引用是合法写法，却报了 16 条（占 12%）纯噪音，盖住真问题。改为 ≥4 段才提示，`--verbose` 看全部 |
| **Step 3 改「校准批 + 反馈闭环」** | SKILL.md | 先跑 2 份 → 过闸门 → **报告原文贴回理解调用** → 再跑 1 份验证 → 才放量 |
| `--fix-safe` 扩容 | `validate_corpus.py` | 增：剥 `quality_gate`、降 `完整`、`cuisine` 取菜系级、标签近义归一（`口感-脆`→`口感-脆嫩`）。10 期可自动修 **46 项** |

**为什么第一条是关键**：v4 实测 6 份手填了 `quality_gate`，0003 声明
`blocking_issues: []` 而实测 26 条 BLOCK。这不是不听话——
**schema 把字段列为必填、给了完整示例，同时叮嘱"不要手填"，指令本身自相矛盾**。
更根本的是"我这份合规吗"在生成时无法自答：生成者已经相信自己合规了。
这与 v2 自检清单全打勾是同一机制，只是形式从复选框升级成了 JSON 对象。
**所以不是叮嘱得更严厉，而是不给填的机会。**

效果：119 条（`QUOTE_COMPOSITE` 静默 + cuisine 修好）→ 跑 `--fix-safe` 后 **84 条**。
剩下的基本都是真需要回原始素材的语义问题。

### v4.2 补修：`TS_OVERLAP` 惩罚了唯一正确的做法

重跑后的语料暴露了 v4.1 自己引入的一个假阳性。**判据搞错了对象**：
它查的是"区间有没有重叠"，而真正该查的是"**时长有没有被重复计入**"。

火锅、烤肉、烧烤这类连续涮煮的场景，多道菜天然在同一段落里被讨论。
schema 规定的正确写法就是：**该段秒数归主要讨论对象，其余记 0，区间照实写**。
0010（袁老四火锅）10 道菜正是这么写的——41s/0s/0s/0s，Σ155s < 214s，
一秒都没重复。而 v4.1 一律 BLOCK，报了 8 条，把标准答案判成了错。

修法：只有**双方 `shot_duration_sec` 都 > 0** 时才算重复计入。
双方都是 0 且共用同一区间 ⇒ 新增 `TS_SHARED_NO_OWNER`(WARN)——
不重复计时长，但整段没人认领，Σ时长会偏低。

效果：0010 从 8 条 BLOCK 降到 0；全语料 15 处重叠中，
**3 处真重复计入**（0002/0005/0007，双方都计了秒）保留，12 处误报消除。

> 这条和 v3 的 `statement`/`pattern`、v4 的 B1 区正则是同一族错误，
> 但方向相反：前两个是**漏检**（规则没运行），这个是**误检**（规则运行了，
> 但判据对准了错的东西）。`--selftest` 只能防漏检——它证明规则会触发，
> 不能证明规则该触发。**误检只能靠拿真实产出对着跑**，
> 而且要专门问一句："被拦的这条，会不会其实是对的？"

**首次上手的正确姿势**：

```bash
python3 scripts/validate_corpus.py --selftest        # 先确认闸门自己是好的
python3 scripts/validate_corpus.py {语料目录} --variant 5.3-flash         # 再看它拦什么
```

顺序不能反。**闸门未自检就信它的结论，等于信一份没人核对过的自检清单**——
那正是 v2 的错误，只不过换了个主体。

---

## v3 变更摘要（历史，仍有效）

v2 的实跑结论是：**方法论和字段设计已经够用，但约束不生效。**
十份产出的自检清单逐项打勾，实际却有枚举越界 46 处、
工艺归因署名博主 24 处、标签括号分裂 23 种、scope 无据升级 13 处。

所以 v3 不再往 prompt 里加强调，而是转向 **Schema 约束 + 规则校验 + 自动回修**：

| 变更 | 文件 | 要点 |
|------|------|------|
| **新增 Step 3.5 验证闸门** | `scripts/validate_corpus.py` | 外部脚本、不调模型、17 类机械检查。**这是本次最重要的改动** |
| **枚举单一事实源** | `references/enums.json` | 枚举/禁用词/工艺术语/小节白名单集中一处 |
| **标签闭词典** | `references/tag-dictionary.json` | 38 个标签 + 别名映射；标签内禁止括号 |
| **`processing_status` 增 `完成待修订`** | schema | 有 BLOCK 时的落点，防止"要么失败要么完整"逼出虚假完整 |
| **新增 `quality_gate` 对象** | schema | 由脚本回写，不得手填 |
| **`candidate_patterns` 进 json** | schema | B1 原先只在 md，Phase 2 读不到，免责声明形同虚设 |
| **新增禁区：不得补全餐饮技术结论** | `understand-prompt.md` | 博主没说过的工艺术语不得署名给博主 |
| **画面三态 `[画面]`/`[花字]`/`[推断]`** | `understand-prompt.md` | 一行只能一种；读不清的花字不进 A1 |
| **新增字段** | schema | `scope_quote` `tag_qualifier` `party_size_basis` `price_per_person_basis` |
| **合并前置准入** | `merge-guide.md` | Step 1 拒收非 `完整` / 有 BLOCK / 无 `quality_gate` 的记录 |

**首次上手的正确姿势**：先对已有产出跑一次闸门，看它拦什么，
再决定是修订旧产出还是重跑。闸门是只读的，加 `--write-gate` 才会改文件。

---

## 为什么独立成 skill

视频理解依赖多模态能力，并且需要独立管理帧资产、批次进度、丰富性审计和事实闸门。因此本 skill 只负责一条闭合链路：

```
视频全集 → 逐条理解 → 双轨验收 → 合并整理 → 交付检查
```

交付物是保留完整信息的理解语料，不在本 skill 内继续做跨期归纳或专家蒸馏。若干份理解文件如何进一步蒸馏，后续另行设计。

---

## 核心约束（违反任何一条都会污染下游）

本环节在折损链路中的位置是**前置提炼**——它的输出被下游读取，**它丢掉的信息下游永远看不见**。因此：

### 1. 只做还原与纠错，不做语义压缩

保留完整原话，画面信息作为**增补**而非替代。不要把"这没法儿评价了，这个东西就不能吃了"重述成"他认为该菜品不可食用"——重述过的部分，表达DNA 的词汇指纹就丢了。

### 2. 分层输出，使筛选失误可挽回

还原层（完整记录）与提炼层（初步信号）分区存放。下游默认读提炼层，需要时回查还原层。

### 3. 提炼深度对齐防抖阈值

单条语料能支撑到什么程度就提到什么程度：

| 层次 | 防抖阈值 | 单条视频能否确认 | 本环节的处理 |
|------|---------|:---:|------------|
| 价值观红线 | ≥1次明确表态+行为一致 | ✅ 能 | **按结构提取** |
| 决策启发式 | ≥2次不同内容出现 | ⚠️ 部分 | **提取但标注来源类型**，交下游做次数校验 |
| 判断方法论 | ≥2个完整案例同一流程 | ❌ 不能 | **只记线索**（按六环节归位） |
| 心智模型 | ≥3次跨场景+能预测新情况 | ❌ 不能 | **只记线索**，严禁输出结论 |

从一顿饭里硬提炼出"他的世界观是……"，全批次都是这种过度归纳，下游拿到的就是一堆噪声。

### 4. 合并阶段只做物理拼接，不做二次归纳

否则形成三级 reduce，失真叠加。合并的价值在**分组维度选得好**，不在文件变少。

### 5. 约束必须可机械验证，否则等于没有（v3 新增）

前四条约束在 v1/v2 都写清楚了，prompt 里也反复强调了，
**但实跑仍然违反，且违反了没人发现**。

v2 十份产出的实测数据：自检清单逐项打勾，同时存在
枚举越界 46 处、工艺归因署名博主 24 处、标签括号分裂 23 种、
scope 无据升级 13 处、时长超实测总长 2 期。

结论很直接：**"在 prompt 里说清楚"和"约束生效"之间没有因果关系。**
模型不是故意违反，是它相信自己没违反——自检因此系统性无效。

所以 v3 的做法是把约束落到三个能验证的地方：

| 手段 | 文件 | 作用 |
|------|------|------|
| Schema 约束 | `enums.json` / `tag-dictionary.json` | 取值只能从闭集合里选，不给自创空间 |
| 规则校验 | `scripts/validate_corpus.py` | 外部脚本读产出，机械判定，不调模型 |
| 机械回修 | `--fix-safe` | 零语义判断的问题脚本直接改；需判断的回到原始素材 |
| 定点修订 | Step 3.5 循环 | 按检查码改该字段 → 重跑 `--id` → 直到无 BLOCK |

**下一轮迭代的方向也在这里**：发现新的失效模式时，
优先问"这条能不能写成脚本检查"，而不是"prompt 里再加一段强调"。
加强调的边际收益已经接近于零。

### 6. 校验器本身也必须可验证（v4 新增）

第 5 条把约束从 prompt 搬进了脚本。代价是**风险也跟着搬家**：
从"模型相信自己没违反"变成"我们相信闸门在工作"。后者更危险，
因为闸门会输出一大堆问题，这个勤奋的外观本身就是一种担保。

实测：v3 闸门对 10 期语料报出 419 条，而 `B1_FORBIDDEN_PHRASE`
因为读错一个字段名，**从未运行过**——恰好是最关键的那条。
它不报错、不告警，看上去就像"本批没有这个问题"。

所以每条规则都要有一对样本：should-fail（不拦就是 bug）
与 should-pass（拦了就是误杀）。

```bash
python3 scripts/validate_corpus.py --selftest
```

**判据**：输出末行 `N 条规则生效，0 条未生效`，且两份基准样本零 BLOCK。
**不要把 N 写进文档当硬指标**——每加一条检查它就变；要看的是「0 条未生效」。
加新检查时同时加一对样本，否则新规则的生效状态无人知晓。

这条是前五条的元规则：**没有它，"规则存在"和"规则生效"之间
仍然没有因果关系——只不过失效的位置从 prompt 挪到了脚本。**

---

## 目录约定

本 Skill 的产物版本默认为 `5.3-flash`。生成、阶段闸门、校验、丰富性审计与合并脚本均使用同一个 `--variant`；省略参数即使用 `5.3-flash`，只有读取旧根目录产物时才显式传 `--variant root`。版本信息由目录承担，新文件统一命名为 `{编号}.md` / `{编号}.json`，不得再追加模型后缀。

```
{语料目录}/
├── {编号}.mp4                        视频原件（已有）
├── {编号}_audio_transcript.md        ASR转写稿（已有）
├── frames_{编号}/                    视频帧目录（本 skill 自动检测/按需抽取）
│   └── f_00001.jpg ...               建议每秒 1 帧，保留原始帧文件名
│
├── understanding/5.3-flash/{编号}.md      ← 本skill产出：还原层+提炼层+纠错清单
├── data/5.3-flash/{编号}.json             ← 本skill产出：结构化字段
├── run-manifests/5.3-flash/{编号}.json       ← 输入资产与阶段状态
├── shot-ledgers/5.3-flash/{编号}.json        ← 镜头账本
├── visual-ledgers/5.3-flash/{编号}.json      ← 空间视觉证据
├── reaction-windows/5.3-flash/{编号}.json    ← 动作与微反应
├── sound-edit-ledgers/5.3-flash/{编号}.json  ← 声音与剪辑账本
├── assembly/5.3-flash/{编号}.json            ← 固定渲染 payload
├── validation-report.5.3-flash.json          ← Step 3.5 安全闸门报告（保存 --json 输出时使用）
├── richness-report.5.3-flash.json            ← 丰富性报告（保存 --json 输出时使用）
├── grouped/5.3-flash/{品类}.md               ← 合并阶段产出（脚本，可重跑）
├── corpus-index.5.3-flash.json               ← 合并阶段产出（脚本，可重跑）
├── prescreen.json               ← 前置粗筛产出
└── progress.md                  ← 批次进度台账
```

**编号必须与已有文件一致**——它是跨目录关联的唯一键。

⚠️ **编号只能是纯编号。** 不要写成 `0004_csvrow91.json` 这类带来源后缀的名字——
`frames_0004/`、`0004.mp4`、`0004_audio_transcript.md` 都以纯编号为键，
文件名一旦掺入其他成分，跨目录关联就断了。
（闸门做了容错，会剥掉前导数字之后的部分去匹配，但不要依赖这个容错。）

---

## 单一事实源文件（改这些文件即改规则）

| 文件 | 内容 | 谁读它 |
|------|------|--------|
| `references/enums.json` | 全部枚举取值、禁用词表、工艺术语表、小节白名单 | 闸门脚本 |
| `references/tag-dictionary.json` | `standard_tags` 闭词典 + 别名映射 | 闸门脚本 |
| `references/output-schema.md` | 字段定义（枚举部分是上面两个 json 的可读镜像） | 人 + 理解调用 |
| `references/richness-rubric.md` | 0011–0030 为下限的丰富性验收、金标与回归判据 | 人 + `audit_richness.py` |

**新增枚举值或标签时，改 json，不要只改 md。** 闸门读的是 json；
只改 md 会导致"文档说合法、闸门判越界"。反之只改 json 则文档失真——两个都要改，以 json 为准。

---

## 执行流程

```
Step 1  前置粗筛（脚本，不占多模态成本）
          └─ 内容三分类 + 输出待处理清单
Step 2  三尺度资产与 run manifest（必经）
          └─ 全片2fps + shot keyframes / 事件8fps / 微反应25fps
Step 3  5.3-Flash 分阶段理解（每阶段 schema 通过后才前进）
          ├─ 3a shot-ledger：镜头边界、构图、光线、景深、食物形态
          ├─ 3b visual-ledger：筛选判断相关空间事实
          ├─ 3c reaction-window：动作边界与FACS-lite微反应
          ├─ 3d sound-edit-ledger：声音、剪辑、节奏、声画关系
          ├─ 3e 标准 JSON + assembly payload
          └─ 3f renderer 生成固定 A1-A15/B1-B7 Markdown
Step 3.5 双轨验收（必经，不可跳过）
          ├─ 丰富性审计：audit_richness.py → 对照0011–0030金标补理解
          └─ 安全闸门：validate_corpus.py --selftest → 校验 → --fix-safe
             → 只做标注/定点修订，不得删除丰富信息 → --write-gate
Step 4  合并整理（脚本，可反复重跑）
          └─ 汇总index → 按品类切分 → 拼接分组文件
Step 5  交付检查
          └─ 核对逐期理解、结构化索引、分组文件与异常台账；流程到此结束
```

> ⚠️ **Step 3 与 Step 3.5 是两轮，不能合成一轮。**
> 第一轮生成，第二轮**只读已生成的文件**按硬规则校验。
> 这个分离是必要的：v2 十份产出的自检清单全部逐项打勾，
> 而实际有 46 处枚举越界、24 处工艺归因署名博主。
> **生成者无法审查自己的生成**——它已经相信自己合规了。

### Step 1：前置粗筛

见 `references/prescreen.md`。用转写稿做纯文本判断，产出 `prescreen.json`：

- **探店**：走完整 schema
- **表态类**：走简化 schema（无店铺无价格，只提价值观+表达DNA）
- **无关**：排除，记录原因

粗筛很便宜，能省掉一批无效的多模态调用。**但不要过度信任它**——边界样本按"探店"处理，宁可多跑不可漏掉。

### Step 2：帧资产检查与抽取（必经，不可跳过）

> ⚠️ **完整理解的前置条件是视频帧可用。** 不得仅因已有 ASR 转写稿就跳过画面分析；未检查帧目录不得将任务标记为完整。

对每个 `{编号}.mp4`，按以下顺序处理：

1. **检测帧目录**：查找 `{语料目录}/frames_{编号}/`；目录存在但无图片文件也视为缺失。
2. **复用有效帧**：目录有可读图片帧时，直接复用；保留既有文件名，不重复抽取。
3. **三尺度资产生成**：使用 `scripts/prepare_visual_assets.py`，而不是手工编造帧编号：

```bash
python3 scripts/prepare_visual_assets.py {语料目录} --id {编号} --variant 5.3-flash \
  --event J1=00:30-00:45 --event J2=01:10-01:28 \
  --micro M1=00:36-00:40
```

   - 全片层：2fps + shot keyframes，支持构图、环境、食物静态形态、花字；
   - 判断层：8fps/连续视频，事件前2–3秒至后3–5秒，单窗≤20秒；
   - 微反应层：脸清晰的2–5秒窗口，目标25fps、最低15fps。
4. **定位判断事件窗口**：先用 ASR/2fps 帧找强判断、转折、复尝/复核、菜品切换、停吃/退菜和总结回扣；只给确有机会的窗口建密帧。
5. **阶段状态机**：每阶段完成后更新 manifest status 并运行 `scripts/check_stage.py`；未通过不得进入下一阶段。
6. **视觉覆盖台账**：每个 A1 时间段写 `visual_status`、`visual_basis` 与花字可读性；完整专业编码写 shot/action/sound ledger，A1 只投影高价值事实。
7. **抽帧校验**：记录采样率、窗口、资产清单；连续动作须有不同端点，微反应须有 baseline/onset/apex/offset 和 face visibility。
8. **失败处理**：缺视频、帧或音轨先停止并报告；只有用户明确同意才能降级纯转写。

### Step 3：分批理解（v4.3 改为「校准批 + 反馈闭环」）

**不要一上手连跑 10 份。** 分三段：

```
3a  校准批：覆盖三类样本——强烈踩雷、多菜正餐、市集扫街
      └─ 每类至少1份；先完成视觉台账与事件窗口复核，再跑双轨验收
      └─ 每份独立抽检2-3条视觉声明：静态观察、动作/反应、花字/不可读各覆盖；任一硬事实不符即停止放量
3b  确认校准生效：再跑 1 份，检查视觉覆盖和事实闸门
      └─ 新的 1 份 BLOCK 数应显著低于校准批的初始值；否则不要放量
3c  放量：其余每批 10-20 份，每批落盘后过闸门 + 更新 progress.md
      └─ 每批随机抽至少2期、每期2-3条；表情变化/停顿/复尝/看向同伴/退菜/蒙太奇/花字价格强制核验
```

> **为什么改**：v4.3 前的做法是首批 10 份连跑。实测这 10 份的问题**高度聚集
> 在最先跑的几份**——0003 单份 26 条（10 条是标签括号，v3 的老写法一条没改）、
> 0001 单份 16 条（唯一仍用旧式 `A3 无反应自检` 占位的），而后 7 份平均只有 4.6 条。
>
> 关键证据是**同一次运行内部的分裂**：同一模型、同一批规则、同一次连续运行，
> 0006 写出 `['口感-酥脆','口感-干硬'] + {'口感-酥脆':'过度'}`（教科书级正确），
> 0003 写出 `['口感-软烂(九分烂)','味道-辣(微辣)'] + {}`（v3 老习惯，零采用）。
>
> **同一能力、同一规则、结果两极 ⇒ 病因是执行一致性，不是能力上限。**
> 而执行一致性靠"prompt 里再强调一遍"是提不上来的——v2 到 v3 已经证明过。
> 唯一有效的手段是把**反馈闭环放进生成过程**：让它看见闸门对自己前两份的判决，
> 而不是等 10 份跑完再回头修。闸门报告是机械、具体、带行号的，
> 比任何抽象强调都好使。

每条严格分阶段调用，不得合并成一个“请深度理解视频”的自由任务：

```text
Phase 0  prepare_visual_assets.py → run-manifests/5.3-flash/{编号}.json + 三尺度资产
Phase 1  2fps/shot keyframes + ASR → shot-ledgers/5.3-flash/{编号}.json
Phase 2  shot ledger → visual-ledgers/5.3-flash/{编号}.json（判断相关空间事实）
Phase 3  8fps/25fps窗口 + ASR → reaction-windows/5.3-flash/{编号}.json
Phase 4  连续视频/音轨 + shot ledger → sound-edit-ledgers/5.3-flash/{编号}.json
Phase 5  全部账本 + ASR + schema → data/5.3-flash/{编号}.json + assembly/5.3-flash/{编号}.json
Phase 6  render_understanding.py → understanding/5.3-flash/{编号}.md
```

每个 Phase 后运行 `scripts/check_stage.py {语料目录} --id {编号} --target {阶段} --variant 5.3-flash`。运行清单由 `scripts/check_run_manifest.py {语料目录} --id {编号} --variant 5.3-flash` 复核。`processing_status` 固定写 `完成待修订`，不输出 `quality_gate`。任一阶段输出自由文章、缺 JSON、引用未输入资产或声称未提供的视觉模式，均视为失败并停止后续阶段。

> **`processing_status` 与 `quality_gate` 不属于理解调用（v4.3）。**
> v4 实测 10 份里 6 份手填了 `quality_gate`，0003 声明 `blocking_issues: []`
> 而实测 26 条 BLOCK；9 份自称 `完整` 而全部有 BLOCK。
> 根因是指令自相矛盾：字段列为必填、给了示例，同时叮嘱"不要手填"。
> v4.3 把它们从输出契约里删掉——**让违反在结构上无法发生，而不是靠自律**。
> 闸门发现残留的自我声明会报 `GATE_SELF_REPORTED`。

> ⚠️ **每个需要联合判断的阶段，视频/帧、转写与上游账本必须在同一次理解调用中提供**。拆成“先定稿转写、再补画面”会丧失两项能力：画面纠正 ASR 错误、话语与画面的对应关系（“他说这句时正盯着后厨”）。本 Skill 不直接调用供应商 API；执行环境负责 5.3-Flash 推理，run manifest 必须如实记录实际模型族与实际提供的资产，不得用模型名称代替输入证明。

**失败与降级处理（降级必须经用户确认）**：

| 失败类型 | 处理 |
|---------|------|
| 调用超时 / 报错 / 输出不符合 schema | 自动重试 2–3 次；重试时必须继续携带帧资产 |
| 帧缺失 / 抽帧失败 / 多模态画面不可读 | 先说明编号、已尝试步骤、失败原因及对 A1/A2/C 区的影响，**通过询问取得用户明确同意后**，才可降级纯转写 |
| 用户明确同意降级 | 生成 `processing_status: "降级-纯转写"`，在 MD 开头和 JSON 中说明降级原因、缺失帧资产和受影响字段；不得把推断伪装为画面事实 |
| 用户未同意或未回复 | **停止该条产出**，标记为 `待确认`；不得默认降级、不得写入完整结果 |
| 视频文件损坏 / 时长与转写严重不符 | 标 `失败`，记入 progress.md，向用户报告问题并询问下一步处理方式 |
| 粗筛漏判的非探店内容 | 标 `无关`，不重试 |
| **闸门报 BLOCK** | 标 `完成待修订`，按检查码定点修订该字段后重跑 `--id`。**不要重跑整条理解**，也不要为了让状态好看而改状态不改内容 |

### 版本参数（全链路一致）

本 Skill 默认 `--variant 5.3-flash`。同一轮的生成、审计、校验、回写和合并必须使用同一 variant；旧根目录 0011–0030 仅在显式传 `--variant root` 时读取。脚本不跨版本 fallback，找不到文件即报错，避免串用其他模型产物。

### Step 3.5：丰富性审计 + 安全闸门（双轨必经）

先检查有没有**少理解、少记录**，再检查写出的内容是否合规。顺序不能反：若先追求零 BLOCK，生成者容易通过少写来规避风险。

```bash
# 0. 丰富性审计自检与单批诊断（只读、不阻塞、不改文件）
python3 scripts/audit_richness.py --selftest
python3 scripts/audit_richness.py {语料目录} --variant 5.3-flash
python3 scripts/audit_richness.py {语料目录} --variant 5.3-flash --json

# 发现 RICH_*：回原视频补 A9-A15/B3-B7 与对应 json；不得靠凑数，也不得删内容
# 对照 references/richness-rubric.md 和 0011/0014/0017/0019/0028/0030 金标

# 1. 再自检安全闸门自己（v4 新增，第一次用或改过规则后必跑）
python3 scripts/validate_corpus.py --selftest

# 1. 全量校验
python3 scripts/validate_corpus.py {语料目录} --variant 5.3-flash

# 2. 机械回修（零语义判断的那批）——先 dry-run 看清再落盘
python3 scripts/validate_corpus.py {语料目录} --variant 5.3-flash --fix-safe --dry-run
python3 scripts/validate_corpus.py {语料目录} --variant 5.3-flash --fix-safe

# 3. 单条校验（定点修订时用，快）
python3 scripts/validate_corpus.py {语料目录} --variant 5.3-flash --id 0007

# 4. 机器可读输出
python3 scripts/validate_corpus.py {语料目录} --variant 5.3-flash --json

# 5. 校验通过后回写 quality_gate 字段
python3 scripts/validate_corpus.py {语料目录} --variant 5.3-flash --write-gate
python3 scripts/validate_corpus.py {语料目录} --variant 5.3-flash --write-gate --date 2026-08-14
# 已由同版本 validator 签发（validator_version 匹配且 validated_at 非空）的 gate，
# 后续普通只读复核会被识别为合法，不会再误报 GATE_SELF_REPORTED。
```

退出码：`0` = 无 BLOCK；`1` = 有 BLOCK；`2` = 用法错误 / 自检基准不干净。

> ⚠️ **Step 0 不可省。** 闸门未自检就信它的结论，等于信一份没人核对过的
> 自检清单——正是 v2 的错误，只是换了主体。v3 实测有 1 条规则从未运行过。

**`--fix-safe` 只修这三类**（改动零语义判断）：

| 类型 | 例 |
|------|-----|
| 标签括号 → `tag_qualifier` | `口感-绵软(负面)` → `口感-绵软` + `{"口感-绵软": "负面"}`。非标准限定词保留为 `原括注：{原文}`，不丢信息 |
| 标签近义归一 | `口感-脆` → `口感-脆嫩`、`分量-偏少` → `分量-小气`、`香-辣椒香` → `香气-椒香`（只归**无歧义**的，需要判断原意的不动）|
| 组合枚举 → 规范值 | `visual+audio` / `audio+visual` → `both` |
| `cuisine` 取菜系级 | `湖北菜·家常馆` → `湖北菜`、`小吃/综合` → `小吃综合` |
| **剥掉自我声明**（v4.3）| 删除产出自带的 `quality_gate`；`processing_status: 完整` → `完成待修订` |
| v4 新字段补 null | 缺 `tag_qualifier` 补 `{}`、缺 `scope_quote` 补 `null`；`sample_count` → `video_count`+`within_video_sample_count` |

**它绝不碰** `TECH_TERM_NOT_SPOKEN` / `QUOTE_NOT_IN_TRANSCRIPT` /
`SCOPE_UPGRADE_NO_QUOTE` / `VISUAL_HAS_INFERENCE`——这些都要回答"博主到底说了什么"，
脚本替你猜就是又加一层折损。**能自动修的都不是事实错误，事实错误都不能自动修。**

**闸门检查的问题类别**（全部机械可判，不依赖模型判断）：

| 类别 | 代表检查码 | 拦的是什么 |
|------|-----------|-----------|
| 枚举合法性 | `ENUM_INVALID` | 自创 `D7出餐速度` / `city_level` 这类不存在的取值 |
| 原话可溯源 | `QUOTE_NOT_IN_TRANSCRIPT` | quote 不是逐字的（拿转写稿逐片段比对） |
| 工艺归因 | `TECH_TERM_NOT_SPOKEN` | 博主没说过"保水剂"，却署名给了博主 |
| 认知分层 | `LAYER_ATTR_ON_EXPLICIT` | 一条记录里混着感受与推测 |
| 范围升级 | `SCOPE_UPGRADE_NO_QUOTE` / `SCOPE_QUOTE_NOT_IN_TRANSCRIPT` / `D10_SCOPE_NOT_THIS_SERVING` | scope 升级但拿不出原话依据；原话是编的；D10 的 scope 被升级（它只能是 `this_serving`）|
| 候选规律 | `B1_COUNT_MISMATCH` / `B1_FORBIDDEN_PHRASE` / `B1_VIDEO_COUNT` | md 与 json 条数不一致（实测抓出 30 条只写在 md 的）；出现"标尺""必点"；`video_count` 不为 1 |
| 标签规范 | `TAG_PAREN` / `TAG_NOT_IN_DICT` / `TAG_NO_PREFIX` / `TAG_QUALIFIER_*` | 括号变体、词典外、缺前缀、限定词值域外或悬空 |
| 画面分层 | `VISUAL_HAS_INFERENCE` | `[画面]` 行里混着推断词 |
| 视觉跨层证据 | `VISUAL_STATUS_NO_MD_BASIS` / `FRAME_SEQ_NO_MD_OBSERVATION` | JSON 声称已看画面但 A1 无同源客观观察；frame_sequence 缺两个真实帧端点或无对应观察 |
| 模板一致 | `MD_H3_DIVERGED` | 同一编号小节挂了不同内容（白名单按 `content_type` 分流） |
| 时长约束 | `DUR_OVERFLOW` / `TS_DUPLICATE` / `TS_OVERLAP` | 各菜加总超过 ffprobe 实测时长；区间完全相同 / 部分重叠 |
| 帧资产 | `FRAME_RATE_LOW` / `FRAME_REF_BROKEN` | 帧数远少于秒数却声称已看画面；引用了不存在的帧 |
| 价格 | `DERIVED_NO_BASIS` / `PRICE_INCONSISTENT_FLAG` | 人数人均都是算的却没标依据 |
| 反应三分法 | `REACT_ALL_EXPLICIT` | 整表全是"明确评论"，说明漏记了"无反应" |
| 状态自洽 | `STATUS_OVERCLAIM` / `GATE_SELF_REPORTED` | 有 BLOCK 却标了 `完整`；产出自带 `quality_gate`（自我声明合规，v4 实测 6 份，其中一份声明零 BLOCK 而实测 26 条）|

**处理规则**：

1. **先过丰富性审计。** 有 `RICH_*` 提示时回原视频补理解；零 BLOCK 不能覆盖低召回失败。
2. **有任何 BLOCK ⇒ `processing_status` 写 `完成待修订`**，不得写 `完整`，但原始丰富产物保留不覆盖。
3. 先跑 `--fix-safe` 清掉机械项，再处理剩下的——否则语义问题会淹在括号噪音里。
4. 按检查码**定点修订**：优先改归属、置信度、层级或移入 `open_interpretations`；不得直接删除有价值信息来消除 BLOCK。
5. 修订后同时重跑 `audit_richness.py --id {编号}` 与 `validate_corpus.py --id {编号}`，确认安全修订没有造成丰富性回归。
6. 全量无 BLOCK 后跑 `--write-gate`，把 `quality_gate` 对象落进 json
   （含 `validated_at`，合并准入要读它）。
7. **WARN 不阻塞**，但要在 `progress.md` 记一笔。最常见的三个：
   `QUOTE_COMPOSITE`（多段拼接引用，通常无需处理）、
   `QUOTE_ELIDED`（漏标省略号，补 `…` 即可）、
   `TS_OVERLAP`（少量重叠，归入主要讨论对象）。

> 闸门默认读的是 `data/5.3-flash/*.json` + `understanding/5.3-flash/*.md` + `*_audio_transcript.md` +
> `frames_*/` + mp4 实测时长。**它不调用模型**，因此结论稳定可复现。

### Step 4：合并整理

见 `references/merge-guide.md`。纯脚本，不占多模态成本，**分组维度可随时重切**。

⚠️ **Step 4 只消费 `processing_status: 完整` 的记录。**
`完成待修订` 的记录留在 `data/5.3-flash/` 里但不进 `corpus-index.5.3-flash.json`——
带着已知缺陷合并，等于把缺陷永久固化进下游画像。

### Step 5：交付检查

确认以下产物齐备：

1. `understanding/5.3-flash/` × N：逐期完整理解文件；
2. `data/5.3-flash/` × N：逐期结构化数据；
3. `corpus-index.5.3-flash.json`：仅包含通过安全闸门的记录；
4. `grouped/5.3-flash/`：组数与实际品类数相符，保留完整理解，不做语义压缩；
5. `progress.md`：完整登记已完成、降级、失败和待确认条目；
6. `validation-report.5.3-flash.json` 与 `richness-report.5.3-flash.json`：保存最终一轮 `--json` 验收结果。

完成数量、准入状态、分组结果和异常台账核对后，本 skill 流程结束。**不在此处启动任何主蒸馏流程，也不定义多份理解文件的后续蒸馏方式。**

---

## progress.md 台账格式

手工调用意味着**批次调度不能靠脚本兜底**，须由人与 Agent 共同维护台账：

```markdown
# 理解进度

- 语料总数：{N}    粗筛后待处理：{N}（探店 {N} / 表态 {N}）    排除：{N}
- 已完成：{N}      降级：{N}      失败：{N}      剩余：{N}
- 最后更新：{日期}

## 批次记录

| 批次 | 编号范围 | 数量 | 状态 | 完成时间 | 备注 |
|------|---------|------|------|---------|------|
| 01 | 0001-0010 | 10 | ✅ | | 首批，schema 校验通过 |
| 02 | 0011-0030 | 20 | 🔄 进行中 | | |

## 待处理异常

| 编号 | 问题 | 处理方式 | 状态 |
|------|------|---------|------|
| {编号} | 帧抽取失败 / 画面不可读 | 已向用户说明并等待是否同意降级 | 待确认 |
| {编号} | 视频文件损坏 | 已向用户报告并等待处理决定 | 待确认 |
| {编号} | 粗筛判为存疑 | 人工确认后排除 | 待确认 |
```

**断点续跑判据**：新探店产物仅当以下条件全部成立，才算该条已完成——

1. `understanding/5.3-flash/{编号}.md` 与 `data/5.3-flash/{编号}.json` 均存在；
2. `frames_{编号}/` 中至少一张可读图片存在；
3. `processing_status` 为 `完整`；
4. **`quality_gate.blocking_issues` 为空数组**，且 `validated_at` 不为空；
5. A1 每段有视觉覆盖状态，关键判断事件有连续视频/密帧覆盖或明确标 `audio_only`；
6. 9 个丰富性 JSON 字段与 `visual_coverage` 均存在，episode 引用完整；
7. `audit_richness.py` 的视觉覆盖/对齐提示已复核，不以删减信息消除提示。

`完成待修订`、`待确认`、`失败` 与经用户同意的 `降级-纯转写` 必须单独保留在台账中，
恢复时不得误判为完整。

### 旧版 5.3-Flash 产物迁移边界

只有 `data/5.3-flash/` 与 `understanding/5.3-flash/`、但缺少同 variant 的 run manifest、shot/visual/reaction/sound-edit ledger 和 assembly 的历史产物，不得补写或伪造账本来满足新契约。它们可以保留作历史理解稿；若要升级为完整可审计交付，必须从原视频、ASR 与真实帧重新执行 Phase 0–6。

⚠️ 第 4 条是 v3 新增的。加它的原因：前三条只能证明"文件生成了"，
不能证明"生成的内容对"。v2 的十份产出前三条全部满足，
而闸门一跑，十份全有 BLOCK。**"跑完了"和"跑对了"是两件事，台账要能区分。**

台账的异常表里增加一类：

| 编号 | 问题 | 处理方式 | 状态 |
|------|------|---------|------|
| {编号} | 闸门 BLOCK：`TECH_TERM_NOT_SPOKEN` ×7 | 已按码定点修订 blogger_attribution，待重跑 | 完成待修订 |

---

## 行业适配

本 skill 的**流程通用**，但**字段定义按行业不同**。

结构化字段对应《蒸馏方法论》第11章**参数10「结构化字段定义」**，须读取对应行业的配置卡片。`references/output-schema.md` 中给出的是**到店餐饮**的字段定义（默认值）。

换行业时需替换的部分：
- 结构化字段的 A/B/C 三档维度清单
- 逐条目数组的字段（餐饮是"逐道菜"，美发是"逐个作品"，景点是"逐个项目"）
- 分组维度（餐饮按菜系，美发按风格，景点按类型）

**不需要替换**的部分：分层结构、四条核心约束、失败分级、台账格式、ASR 纠错规则。

---

## 验收清单（每批落盘后逐项核对）

下列各项都是实跑中出现过的错误，按出错概率从高到低排列。

> ⚠️ **这份清单已有大半被 Step 3.5 的闸门机械化了。**
> 标了检查码的项目**不要靠人眼核对**——跑 `validate_corpus.py` 更快更准。
> 清单的剩余价值在两处：①没标检查码的项目（需要语义判断，脚本判不了）；
> ②理解生成时提前避坑，减少返工轮数。
>
> **不要把"我核对过了"当成验收通过。** v2 十份产出的自检全勾，
> 闸门一跑十份全 BLOCK——人眼核对的实测有效率接近于零。

**★ 事实边界（错了下游看不出来，最优先）**

| 检查 | 典型错误 |
|------|---------|
| 每道菜、每个事件、每条候选规律都有 `source_type` ⟨`FIELD_MISSING`⟩ | 缺失 |
| 博主的推测没被写成确定因果 ⟨`CAUSAL_IN_HYPOTHESIS`⟩ | 博主说"碱发的效果问题，海参会有异味"（推测）→ 写成"因碱发过度产生异味" |
| 模型自己的假设没混进博主观点 ⟨`TECH_TERM_NOT_SPOKEN`/`LAYER_ATTR_ON_EXPLICIT`⟩ | 博主只说"这个脆不对"→ 产出补了"疑似碱发/保水剂"，读起来像博主说的 |
| 每条评价都有 `scope`，默认 `this_serving`，升级填了**可溯源的** `scope_quote` ⟨`SCOPE_UPGRADE_NO_QUOTE`/`SCOPE_QUOTE_NOT_IN_TRANSCRIPT`⟩ | "蟹粉豆腐完全无咸淡口"——本店本次的问题写成了这道菜式的通病；或编一句"他们家每次都这样"给升级背书（v4 起拿转写稿核对） |
| `d10_ordering.scope` 是 `this_serving` ⟨`D10_SCOPE_NOT_THIS_SERVING`⟩ | 填成 `dish_type` 或自由文本"本帮菜普遍如此"——D10 记的就是本期这一顿 |
| `evidence_source` 已填，`dimension_events` 尤其不能漏 | `微反应`/`无反应` 只可能来自画面，不标来源就无法区分"他说的"与"模型看出来的" |

**★ 候选规律**

| 检查 | 典型错误 |
|------|---------|
| B1 无"XX=YY""XX是YY的标尺""优先点XX"式表述 ⟨`B1_FORBIDDEN_PHRASE`⟩ | "响油鳝糊=淮扬菜馆的定海神针"（1店1菜）、"焯水浇辣椒油=不合格川菜"（1店3菜） |
| 每条都有 `video_count=1` / `confidence=low` / `not_stable_rule` / `next_verify` ⟨`B1_VIDEO_COUNT`/`B1_CONFIDENCE`/`B1_NO_DISCLAIMER`/`B1_NO_NEXT_VERIFY`⟩ | 缺字段；或把"本期 4 道菜"当 4 个样本去升 confidence |
| **md 的 B1 每条都同步进了 json 的 `candidate_patterns`** ⟨`B1_COUNT_MISMATCH`⟩ | 只写 md，Phase 2 读不到，免责声明白写。v4 起逐条比对数量（两种 md 写法都认），实测 10 期抓出 **30 条只写在 md** |
| 候选规律的 `source_type` 已填且非 `model_inference` ⟨`ENUM_NULL`⟩ | 缺失；或把模型自己猜的"规律"混进 B1 |
| B2 中从单次体验推出的态度标了"待跨期验证" | "对米其林的务实态度"当成稳定价值观 |
| **`d10_ordering` 未绕过上述约束** ⟨`D10_FORBIDDEN_PHRASE`/`D10_NO_SAMPLE_NOTE`⟩ | A 档里唯一在做归纳的字段。`strategy_notes` 写成"便宜家常菜反而稳，贵菜踩雷"（4道菜推通用规律），等于把 B1 赶走的东西从必填字段放了进来 |

**★ 字段完整性（新增字段最容易整批漏填）**

| 检查 | 典型错误 |
|------|---------|
| `dishes` 每项 **18 个字段**齐全 ⟨`FIELD_MISSING`/`FIELD_MISSING_V3`⟩ | 易漏：`object_level` / `intensity` / `standard_tags` / `blogger_attribution` / `evidence_source` / `confidence` / `quote` / `timestamp` |
| **`quote` 逐字原话，未被重述** ⟨`QUOTE_NOT_IN_TRANSCRIPT`⟩ | json 里只有归纳没有原话 → 下游提表达DNA 必须回查全部 md，`corpus-index.json` 在该用途上废掉 |
| `timestamp` 已填 | 有原话无时间戳，回查定位不了 |
| `confidence` 已填且与 `source_type` 分清 | 两者混填。`source_type`＝谁说的；`confidence`＝这条记录本身靠不靠得住（ASR 存疑段落提取的评价应降为 medium/low） |
| `standard_tags` 与 `reason` 双写，标签无括号、带前缀、在词典内 ⟨`TAG_PAREN`/`TAG_NO_PREFIX`/`TAG_NOT_IN_DICT`⟩ | 只填其一；或为套进现有标签而扭曲原意（应填 `其他-{描述}`） |

**★ 数据质量**

| 检查 | 典型错误 |
|------|---------|
| 各菜时长 + 开场结尾 ≤ **ffprobe 实测**总时长，区间不重叠 ⟨`DUR_OVERFLOW`/`TS_DUPLICATE`/`TS_OVERLAP`⟩ | 合计 294 秒 > 视频 282 秒（说明是估的，须用转写时间轴重算）；区间部分重叠（v4 起也拦，实测新发现 8 处） |
| `price_check` 对象已填（对应 A5），人数/人均标了 basis ⟨`DERIVED_NO_BASIS`⟩ | 只在 md 里做了校验，json 漏填，汇总表读不到 |
| A5 价格交叉校验已做，不一致时标 `price_mismatch` ⟨`PRICE_INCONSISTENT_FLAG`⟩ | 语音 568 / 花字 338 / 菜价加总 519，产出直接采用 338 未提差异 |
| ASR 关键信息（价格/菜名/店名）不得只标"存疑保留" ⟨`ASR_ALL_SUSPECT`/`ASR_KEY_NO_GUESS`⟩ | 某期 16 处 ASR 标注**全部**是"存疑保留"，等于没做 |
| 纠错依据引用的帧真实存在 ⟨`FRAME_REF_BROKEN`⟩ | 写成 `frame_005 可见`，但链路根本没给帧文件——是幻觉 |
| 一处错误一行，"纠正后"唯一确定 | `1 8 9 → 189 / 298 / 300` 三个价格塞一行且值不唯一 |

**★ 格式**

| 检查 | 典型错误 |
|------|---------|
| 三个二级标题逐字照抄，三级小节用 `enums.json` 白名单里的名字（新探店模板 A1-A15/B1-B7；表态模板 A1/B1-B7）⟨`MD_H2_MISSING`/`MD_H3_DIVERGED`⟩ | 写成 `## C. ASR纠错清单`（漏空格），合并脚本会静默把 C 区并进 B 区；把"无反应自检"写成 `A3`（应为 `A7`）、"镜头时长分配"写成 `A4`（应为 `A8`）|
| 枚举值逐字取自 `enums.json` ⟨`ENUM_INVALID`⟩ | `dimension` 写成 `D9卫生/安全`；`evidence_source` 写成 `visual+audio`（两者皆有填 `both`）；`object_level` 写成 `整道菜/配菜`。⚠️ v4 起 `sentiment` 是六级、含 `有保留`，不再是错误 |
| A1 中 `[画面]`/`[花字]`/`[推断]` 分开成独立行 ⟨`VISUAL_HAS_INFERENCE`⟩ | "表情明显不适——像吃到极不舒服的东西"，看到的和想到的糊在一起 |
| JSON 的 reviewed 声明在重叠 A1 段有同源视觉留痕 ⟨`VISUAL_STATUS_NO_MD_BASIS`⟩ | JSON 声称全片 `reviewed_frames`，Markdown 却没有任何 `[画面]`；无信号须写规范留痕，不能沉默或编造 |
| `frame_sequence` 至少两个真实帧端点并与 A1 观察共享 basis ⟨`FRAME_SEQ_NO_MD_OBSERVATION`⟩ | 只列一张帧却证明停顿/复尝，或 JSON 列的帧与 Markdown 观察完全无关 |
| A2 表不应清一色 `明确评论` ⟨`REACT_ALL_EXPLICIT`⟩ | 漏了 `微反应` / `无反应`——后者是权重的负向证据 |
| 原话逐字保留未被重述 | 改写成书面语会丢掉表达DNA的词汇指纹 |
| 六环节逐项完成机会扫描；无信号写“本期未观察到”及扫描范围，不硬编也不留白 | 为填满而编造，或用空白掩盖漏扫 |
| `processing_status` 与闸门结果自洽 ⟨`STATUS_OVERCLAIM`⟩ | 有 BLOCK 却标 `完整` |

### 两项刻意保留（曾有评测建议削减，未采纳）

- **镜头时长分配**——建议方理由是"不直接支持评价结论"。单期视角下成立，但该字段价值本就不在单期：它是「行为 > 言论」在视频语料上的唯一客观载体，跨期时长分布能揭示他实际在什么上花时间，比口头声明的"我最看重食材"更可靠。**保留必填。**
- **表情解读**——表情是 D8/D9/D11 判定 `微反应` 的唯一依据，砍掉则"明确评论/微反应/无反应"三分法坍塌。**保留，但要求观察与解读分写**（`[画面]` vs `[推断]`）。环境描写可精简。

---

## 已知局限（须写入下游的诚实边界）

1. **覆盖面受专家选题限制**——他没拍过的品类/价位/城市，语料里就没有。样本量看似很大，但地域/品类分布往往极不均衡（实测某专家北京占 34%，其余城市多数仅 1-3 期），跨城对比不成立——须在诚实边界中按实际分布说明。
2. **ASR 折损不可完全消除**——画面能纠正一部分（有实物出镜的术语、有花字的数字），但纯口头表述的专业词汇仍可能错且无从校验。
3. **前置提炼折损不可逆**——本环节丢掉的信息下游看不见。这是分层输出与"不做语义压缩"约束存在的原因，但约束只能降低风险不能消除。
4. **味觉仍不可传递**——视频改善的是"记录他的判断过程"，不是"复现他的感官"。不要因为拿到高质量视频语料就上调身体性维度的蒸馏预期。
