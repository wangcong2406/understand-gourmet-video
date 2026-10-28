# 合并与分组

> 本文默认操作版本 `5.3-flash`；对应脚本默认 `--variant 5.3-flash`。读取旧根目录产物时显式使用 `--variant root`，不会跨版本自动回退。


> 纯脚本，不占多模态成本，**可反复重跑**——分组维度选错了随时能重切。
> 前提：全部子任务已完成（或已知哪些降级/失败）。

---

## 核心原则：只做物理拼接，不做语义压缩

合并阶段**绝不能**让模型读 N 份输出再写一份"总结"。

完整语料包必须保留 A1-A15 与 B1-B7，包括 A6 未定用途观察、判断事件、比较与转折、反应序列、三种注意力、推理链、表达DNA、原始感官措辞、品味谱系和开放解释。它们可以不进入默认统计，但不得在合并时删除；否则前置理解中的筛选失误将不可逆。标准标签只用于统计，不能替代原始措辞。

原因：主流程的 Phase 2 本身就是一次 reduce（N份 → 四层框架）。在它之前再做一次语义归并，等于**两级 reduce**，而第一级看不见全局——它做不了跨场景复现、预测力、排他性这三重验证（都需要全量视野），却已经替下游做了取舍。取舍错了不可逆。

**合并的价值在分组维度选得好，不在文件变少。** 物理拼接后 context 压力一点没减，但分组本身给了下游一副骨架。

丰富性与准入分离：某条信息若事实归属未定，应保留在 `open_interpretations` 或完整 Markdown 中并标注限制；只是不进入对应的稳定统计。禁止通过删除原始观察来让整条记录看起来更干净。

跨章节聚合以 `judgment_episodes[].episode_id` 为证据主键；A9–A15/B3–B7 的 `episode_refs` 是不同视角，不得把同一原话的重复出现计为多份独立证据。视觉统计按 `visual_status`/`evidence_level` 分层，`audio_timeline` 与 `editorial_inference` 不得混入直接视觉事实计数。

---

## Step 0：确认闸门已放行（v3 新增，前置条件）

```bash
python3 scripts/audit_richness.py --selftest
python3 scripts/audit_richness.py {语料目录}           # 先查遗漏；有 RICH_* 回视频补理解
python3 scripts/validate_corpus.py --selftest          # 再验证安全闸门自己
python3 scripts/validate_corpus.py {语料目录}
echo "exit=$?"      # 必须为 0
python3 scripts/validate_corpus.py {语料目录} --write-gate    # 落 quality_gate
```

⚠️ **`--write-gate` 不能省**：Step 1 的准入要读 `quality_gate.validated_at`，
而这个键只有 `--write-gate` 会写。（v3 的 `build_gate()` 压根不输出它，
导致零 BLOCK 的记录也被拒收——若在旧产出上撞到这个死循环，重跑一次即可。）

**退出码非 0 时不要开始合并。** 合并是不可逆的信息固化：
带 BLOCK 的记录一旦并进 `corpus-index.5.3-flash.json`，
下游 Phase 2 就无法区分它和干净记录，缺陷会永久留在专家画像里。

---

## Step 1：汇总 corpus-index.5.3-flash.json

把 `data/5.3-flash/*.json` 合并成一张表。**只收闸门放行的记录。**

```python
import json, glob, os
from collections import Counter

rows, rejected = [], []
for f in sorted(glob.glob('data/5.3-flash/*.json')):
    d = json.load(open(f, encoding='utf-8'))
    d = {k: v for k, v in d.items() if not k.startswith('_comment')}

    # ── 闸门准入：四个条件都要满足 ──
    # 第 4 条（content_type 白名单）是防御性的：理论上 无关/失败 的记录
    # 不会同时是 完整，但准入是不可逆的信息固化，多一道显式排除成本为零。
    gate = d.get('quality_gate') or {}
    ok = (d.get('processing_status') == '完整'
          and not gate.get('blocking_issues')
          and gate.get('validated_at')
          and d.get('content_type') in ('探店', '表态'))
    if not ok:
        rejected.append((d.get('id'), d.get('processing_status'),
                         len(gate.get('blocking_issues') or []),
                         '无 quality_gate' if not gate else ''))
        continue
    rows.append(d)

json.dump(rows, open('corpus-index.5.3-flash.json', 'w'), ensure_ascii=False, indent=2)

print('纳入', len(rows), ' 拒收', len(rejected))
for r in rejected:
    print('  拒收', r)
print('类型', Counter(r['content_type'] for r in rows))
print('品类', Counter(r.get('_meta', {}).get('cuisine') for r in rows).most_common())
```

⚠️ **拒收不是丢弃**：被拒的记录仍在 `data/5.3-flash/` 里，修订后重跑本脚本即可纳入。
但**不要为了让数量好看而放宽准入**——`quality_gate` 缺失也算不合格，
因为"没跑过闸门"和"跑了没通过"对下游是同一件事：都无法保证内容正确。

> 为什么把准入放在 Step 1 而不是靠人记得：v2 的十份产出全部有 BLOCK，
> 若合并脚本不设门，它们会被静默全量纳入——脚本不报错，人也看不出来。

**校验**：字段是否齐全（缺失字段会使表列对不齐）、品类取值是否都在菜系级清单内、`price_total` 与 `price_per_person` 是否都有值。

### ⚠️ 跨期统计必须排除 `model_inference`（v4.6 新增）

`output-schema.md` 纪律二写明 `model_inference` 条目"不得进入
`candidate_patterns`、价值观**与跨期统计**"。前两条闸门已强制
（`B1_MODEL_INFERENCE` / `VALUES_MODEL_INFERENCE`），**第三条落在这里**——
闸门管不到合并脚本怎么用数据，只能靠这一步自觉。

做标签频次、情感分布、维度权重这类跨期聚合时，先滤掉模型推断：

```python
def blogger_only(dishes):
    """跨期统计只用博主自己的判断。模型推断保留在明细里可回查，但不参与计数。"""
    return [x for x in (dishes or [])
            if x.get('source_type') in ('blogger_explicit', 'blogger_hypothesis',
                                        'externally_verified')]

# 例：标签频次
from collections import Counter
tag_freq = Counter(t for row in rows
                     for x in blogger_only(row.get('dishes'))
                     for t in (x.get('standard_tags') or []))
```

**不滤会怎样**：模型补的"疑似预制菜"会和博主亲口说的混在同一个计数里，
下游看到"该专家 30% 的负面评价指向预制菜"——而其中一半是我们自己写进去的。
这类污染在合并后**不可追溯**，因为聚合结果里已经不带 `source_type` 了。

**新增字段的批量体检**——新字段最典型的失效方式是"整批漏填"，而单看某一份不易发现：

```python
REQUIRED_DISH = ['name','object_level','price','sentiment','intensity','reason',
                 'standard_tags','tag_qualifier','blogger_attribution',
                 'source_type','scope','scope_quote',
                 'evidence_source','confidence','quote','timestamp',
                 'shot_duration_sec','has_caption']   # v3：18 个字段

miss = Counter()
noquote = []
for r in rows:
    for d in (r.get('dishes') or []):
        for k in REQUIRED_DISH:
            if k not in d:
                miss[k] += 1
        if not d.get('quote'):
            noquote.append(f"{r['id']}/{d.get('name')}")
    for e in (r.get('dimension_events') or []):
        for k in ['evidence_source','source_type','scope','intensity']:
            if k not in e:
                miss[f'event.{k}'] += 1

print('缺失字段计数:', dict(miss))
print('无原话的菜:', len(noquote), noquote[:10])
print('无 price_check:', [r['id'] for r in rows if not r.get('price_check')])
```

⚠️ **`quote` 缺失要当作阻塞项**，不是提醒。下游提取表达DNA 只读 json；
原话缺了，那条记录在表达DNA 用途上等于不存在，且不会报错。

---

## Step 2：按品类切分

### 切分规则

**品类一层切分，价格带作为组内排序字段。**

不做二级切分。实测品类分布通常较均匀（最大品类约占全量 12%），再按价格带二次切会把中等组切成十几期的小组，反而削弱组内对比强度。**若某品类确实过大（>全量 20%），再考虑二级切分。**

| 规则 | 说明 |
|------|------|
| 粒度 | 菜系级（本帮菜/川菜/粤菜/日料/火锅/烧烤/西餐/面食小吃/…） |
| 小组合并 | 组内 <5 期的品类合并进 `其他-地方菜系`。摸底实测仅湘菜(3)、东南亚(2) 需合并 |
| 组内排序 | **按人均升序**——同品类不同价位的标准差异读得出来，且不切碎样本 |
| 城市 | **不参与切分**，仅作字段 |

### 为什么城市不参与切分

探店类专家的城市分布通常极度倾斜（实测某专家常驻城市占 34%，其余 40+ 城市多数仅 1-3 期），除常驻城市外没有任何城市样本量够做对比。

可行的在地性分析只有 **"常驻城市 vs 其余"** 这一组对照——作为专门的分析角度，不作为分组维度。

### 参考脚本

```python
import json, os
from collections import defaultdict, Counter

rows = json.load(open('corpus-index.5.3-flash.json', encoding='utf-8'))
# 只对探店类分组——表态类无 _meta 店铺字段，单独成组
tan  = [r for r in rows if r.get('content_type') == '探店' and r.get('_meta')]
stmt = [r for r in rows if r.get('content_type') == '表态']
skipped = [r['id'] for r in rows
           if r.get('content_type') == '探店' and not r.get('_meta')]
if skipped:
    print(f'⚠️ 探店类但缺 _meta，已跳过：{skipped}')

cnt = Counter(r['_meta'].get('cuisine') or '未标注' for r in tan)
SMALL = {c for c, n in cnt.items() if n < 5}

groups = defaultdict(list)
for r in tan:
    c = r['_meta'].get('cuisine') or '未标注'
    groups['其他-地方菜系' if c in SMALL else c].append(r)

os.makedirs('grouped/5.3-flash', exist_ok=True)
for name, items in groups.items():
    # 组内按人均升序——支撑"同品类不同价位的标准差异"
    items.sort(key=lambda r: r['_meta'].get('price_per_person') or 0)

    parts = [f'# {name}（{len(items)} 期）\n',
             '> 组内按人均升序排列。提炼层拼接，未做任何语义压缩。\n',
             '## 索引\n',
             '| 编号 | 店名 | 城市 | 人均 | 结论 |',
             '|------|------|------|------|------|']
    for r in items:
        m = r['_meta']
        pc = r.get('price_check') or {}
        # 价格存疑要在分组文件里可见——否则只有翻 json 才知道这期价格不可信
        flag = ' ⚠️价格存疑' if pc.get('consistent') is False or pc.get('is_estimated') else ''
        parts.append(f"| {r['id']} | {m.get('shop_name')} | {m.get('city')} | "
                     f"{m.get('price_per_person')}{flag} | "
                     f"{(r.get('d1_flavor') or {}).get('overall')} |")
    parts.append('\n---\n')

    missing = []
    for r in items:
        p = f"understanding/5.3-flash/{r['id']}.md"
        if not os.path.exists(p):
            missing.append(r['id']); continue
        md = open(p, encoding='utf-8').read()
        # 丰富性优先：拼接完整单期理解，不再只抽 B 区。
        # A9-A15 的判断过程与 A6 暂未归位观察是下游无法重建的一手信息。
        parts.append(f"\n\n{'='*60}\n## {r['id']} · {r['_meta'].get('shop_name')}"
                     f"（{r['_meta'].get('city')}，人均{r['_meta'].get('price_per_person')}）\n")
        parts.append(md)

    if missing:
        print(f'  ⚠️ {name}: 异常条目 {missing}')
    open(f'grouped/5.3-flash/{name}.md', 'w', encoding='utf-8').write('\n'.join(parts))

print('分组完成:', {k: len(v) for k, v in sorted(groups.items(), key=lambda x: -len(x[1]))})
print(f'表态类 {len(stmt)} 条另存 grouped/5.3-flash/_表态.md')
```

表态类不参与品类分组（无店铺无菜品），单独拼成 `grouped/5.3-flash/_表态.md` 即可——
下游提取价值观与表达 DNA 时整体读一遍。

### ⚠️ 完整语料是默认交付，提炼层抽取仅作可选视图

默认 grouped 文件拼接完整 Markdown，不再只抽 B 区。若特定下游为节省上下文需要生成
“仅提炼层”派生视图，`extract_section_b` 不能靠**精确匹配标题字符串**。实测 10 份产出里
有 5 份把标题写成了 `## C. ASR纠错清单`（无空格），与 prompt 模板的
`## C. ASR 纠错清单`（有空格）不符——若用 `md.split('## C. ASR 纠错清单')`
精确切分，这 5 份会**静默地把 C 区一起并进提炼层**，且不报错。

可选视图用正则容错，并对异常出声；该视图不能覆盖完整语料：

```python
import re

def extract_section_b(md):
    """抽取 B 提炼层。返回 (正文, 警告)。标题空格/全半角差异均容错。"""
    mb = re.search(r'^##\s*B[\.、]?\s*提炼层.*$', md, re.M)
    if not mb:
        return md, 'B区标题未找到，已回退为全文'
    mc = re.search(r'^##\s*C[\.、]?\s*ASR\s*纠错清单.*$', md[mb.end():], re.M)
    body = md[mb.start(): mb.end() + mc.start()] if mc else md[mb.start():]
    return body, (None if mc else 'C区标题未找到，B区可能含多余内容')
```

**通用原则**：所有依赖 md 标题定位的脚本都要用正则 + 缺失告警，
不要用 `split('精确字符串')`。模型输出的标题空格不稳定，静默失效比报错更危险。

---

## Step 3：交付前校验

| 检查项 | 标准 |
|--------|------|
| `understanding/5.3-flash/` 文件数 | = 粗筛后待处理数 −（失败数） |
| `data/5.3-flash/` 文件数 | 同上 |
| `corpus-index.5.3-flash.json` | 字段齐全，无列对不齐 |
| `grouped/5.3-flash/` 组数 | 与实际品类数相符，无 <5 期的小组（应已合并进"其他-地方菜系"） |
| 降级/失败条目 | 已在 `progress.md` 中登记 |

---

## 重切分组

分组是纯脚本产物，**换维度直接删掉 `grouped/5.3-flash/` 重跑即可**，不影响 `understanding/5.3-flash/` 与 `data/5.3-flash/`。

可选的其他分组维度（视下游需要）：

| 维度 | 用途 | 可行性 |
|------|------|--------|
| 品类（默认） | 三重验证第一重「跨场景复现」 | ✅ 分布均匀 |
| 价格带 | 内在张力（对高端与市井的标准差异） | ✅ 中间段厚实 |
| 时间序（编号即时序） | 时间衰减、演化信号识别 | ✅ 零成本 |
| 城市 | 在地差异 | ❌ 除北京外样本不足 |
| 结论倾向 | 好评组 vs 差评组的判据对比 | ✅ 可做 |
