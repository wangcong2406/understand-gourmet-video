# 前置粗筛

> 纯文本判断，不占多模态成本。目的是省掉无效调用，并为每条选定 schema。
> **宁可多跑不可漏掉**——边界样本一律按"探店"处理。

---

## 三分类

| 类型 | 特征 | 处理 |
|------|------|------|
| **探店** | 有店铺、有菜品评价、通常有价格 | 完整 schema（`understand-prompt.md`） |
| **表态** | 无具体店铺，但有强观点表述（回应质疑、行业看法、方法论自述） | 简化 schema（`understand-prompt-statement.md`） |
| **无关** | 花絮、纯剧情段子、与餐饮判断无关的内容 | 排除，记入 prescreen.json 并注明原因 |

**表态类为什么不能一刀切掉**：它恰恰是价值观红线的最强证据。红线的确认阈值是"≥1次明确表态+行为一致"——这类视频就是明确表态本身。按"非探店"排除会丢掉四层中最容易拿到的那一层。

---

## 判据

对每份转写稿统计三个计数：

```
money = 匹配 "块钱|人均|一共|总共|多少钱" 的次数
dish  = 匹配 "好吃|难吃|味道|口感|火候|新鲜|食材|锅气|咸|甜|辣|香" 的次数
reco  = 匹配 "推荐|值不值|性价比|不值|划算" 的次数
```

**顺序很重要**——表态判据必须在探店判据之前，否则永远命中不了：

| 序 | 条件 | 判定 |
|:--:|------|------|
| 1 | `dish<8 且 money<2 且 reco>=2` | **表态** |
| 2 | `money>=3 且 dish>=10` | 探店（强） |
| 3 | `dish>=8 或 money>=2` | 探店（弱） |
| 4 | 其余 | **存疑 → 人工确认**，默认按探店处理 |

> ⚠️ 早期版本把"表态"放在探店之后判定，导致该分支**实跑 427 期命中 0 次**——
> 表态类视频里博主也会大量说"推荐""值不值"，`reco>=2` 早被前面的探店条件吃掉了。
> 表态的本质是**没有具体菜品和价格**，所以判据必须以 `dish` 和 `money` 双低为前提。

---

## 参考脚本

```python
import re, glob, json, os

SRC = '.'                       # 语料目录
PAT_MONEY = r'块钱|人均|一共|总共|多少钱'
PAT_DISH  = r'好吃|难吃|味道|口感|火候|新鲜|食材|锅气|咸|甜|辣|香'
PAT_RECO  = r'推荐|值不值|性价比|不值|划算'

out = []
for f in sorted(glob.glob(os.path.join(SRC, '*_audio_transcript.md'))):
    raw = open(f, encoding='utf-8').read()
    parts = raw.split('## 原始自动转写')
    body = parts[1] if len(parts) > 1 else parts[0]   # 用原始版：数字未被转成中文

    money = len(re.findall(PAT_MONEY, body))
    dish  = len(re.findall(PAT_DISH,  body))
    reco  = len(re.findall(PAT_RECO,  body))
    chars = len(re.sub(r'\s', '', body))

    # ⚠️ 表态判据必须在最前——放到探店之后会永远命中不了（实跑427期命中0次）
    if   dish < 8 and money < 2 and reco >= 2: t, conf = '表态', '中'
    elif money >= 3 and dish >= 10:            t, conf = '探店', '强'
    elif dish  >= 8 or  money >= 2:            t, conf = '探店', '弱'
    else:                                      t, conf = '探店', '存疑'   # 默认按探店，待人工确认

    out.append({
        'id': os.path.basename(f).replace('_audio_transcript.md', ''),
        'type': t, 'confidence': conf,
        'signals': {'money': money, 'dish': dish, 'reco': reco, 'chars': chars},
    })

json.dump(out, open(os.path.join(SRC, 'prescreen.json'), 'w'),
          ensure_ascii=False, indent=2)

from collections import Counter
print(Counter((o['type'], o['confidence']) for o in out))
print('存疑需人工确认：', [o['id'] for o in out if o['confidence'] == '存疑'])
```

---

## 人工确认

`confidence == '存疑'` 的条目须逐个看开场几句再定类型。经验上这类占约 5%，主要是三种：

- **夜市/市集多店逛吃** —— 有餐饮内容但无单一店铺。按探店处理，`shop_name` 填 `null`，`dishes` 照常记
- **剧情段子** —— 有对话表演成分（"老唐今儿咱吃什么呀"）。若后续进店则按探店，纯段子则排除
- **完全无关** —— 花絮、体验类非餐饮内容。排除

**注意转写稿的两个版本**：整理版把数字转成了中文（"一百八十九"），原始版保留阿拉伯数字但带空格（"1 8 9"）。粗筛与任何数字提取都应读 `## 原始自动转写` 之后的部分。
