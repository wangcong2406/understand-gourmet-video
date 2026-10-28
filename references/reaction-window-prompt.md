# 5.3-Flash 时间流：动作与微反应窗口

先读 `audiovisual-coding-framework.md`、`visual-observation-taxonomy.json` 和 `action-reaction.schema.json`。

## 采样要求

- 判断事件：前2–3秒至后3–5秒，连续视频或8fps密帧，单窗≤20秒。
- 微反应：只有脸清晰且对判断有价值时，2–5秒窗口目标25fps、最低15fps。
- 单帧永远不能证明动作、停顿、复尝、视线转移或反应变化。

## 动作编码

每个事件记录：actor、object/tool、onset、关键步骤/apex、offset、方向/轨迹、速度、幅度、次数、结果状态、遮挡/可见性。区分主体运动和摄影机运动。

## FACS-lite 客观编码

1. 先记录刺激前中性基线。
2. 只记录可见变化：眉、眼睑、视线、鼻、嘴角、嘴唇、下颌、头部、身体前倾/后撤、手部停顿/撤回等。
3. 记录 onset–apex–offset、持续时间、A_trace/B_slight/C_marked 强度、face_visibility。
4. 不直接输出“喜欢/厌恶/震惊”。解释必须并列支持与限制，并由明确口播、复尝、停吃、退菜等后续行动裁决。
5. 脸不可见/被切掉时写 visibility code；不能写无反应。

输出 `reaction-windows/5.3-flash/{id}.json`，严格通过 `action-reaction.schema.json`。证据不足写 `not_observable_from_sampled_frames`。
