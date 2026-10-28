# 专业视听编码框架（Flash.2）

## 目标

比 0011–0030 更完整地保留视频独有信息，同时比旧产物更可核验。完整技术编码留在 ledger；最终 Markdown 只投影与判断、表达、情境有关的条目。

所有输出遵循三层：

1. **Observable**：可回看验证的事实。
2. **Relation**：事实与 episode、口播、前后镜头或声音的关系。
3. **Interpretation**：竞争解释、支持与限制；不得由术语直接推出情绪、人格或品味。

## 空间流

### 镜头与画面内组织

逐 shot 记录景别、角度、构图、前中后景、遮挡、主体位置和空间布局。景别变化只描述信息可见度变化；“俯拍显得弱小”“暖光代表温馨”等属于解释，不是事实。

### 焦点、光线、色彩

记录景深、焦点主体/转移，主光方向、软硬、对比、色温、曝光和反光。环境氛围拆成可见/可听事实（亮度、色温、人数、空间、噪声）和单独解释。

### 食物形态

按颜色、形状、表面、内部结构、动态状态和前后变化记录。视觉不得写香、甜、软、脆等不可见感官结论；可以写油亮、焦边、断面颗粒、肥瘦分层、按压形变、蒸汽、气泡、滴落、拉丝、碎裂或回弹。

## 时间流

### 动作事件

每个动作包含 actor、object/tool、onset、关键步骤/apex、offset、方向、速度、幅度、次数、结果状态、可见性和证据资产。区分主体运动与摄影机运动。单帧不构成动作证据。

### 微反应（FACS-lite）

不输出情绪标签，先记录面部可见性和刺激前基线，再记录眉、眼睑、视线、鼻、嘴角、嘴唇、下颌、头部及身体动作；标 onset–apex–offset 与 A/B/C 强度。微反应窗口最低 15fps，目标 25fps。脸不可见不等于无反应；必须使用 visibility code。

“可能不喜欢”只能作为竞争解释，并列支持（如停吃、退菜、明确负评）和限制（如正在咀嚼、被辣、切镜）。

### 摄影机运动与剪辑

逐 shot 记录静止、摇、俯仰、推拉/变焦、跟移、横移、手持、升降和重构图。剪辑记录 shot ID、边界、时长和转场；关系分空间、时间、节奏、图形以及比较/揭示/回扣/省略。必须有两个 shot ID 才能声称镜头关系。

## 声音流

记录对白、旁白、环境、餐具、烹饪、咀嚼、音乐、音效与静音；标画内/画外、同步/异步、声桥、补充、反差、提前、延迟、遮蔽、回扣。脆响、滋啦、吞咽、咀嚼中断须有直接音频时间窗，字幕不能代替声音。

## 三尺度采样

- 全片：2fps + shot boundary keyframes；支持静态形态、环境、构图、光线、花字。
- 事件：8fps 或连续视频，事件前2–3秒至后3–5秒，单窗≤20秒；支持动作、镜头运动、剪辑与声画。
- 微反应：面部清晰的强判断窗口2–5秒，目标25fps、最低15fps；支持 onset–apex–offset。

## 解释边界

- 构图、光线、景别、音乐和表情都不能单独证明专家态度。
- 摄影选择/后期包装不署名给专家。
- raw detector 只作定位，不进入正文丰富度。
- OCR 与口播重复不算视频独有事实。
- 无连续证据时写 `not_observable_from_sampled_frames`。

## 参考来源

- Pitzer College film terms: https://pzacad.pitzer.edu/~mma/teaching/MS50/MS50_keyterms.html
- Pressbooks cinematography: https://icc.pressbooks.pub/iccfilm110/chapter/chapter-5-cinematography
- Oklahoma State editing: https://open.library.okstate.edu/introfilmtv/part/editing
- FACS systematic review: https://pmc.ncbi.nlm.nih.gov/articles/PMC7264164
- Classifying Facial Actions: https://pmc.ncbi.nlm.nih.gov/articles/PMC3008166
- TemporalBench: https://arxiv.org/html/2410.10818v1
- Food appearance attributes: https://iastate.pressbooks.pub/foodpreparationlab/chapter/1-3
- Sensory lexicons: https://pmc.ncbi.nlm.nih.gov/articles/PMC6352027
