# 5.3-Flash 标准产物组装

## 前置门槛

只有 `scripts/check_stage.py {corpus} --id {id} --target assembly --variant 5.3-flash` 通过后才运行。唯一事实输入：ASR、shot ledger、visual ledger、reaction windows、sound-edit ledger 和闭集 schema/taxonomy；不得凭记忆重新补画面。

## 输出

1. `data/5.3-flash/{id}.json`：严格 `output-schema.md`，`processing_status=完成待修订`，不输出 `quality_gate`。
2. `assembly/5.3-flash/{id}.json`：`render_understanding.py` 的固定 payload。
3. 运行 `scripts/render_understanding.py assembly/5.3-flash/{id}.json --corpus {corpus} --id {id} --variant 5.3-flash` 生成 `understanding/5.3-flash/{id}.md`，禁止手写另一套章节。

## 投影规则

- A1：只回收对判断、表达、情境有贡献的空间/动作/声音事实；完整电影学编码留在 ledger。
- A9：从 sound-edit ledger 投影镜头/声画关系，至少两个 shot ID。
- A10：从 reaction windows 投影动作与微反应；没有连续证据写不可观察。
- A11：expert attention 只来自注视/操作/追问/复尝/行动；verbal 来自语音；editorial 来自 shot duration/特写/字幕/回放/音效。三者分别记录。
- A12–A15/B3–B7：每条高层 claim 必须带 `audiovisual_claim_refs`，引用 ledger event ID；同一 episode 重复引用不得重复计权。

## 禁止

- 内嵌自创 JSON 代替独立 `data/5.3-flash/{id}.json`；
- Mermaid、自由“深度理解”结构、人格侧写、星级；
- 构图/光线/单一表情直接推出情绪、品味或人格；
- raw detector 和重复 OCR 计作视频独有增量；
- audio timeline 推镜头、剪辑、BGM或动作。
