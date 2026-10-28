# 5.3-Flash 空间流：shot ledger 与视觉证据账本

先读 `audiovisual-coding-framework.md`、`visual-observation-taxonomy.json` 和 `shot-ledger.schema.json`。

## 输入

- manifest 中实际附带的 2fps 全片帧与 shot-boundary keyframes；
- ASR 仅用于时间对齐，不得替代视觉；
- 本阶段不得读取既有最终理解作为视觉事实来源。

## 输出

1. `shot-ledgers/5.3-flash/{id}.json`：严格通过 `shot-ledger.schema.json`。
2. `visual-ledgers/5.3-flash/{id}.json`：只保存需要回收到 A1 的高价值空间事实及其 shot/event refs。

## 每个 shot 必扫

- 景别、角度、构图、前中后景、遮挡；
- 景深、焦点主体/焦点转移；
- 摄影机运动（静态帧不能断言运动）；
- 光线方向/软硬/对比/色温；
- 人物、食物、环境及其空间关系；
- 食物颜色、形状、表面、内部结构、动态可见状态；
- 花字及可读性。

## 食物观察规则

可写：油亮、哑光、焦边、皱缩、挂汁、断面颗粒、肥瘦分层、纤维、空腔、蒸汽、气泡、滴落、拉丝、碎裂、卷曲、按压形变。

不可写：香、甜、咸、软、脆、弹、好吃——除非明确标成口播，不得冒充视觉。

## 三层输出

- observable：客观事实；
- relation：与 episode/口播/前后 shot 的关系；
- interpretation：竞争解释+支持+限制，不能由构图或光线直接推出情绪/人格。

raw detector 只作定位，不进入最终 `[画面]`。OCR 与口播完全相同不算视觉语义增量。
