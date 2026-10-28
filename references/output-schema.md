# 输出 Schema（到店餐饮，5.3-Flash 分支）

> 对应《蒸馏方法论》第11章**参数10「结构化字段定义」**。
>
> 5.3-Flash 分支的生成顺序固定为：run manifest → visual ledger → reaction windows → 本 JSON → 标准 Markdown。只生成自由 Markdown 或缺少前置证据产物均不构成合格交付。视觉字段只能引用前置证据产物实际登记的资产；模型名不能充当已读取画面的证明。
> 本文件是**到店餐饮**的字段定义。换行业须替换 A/B/C 三档维度清单与逐条目数组。

---

## 三条全局纪律（v3 新增，违反即 BLOCK）

前两版的教训是：**schema 写得够全，但模型执行时仍会违反，且违反了没人发现。**
实测 v2 十份产出中，自检清单全部打勾，却仍有枚举越界 46 处、
工艺归因署名博主 24 处、标签括号分裂 23 种。因此 v3 的重点不是加字段，
而是让违反**结构上难以发生、发生后能被机械发现**。

### 纪律一：枚举与标签取自单一事实源

- 全部枚举值以 `references/enums.json` 为准，**本文件的取值表是它的可读镜像**。
- `standard_tags` 取自 `references/tag-dictionary.json` 的闭词典。
- 两者冲突时以 json 文件为准（校验器读的是 json）。

### 纪律二：一条记录只能有一个认知层级

一条评价**不得同时装**博主感受、博主归因、模型补充。实测错例（0010 本味牛肉）：
一条 dishes 记录里既有"吃不出牛肉味"（博主明确）、又有"放石粉"（博主推测）、
还有模型补的"嫩肉粉/保水剂"——归属必然串位。

正确做法是**拆成原子条目**，各自一个 `source_type`：

```json
[
  { "object": "本味牛肉", "claim": "口感滑嫩且弹性异常，吃不出牛肉味",
    "source_type": "blogger_explicit", "scope": "this_serving",
    "quote": "滑滑嫩嫩还很有弹性……吃不出牛肉味儿" },
  { "object": "本味牛肉", "claim": "异常口感可能与石粉有关",
    "source_type": "blogger_hypothesis", "scope": "this_serving",
    "quote": "它就是放的那个石粉呀" }
]
```

模型若要补"保水剂/碱发"，须写入 `open_interpretations`：保留可观察事实、至少一种竞争解释、各自支持与限制，并默认低置信度。不得进入 `candidate_patterns`、价值观与跨期统计；但也不得为了避错直接删除这条可能有用的解释。

### 纪律三：产出后必过验证闸门

```bash
python3 scripts/validate_corpus.py {语料目录}
```

**有任何 BLOCK 时，`processing_status` 一律写 `完成待修订`，不得写 `完整`。**
`完整` 的含义从"跑完了"改为"跑完且通过硬校验"。

---

## 分档原则

字段不平均用力，按《行业蒸馏折损分析》3.1.1 的**三级阶梯**分档：

| 档 | 维度 | 记录方式 | 依据 |
|---|------|---------|------|
| **A 必填** | D1味道 D2食材 D3烹饪 D4出品稳定 D5场景适配 D7性价比 D10点菜策略 | 每期必填，无信息填 null | D5/D7/D10 折损低且 L1-L2，是Skill主战场；D1-D4 虽折损高，但**判断过程本身**是表达素材（矩阵中 D2/D3 方法论★★★） |
| **B 事件驱动** | D6环境 D8服务 D9卫生 D11呈现 D12私密社交 | 有事件/有反应才记 | 视觉主导阶梯，折损低-中，但非每期触发 |
| **C 顺带** | D13–D22 | 仅明确提及时记 | 理性/数据阶梯，Agent自身能力已强（多数L1），专家增量小 |

**D22 餐后体感的例外**：它属身体性感官阶梯（折损高），本该进 A 档，但因专家极少提及，设为必填会产生大量空值，故归 C 档、提到即记。

---

## Flash.2 专业账本引用摘要

完整电影学与行为编码保存在独立 ledger，最终 JSON 只保存可追溯摘要，避免把技术字段塞进每道菜：

```json
{
  "shot_coverage_summary": {"shot_count": 24, "covered_duration_sec": 180, "ledger_refs": ["S1", "S2"]},
  "food_visual_evidence": [{"object": "红烧肉", "observable": "断面可见肥瘦分层", "ledger_refs": ["S7:F1"]}],
  "action_evidence": [{"episode_refs": ["J1"], "observable": "夹起→入口→放下筷子", "ledger_refs": ["W1:A1"]}],
  "microreaction_evidence": [{"episode_refs": ["J1"], "observable": "嘴唇收紧、头部后撤", "ledger_refs": ["W1:M1"], "interpretation": "可能不适", "limits": "正在咀嚼"}],
  "sound_edit_evidence": [{"episode_refs": ["J1"], "observable": "咀嚼声后出现2秒停顿，随后硬切总结", "ledger_refs": ["AU3", "E4"]}],
  "audiovisual_claim_refs": [{"claim_id": "C1", "episode_refs": ["J1"], "ledger_refs": ["S7:F1", "W1:A1", "AU3"]}]
}
```

每条高层 claim 必须引用 ledger event ID；同一 evidence 被 A9–A15/B3–B7 重复引用时不得重复计权。

## json 完整结构

```json
{
  "id": "{编号}",
  "content_type": "探店",
  "_comment_status": "★ 生成时固定写 完成待修订。`完整` 由 --write-gate 在闸门零 BLOCK 时改写，不是自我评价。",
  "processing_status": "完成待修订",
  "video_duration_sec": 282,

  "_meta": {
    "city": "上海",
    "shop_name": "本帮馆",
    "cuisine": "本帮菜",
    "shop_tier": "正餐",
    "party_size": 3,
    "price_total": 189,
    "price_per_person": 63,
    "price_tier": "150-400",
    "party_size_basis": "博主明说",
    "price_per_person_basis": "总价÷人数"
  },

  "_comment_quality_gate": "★ 生成时**不要输出** quality_gate 对象，一个键都不要写。它由 scripts/validate_corpus.py --write-gate 事后写入。结构定义见本文档「quality_gate 闸门结果」一节——那节是给人读的，不是给生成者抄的。",

  "_comment_A": "A档·7个必填维度，无信息填 null",

  "d1_flavor": {
    "overall": "有保留",
    "notes": "前两道好评，后两道原料出问题",
    "keywords": ["微甜", "酒香", "金属味"]
  },
  "_comment_d2": "⚠️ evidence 只写可观察到的事实，reasoning 里的归因必须标明是谁的推测。v3 这里写的是『大乌参碱发过度产生异味』+『碱发能让海参涨发变大，但会留异味』——把博主的推测写成了确定因果，还把行业常识包装成他的判断。示例本身就在教错的写法。",
  "d2_ingredient": {
    "assessment": "负面",
    "evidence": "本次的大乌参入口有金属/电池样异味、舌根发麻；扣肉7片中3片纯肥",
    "reasoning": "博主推测异味可能与发制工艺有关（他的原话与归因见 dishes 中 source_type=blogger_hypothesis 的独立条目）；本字段不替他补全工艺名称"
  },
  "d3_cooking": {
    "assessment": "正面",
    "evidence": "烂糊肉丝勾芡到位；草头带酒香非清炒",
    "is_prepared_food": null
  },
  "d4_consistency": null,
  "d5_scene_fit": {
    "suitable_for": ["家常便饭", "两三人小聚"],
    "not_suitable_for": null,
    "evidence": "人均六十几，家常菜为主"
  },
  "d7_value": {
    "verdict": "偏贵",
    "quote": "人均大几十块钱儿，我觉得有点儿贵，但上海这个消费算普通价格",
    "price_vs_quality": "高开低走"
  },
  "d10_ordering": {
    "worth_ordering_this_time": ["老上海圈子", "烂糊肉丝"],
    "avoid_this_time": ["虾籽大乌参"],
    "strategy_notes": "本期他对便宜的家常菜评价高于两道贵菜（样本：4道菜，不足以成规律）",
    "scope": "this_serving"
  },

  "_comment_B": "B档·事件驱动，无则空数组/null",

  "dimension_events": [
    {
      "dimension": "D8服务",
      "event": "退菜",
      "description": "大乌参有异味，当场要求退掉",
      "his_reaction": "主动说了'不好意思'",
      "reaction_type": "明确评论",
      "intensity": "中",
      "source_type": "blogger_explicit",
      "scope": "this_serving",
      "evidence_source": "both",
      "quote": "这个东西就不能吃了",
      "timestamp": "01:32-02:20"
    }
  ],
  "environment": {
    "open_kitchen": null,
    "noise_level": null,
    "cleanliness_visible": null,
    "privacy_social": null,
    "presentation_note": null,
    "overall_impression": "菜单看着有食欲，整体是普通正餐馆"
  },

  "_comment_C": "C档·仅明确提及时填，否则 null",

  "aux_mentions": {
    "d13_location": null,
    "d14_queue": null,
    "d15_price_info": null,
    "d16_hours": null,
    "d17_reputation": "看点评来的",
    "d18_special_needs": null,
    "d19_payment": null,
    "d20_risk": null,
    "d21_seasonality": null,
    "d22_aftereffect": "吃的我现在嗓子眼还难受"
  },

  "price_check": {
    "total_from_audio": 189,
    "total_from_caption": 189,
    "sum_of_dishes": 337,
    "consistent": false,
    "mismatch_note": "price_mismatch：菜价加总337高于总价189，因大乌参298已退菜，扣除后吻合",
    "is_estimated": false
  },

  "dishes": [
    {
      "name": "虾籽大乌参",
      "object_level": "整道菜",
      "price": 298,
      "sentiment": "强烈负面",
      "intensity": "强",
      "reason": "入口有金属/电池样异味，舌头根发麻，不可食用",
      "standard_tags": ["异味-金属味", "口感-发麻"],
      "tag_qualifier": {"口感-发麻": "异常"},
      "blogger_attribution": null,
      "source_type": "blogger_explicit",
      "scope": "this_serving",
      "scope_quote": null,
      "evidence_source": "audio",
      "confidence": "high",
      "quote": "铜的东西你拿舌头舔一下，那个感觉有，你明白吗？感觉给电了一点，有点儿麻",
      "timestamp": "01:32-02:20",
      "shot_duration_sec": 95,
      "has_caption": true
    },
    {
      "_comment": "同一道菜的博主推测，按纪律二拆成独立条目——感受与归因不同层，不能挤在一条里",
      "name": "虾籽大乌参",
      "object_level": "技法",
      "price": null,
      "sentiment": "负面",
      "intensity": "中",
      "reason": "博主推测异味可能与碱发有关",
      "standard_tags": [],
      "tag_qualifier": {},
      "blogger_attribution": "碱发过度",
      "source_type": "blogger_hypothesis",
      "scope": "this_serving",
      "scope_quote": null,
      "evidence_source": "audio",
      "confidence": "medium",
      "quote": "这个我觉得是碱发发过了",
      "timestamp": "02:05-02:20",
      "shot_duration_sec": 0,
      "has_caption": false
    },
    {
      "name": "本帮烂糊肉丝",
      "object_level": "整道菜",
      "price": 39,
      "sentiment": "正面",
      "intensity": "强",
      "reason": "勾芡黏糊，白菜丝本身甜，很下饭",
      "standard_tags": ["口感-黏糯", "味道-甜", "功能-下饭"],
      "tag_qualifier": {},
      "blogger_attribution": null,
      "source_type": "blogger_explicit",
      "scope": "this_serving",
      "scope_quote": null,
      "evidence_source": "both",
      "confidence": "high",
      "quote": "白菜丝儿本身就甜，再滑溜溜地配点儿肉丝儿，很下饭",
      "timestamp": "00:54-01:32",
      "shot_duration_sec": 58,
      "has_caption": true
    }
  ],

  "_comment_values": "★ 探店类也要写 values_triggered（v4.6 新增）。它原先只在表态类 schema 里出现，而探店 prompt 的 B2『价值观与红线』没有任何 json 对应字段——于是 B2 只存在于 md，下游只读 json 就全丢了。这与 v3 时 B1 的失效方式完全相同（当时是 30 条候选规律静默消失）。本期无触发则写空数组。",
  "values_triggered": [
    {
      "content": "对原材料问题的零容忍",
      "context": "两道贵菜均因原料问题被否",
      "intensity": "强",
      "quote": "俩菜都是用料上的问题",
      "timestamp": "02:20-02:35",
      "value_type": "候选倾向",
      "source_type": "blogger_explicit",
      "evidence_source": "audio",
      "confidence": "high"
    }
  ],

  "visual_coverage": [
    {
      "timestamp": "01:20-02:37",
      "visual_status": "reviewed_video",
      "visual_basis": ["连续观看 01:20-02:37", "f_00081-f_00157"],
      "caption_readability": "verified"
    }
  ],

  "judgment_episodes": [
    {
      "episode_id": "J1",
      "object": "虾籽大乌参",
      "initial_expectation": "高价大菜；入口前先闻到炒虾籽香味",
      "trigger": "入口后出现舌根发麻、像舔铜和含电池的感受",
      "information_actions": ["停止正常品尝", "描述身体感受", "邀请同伴复尝", "再次确认"],
      "reaction_sequence": "入口→停顿皱眉→怀疑个人过敏→询问同伴→确认异常→提出退菜",
      "reasoning_chain": "异常身体感受→先排查个人原因→同伴复核→转向本次菜品/原料问题→不可继续食用",
      "revision": "从‘还是我个人过敏’修正为‘这个东西不能吃了’",
      "final_judgment": "本次出品不可接受",
      "action_result": "退菜",
      "comparison_refs": ["本期前两道正常菜", "个人舔铜/电池经验"],
      "quote": "还是我个人过敏？你俩尝尝……这个东西就不能吃了",
      "timestamp": "01:20-03:22",
      "confidence": "high",
      "open_questions": ["具体异常来源仍未得到外部检验"]
    }
  ],

  "comparisons": [
    {
      "episode_refs": ["J1"],
      "left": "前两道平价家常菜",
      "right": "后两道高价菜",
      "dimension": "本期实际评价",
      "trigger_context": "结尾复盘整顿饭",
      "quote": "先上来两个菜……都挺好……后边儿两个菜……都有点问题",
      "timestamp": "03:23-04:42",
      "reasoning_role": "支持‘高开低走’的整店总结",
      "reference_scope": "本期内比较"
    }
  ],

  "tensions_and_revisions": [
    {
      "episode_refs": ["J1"],
      "type": "判断修正",
      "before": "怀疑是个人过敏",
      "new_evidence": "邀请同伴品尝并继续描述共同可感的异常",
      "after": "判定本次菜品不可继续食用",
      "behavior_change": "从继续辨认转为退菜",
      "quote": "还是我个人过敏？你俩尝尝……不能吃了",
      "timestamp": "01:20-03:22"
    }
  ],

  "methodology_clues": {
    "information_acquisition": ["用身体异常感受发现问题，并邀请同伴复核"],
    "evaluation_order": ["先描述感受，再排查个人原因，最后判断菜品并采取行动"],
    "reasoning_logic": ["多人复核式排除"],
    "anti_interference": ["没有因高价或菜单吸引力压过实际入口体验"],
    "revision_mechanism": ["同伴复核后修正个人过敏假设"],
    "output_organization": ["开场结论前置，结尾以‘高开低走’回扣全过程"],
    "scan_notes": "六环节均已扫描；只描述本期线索，不宣称稳定方法论"
  },

  "expression_materials": [
    {
      "episode_refs": ["J1"],
      "type": "感官类比",
      "quote": "好像把这电池含在嘴里那种感觉",
      "timestamp": "01:54-02:37",
      "context": "将难以言传的金属味和发麻感转成日常经验",
      "function": "具象化陌生感官体验",
      "prosody_or_delivery": "连续使用舔铜、氨水、电池三个类比，语气逐步加强"
    }
  ],

  "raw_sensory_descriptors": [
    {
      "object": "虾籽大乌参",
      "quote": "感觉给电了一点儿，有点儿麻",
      "timestamp": "01:20-02:37",
      "mapped_tags": ["异味-金属味", "口感-发麻"]
    }
  ],

  "audiovisual_analysis": {
    "shot_sound_relations": [
      {
        "episode_refs": ["J1"],
        "timestamp": "01:20-02:37",
        "relation_type": "刺激→反应",
        "evidence_level": "direct_video",
        "visual_basis": ["连续观看 01:20-02:37", "f_00081-f_00157"],
        "description": "菜品特写与入口后的停顿、皱眉和异常感描述连续出现",
        "judgment_contribution": "保留异常判断形成的时间顺序",
        "agency": "专家言行+摄影剪辑",
        "uncertainty": "成片存在剪辑，不能据此还原被删去的全部过程"
      }
    ],
    "reaction_sequences": [
      {
        "episode_refs": ["J1"],
        "object": "虾籽大乌参",
        "evidence_level": "direct_video",
        "visual_basis": ["连续观看 01:20-03:22"],
        "sequence": "正常品尝→停顿皱眉→描述舌根发麻→看向同伴并请其复尝→退菜",
        "observation_opportunity": "面部与动作在关键反应窗口连续可见",
        "interpretations": ["味道/身体感受异常", "最初也可能是个人过敏"],
        "resolved_by": "后续明确原话与退菜行动"
      }
    ],
    "attention_distribution": [
      {
        "episode_refs": ["J1"],
        "object": "虾籽大乌参",
        "evidence_level": "direct_video",
        "visual_basis": ["连续观看 01:20-03:22"],
        "expert_attention": "高：复尝、描述、邀请同伴复核并退菜",
        "verbal_attention": "高：持续讨论异常感与可能原因",
        "editorial_attention": "高：开场预告、正片长段、结尾回扣",
        "alignment": "三者一致",
        "basis": "动作、语音时长与成片位置"
      }
    ],
    "judgment_arc": "菜单带来正面预期→两道家常菜好评→高价海参异常成为转折→同伴复核→退菜→区分厨师技法与原料问题→‘高开低走’总结",
    "nonreaction_opportunities": []
  },

  "taste_lineage": [
    {
      "reference": "个人舔铜/含电池的身体经验",
      "role": "为陌生异味提供可传达的感官参照",
      "quote": "铜的东西你拿舌头舔一下",
      "timestamp": "01:20-02:37"
    }
  ],

  "open_interpretations": [
    {
      "observable_fact": "入口后舌根发麻并出现连续负面反应",
      "interpretations": [
        {"text": "本次菜品存在异常", "support": "明确原话、同伴复核与退菜", "limitation": "无实验检测"},
        {"text": "个人过敏", "support": "博主最初主动提出", "limitation": "后续行为使其可能性降低"}
      ],
      "current_tendency": "倾向本次菜品异常，但具体原因未决",
      "downstream_limit": "不得把具体工艺原因直接写成博主稳定判断"
    }
  ],

  "candidate_patterns": [
    {
      "pattern": "本期他对两道平价家常菜的评价高于两道高价菜",
      "video_count": 1,
      "within_video_sample_count": 4,
      "source_type": "blogger_explicit",
      "scope": "this_serving",
      "scope_quote": null,
      "confidence": "low",
      "not_stable_rule": true,
      "counter_example": null,
      "next_verify": "看后续几期价格与评价是否仍呈负相关",
      "supporting_dish_names": ["本帮烂糊肉丝", "虾籽大乌参"]
    }
  ],

  "asr_corrections_count": 10
}
```

---

## 字段取值约定

### 顶层

| 字段 | 取值 |
|------|------|
| `content_type` | `探店` / `表态` / `无关` |
| `processing_status` | **生成时固定写 `完成待修订`**。其余取值由脚本或人在事后写：`完整`（`--write-gate` 零 BLOCK 时）/ `降级-纯转写`（用户同意降级后）/ `待确认` / `失败` / `无关` |
| `quality_gate` | **生成时不输出**。由 `--write-gate` 写入，见下方专节 |

> ### ★ 这两个字段不属于生成者（v4.3）
>
> v4 实测：10 份产出里 6 份手填了 `quality_gate`，其中 0003 填的是
> `blocking_issues: []` + 八项全 `true`，而闸门实测该份有 **26 条 BLOCK**；
> 9 份把 `processing_status` 写成 `完整`，实则全部有 BLOCK。
>
> 根因不是模型不听话，而是**指令自相矛盾**：schema 把这两个字段列为必填、
> 给了完整示例结构，同时又在旁边写"不要手填"。必填字段摆在面前，
> 唯一能做的就是填满它。更根本的是，**"我这份合规吗"在生成时无法自答**——
> 生成者已经相信自己合规了，否则不会那样写。这与 v2 的自检清单全打勾
> 是同一个机制，只是形式从 markdown 复选框升级成了 JSON 对象。
>
> 所以 v4.3 的做法不是叮嘱得更严厉，而是**把字段从输出契约里拿掉**：
> 让违反在结构上无法发生，而不是靠自律。
> 闸门发现产出里带 `quality_gate` 会报 `GATE_SELF_REPORTED`。

> `完成待修订`（v3 新增）：内容跑完了，但 `validate_corpus.py` 报了 BLOCK。
> 这类记录**允许存在**，但 `merge-guide.md` Step 1 会拒绝纳入 `corpus-index.json`。
> 设这一档的原因：不设它，模型面对"要么标失败要么标完整"只会标完整。

### _meta

| 字段 | 说明 |
|------|------|
| `cuisine` | **菜系级**粒度：本帮菜/川菜/粤菜/日料/火锅/烧烤/西餐/面食小吃/烤鸭/海鲜/西北菜/淮扬菜/东北菜/鲁菜/云贵菜/湘菜/东南亚/自助餐/融合菜 |
| `shop_tier` | 大排档 / 小馆 / 正餐 / 高端 / 米其林黑珍珠 |
| `price_total` | **总价**（他开场报价的习惯形式，如"仨人189"） |
| `price_per_person` | **人均**（他做性价比判断时用的形式）。两个都要存 |
| `price_tier` | `<150` / `150-400` / `400-800` / `800-2000` / `2000+`（按总价划分） |
| `party_size_basis` | 人数的**来源**：`博主明说` / `画面可数` / `按人均反推`。填 `按人均反推` 时 `price_per_person` 不得同时也是反推来的 |
| `price_per_person_basis` | 人均的来源：`博主明说` / `总价÷人数` / `花字` |

> 为什么要加这两个 basis 字段：v2 的 0004 同时给出 `party_size` 和 `price_per_person`，
> 但转写稿里博主只报了总价——两个数都是模型自己算的，却和博主明说的数字长得一样。
> 下游做性价比统计时无法区分"他自己算的人均"和"我们替他算的人均"。
> 循环反推（用人均猜人数、再用人数算人均）会被闸门判 `DERIVED_NO_BASIS`。

### A 档维度

各维度的 `assessment` / `overall` / `verdict` 统一取值：
`强烈正面` / `正面` / `中性` / `有保留` / `负面` / `强烈负面`

（v4 起 `dishes[].sentiment` 与本表同为六级，不再有五级/六级之分。）

`d3_cooking.is_prepared_food`：`true` / `false` / `null`（未判断）

#### ⚠️ `d10_ordering` 是 A 档里唯一在做归纳的字段，同样受候选规律约束

B1 已被严格限定为"候选规律"，但 `d10_ordering` 是必填的 A 档字段，很容易绕过那条约束，
把单期观察写成通用点菜策略。**它与 B1 适用同一条纪律。**

| 字段 | 填法 |
|------|------|
| `worth_ordering_this_time` | **本期他吃了且评价正面**的菜。不是"推荐去这家必点" |
| `avoid_this_time` | **本期他吃了且评价负面**的菜 |
| `strategy_notes` | 只写本期观察到的现象 + 样本量。**禁止**写成通用规则 |
| `scope` | 默认 `this_serving`。升级需博主明说"他们家每次都""这类店都这样" |

```
❌ "便宜的家常菜反而稳，贵菜踩雷"           ← 从 4 道菜推出的通用规律
❌ "本帮菜优先点带'烂糊'二字的家常菜"        ← 从 1 道菜推出的点菜策略
✅ "本期他对两道便宜家常菜评价高于两道贵菜（样本：4道菜，不足以成规律）"
```

字段名从 `must_order` / `avoid` 改为 `worth_ordering_this_time` / `avoid_this_time`，
就是为了让字段名本身携带范围限定——"must_order"读起来像跨期结论，改名后不会。

### B 档

| 字段 | 取值 |
|------|------|
| `dimension_events[].dimension` | `D6环境` / `D8服务` / `D9卫生` / `D11呈现` / `D12私密社交` |
| `dimension_events[].reaction_type` | `明确评论` / `微反应` / **`无反应`** |
| `dimension_events[].intensity` | `强` / `中` / `弱`（`无反应` 时填 `无`） |
| `dimension_events[].source_type` | 同 dishes，见下方专节 |
| `dimension_events[].scope` | 同 dishes，见下方专节。默认 `this_serving` |
| `dimension_events[].scope_quote` | **与 dishes 同规则**：`scope` 升级到 `this_restaurant`/`dish_type`/`brand_chain` 时必填，且须能在转写稿中查到；`this_serving` 时填 `null`。<br>⚠️ v4.4 之前本行漏写，而闸门一直在查——严格照 schema 写的人只能从报错里得知需要它（`SCOPE_UPGRADE_NO_QUOTE` / `SCOPE_QUOTE_NOT_IN_TRANSCRIPT`）|
| `dimension_events[].evidence_source` | `audio` / `visual` / `both` / `inference`。**B 档尤其要填**——`微反应`/`无反应` 只可能来自画面，不标来源，下游无法判断这条是他说的还是模型看出来的 |
| `dimension_events[].quote` | 原话。`微反应`/`无反应` 时填 `null` |
| `dimension_events[].timestamp` | `MM:SS-MM:SS`，用于回查还原层 |

⚠️ **必须逐字使用上述取值，不得自行变体。** 写成 `D9卫生/安全`、`D8服务水平` 在汇总时会被当成不同的组，导致统计失真。
v2 实测越界 13 处，自创出 `D7出餐速度`、`D10点菜`、`city_level` 等九个不存在的维度值。
权威清单在 `enums.json`，越界即 BLOCK。

⚠️ **`无反应` 是有效值不是缺失值**——事件发生但他毫无反应，是该维度权重极低的负向证据。这防止下游把行业常识误当成此人的判断标准。

**"无反应"最容易被漏记**——"他评论了什么"很显眼，"他对什么没反应"要主动找。填表后应逐项自检五个维度：该维度这期有没有出现值得反应的情况？出现了他反应了吗？若整表全是 `明确评论`，大概率漏了。

### 丰富性字段：本期判断过程与视听语义

这些字段是为减少“前置提炼折损”而设。它们记录**本期已经发生的过程**，不是稳定人格结论，不受候选规律的跨期门槛限制。安全处理采用保留+标注：不确定内容进入 `open_interpretations`，不得因无法唯一判断而删除。

| 字段 | 说明 |
|------|------|
| `visual_coverage[]` | 每个 A1 时间段的视觉覆盖台账：`timestamp`、`visual_status`、`visual_basis[]`、`caption_readability`。区分实际看过连续视频、只看抽帧、纯音频与不可读 |
| `judgment_episodes[]` | 每个重要判断的完整事件；`episode_id`（J1/J2…）本期唯一。初始预期、刺激、信息获取动作、反应序列、推理链、复核、修正、结论、行动、原话、时间戳和未决点。重要判断不得只剩 sentiment |
| `comparisons[]` | 本期所有显式比较及参照系；每项带 `episode_refs`。比较两端、维度、语境、原话、推理作用和参照范围。包括预期/实际、菜间、店间、地域、个人历史、价格/品质等 |
| `tensions_and_revisions[]` | 每项带 `episode_refs`；言行一致/背离、即时反应与结尾变化、判断修正、价值取向张力。矛盾保留，不替专家调和 |
| `methodology_clues` | 六环节对象，六个数组与 `scan_notes` 均须存在。无信号写空数组并在 scan_notes 说明已扫描，禁止默默省略 |
| `expression_materials[]` | 每项带 `episode_refs`；类比、反问、推荐/否定句、不确定性表达、自我修正、观众对话、互动、开场收尾及副语言；每条保留完整原话、时间戳、语境和表达功能 |
| `raw_sensory_descriptors[]` | 标准标签不能承载的原始感官措辞。与 `standard_tags` 双存，不互相替代 |
| `audiovisual_analysis` | 镜头/声画关系、反应序列、专家/言语/剪辑三种注意力、判断弧线及无反应可观察机会。各数组条目须有 `episode_refs`、`evidence_level`、`visual_basis`；口播关系用 audio_timeline，不得冒充镜头关系 |
| `taste_lineage[]` | 本期实际调用的个人经历、地域、同行/师傅、旧店旧菜等参照材料；只记它在本期推理中的作用 |
| `open_interpretations[]` | 可观察事实、多种竞争解释、各自支持与限制、当前倾向和下游限制。是高价值不确定信息的正式容器 |

#### 视觉证据规则

- `visual_status=reviewed_video`：可以记录连续动作、反应序列和镜头关系，`evidence_level=direct_video`。
- `reviewed_frames`：单帧只能记录静态事实（`evidence_level=single_frame`）；连续多帧可用 `frame_sequence` 支撑动作。`frame_sequence` 至少引用两个真实帧端点；单帧不得证明停顿、复尝、眼神转移或蒙太奇。
- JSON 的 reviewed 声明必须在重叠的 Markdown A1 时间段留下同源 `visual_basis` 的 `[画面]` / `[花字]` 客观观察；确实没有判断相关视觉信号时，写规范的“已检查但无判断相关视觉信号”留痕，不得为了过闸门编造观察。
- 模型输出的帧清单只是可审计声明，不等于实际读取证明。执行环境若能提供不可由模型改写的工具访问日志，以工具日志为准；否则必须明确其证明力边界。
- `audio_only`：不得写视觉/花字/BGM事实；A9 只能用 `audio_timeline` 描述口播关系，A10/A11 的视觉部分写不可观察。
- `unreadable`：允许注明已检查但无法辨认；对应解释只能用 `audio_timeline` 或保留为开放问题。
- `unreadable`：保留覆盖事实及不可读原因，不猜内容。
- 花字只有 `caption_readability=verified` 才能逐字进入价格和事实字段。
- `editorial_inference` 必须说明依赖哪些实际镜头/声音，只表示理解者对后期意图的解释。
- 花字状态逐字使用：`verified` / `partially_readable` / `unreadable` / `not_present` / `not_reviewed`。
- `episode_refs` 必须指向本期已存在的 `judgment_episodes[].episode_id`；跨章节重复原话时优先引用 episode，不把复述当多份证据。

#### 最低丰富度原则

- 有重要评价就应有对应 `judgment_episodes`；不是要求机械凑数，而是防止只留结论。
- 六环节必须完成机会扫描；空数组合法，整块缺失或无扫描说明不合法。
- `standard_tags` 只用于跨期统计；`raw_sensory_descriptors` 保留语言纹理。
- `editorial_attention` 只代表成片强调，不能直接等同于专家偏好。
- 无反应只有在专家确实接触事件且反应窗口连续可见时才记为 `observed_nonreaction`；否则记 `reaction_not_shown` / `reaction_ambiguous` / `not_exposed`。
- 开放解释允许使用模型推断，但必须保留竞争性解释和限制，不进入价值观或稳定规律。

### candidate_patterns 候选规律（v3：从 md 散文改为结构化数组）

**为什么要结构化**：v2 把候选规律只写在 md 的 `### B1` 小节里，
json 里没有对应字段。结果是 Phase 2 合并时只能读 json，
B1 的样本量与置信度声明全部丢失，"样本=1 的候选"被当成既成结论合并进画像。
**json 是唯一可合并的事实源** —— md 里有而 json 里没有的东西，下游看不见。

```json
"candidate_patterns": [
  {
    "pattern": "本期他对两道平价家常菜的评价高于两道高价菜",
    "video_count": 1,
    "within_video_sample_count": 4,
    "source_type": "blogger_explicit",
    "scope": "this_serving",
    "scope_quote": null,
    "confidence": "low",
    "not_stable_rule": true,
    "counter_example": null,
    "next_verify": "看后续几期是否重复出现价格与评价的负相关",
    "supporting_dish_names": ["烂糊肉丝", "扣肉", "刀鱼馄饨", "河豚"]
  }
]
```

| 字段 | 说明 |
|------|------|
| `pattern` | 候选规律的陈述。**必须自带范围限定词**（"本期""这一次"），不得写成通用规则。⚠️ 键名就是 `pattern`，不是 `statement` |
| `video_count` | **恒为 1**。单期产出只可能有一期样本——这是防抖阈值真正关心的量 |
| `within_video_sample_count` | 本期内有几道菜／几个事件支撑这条候选。可以 >1 |
| `source_type` | **必填，不可为 null**（闸门查 `ENUM_NULL`）。只接受 `blogger_explicit` / `blogger_hypothesis`——即有可回查博主原话的。<br>⚠️ **`model_inference` 的东西不进 `candidate_patterns`**：模型自己猜出来的"规律"没有跨期验证价值，混进来只会污染下游归并。要留就留在 `open_interpretations`，保留事实、竞争解释和限制 |
| `scope` | 默认 `this_serving`，取值同 dishes |
| `scope_quote` | `scope` 升级到非 `this_serving` 时必填的博主原话；否则 null |
| `confidence` | **恒为 `low`**。跨期归并、升级 confidence 都是下游的事，单期产出无权做 |
| `not_stable_rule` | 恒为 `true`。这个字段存在的意义就是让下游没法把它当稳定规律 |
| `counter_example` | 本期内的反例，有则必填。有反例还想留这条，就该在 `next_verify` 里说明 |
| `next_verify` | 下一步要验证什么。写不出来说明这条候选没有可验证性 |
| `supporting_dish_names` | 关联的菜名，便于回查 |

> **v4 为什么把 `sample_count` 拆成两个**：v3 只有一个字段，
> 而校验器要求 `==1`、本文档却说 `low`=样本1-2 / `medium`=3-4、示例还写着 `4`——
> **文档与校验直接对立，模型无论怎么填都会挨一刀**。
> 根因是一个字段承担了两个语义："几期"和"本期内几道菜"。拆开后各自明确：
> `video_count` 恒 1（铁律），`within_video_sample_count` 随便填几都行（描述性）。
>
> **v4 同时收紧 `confidence` 为恒 `low`**：原先允许 3-4 道菜填 `medium`，
> 但"同一期里的 4 道菜"不是 4 个独立样本——同一顿饭、同一家店、同一天的心情，
> 相关性极高。把它当成 4 个样本升 confidence，正是"从单期偷渡稳定结论"的标准路径。

**禁用表述**（闸门检查 `B1_FORBIDDEN_PHRASE`）：
`是……的标尺` / `标志性` / `定海神针` / `必点` / `通病` / `凡是` / `都是这样` / `普遍`。
这些词把单期观察伪装成跨期结论。v2 泄漏 3 处。

**防抖阈值**（沿用）：价值观红线单期可立 → 决策启发式 ≥2 期 → 判断方法论 ≥2 期 →
心智模型 ≥3 期且只作线索。**单期产出里，一切归纳都只能是候选。**

### quality_gate 闸门结果（v3 新增，必填）

```json
"quality_gate": {
  "validated_at": "2026-08-17",
  "validator_version": "v4.7",
  "schema_valid": true,
  "fact_boundary_valid": true,
  "scope_valid": true,
  "candidate_pattern_valid": true,
  "tag_valid": true,
  "visual_valid": true,
  "duration_valid": true,
  "frame_valid": true,
  "blocking_issues": [],
  "warnings": ["QUOTE_COMPOSITE: dishes[2] quote 由多段拼接"]
}
```

由 `scripts/validate_corpus.py --write-gate` 写入，**不要手填**。
手填的自检从来都是全部打勾——v2 十份产出的自检清单无一例外全勾，
而实际有 46 处枚举越界、24 处工艺归因串位。这就是为什么这个对象必须由脚本生成。

`blocking_issues` 非空 ⇒ `processing_status` 必须是 `完成待修订`。

⚠️ **`validated_at` / `validator_version` 也由脚本写**（v4 修）。
v3 的 `build_gate()` 漏了这两个键，而 `merge-guide.md` Step 1 与 SKILL.md
的断点续跑判据都要求 `validated_at` 非空——结果**零 BLOCK 的记录也过不了合并准入**。
若在旧产出里看到没有 `validated_at` 的 `quality_gate`，重跑 `--write-gate` 即可。
需要固定日期时用 `--write-gate --date 2026-08-14`。

### dishes 数组

| 字段 | 说明 |
|------|------|
| `name` | 菜名 |
| `object_level` | `整道菜` / `组成部分` / `食材` / `技法` / `分量` / `价格`——评价的是哪一层 |
| `price` | 单价，未报价填 null |
| `sentiment` | **六级**：`强烈正面` / `正面` / `中性` / `有保留` / `负面` / `强烈负面`<br>v4 与 A 档维度统一。v3 曾刻意让这里只有五级（无 `有保留`），实测是单一最高产的枚举错误（46 条越界里 7 条），而 schema 从未说明为何要有这个差异。"挺好吃但太咸"确实是有保留，强行归入正面或负面都失真 |
| `intensity` | 评价强度：`强` / `中` / `弱`。区别于 sentiment（方向）——"还行吧"是正面但弱 |
| `reason` | **自由文本，不设受控词表**。保留博主的原始表述方式 |
| `standard_tags` | **标准标签数组**，取自 `tag-dictionary.json` 闭词典，与 reason 双写。用于跨期统计。**标签内不得带括号**（见下方专节） |
| `tag_qualifier` | 限定词映射，如 `{"口感-绵软": "负面"}`。取值 `负面`/`异常`/`过度`/`不足`。原先写在标签括号里的信息移到这里 |
| `blogger_attribution` | **博主自己说出口的归因**（如他说了"碱发过度"）。他没归因则 null。⚠️ 博主没说的词绝不能填这里——闸门会拿转写稿逐词核对 |
| `source_type` | ★ 见下方专节 |
| `scope` | ★ 见下方专节 |
| `scope_quote` | scope 升级到非 `this_serving` 时**必填**的博主原话依据；`this_serving` 时填 null |
| `evidence_source` | `audio` / `visual` / `both` / `inference`——这条信息从哪来 |
| `confidence` | `high` / `medium` / `low`——**这条记录本身可不可靠**。区别于 `source_type`（那是"谁说的"）：原话清晰完整→high；所在段落 ASR 有存疑、或需要较多推断才成立→medium/low |
| `quote` | **博主原话，逐字引用，不得重述。** 这是下游提取表达DNA词汇指纹的唯一结构化来源 |
| `timestamp` | `MM:SS-MM:SS`，该菜被讨论的主区间。与 `quote` 配套，用于回查还原层 |
| `shot_duration_sec` | **该菜的镜头停留总秒数**。权重的客观证据——他自己都未必意识到的优先级排序 |
| `has_caption` | 是否有花字标注。有花字时价格以花字为准 |

> **`quote` 与 `reason` 是两件事，都要填**：`reason` 是你归纳的评价理由（可以是多句话的概括），`quote` 是他的原话逐字照抄。
>
> **为什么 `quote` 必填**：本 skill 的分层约定是"下游默认读提炼层，需要时才回查还原层"。若 json 里没有原话，下游要提表达DNA 就必须每次回查全部 `understanding/*.md`，`corpus-index.json` 在这个用途上等于废掉。原话进 json 是这条分层约定能成立的前提。
>
> **v3 增补：`quote` 会被机械溯源。** 闸门把 quote 按 `；`/`…`/`/` 切片，
> 每片都要能在转写稿里查到（忽略标点与空白差异）。实测拦下的真实错误：
> 转写稿是"有点儿像叉烧"，json 写成"像叉烧"；转写稿是"吱嘎吱"，json 写成"吱嘎吱嘎"。
> **逐字就是逐字**，多段拼接可以（会记一条 WARN），改字不行。

#### ★ source_type 与 scope（两个最容易出错的字段）

**`source_type`——这话是谁说的、是判断还是推测**

| 取值 | 含义 | 判据 |
|------|------|------|
| `blogger_explicit` | 博主明确说出的判断 | 有原话，陈述句 |
| `blogger_hypothesis` | **博主自己的推测** | 原话含"我觉得""应该是""可能" |
| `model_inference` | **模型推断的** | 博主没说，是模型补的 |
| `externally_verified` | 多方确认 | 画面直接可见，或他人印证 |

> `model_inference` 不是删除指令。它表示内容应保留在 `open_interpretations`，带可观察事实、竞争解释、支持/限制与下游边界；只是不进入稳定统计和价值观。

⚠️ 非 `externally_verified` 时，`reason` 字段**禁止**用"因X导致Y""X是Y的原因"这类确定因果，
须写成"博主推测可能与X有关"。`blogger_attribution` 字段专门放博主的归因，不要混进 `reason`。

**`scope`——这个评价管多大范围**

| 取值 | 含义 |
|------|------|
| `this_serving` | **仅本次这一份（默认值）** |
| `this_restaurant` | 本店的稳定表现 |
| `dish_type` | 这道菜式本身 |
| `brand_chain` | 整个品牌/连锁 |

⚠️ 默认一律 `this_serving`。升级需博主原话支撑（"这道菜就是这样""他们家每次都"）。
跨期合并时，"本店本次这条鱼不新鲜"若被当成"这道菜式不行"，专家画像就废了。

**v3 收紧：升级必须留证。** 升级到 `this_restaurant` / `dish_type` / `brand_chain` 时，
`scope_quote` 必填，且须是转写稿里能查到的原话。填不出原话就说明这次升级没有依据——
那就应该退回 `this_serving`。闸门会检查这一条（`SCOPE_UPGRADE_NO_QUOTE`）。

实测 v2 的两处典型越界：

```
❌ scope: dish_type    ← 博主只说了"这次这个不行"，没说过这道菜式普遍如何
✅ scope: this_serving, scope_quote: null

✅ scope: this_restaurant,
   scope_quote: "他们家这个东西一直都这样"     ← 有原话，升级成立
```

判据很简单：**scope 描述的范围，必须由博主的话本身撑起来，不能由模型的常识撑起来。**
"这类店都这样"是行业常识时也不能升级——那是模型的知识，不是这位博主的判断。

#### standard_tags 映射表（与 reason 双写，不替代 reason）

博主用口语描述口感（"九分烂""入口即化"），跨期无法合并统计。
解法是**双写**：`reason` 保留原话表述不变，`standard_tags` 另填标准标签。

**⚠️ 标签的权威定义在 `references/tag-dictionary.json`，下表只是可读镜像。**
以 json 为准的原因：v2 实测产出了 108 个不同标签，其中 23 个是同一概念的括号变体
（`口感-绵软（负面）` / `口感-绵软(负面)` / `口感-绵软`），跨期统计时被当成三个标签。

**三条硬规则**（闸门检查）：

1. **标签内不得出现任何括号。** 限定词写进 `tag_qualifier`：
   ```json
   "standard_tags": ["口感-绵软"],
   "tag_qualifier": {"口感-绵软": "负面"}
   ```
2. **必须带前缀**：`口感-` `味道-` `香气-` `异味-` `功能-` `温度-` `分量-` `性价比-` `其他-`。
3. **必须在词典内**，逃生口是 `其他-{简短描述}` 或 `{前缀}其他-{简短描述}`。

> **v4 放宽了逃生口**：`味道-其他-味儿浓` 现在合法。v3 只认裸 `其他-{描述}`，
> 而模型实际写的是带前缀的形式——它在保留统计轴，这个直觉是对的，
> 被 BLOCK 掉反而损失信息。归不进任何轴时才用裸 `其他-`。
>
> **词典同时从 38 个扩到 57 个**。扩容依据是实测：10 期语料撞出 37 种词典外标签，
> 其中 `味道-咸甜`、`味道-鲜甜`、`口感-多汁`、`香气-蒜香`、`口感-绵密`
> 都是合理的新概念而非扭曲原意。**闭词典太小时，模型的自救方式是自创，结果更乱**——
> 复合口味（咸甜/咸鲜/鲜甜）单独立项而不拆成两个标签，因为它们在中餐里
> 是一种独立的风味判断，拆开会丢掉"复合"这个信息本身。

| 标准标签 | 博主可能的原话 |
|---------|--------------|
| 口感-软烂 | 九分烂、软烂、入口即化、烂糊、脱骨 |
| 口感-黏糯 | 黏黏糊糊、糯、挂芡、稠 |
| 口感-绵软 | 绵绵的、烂烂的、像棉花、发面（负面语境时填 `tag_qualifier: 负面`） |
| 口感-弹韧 | 有弹性、Q弹、筋道、弹牙、像猴皮筋（异常弹性填 `tag_qualifier: 异常`） |
| 口感-紧实 | 硬、有嚼头、结实 |
| 口感-柴 | 柴、干、老 |
| 口感-脆嫩 | 脆、爽脆、脆生 |
| 口感-酥脆 | 酥、酥脆、外脆 |
| 口感-滑嫩 | 滑嫩、软嫩、滑溜、嫩 |
| 味道-甜 / 味道-咸 / 味道-辣 / 味道-麻 / 味道-鲜 / 味道-酸 | 对应口语表述。**逐个单填，不要写成 `味道-甜/咸`** |
| 味道-寡淡 | 没味儿、没咸淡、寡、淡 |
| 味道-齁 | 太咸、齁、过咸 |
| 香气-锅气 | 锅气、镬气、火候香 |
| 香气-焦香 / 香气-酱香 / 香气-酒香 / 香气-药材香 / 香气-烟熏味 | 对应口语表述。同样逐个单填 |
| 异味-金属味 | 舔铜、像电池、铁锈味 |
| 异味-脏器味 | 脏器味、下水味、腥臊 |
| 异味-腥 | 腥、土腥、鱼腥 |
| 功能-下饭 | 下饭、配米饭好、就饭 |
| 功能-解腻 | 解腻、清口 |
| 温度-烫 / 温度-温 / 温度-凉 | 对应口语表述 |
| 分量-实诚 / 分量-小气 | 量大管饱 / 就这么点儿 |
| 性价比-高 / 性价比-低 | 值、便宜、划算 / 贵、不值 |

> **表未穷尽**。遇到映射不上的口感，`standard_tags` 填 `其他-{简短描述}`，
> 并在 `raw_sensory_descriptors` 中保留原始措辞，供后续补充映射表。**不要为了套进现有标签而扭曲原意**。
> 但 `其他-` 是逃生口不是垃圾桶——同一个概念反复用 `其他-` 时，应回补进词典。

#### price_check 价格交叉校验（必做）

| 字段 | 说明 |
|------|------|
| `total_from_audio` | 语音报的总价，无则 null |
| `total_from_caption` | 花字打的总价，无则 null |
| `sum_of_dishes` | 各菜价加总（仅计已报价菜品） |
| `consistent` | true / false |
| `mismatch_note` | 不一致时必填：标 `price_mismatch` + 说明可能原因（酒水/未报价菜品/大小份/退菜） |
| `is_estimated` | 总价是否为估算。true 时须在 note 中列出已知分项 |

⚠️ 三个数字打架时**不要沉默地挑一个**。实测错例：语音报 568 / 花字打 338 /
菜价加总 519，产出直接采用 338 且未提 519 的差异，下游无从判断哪个可信。

#### shot_duration_sec 的计算口径（务必统一，否则跨期无法横向比较）

**用转写稿时间轴计算，不要靠看画面估算。**

做法：找出讨论该菜的所有转写段落，把这些段落的时间区间相加。
例：某菜在 `[00:54-01:32]` 和 `[01:40-01:52]` 被讨论 → 38 + 12 = **50 秒**

三条硬约束：

| 约束 | 说明 |
|------|------|
| **总和不超时长** | 各菜时长 + 开场/结尾/转场 ≤ `video_duration_sec`。超出即说明是估算的 |
| **不重复计入** | 同一段落不得计入两道菜；一段同时讲两道菜时归入主要讨论对象 |
| **只计菜品本身** | 退菜沟通、与服务员交涉、店铺介绍**不计入**菜品时长——它们归 `dimension_events` |

---

## 空值约定

**一律填 `null`，不得省略字段。**

全部 json 要合并成一张表，缺失字段会导致列对不齐。逐道菜数组内的字段同样填 `null` 而非跳过。

`_comment_*` 开头的键是给执行者看的分档说明，合并时会被脚本忽略，不是数据。

---

## 表态类简化 schema

`content_type: "表态"` 时使用，**不含** `_meta` 的店铺字段、A档维度、B档事件、dishes 数组。

```json
{
  "id": "{编号}",
  "content_type": "表态",
  "processing_status": "完成待修订",
  "_comment_status": "★ 同探店：生成时固定 完成待修订，且不输出 quality_gate。两者都由 --write-gate 事后写入。",
  "video_duration_sec": 198,
  "topic": "回应恰饭质疑",
  "values_triggered": [
    {
      "content": "不收钱推广",
      "context": "有粉丝质疑某期是广告",
      "intensity": "强",
      "quote": "我要是恰了这顿饭，我这号就别做了",
      "timestamp": "02:14-02:31",
      "value_type": "红线",
      "source_type": "blogger_explicit",
      "evidence_source": "audio",
      "confidence": "high"
    }
  ],
  "expression_notes": "语速加快、重复强调、直视镜头",
  "asr_corrections_count": 2
}
```

| 字段 | 取值 |
|------|------|
| `values_triggered[].intensity` | `强` / `中` / `弱` |
| `values_triggered[].quote` | **原话逐字，不得重述**——表态类的原话密度高于探店类，是表达DNA的主要来源 |
| `values_triggered[].timestamp` | `MM:SS-MM:SS`，供回查还原层 |
| `values_triggered[].value_type` | `红线`（明确表态，单期可确认）/ `候选倾向`（单次经历推出，待跨期验证） |
| `values_triggered[].source_type` | **只能是** `blogger_explicit` / `blogger_hypothesis`（收窄枚举）。<br>⚠️ **不接受 `model_inference`**（闸门查 `VALUES_MODEL_INFERENCE`）。模型推断不删除，移入 `open_interpretations`，保留竞争解释和下游限制 |
| `values_triggered[].evidence_source` | `audio` / `visual` / `both` / `inference` |
| `values_triggered[].confidence` | `high` / `medium` / `low`——这条记录本身可不可靠（区别于 source_type） |

⚠️ 区分 `红线` 与 `候选倾向`：前者是"绝不收钱推广"这类明确表态+情绪强烈的红线，
单期可确认；后者是"对米其林的务实态度"这类从一次经历推出的倾向，须跨期验证。
混为一谈会让单次体验被当成稳定价值观。
