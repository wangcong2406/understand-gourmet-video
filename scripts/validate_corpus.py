#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
输出后验证闸门（Step 3.5）——只读取已生成的产出，按硬规则机械判定。

设计前提：第一轮生成时模型认为自己已经合规了（实测 0007 加了"推测"两字、
把归因挪进 blogger_attribution，自检清单全部打勾，但"保水剂/碱发"三个词
在转写稿里一次都没出现）。所以闸门不能是"让模型再看一遍自己的输出"，
必须是外部的、机械的、能对着转写稿溯源的。

用法：
    python3 scripts/validate_corpus.py <语料目录>
    python3 scripts/validate_corpus.py <语料目录> --id 0007      # 单期
    python3 scripts/validate_corpus.py <语料目录> --json         # 机器可读
    python3 scripts/validate_corpus.py <语料目录> --write-gate   # 回写 quality_gate

退出码：0 = 无 BLOCK；1 = 有 BLOCK；2 = 用法/环境错误。

BLOCK 项一律禁止 processing_status: 完整（须写 完成待修订）。
WARN 项不阻塞，但要在交付说明里列出。
"""

import argparse, datetime, json, os, re, subprocess, sys, unicodedata
from collections import Counter, defaultdict
from output_paths import DEFAULT_VARIANT, output_dir, output_file, validate_variant

VALIDATOR_VERSION = 'v5.3-flash.1'

# --verbose：显示默认静默的低价值 WARN（如合法的拼接引用）
VERBOSE = False

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(os.path.dirname(HERE), 'references')


def load_ref(name):
    p = os.path.join(REF, name)
    if not os.path.exists(p):
        sys.exit(f"[环境错误] 缺少 {p}")
    with open(p, encoding='utf-8') as f:
        return json.load(f)


ENUM = load_ref('enums.json')
TAGDICT = load_ref('tag-dictionary.json')

# 加载期一致性断言（v4.5）。v3 曾刻意让 dishes 用五级、A 档用六级，
# 实测是最高产的枚举错误（46 条越界里 7 条），v4 已统一。两个键名保留是为了
# 兼容既有字段引用，但取值必须相同——否则五级/六级分叉会静默回归，
# 而这次不会有人记得当年为什么统一。单一事实源要能自证一致。
if ENUM['sentiment_dish'] != ENUM['assessment_dimension']:
    sys.exit('[环境错误] enums.json 的 sentiment_dish 与 assessment_dimension '
             '取值必须完全相同（v4 起统一为六级，含「有保留」）。\n'
             f'  sentiment_dish       = {ENUM["sentiment_dish"]}\n'
             f'  assessment_dimension = {ENUM["assessment_dimension"]}')

# ── 工具 ──────────────────────────────────────────────────────────────

PUNCT_RE = re.compile(r'[\s，。、！？；：""''（）()\[\]【】…—\-~·,.!?;:\'"]+')


def normalize(s):
    """溯源比对用的归一化：全角→半角、去标点空白、小写。

    ASR 转写稿与 quote 之间常有标点/空格差异（"1 8 9" vs "189"、
    整理版把数字转成中文），逐字 in 判定会误报，故先归一化。
    """
    if not s:
        return ''
    s = unicodedata.normalize('NFKC', str(s))
    return PUNCT_RE.sub('', s).lower()


def ts_to_sec(ts):
    """MM:SS → 秒。失败返回 None。"""
    m = re.match(r'^(\d{1,3}):(\d{2}(?:\.\d+)?)$', ts.strip())
    if not m:
        return None
    return int(m.group(1)) * 60 + float(m.group(2))


def parse_range(s):
    """'MM:SS-MM:SS' → (start, end)。失败返回 None。"""
    if not isinstance(s, str):
        return None
    parts = re.split(r'\s*[-–~]\s*', s.strip())
    if len(parts) != 2:
        return None
    a, b = ts_to_sec(parts[0]), ts_to_sec(parts[1])
    if a is None or b is None or b < a:
        return None
    return (a, b)


def has_paren(s):
    return bool(re.search(r'[()（）]', str(s)))


def forbidden_hits(text):
    """命中的禁用表述，最长词优先去重（v4.5）。

    禁用表是子串匹配，`核心标尺` 会同时命中 `核心标尺` 与 `标尺`——
    同一处问题报两条，不漏检但让问题总数虚高，也让人误判严重程度。
    这里只保留最长的那个：短词被长词完全覆盖时丢弃。
    """
    if not text:
        return []
    hits = [t for t in ENUM['forbidden_pattern_phrases'] if t in str(text)]
    return [t for t in hits
            if not any(o != t and t in o and o in hits for o in hits)]


def pattern_text(p):
    """候选规律的陈述文本。

    ⚠️ v3 的 bug 就在这里：schema.md 与 understand-prompt.md 都用 `pattern`，
    而校验器读的是 `p.get('statement')` —— 于是 B1_FORBIDDEN_PHRASE 与
    CAUSAL_IN_HYPOTHESIS 对候选规律**从未生效过**。实测把
    `"pattern": "他普遍厌恶技术处理牛肉，是标志性偏好"` 喂进去一声不响，
    而"从单期偷渡稳定偏好"恰恰是 B1 这套约束唯一要防的事。
    两个键名都接受，以 pattern 为正名。
    """
    return p.get('pattern') or p.get('statement') or ''


def asr_corrected_terms(md_text):
    """从 C 区纠错表提取「纠正后」列的值。

    为什么必须做：enums.json 的注释早就写明「ASR 纠错后的『纠正后』值命中时
    也算博主说过」，但 v3 没实现这条。实测 0001 转写稿里是「剪发」
    （"剪发它就能到这么大"），C 区已判定纠正为「碱发」，结果 6 处
    TECH_TERM_NOT_SPOKEN 全被误报——连 C 区纠错表自己那一行都被拦。
    ASR 纠错是本 skill 的核心能力之一，校验器不认它等于自废武功。
    """
    if not md_text:
        return ''
    m = re.search(r'##\s*C\.\s*ASR\s*纠错清单\s*\n(.*?)(?=\n##|\Z)', md_text, re.S)
    if not m:
        return ''
    out, col = [], None
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line.startswith('|') or '---' in line:
            continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        # 按表头定位「纠正后」列，不要写死列号：prompt 模板是
        # | 原转写 | 纠正后 | 依据类型 | 置信度 |（4 列），
        # 实跑产出却是 | 序号 | 原始识别 | 纠正后 | 依据 | 置信度 |（5 列）。
        # v4 初版写死 cells[1] 取到的是「原始识别」，等于没修。
        if col is None:
            for j, c in enumerate(cells):
                if '纠正' in c:
                    col = j
                    break
            if col is not None:
                continue                # 这行是表头
            col = 1 if len(cells) <= 4 else 2      # 无表头时的兜底
        if col < len(cells) and cells[col]:
            out.append(cells[col])
    return ' '.join(out)


class Report:
    def __init__(self, vid):
        self.id = vid
        self.items = []          # (level, code, msg)

    def block(self, code, msg):
        self.items.append(('BLOCK', code, msg))

    def warn(self, code, msg):
        self.items.append(('WARN', code, msg))

    @property
    def blocks(self):
        return [i for i in self.items if i[0] == 'BLOCK']

    @property
    def warns(self):
        return [i for i in self.items if i[0] == 'WARN']

    def codes(self, level=None):
        return sorted({c for lv, c, _ in self.items if level is None or lv == level})


# ── 各项检查 ──────────────────────────────────────────────────────────

def check_enums(d, r):
    """C-ENUM：枚举值逐字比对。v2 实测 dishes 12/64、events 13/56 越界。"""
    def chk(val, key, where, allow_none=False):
        if val is None:
            if not allow_none:
                r.block('ENUM_NULL', f'{where}.{key} 为 null（该字段不可空）')
            return
        if val not in ENUM[key]:
            r.block('ENUM_INVALID',
                    f'{where}.{key} = {val!r} 不在枚举内，合法值：{ENUM[key]}')

    chk(d.get('content_type'), 'content_type', 'root')
    chk(d.get('processing_status'), 'processing_status', 'root')

    meta = d.get('_meta') or {}
    if d.get('content_type') == '探店':
        for k in ('shop_tier', 'price_tier', 'cuisine'):
            if meta.get(k) is not None:
                chk(meta.get(k), k, '_meta')

    for i, dish in enumerate(d.get('dishes') or []):
        w = f'dishes[{i}]({dish.get("name")})'
        chk(dish.get('sentiment'), 'sentiment_dish', w)
        chk(dish.get('object_level'), 'object_level', w)
        chk(dish.get('intensity'), 'intensity', w)
        chk(dish.get('source_type'), 'source_type', w)
        chk(dish.get('evidence_source'), 'evidence_source', w)
        chk(dish.get('confidence'), 'confidence', w)
        sc = dish.get('scope')
        if isinstance(sc, dict):
            chk(sc.get('value'), 'scope', w + '.scope')
        else:
            chk(sc, 'scope', w)

    for i, e in enumerate(d.get('dimension_events') or []):
        w = f'dimension_events[{i}]'
        chk(e.get('dimension'), 'dimension', w)
        chk(e.get('reaction_type'), 'reaction_type', w)
        chk(e.get('intensity'), 'intensity', w)
        chk(e.get('source_type'), 'source_type', w)
        chk(e.get('evidence_source'), 'evidence_source', w)
        sc = e.get('scope')
        if isinstance(sc, dict):
            chk(sc.get('value'), 'scope', w + '.scope')
        else:
            chk(sc, 'scope', w)

    for i, p in enumerate(d.get('candidate_patterns') or []):
        w = f'candidate_patterns[{i}]'
        chk(p.get('source_type'), 'source_type', w)
        sc = p.get('scope')
        if isinstance(sc, dict):
            chk(sc.get('value'), 'scope', w + '.scope')
        elif sc is not None:
            chk(sc, 'scope', w)

    for i, v in enumerate(d.get('values_triggered') or []):
        w = f'values_triggered[{i}]'
        chk(v.get('value_type'), 'value_type', w)
        chk(v.get('source_type'), 'source_type', w)
        chk(v.get('evidence_source'), 'evidence_source', w)
        # ★ 与 B1 同理的收窄枚举（v4.6）。values_triggered 是下游直接吸收的
        # 价值观/红线事实源，而红线按防抖阈值「≥1次明确表态+行为一致」**单期即可确认**
        # ——没有 not_stable_rule 那样的免责声明，也不需要跨期验证。
        # 所以模型推断混进来的污染比 B1 更严重：B1 的猜测下游至少知道要再验，
        # 红线的猜测会直接成为专家画像里的"他绝不接受 X"。
        if v.get('source_type') == 'model_inference':
            r.block('VALUES_MODEL_INFERENCE',
                    f'{w}.source_type=model_inference，value_type='
                    f'{v.get("value_type")!r} → 价值观/红线只接受 '
                    f'blogger_explicit / blogger_hypothesis（须有可回查原话）。'
                    f'红线单期即可确认、无免责声明，模型推断进来会直接成为'
                    f'专家画像的一部分。请移入 B7 开放解释与竞争性解释')


def check_required_fields(d, r):
    """C-FIELD：必填字段。空值填 null 不算缺失，键不存在才算。"""
    REQUIRED_DISH = ['name', 'object_level', 'price', 'sentiment', 'intensity',
                     'reason', 'standard_tags', 'tag_qualifier',
                     'blogger_attribution',
                     'source_type', 'scope', 'scope_quote',
                     'evidence_source', 'confidence',
                     'quote', 'timestamp', 'shot_duration_sec', 'has_caption']
    # v3 新增字段：旧批次必然没有，缺失只提醒不阻塞——否则 128 条噪音会盖住真问题。
    # 但它们各自的语义检查照常 BLOCK：scope 升级了却没 scope_quote 仍然拦，
    # 标签带括号仍然拦。缺字段是格式债，填错值才是事实错误。
    V3_NEW = {'tag_qualifier', 'scope_quote'}
    for i, dish in enumerate(d.get('dishes') or []):
        for k in REQUIRED_DISH:
            if k in dish:
                continue
            if k in V3_NEW:
                r.warn('FIELD_MISSING_V3',
                       f'dishes[{i}]({dish.get("name")}) 缺 v3 新字段 {k}')
            else:
                r.block('FIELD_MISSING', f'dishes[{i}]({dish.get("name")}) 缺字段 {k}')
        if not dish.get('quote'):
            r.block('QUOTE_MISSING',
                    f'dishes[{i}]({dish.get("name")}) quote 为空——下游提表达DNA 唯一来源')

    for i, e in enumerate(d.get('dimension_events') or []):
        for k in ['dimension', 'event', 'reaction_type', 'intensity',
                  'source_type', 'scope', 'evidence_source', 'quote', 'timestamp']:
            if k not in e:
                r.block('FIELD_MISSING', f'dimension_events[{i}] 缺字段 {k}')

    if d.get('content_type') == '探店' and not d.get('price_check'):
        r.block('FIELD_MISSING', 'price_check 对象缺失（A5 必做）')


def check_causality(d, r):
    """C-CAUSAL：推测不得写成确定归因。

    只查 blogger_hypothesis / model_inference。blogger_explicit 与
    externally_verified 里出现"导致"往往是合法的工艺描述，不拦。
    """
    bad_types = {'blogger_hypothesis', 'model_inference'}
    terms = ENUM['forbidden_causality']

    def scan(text, where):
        if not text:
            return
        hit = [t for t in terms if t in str(text)]
        if hit:
            r.block('CAUSAL_IN_HYPOTHESIS',
                    f'{where} source_type 为推测类，但文本含确定归因词 {hit}：'
                    f'{str(text)[:60]}…  → 改写为「博主推测可能与X有关」')

    for i, dish in enumerate(d.get('dishes') or []):
        if dish.get('source_type') in bad_types:
            scan(dish.get('reason'), f'dishes[{i}]({dish.get("name")}).reason')
    for i, e in enumerate(d.get('dimension_events') or []):
        if e.get('source_type') in bad_types:
            scan(e.get('description'), f'dimension_events[{i}].description')
    for i, p in enumerate(d.get('candidate_patterns') or []):
        if p.get('source_type') in bad_types:
            scan(pattern_text(p), f'candidate_patterns[{i}].pattern')


def check_scope_upgrade(d, r, transcript_norm=None):
    """C-SCOPE：非 this_serving 必须有博主原话支撑，且原话须能在转写稿命中。

    v3 的 docstring 就写着"须能在转写稿命中"，但实现只检查了非空——
    模型编一句"他们家每次都这样"塞进 scope_quote 就能给升级背书，
    而这正是 scope_quote 这个字段唯一要防的事。v4 补上溯源。
    """
    need = set(ENUM['scope_requires_quote'])

    def one(scope_val, quote, where):
        if scope_val not in need:
            return
        if not quote:
            r.block('SCOPE_UPGRADE_NO_QUOTE',
                    f'{where} scope={scope_val} 但无 scope_quote/upgrade_evidence'
                    f' → 校验器判定应降级为 this_serving')
            return
        if not transcript_norm:
            return
        # 与 quote 溯源同一套归一化。分句级判定：允许省略号拼接，不允许改字。
        frags = [f for f in re.split(r'[；;…，,、。]|\.{3}', str(quote))
                 if len(normalize(f)) >= 4]
        if not frags:
            return
        missing = [f for f in frags if normalize(f) not in transcript_norm]
        if missing:
            r.block('SCOPE_QUOTE_NOT_IN_TRANSCRIPT',
                    f'{where} scope={scope_val}，但 scope_quote 在转写稿中查不到：'
                    f'{missing[0].strip()[:40]} → 升级依据是编的，'
                    f'应退回 this_serving。范围必须由博主的话撑起来，'
                    f'不能由模型的常识撑起来')

    for i, dish in enumerate(d.get('dishes') or []):
        sc = dish.get('scope')
        w = f'dishes[{i}]({dish.get("name")})'
        if isinstance(sc, dict):
            one(sc.get('value'), sc.get('upgrade_evidence'), w)
        else:
            one(sc, dish.get('scope_quote'), w)
    for i, e in enumerate(d.get('dimension_events') or []):
        sc = e.get('scope')
        w = f'dimension_events[{i}]'
        if isinstance(sc, dict):
            one(sc.get('value'), sc.get('upgrade_evidence'), w)
        else:
            one(sc, e.get('scope_quote'), w)
    for i, p in enumerate(d.get('candidate_patterns') or []):
        sc = p.get('scope')
        w = f'candidate_patterns[{i}]'
        if isinstance(sc, dict):
            one(sc.get('value'), sc.get('upgrade_evidence'), w)
        else:
            one(sc, p.get('scope_quote'), w)


def check_quote_traceable(d, r, transcript_norm):
    """C-TRACE：★ 最能拦住实际回归的一条。

    凡 source_type 为 blogger_* 的条目，quote 必须是转写稿的子串（归一化后）。
    实测 0007 把"保水剂/碱发"写成博主推测，而这两个词在转写稿里
    一次都没出现——这条检查能一次性抓出全部 7 个位置。
    """
    if not transcript_norm:
        r.warn('TRACE_NO_TRANSCRIPT', '未找到转写稿，跳过 quote 溯源与技术归因检查')
        return

    blogger = {'blogger_explicit', 'blogger_hypothesis'}

    def one(q, st, where):
        if st not in blogger or not q:
            return
        # quote 常把多个不相邻段落用 ；/… 拼接。逐片段溯源：
        # 全部命中 → 只是拼接（WARN）；有片段落空 → 重述或归因错位（BLOCK）。
        frags = [f for f in re.split(r'[；;…]|\.{3}|/', str(q)) if len(normalize(f)) >= 6]
        if not frags:
            return                      # 太短易误判，交人工
        missing = [f for f in frags if normalize(f) not in transcript_norm]
        if not missing:
            # v4.3：拼接引用**默认静默**。它本身是合法写法（schema 明确允许，
            # 只记一条 WARN），但实测 10 期报了 16 条，占全部问题的 12%,
            # 纯噪音且会盖住真问题。只有拼得特别碎（≥4 段）才提示——
            # 那时确实该拆成多条了。`--verbose` 可看全部。
            if len(frags) >= 4 or VERBOSE:
                r.warn('QUOTE_COMPOSITE',
                       f'{where} quote 由 {len(frags)} 段拼接（含 ；/…）。'
                       f'各段均可溯源，但下游按单一区间回查会对不上'
                       f' → 宜拆为多条或只留主区间原话')
            return

        # 二次判定：逗号级切分后每个分句都能溯源 ⇒ 只是中间省略了分句而未标 `…`，
        # 词汇指纹完好，降为 WARN。实测 10 条 BLOCK 里 2 条属此类
        # （0004 狮子头、0006 小笼），8 条是真改写（`吱嘎吱`→`吱嘎吱嘎`、
        # `有点儿像叉烧`凭空多出）。不区分这两者会让真问题淹在噪音里。
        subs = [s for s in re.split(r'[，,、。！？!?]', str(q)) if len(normalize(s)) >= 4]
        bad = [s for s in subs if normalize(s) not in transcript_norm]
        if subs and not bad:
            r.warn('QUOTE_ELIDED',
                   f'{where} quote 各分句均可溯源，但整段连读对不上'
                   f' → 中间省略了分句却未标 `…`。补省略号即可，词汇指纹未受损')
            return

        r.block('QUOTE_NOT_IN_TRANSCRIPT',
                f'{where} source_type={st} 但 quote 在转写稿中找不到，'
                f'落空分句：{(bad or missing)[0].strip()[:40]}'
                f' → 要么是重述/改字（须逐字），要么归因错位（应为 model_inference）')

    for i, dish in enumerate(d.get('dishes') or []):
        one(dish.get('quote'), dish.get('source_type'),
            f'dishes[{i}]({dish.get("name")})')
    for i, e in enumerate(d.get('dimension_events') or []):
        one(e.get('quote'), e.get('source_type'), f'dimension_events[{i}]')
    for i, p in enumerate(d.get('candidate_patterns') or []):
        one(p.get('quote'), p.get('source_type'), f'candidate_patterns[{i}]')
    for i, v in enumerate(d.get('values_triggered') or []):
        one(v.get('quote'), v.get('source_type'), f'values_triggered[{i}]')


def check_technical_attribution(d, md_text, r, transcript_norm):
    """C-TECH：禁止把餐饮技术结论补写成博主判断。

    规则：文件里出现工艺/添加物词 → 转写稿必须也出现该词，否则 FAIL。
    这是纯机械判定，且完全对症——0007 的 7 处会全部命中。
    """
    if not transcript_norm:
        return
    terms = ENUM['technical_attribution_terms']
    absent = [t for t in terms if normalize(t) not in transcript_norm]
    if not absent:
        return

    blogger = {'blogger_explicit', 'blogger_hypothesis'}

    def scan(text, where, st=None):
        if not text:
            return
        s = str(text)
        hit = [t for t in absent if t in s]
        if not hit:
            return
        if st is None or st in blogger:
            r.block('TECH_TERM_NOT_SPOKEN',
                    f'{where} 出现工艺归因词 {hit}，但转写稿中博主从未说出该词'
                    f' → 只能另起一条 model_inference，不得署名博主')

    for i, dish in enumerate(d.get('dishes') or []):
        w = f'dishes[{i}]({dish.get("name")})'
        st = dish.get('source_type')
        scan(dish.get('blogger_attribution'), w + '.blogger_attribution', st)
        scan(dish.get('reason'), w + '.reason', st)
        scan(' '.join(map(str, dish.get('standard_tags') or [])),
             w + '.standard_tags', st)
    for i, e in enumerate(d.get('dimension_events') or []):
        scan(e.get('description'), f'dimension_events[{i}].description',
             e.get('source_type'))
    for i, p in enumerate(d.get('candidate_patterns') or []):
        scan(pattern_text(p), f'candidate_patterns[{i}].pattern',
             p.get('source_type'))

    if md_text:
        for t in absent:
            for m in re.finditer(re.escape(t), md_text):
                line_no = md_text[:m.start()].count('\n') + 1
                line = md_text.splitlines()[line_no - 1].strip()
                # [推断]/model_inference 是豁免通道，但不是无条件的（v4.4 收紧）：
                # 该行必须同时说清「这个词不是博主说的」。
                # 实测 0001 L72「"剪发"=碱发/化学发制海参，博主将异味归因于
                # 原料处理方式」——标了 [推断] 就过关，但它把等式写成了确定的
                # （`=`），还替博主把归因扩写成"原料处理方式"。
                # 对比 0007 L131 是合规写法：明写"博主只表达不对劲这个感受，
                # 未说碱发/保水剂——不得将模型的化学知识署名给博主"。
                # 判据：出现"博主未说/没说/未明说/不得署名/非博主"这类界定，
                # 或把词包在"可能/疑似"里，才算真的划清了界限。
                if '[推断]' in line or 'model_inference' in line:
                    disclaims = re.search(
                        r'未说|没说|未明说|未提及|不得署名|非博主|不是博主|'
                        r'模型(推断|假设|补充)|待外部验证|无外部验证', line)
                    hedged = re.search(r'可能|疑似|或许|不排除', line)
                    if disclaims or hedged:
                        continue
                    r.block('TECH_TERM_INFERENCE_UNHEDGED',
                            f'md L{line_no} [推断] 行出现工艺词 {t!r}'
                            f'（转写稿无此词），虽标了 [推断] 但未划清界限：'
                            f'{line[:70]} → 须明写"博主未说过该词"或加"可能/疑似"，'
                            f'否则读起来仍像已确认的归因')
                    continue
                # 否定句不是归因。实测 0004「本期无明显价值观触发……未涉及食品安全、
                # 餐饮行业规范、添加剂等议题」被判违规——它恰恰是在说没有这回事。
                if re.search(r'未涉及|未提及|不涉及|未出现|没有提到|无明显', line):
                    continue
                # 同理，「待验证：后续是否明确说出具体归因（如保水剂/碱发等）」
                # 是在说博主**尚未**说出这些词，属于正确的边界声明而非归因。
                # v4.6 实测 0007 L322 被误判——这类元讨论恰恰是我们希望看到的写法。
                if re.search(r'待验证|是否明确说出|是否说出|尚未|后续是否', line):
                    continue
                r.block('TECH_TERM_NOT_SPOKEN',
                        f'md L{line_no} 出现 {t!r}（转写稿无此词）且未标 [推断]/'
                        f'model_inference：{line[:70]}')


def check_atomic_layers(d, r):
    """C-ATOM：一条评价事件只能有一个认知层级。

    实测 0010 一条 dishes 记录同时装了博主明确感受、博主推测、模型补充，
    这天然诱发归属串位。model_inference 必须独立成条。
    """
    for i, dish in enumerate(d.get('dishes') or []):
        st = dish.get('source_type')
        w = f'dishes[{i}]({dish.get("name")})'
        if st == 'model_inference' and dish.get('blogger_attribution'):
            r.block('LAYER_MIXED',
                    f'{w} source_type=model_inference 却填了 blogger_attribution'
                    f' → 模型推断不得携带博主归因')
        if st in ('blogger_explicit', 'externally_verified') and dish.get('blogger_attribution'):
            r.warn('LAYER_ATTR_ON_EXPLICIT',
                   f'{w} source_type={st} 且有 blogger_attribution'
                   f' → 归因本身是推测，该条宜拆为两条（事实 + hypothesis）')


def check_candidate_patterns(d, md_text, r):
    """C-B1：候选规律逐条四要件 + 禁用表述。

    v2 是"章节/表格总提示"，靠标题继承说明；下游合并时约束会丢。
    """
    pats = d.get('candidate_patterns')
    if pats is None:
        # 表态类的 B1 小节是「价值观与红线」，对应 values_triggered，本就没有
        # candidate_patterns —— 只对探店类提醒。
        if d.get('content_type') != '表态':
            r.warn('B1_NO_JSON', 'json 缺 candidate_patterns 数组——B1 仅存在于 md，'
                                 '下游只读 json 时约束会丢失')
    else:
        for i, p in enumerate(pats):
            w = f'candidate_patterns[{i}]'
            # v4 拆分样本量：video_count 恒为 1（单期产出的铁律，这才是防抖阈值关心的），
            # within_video_sample_count 记本期有几道菜/几个事件支撑（可以 >1）。
            # v3 只有一个 sample_count，脚本要求 ==1 而 schema.md 说 3-4 可填 medium、
            # 示例还写着 4 —— 文档与校验直接对立，模型无论怎么填都会挨一刀。
            vc = p.get('video_count', p.get('sample_count'))
            if vc != 1:
                r.block('B1_VIDEO_COUNT',
                        f'{w}.video_count 必须为 1（单期产出的候选规律只可能有 1 期样本），'
                        f'实为 {vc!r}。本期内有几道菜支撑请填 within_video_sample_count')
            if p.get('confidence') != 'low':
                r.block('B1_CONFIDENCE',
                        f'{w}.confidence 必须为 low，实为 {p.get("confidence")!r}'
                        f'（单期样本不足以支撑 medium/high，跨期归并由下游做）')
            if not p.get('next_verify'):
                r.block('B1_NO_NEXT_VERIFY', f'{w}.next_verify 缺失（后续验证方向必填）')
            if not p.get('not_stable_rule'):
                r.block('B1_NO_DISCLAIMER', f'{w}.not_stable_rule 缺失（不可作为稳定规律使用）')
            # ★ B1 的 source_type 是**收窄**枚举，不是全局枚举（v4.5）。
            # schema 与 prompt 都写明"model_inference 不进 B1"，但 check_enums
            # 只验它是否属于全局 source_type——而全局枚举本身就含 model_inference，
            # 于是「模型推测他通常更重视食材新鲜度」这类条目一路放行，
            # 以"可跨期归并的候选规律"身份进入下游。这恰好违背 B1 的设立目的：
            # B1 收的是**博主的**观察线索，模型自己的猜测没有跨期验证价值。
            # 只在"填了但填错"时报；为 null 由 ENUM_NULL 负责，不重复计数。
            if (p.get('source_type') is not None
                    and p.get('source_type') not in ENUM['source_type_blogger_only']):
                r.block('B1_MODEL_INFERENCE',
                        f'{w}.source_type={p.get("source_type")!r}——候选规律只接受 '
                        f'{ENUM["source_type_blogger_only"]}（须有可回查的博主原话）。'
                        f'模型自己的推测请移入 B7 开放解释与竞争性解释，不要进 candidate_patterns：'
                        f'它会被下游当作可跨期归并的线索')
            if 'counter_example' not in p:
                r.warn('B1_NO_COUNTER', f'{w} 无 counter_example 键（无反例填 null）')
            stmt = str(pattern_text(p))
            hit = forbidden_hits(stmt)
            if hit:
                r.block('B1_FORBIDDEN_PHRASE',
                        f'{w}.pattern 含禁用表述 {hit}：{stmt[:60]}')

    d10 = d.get('d10_ordering') or {}

    # d10_ordering.scope 是 B1 纪律的后门：v3 查了 strategy_notes 的措辞，
    # 却完全没查 scope，于是 "scope": "本帮菜普遍如此" 这种自由文本一路畅通。
    # 这里不复用 dishes 的升级规则，而是直接钉死 this_serving ——
    # 字段名 worth_ordering_this_time / avoid_this_time 已经自带范围限定，
    # 它定义的就是"本期这一顿点菜观察"，任何升级都是概念错误而非证据不足。
    if d10:
        sc = d10.get('scope')
        sc_val = sc.get('value') if isinstance(sc, dict) else sc
        if sc_val is not None and sc_val != 'this_serving':
            r.block('D10_SCOPE_NOT_THIS_SERVING',
                    f'd10_ordering.scope = {sc_val!r}，必须为 this_serving。'
                    f'D10 记的是本期这一顿的点菜观察，跨期/跨店的点菜策略'
                    f'由下游归并产生，不在单期产出的权限内')

    notes = str(d10.get('strategy_notes') or '')
    hit = forbidden_hits(notes)
    if hit:
        r.block('D10_FORBIDDEN_PHRASE',
                f'd10_ordering.strategy_notes 含禁用表述 {hit}：{notes[:60]}')
    if notes and not re.search(r'样本|不足以成规律|本期', notes):
        r.warn('D10_NO_SAMPLE_NOTE',
               'd10_ordering.strategy_notes 未写样本量/本期限定，读起来像通用策略')
    if notes and re.search(r'建议|推荐|优先级', notes):
        r.block('D10_READER_ADVICE',
                f'd10_ordering.strategy_notes 出现面向读者的操作建议：{notes[:60]}'
                f' → 只写本期现象 + 样本量')

    if md_text:
        # ⚠️ 边界必须排除 `####`：v3 写的是 `(?=\n###|\n##|\Z)`，而 `\n###`
        # 会匹配到 `\n#### 候选规律 1：` 的前三个 # —— B1 区内容恒为空字符串，
        # 于是**md 侧的 B1_FORBIDDEN_PHRASE 检查也一直是死的**。
        # 正则里的 off-by-one 不会报错，只会让检查静静地什么都不查。
        m = re.search(r'###\s*B1[^\n]*\n(.*?)(?=\n#{2,3}(?!#)|\Z)', md_text, re.S)
        if m:
            md_hits = forbidden_hits(m.group(1))
            if md_hits:
                r.block('B1_FORBIDDEN_PHRASE',
                        f'md B1 区含禁用表述 {md_hits} → 单期观察不得写成'
                        f'稳定人格或方法论结论，改成"本期…；是否稳定待跨期验证"')

            # md 与 json 逐条对齐。understand-prompt.md 早就写着"闸门检查两边
            # 数量是否一致"，而 v3 只在 candidate_patterns 键完全缺失时报 WARN——
            # md 写 3 条、json 只有 1 条时一声不响，2 条在下游静默消失。
            # 标题格式容忍变体：`#### 候选规律 1：`/`#### 候选规律1 -`/`### 候选规律 N`。
            if d.get('content_type') != '表态':
                body = m.group(1)
                # 两种写法都要认。v3/v2 的实跑产出里两种各占一半：
                #   ① prompt 模板的 `#### 候选规律 1：…`
                #   ② 自创的表格 `| R1 | 规律描述 | 段落 5 | blogger_explicit | … |`
                # 只认 ① 会把 ② 全判成"本期无候选规律"——实测 5 份如此，
                # 而它们各有 3 条候选规律，正好是本检查要抓的静默丢失。
                md_n = len(re.findall(r'^#{3,5}\s*候选规律\s*\d*\s*[：:\-—]?',
                                      body, re.M))
                if md_n == 0:
                    md_n = len(re.findall(r'^\|\s*R\d+\s*\|', body, re.M))
                if md_n == 0:
                    # 第三种写法：编号列表 `1. **规律描述**`（v4.7 补）。
                    # 实测 0007-0010 用的正是这种，而计数器只认前两种，
                    # 于是 md_n=0、json 有 3 条 → 反向报 B1_COUNT_MISMATCH，
                    # 把"两边都写了"误判成"md 漏写"。
                    md_n = len(re.findall(r'^\s*\d+[.、]\s*\*\*', body, re.M))
                json_n = len(pats or [])
                none_marker = re.search(r'本期无|无候选规律|暂无|无候选', body)
                if md_n != json_n and not (md_n == 0 and json_n == 0):
                    if md_n > json_n:
                        r.block('B1_COUNT_MISMATCH',
                                f'md B1 区有 {md_n} 条候选规律，json 的 '
                                f'candidate_patterns 只有 {json_n} 条 → '
                                f'差的 {md_n - json_n} 条下游读不到（Phase 2 只读 json）')
                    else:
                        r.warn('B1_COUNT_MISMATCH',
                               f'json 有 {json_n} 条候选规律，md B1 区只写了 {md_n} 条'
                               f' → md 是人回查用的，宜同步补全')
                elif md_n == 0 and json_n == 0 and not none_marker:
                    r.warn('B1_EMPTY_NO_MARKER',
                           'md B1 区无候选规律条目也无"本期无"标注——'
                           '无法区分"确实没有"与"漏写了"')


def check_values_json(d, md_text, r):
    """C-B2：探店类的 B2 价值观必须同步进 json（v4.6）。

    v4.5 之前 values_triggered 只在表态类 schema 里，探店类的 B2
    没有任何 json 对应字段——B2 只存在于 md，下游只读 json 就全丢了。
    这与 v3 时 B1 的失效方式完全相同（当时 30 条候选规律静默消失），
    只是没人注意到 B2 也有同一个洞：B1 至少有 B1_COUNT_MISMATCH 保护。
    """
    if d.get('content_type') != '探店' or not md_text:
        return
    m = re.search(r'###\s*B2[^\n]*\n(.*?)(?=\n#{2,3}(?!#)|\Z)', md_text, re.S)
    if not m:
        return
    body = m.group(1)
    if re.search(r'本期无|无触发|未触发|暂无', body):
        return
    # md 侧条目数：表格行（| 倾向 | … |）或加粗小标题（**红线：…**）
    rows = len([l for l in body.splitlines()
                if l.strip().startswith('|') and '---' not in l])
    rows = max(0, rows - 1) if rows else 0     # 扣表头
    bolds = len(re.findall(r'^\s*\*\*(?:红线|价值观|倾向)[^*]*\*\*', body, re.M))
    md_n = rows or bolds
    if md_n == 0:
        return
    json_n = len(d.get('values_triggered') or [])
    if json_n == 0:
        r.block('B2_NO_JSON',
                f'md B2 区有 {md_n} 条价值观/倾向，但 json 没有 values_triggered'
                f' → 下游 Phase 2 只读 json，这些条目会静默消失'
                f'（与 v3 时 B1 只写 md 的失效方式相同）')
    elif md_n > json_n:
        r.warn('B2_COUNT_MISMATCH',
               f'md B2 区 {md_n} 条，json values_triggered {json_n} 条'
               f' → 差的 {md_n - json_n} 条下游读不到')


def check_tags(d, r):
    """C-TAG：闭词典 + 禁括号 + 必带前缀。

    实测 108 种标签去括号后只剩 85 种——23 种因括号分裂，
    「口感-酥脆」有 6 种写法，半角全角并存。跨期统计会静默漏算。
    """
    allowed = set(TAGDICT['tags'])
    esc = re.compile(TAGDICT['escape_hatch_pattern'])
    prefixes = tuple(TAGDICT['prefixes'])

    quals = set(TAGDICT.get('qualifiers') or [])
    for i, dish in enumerate(d.get('dishes') or []):
        w = f'dishes[{i}]({dish.get("name")})'
        for t in (dish.get('standard_tags') or []):
            t = str(t)
            if has_paren(t):
                r.block('TAG_PAREN',
                        f'{w} 标签含括号 {t!r} → 限定词移入 tag_qualifier')
                continue
            if not t.startswith(prefixes):
                r.block('TAG_NO_PREFIX',
                        f'{w} 标签无前缀 {t!r} → 前缀取自 {list(prefixes)}')
                continue
            if t not in allowed and not esc.match(t):
                r.block('TAG_NOT_IN_DICT',
                        f'{w} 标签不在词典内 {t!r} → 用词典值或 其他-{{描述}}')

        # tag_qualifier 值域。v3 完全没查这个字段的取值，而词典规定只有
        # 负面/异常/过度/不足 四个 —— 于是 --fix-safe 写入的 `原括注：面包`
        # 处于"schema 说不允许、脚本却主动写入"的矛盾状态。
        # v4 的选择：正式承认 `原括注：{原文}` 为合法的过渡形态（保留信息优先），
        # 但报 WARN，让它在跨期统计时能被识别为"未归一化限定词"。
        tq = dish.get('tag_qualifier')
        if isinstance(tq, dict):
            for k, v in tq.items():
                v = str(v)
                if v in quals:
                    continue
                if v.startswith('原括注：'):
                    r.warn('TAG_QUALIFIER_NONSTANDARD',
                           f'{w} tag_qualifier[{k!r}]={v!r} 是未归一化的原始括注'
                           f' → 可用，但跨期统计时不参与限定词聚合。'
                           f'能归入 {sorted(quals)} 之一时请改写')
                else:
                    r.warn('TAG_QUALIFIER_INVALID',
                           f'{w} tag_qualifier[{k!r}]={v!r} 不在 {sorted(quals)} 内'
                           f' → 归一化，或写成 原括注：{v}')
            for k in tq:
                if k not in [str(x) for x in (dish.get('standard_tags') or [])]:
                    r.warn('TAG_QUALIFIER_ORPHAN',
                           f'{w} tag_qualifier 的键 {k!r} 不在 standard_tags 里'
                           f' → 限定词悬空，跨期统计取不到')


def _frame_refs(text):
    """Return normalized numeric frame references from text.

    Frame directories in existing corpora use both four- and five-digit padding. The
    numeric identity is stable, so f_0001 and f_00001 are the same reference. A range
    contributes both endpoints; frame numbers are never treated as timestamps.
    """
    return {int(x) for x in re.findall(r'\b(?:f|frame)_(\d+)\b', str(text or ''))}


def _a1_segments(md_text):
    """Parse timestamped A1 blocks without letting later sections supply evidence."""
    if not md_text:
        return []
    m = re.search(r'^###\s+A1\s+逐段记录[^\n]*\n(.*?)(?=^###\s+|^##\s+|\Z)',
                  md_text, re.M | re.S)
    if not m:
        return []
    body = m.group(1)
    heads = list(re.finditer(
        r'^\*\*\[\s*(\d{1,3}:\d{2}(?:\.\d+)?)\s*[-–~]\s*(\d{1,3}:\d{2}(?:\.\d+)?)\s*\]\*\*\s*$',
        body, re.M))
    out = []
    for i, head in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
        text = body[head.end():end]
        rng = parse_range(f'{head.group(1)}-{head.group(2)}')
        lines = text.splitlines()
        visual_lines = [line.strip() for line in lines
                        if '[画面]' in line or '[花字]' in line]
        no_signal_lines = [line.strip() for line in lines
                           if '已检查但无判断相关视觉信号' in line]
        trace_lines = visual_lines + no_signal_lines
        out.append({'range': rng, 'text': text, 'visual_lines': visual_lines,
                    'no_signal': bool(no_signal_lines),
                    # 只有客观观察/规范无信号行自己的引用才算证据；同段 ASR、推断或
                    # 覆盖元数据里偶然出现的帧号不能替视觉观察发通行证。
                    'frame_refs': _frame_refs('\n'.join(trace_lines)),
                    'continuous_trace': any('连续观看' in line for line in trace_lines)})
    return out


def _overlapping_a1(segments, timestamp):
    rng = parse_range(timestamp)
    if not rng:
        return []
    return [seg for seg in segments if seg['range'] and
            min(rng[1], seg['range'][1]) > max(rng[0], seg['range'][0])]


def _frame_inventory(corpus, vid):
    fdir = find_frames_dir(corpus, vid)
    if not os.path.isdir(fdir):
        return set()
    return {_n for name in os.listdir(fdir)
            if os.path.splitext(name)[1].lower() in ('.jpg', '.jpeg', '.png')
            for _n in _frame_refs(os.path.splitext(name)[0])}


def check_visual_cross_layer(d, md_text, r, corpus, vid):
    """C-VIS-X: visual JSON claims must leave matching, auditable A1 traces.

    This proves consistency between claims, assets and output layers. It cannot prove
    that the model really inspected an image or that its description is semantically
    true; those require tool-side access logs and independent visual spot checks.
    """
    if d.get('content_type') != '探店':
        return
    # Compatibility boundary: old rich corpora have neither part of the new contract.
    if 'judgment_episodes' not in d or 'visual_coverage' not in d:
        return

    segments = _a1_segments(md_text)
    inventory = _frame_inventory(corpus, vid)
    coverage = d.get('visual_coverage') or []
    for i, item in enumerate(coverage):
        if not isinstance(item, dict):
            continue
        status = item.get('visual_status')
        matched = _overlapping_a1(segments, item.get('timestamp'))
        where = f'visual_coverage[{i}]({item.get("timestamp")})'
        if status in ('reviewed_frames', 'reviewed_video'):
            if not matched:
                r.block('VISUAL_STATUS_NO_MD_BASIS',
                        f'{where} 声称 {status}，但找不到重叠的 A1 时间段')
                continue
            observations = [line for seg in matched for line in seg['visual_lines']]
            no_signal = any(seg['no_signal'] for seg in matched)
            md_refs = set().union(*(seg['frame_refs'] for seg in matched))
            json_refs = _frame_refs(item.get('visual_basis'))
            nonexistent = sorted(json_refs - inventory)
            if nonexistent:
                r.block('FRAME_REF_BROKEN',
                        f'{where}.visual_basis 引用不存在的帧编号 {nonexistent[:8]}')
            has_basis = (status == 'reviewed_frames' and bool(md_refs & json_refs)
                         or status == 'reviewed_video' and
                         '连续观看' in str(item.get('visual_basis')) and
                         any(seg['continuous_trace'] for seg in matched))
            if not ((observations or no_signal) and has_basis):
                r.block('VISUAL_STATUS_NO_MD_BASIS',
                        f'{where} 声称 {status}，但对应 A1 段缺带同源 basis 的'
                        f' [画面]/[花字]，也无“已检查但无判断相关视觉信号”留痕')
        elif status == 'audio_only' and any(seg['visual_lines'] for seg in matched):
            r.block('VISUAL_STATUS_NO_MD_BASIS',
                    f'{where} 标为 audio_only，但对应 A1 段仍有 [画面]/[花字]')

    episode_times = {x.get('episode_id'): x.get('timestamp')
                     for x in (d.get('judgment_episodes') or []) if isinstance(x, dict)}
    av = d.get('audiovisual_analysis') or {}
    for section in ('shot_sound_relations', 'reaction_sequences', 'attention_distribution'):
        for i, item in enumerate(av.get(section) or []):
            if not isinstance(item, dict):
                continue
            level = item.get('evidence_level')
            if level not in ('frame_sequence', 'single_frame', 'direct_video'):
                continue
            where = f'audiovisual_analysis.{section}[{i}]'
            timestamp = item.get('timestamp')
            if timestamp:
                matched = _overlapping_a1(segments, timestamp)
            else:
                # attention_distribution 通常没有自己的 timestamp；用所有 episode_refs
                # 的时间段求并集，而不是要求多个 episode 恰好同一时间。
                matched = []
                for ref in item.get('episode_refs') or []:
                    for seg in _overlapping_a1(segments, episode_times.get(ref)):
                        if seg not in matched:
                            matched.append(seg)
            json_refs = _frame_refs(item.get('visual_basis'))
            md_refs = set().union(*(seg['frame_refs'] for seg in matched)) if matched else set()
            observations = [line for seg in matched for line in seg['visual_lines']]

            if level in ('frame_sequence', 'single_frame'):
                nonexistent = sorted(json_refs - inventory)
                if nonexistent:
                    r.block('FRAME_REF_BROKEN',
                            f'{where}.visual_basis 引用不存在的帧编号 {nonexistent[:8]}')
            if level == 'frame_sequence':
                if len(json_refs) < 2 or not matched or not observations or not (json_refs & md_refs):
                    r.block('FRAME_SEQ_NO_MD_OBSERVATION',
                            f'{where} 声称 frame_sequence，但须有至少两个真实帧端点、'
                            f'可解析时间窗及 A1 中引用同源帧的客观观察')
            elif level == 'single_frame':
                if len(json_refs) != 1 or not matched or not observations or not (json_refs & md_refs):
                    r.block('VISUAL_STATUS_NO_MD_BASIS',
                            f'{where} 声称 single_frame，但缺一张真实帧及 A1 同源静态观察')
            else:  # direct_video
                basis = str(item.get('visual_basis') or '')
                if ('连续观看' not in basis or not matched or not observations
                        or not any(seg['continuous_trace'] for seg in matched)):
                    r.block('VISUAL_STATUS_NO_MD_BASIS',
                            f'{where} 声称 direct_video，但缺连续观看区间或 A1 客观观察')


def check_flash_delivery_contract(corpus, vid, d, md_text, r, variant='root'):
    """5.3-Flash outputs must have staged evidence and a fixed consumable template."""
    if d.get('content_type') != '探店':
        return
    for directory, code in (('run-manifests', 'RUN_MANIFEST_MISSING'),
                            ('shot-ledgers', 'SHOT_LEDGER_MISSING'),
                            ('visual-ledgers', 'VISUAL_LEDGER_MISSING'),
                            ('reaction-windows', 'REACTION_WINDOWS_MISSING'),
                            ('sound-edit-ledgers', 'SOUND_EDIT_LEDGER_MISSING'),
                            ('assembly', 'ASSEMBLY_PAYLOAD_MISSING')):
        path = output_file(corpus, directory, variant, f'{vid}.json')
        if not os.path.isfile(path):
            r.block(code, f'{directory}/{vid}.json 不存在；Flash 分阶段证据不可跳过')

    text = md_text or ''
    required = [f'### A{i} ' for i in range(1, 16)] + [f'### B{i} ' for i in range(1, 8)]
    missing = [heading.strip() for heading in required if heading not in text]
    if missing:
        r.block('FLASH_TEMPLATE_INCOMPLETE', f'标准 A1-A15/B1-B7 缺失：{missing}')

    drift_markers = ('```mermaid', '深度理解 (5V)', '深度理解 (Flash)', '叙事弧光与判断轨迹',
                     '专家知识库激活', '专家人格侧写', '人格维度', '精致度评级')
    hit = [marker for marker in drift_markers if marker in text]
    if hit:
        r.block('FLASH_FREEFORM_DRIFT', f'命中自由文章/人格模板：{hit}')

    stable_markers = ('系列首次', '金标准', '人格侧写', '食材至上主义', '哲学声明',
                      '评价体系', '判断体系', '代名词进入')
    hit = [marker for marker in stable_markers if marker in text]
    if hit:
        r.block('FLASH_SINGLE_VIDEO_OVERCLAIM', f'单期升级为稳定画像/体系：{hit}')

    levels = set(re.findall(r'evidence_level\s*=\s*([A-Za-z0-9_-]+)', text))
    allowed = set(ENUM['visual_evidence_level'])
    invalid = sorted(levels - allowed)
    if invalid:
        r.block('FLASH_EVIDENCE_LEVEL_INVALID', f'非标准 evidence_level：{invalid}')

    if re.search(r'^##\s+(?:D\.|JSON)', text, re.M) or '```json' in text:
        r.block('FLASH_EMBEDDED_JSON', '标准 JSON 必须独立写入 data/{id}.json，不得内嵌自创结构')
    if re.search(r'未(?:在本批次)?逐帧核验', text) and ('reviewed_frames' in text or 'reviewed_video' in text):
        r.block('FLASH_REVIEW_STATUS_CONTRADICTION',
                '正文声明未逐帧核验，却同时声称 reviewed_frames/reviewed_video')

    invisible_sensory = ('视觉上很香', '看起来很甜', '看起来很咸', '看起来很软',
                         '看起来很脆', '看起来很弹', '画面显示很香', '画面显示好吃')
    for ln, line in enumerate(text.splitlines(), 1):
        if '[画面]' in line and any(term in line for term in invisible_sensory):
            r.block('FOOD_INVISIBLE_SENSORY_CLAIM',
                    f'md L{ln} 把不可见味觉/口感写成视觉事实：{line.strip()[:80]}')

    ledger_fields = ('shot_coverage_summary', 'food_visual_evidence', 'action_evidence',
                     'microreaction_evidence', 'sound_edit_evidence', 'audiovisual_claim_refs')
    missing_ledger_fields = [key for key in ledger_fields if key not in d]
    if missing_ledger_fields:
        r.block('FLASH_LEDGER_SUMMARY_MISSING', f'标准 JSON 缺专业账本摘要字段：{missing_ledger_fields}')

    claims = d.get('audiovisual_claim_refs') or []
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict) or not claim.get('ledger_refs'):
            r.block('FLASH_CLAIM_REF_MISSING', f'audiovisual_claim_refs[{index}] 缺 ledger_refs')

    # Markdown lines are also direct claims. The JSON cross-layer check cannot see a
    # one-frame `frame_sequence` that appears only in A1, so enforce it here.
    for ln, line in enumerate(text.splitlines(), 1):
        if '[画面]' not in line and '[花字]' not in line:
            continue
        if 'evidence_level=frame_sequence' in line:
            refs = _frame_refs(line)
            if len(refs) < 2:
                r.block('FRAME_SEQ_SINGLE_ENDPOINT',
                        f'md L{ln} frame_sequence 只有 {len(refs)} 个真实帧端点')

    # Import locally so the validator stays runnable as a copied standalone script.
    try:
        from check_run_manifest import validate_manifest
        for level, code, message in validate_manifest(corpus, vid, variant=variant):
            (r.block if level == 'BLOCK' else r.warn)(code, message)
    except (ImportError, OSError) as e:
        r.block('RUN_MANIFEST_CHECK_UNAVAILABLE', f'无法运行 manifest 校验：{e}')


def check_visual_inference(md_text, r):
    """C-VIS：[画面]/[花字] 行不得混入推断词。

    实测 19 行混写，最典型是 0001 L17「表情明显不适——嘴角下撇」，
    正是报告 C05 回归测试给的错误示范原文。
    """
    if not md_text:
        return
    markers = ENUM['inference_markers']
    n = 0
    for ln, line in enumerate(md_text.splitlines(), 1):
        if '[画面]' not in line and '[花字]' not in line:
            continue
        if '[推断]' in line:
            continue
        # [花字] 行的「」内是字幕原文逐字引用（引用数据，非观察表述）：
        # 字幕自带"明显"等词不构成观察/解读混写——引用不算混写，
        # 但「」外仍全量扫描（v4.2 式误检修复：判据对准引用边界）。
        scan = re.sub(r'「[^」]*」', '', line) if '[花字]' in line and '[画面]' not in line else line
        hit = [t for t in markers if t in scan]
        if hit:
            n += 1
            r.block('VISUAL_HAS_INFERENCE',
                    f'md L{ln} [画面]/[花字] 行含推断词 {hit}：{line.strip()[:70]}'
                    f' → 客观描述留 [画面]，解读移入 [推断] 并注明依据')
    if n:
        r.warn('VISUAL_INFERENCE_COUNT', f'共 {n} 行观察与解读混写')


def check_inference_lines(md_text, r):
    """C-INF：[推断] 行不得搬运行业常识（v4.4）。

    v4.3 之前 [推断] 行对 TECH_TERM 检查是**无条件豁免**的——
    标上 [推断] 就等于拿到通行证，什么都能写。于是模型的餐饮知识
    以「推断」的身份混进了博主的判断材料。实测 0001 L32：
    「微甜、香油重为本帮菜典型特征」——这是模型的先验知识，
    不是本期博主说过的任何一句话。

    [推断] 的定义是「基于已列语音/画面的解释，且必须注明依据」。
    依据只能来自本期素材。行业常识不是依据，它是另一个知识源，
    混进来下游就无法区分「这位博主的判断」与「餐饮常识」——
    而整个 skill 的存在意义正是提取前者。
    """
    if not md_text:
        return
    markers = ENUM.get('industry_knowledge_markers') or []
    for ln, line in enumerate(md_text.splitlines(), 1):
        if '[推断]' not in line:
            continue
        hit = [t for t in markers if t in line]
        if hit:
            r.block('INFERENCE_IS_INDUSTRY_KNOWLEDGE',
                    f'md L{ln} [推断] 行搬运行业常识 {hit}：{line.strip()[:70]}'
                    f' → 推断的依据只能是本期语音/画面，不能是模型的餐饮知识。'
                    f'这类内容会让下游把常识误当成这位博主的判断标准')


def check_md_structure(md_text, r, content_type='探店'):
    """C-MD：二级标题逐字 + 小节白名单（防模板分裂）。

    v4：白名单按 content_type 分流。v3 对表态类也套探店白名单，
    而 understand-prompt-statement.md 的模板是 B1 价值观/B2 内在张力/…/B5 其他观察
    —— 按自己的 prompt 写就必然吃 5 个 MD_H3_DIVERGED，且无论怎么改都过不了。
    """
    if not md_text:
        r.block('MD_MISSING', 'understanding/{id}.md 不存在')
        return
    is_stmt = content_type == '表态'
    h2_key = 'md_required_h2_statement' if is_stmt else 'md_required_h2'
    h3_key = 'md_allowed_h3_statement' if is_stmt else 'md_allowed_h3'
    for h in ENUM.get(h2_key, ENUM['md_required_h2']):
        if h not in md_text:
            r.block('MD_H2_MISSING',
                    f'缺二级标题 {h!r}（逐字，注意 ASR 与 纠错 间有空格）——'
                    f'合并脚本按标题定位，写错会静默把 C 区并进 B 区')

    # 小节比对忽略标点/空格差异（`### A1. 逐段记录` 与 `### A1 逐段记录` 视为同一节），
    # 只抓真正的语义分裂：实测 5 份写 `A3 无反应自检`+`A4 镜头时长分配`，
    # 另 5 份写 `A3 整体环境观感`+`A4 C档顺带记录`，同一编号挂了不同内容。
    # v4 给前者各自一个合法编号（A7/A8），因为它们本来就该有地方放。
    allowed_norm = {normalize(a): a for a in ENUM[h3_key]}
    for ln, line in enumerate(md_text.splitlines(), 1):
        if not line.startswith('### '):
            continue
        head = line.strip()
        hn = normalize(head)
        if any(hn.startswith(k) for k in allowed_norm):
            continue
        m = re.match(r'^###\s*([AB]\d+)', head)
        if m:
            canon = [v for k, v in allowed_norm.items()
                     if normalize(m.group(1)) in k[:6]]
            r.block('MD_H3_DIVERGED',
                    f'md L{ln} 小节 {head[:40]!r} 与规范不符'
                    f'{"（规范为 " + canon[0] + "）" if canon else ""}'
                    f' → 同一编号挂不同内容会使批次模板分裂，下游按编号取节会取错')
        else:
            r.warn('MD_H3_UNKNOWN',
                   f'md L{ln} 非白名单小节 {head[:40]!r}——宜并入 A6 或 B4')


def check_duration(d, r, video_path):
    """C-DUR：Σ时长 ≤ 真实时长；区间不重叠。

    实测 0006 Σ190s > 168.11s（113%）；0009 Σ253s > 203.15s（125%），
    且 3 道菜共用 01:18-01:52 各记 34s，属重复计入。
    """
    declared = d.get('video_duration_sec')
    real = None
    if video_path and os.path.exists(video_path):
        try:
            out = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                 '-of', 'csv=p=0', video_path],
                capture_output=True, text=True, timeout=30)
            if out.returncode == 0 and out.stdout.strip():
                real = float(out.stdout.strip())
        except (OSError, ValueError, subprocess.SubprocessError):
            pass

    if real and declared:
        if abs(real - declared) > max(2.0, real * 0.02):
            r.warn('DUR_DECLARED_MISMATCH',
                   f'video_duration_sec={declared} 与 ffprobe 实测 {real:.2f}s 不符')
    base = real or declared
    if not base:
        r.warn('DUR_NO_BASE', '无 video_duration_sec 且 ffprobe 不可用，跳过时长校验')
        return

    total = sum((dish.get('shot_duration_sec') or 0) for dish in (d.get('dishes') or []))
    if total > base:
        r.block('DUR_OVERFLOW',
                f'菜品 shot_duration_sec 合计 {total}s > 视频 {base:.2f}s '
                f'（{total / base * 100:.0f}%）→ 说明是估算的，须用转写时间轴重算')
    elif total > base * 0.92:
        r.warn('DUR_TIGHT',
               f'菜品合计 {total}s 占视频 {base:.2f}s 的 {total / base * 100:.0f}%，'
               f'未给开场/结尾/转场留余量')

    # v3 只查完全相同的区间字符串，而 SKILL.md 与 schema 承诺的是「区间不重叠」——
    # 部分重叠（00:32-01:15 vs 01:00-01:40）查不出来，正是"时长是估的"的典型痕迹。
    # v4 按秒做区间交集：完全相同 ⇒ TS_DUPLICATE（BLOCK）；
    # 部分重叠 ⇒ TS_OVERLAP，重叠越多越可疑，故按重叠比例分级。
    seen = []
    for i, dish in enumerate(d.get('dishes') or []):
        rng = parse_range(dish.get('timestamp'))
        if rng is None:
            if dish.get('timestamp'):
                r.warn('TS_UNPARSEABLE',
                       f'dishes[{i}]({dish.get("name")}) timestamp 无法解析：'
                       f'{dish.get("timestamp")!r}（须 MM:SS-MM:SS）')
            continue
        name = dish.get('name')
        secs = dish.get('shot_duration_sec') or 0
        for prev_rng, prev_name, prev_ts, prev_secs in seen:
            lo, hi = max(rng[0], prev_rng[0]), min(rng[1], prev_rng[1])
            ov = hi - lo
            if ov <= 0:
                continue
            # ★ 关键判据是「时长有没有被重复计入」，不是「区间有没有重叠」。
            # 火锅/烤肉这类连续涮煮的场景，多道菜天然在同一段落里被讨论——
            # 正确做法就是把该段秒数归给主要讨论对象、其余记 0，区间照实写。
            # 实测 0010 的 12 处重叠全是这种写法（一方 41s、其余 0s），
            # 而 v4.1 初版一律 BLOCK，等于惩罚了唯一正确的做法。
            # 只有双方都计了秒，才真的重复占用了视频时长。
            if secs > 0 and prev_secs > 0:
                shorter = min(rng[1] - rng[0], prev_rng[1] - prev_rng[0]) or 1
                pct = ov / shorter
                msg = (f'dishes[{i}]({name}, {secs}s) 与 {prev_name}'
                       f'（{prev_secs}s）区间重叠 {ov}s'
                       f'（{dish.get("timestamp")} vs {prev_ts}，占较短者 {pct * 100:.0f}%），'
                       f'且两者都计了 shot_duration_sec')
                code = 'TS_DUPLICATE' if rng == prev_rng else 'TS_OVERLAP'
                if rng == prev_rng or pct >= 0.5:
                    r.block(code, msg + ' → 时长重复计入，'
                                        '该段秒数应只归主要讨论对象，另一方记 0')
                else:
                    r.warn(code, msg + ' → 重叠部分宜只归一方')
            elif rng == prev_rng and secs == 0 and prev_secs == 0:
                # 两边都是 0：不重复计时长，但整段没人认领，Σ时长会偏低
                r.warn('TS_SHARED_NO_OWNER',
                       f'dishes[{i}]({name}) 与 {prev_name} 共用 {dish.get("timestamp")}'
                       f' 且双方 shot_duration_sec 都是 0 → 该段无人认领，'
                       f'镜头时长统计会漏掉这段')
        seen.append((rng, name, dish.get('timestamp'), secs))


def check_frames(d, md_text, r, corpus, vid, video_path):
    """C-FRAME：帧率 + 命名一致 + 引用可解析。

    实测 frames_0001 只有 84 个文件 / 282s = 0.30 帧/秒（其余 9 期为 1.0），
    且混入 audio.wav、transcript.md；frames_0008 两套命名并存；
    0006 的 A6 引用 f_0001 但该期是 5 位命名，文件不存在。
    三期 processing_status 都是「完整」。
    """
    fdir = find_frames_dir(corpus, vid)
    if not os.path.isdir(fdir):
        r.block('FRAME_DIR_MISSING',
                f'{os.path.basename(fdir)}/ 不存在 → 未通过 Step 2 校验，不得标 完整')
        return

    imgs = [f for f in os.listdir(fdir)
            if os.path.splitext(f)[1].lower() in ('.jpg', '.jpeg', '.png')]
    if not imgs:
        r.block('FRAME_DIR_EMPTY', f'{os.path.basename(fdir)}/ 无图片文件')
        return

    stems = defaultdict(int)
    for f in imgs:
        m = re.match(r'^([A-Za-z_]+?)_?(\d+)\.', f)
        stems[(m.group(1), len(m.group(2))) if m else ('?', 0)] += 1
    if len(stems) > 1:
        r.block('FRAME_NAMING_MIXED',
                f'{os.path.basename(fdir)}/ 存在 {len(stems)} 套命名 '
                f'{ {f"{p}({n}位)": c for (p, n), c in stems.items()} } '
                f'→ 帧引用会指向不存在的文件')

    nonimg = [f for f in os.listdir(fdir)
              if os.path.splitext(f)[1].lower() not in ('.jpg', '.jpeg', '.png')]
    if nonimg:
        r.warn('FRAME_DIR_POLLUTED',
               f'{os.path.basename(fdir)}/ 混入非帧文件 {nonimg[:5]}')

    base = None
    if video_path and os.path.exists(video_path):
        try:
            out = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                 '-of', 'csv=p=0', video_path],
                capture_output=True, text=True, timeout=30)
            if out.returncode == 0 and out.stdout.strip():
                base = float(out.stdout.strip())
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    base = base or d.get('video_duration_sec')
    if base:
        fps = len(imgs) / base
        if fps < 0.95:
            r.block('FRAME_RATE_LOW',
                    f'帧率 {fps:.2f} 帧/秒（{len(imgs)} 张 / {base:.0f}s），'
                    f'低于口径 1.0 → 画面覆盖不足，不得标 完整')

    if md_text:
        存在 = {os.path.splitext(f)[0] for f in imgs}
        for m in re.finditer(r'\b((?:f|frame)_\d+)\b', md_text):
            ref = m.group(1)
            if ref not in 存在:
                ln = md_text[:m.start()].count('\n') + 1
                r.block('FRAME_REF_BROKEN',
                        f'md L{ln} 引用 {ref} 但 {os.path.basename(fdir)}/ 中无此文件'
                        f'（该期命名为 {sorted(存在)[0] if 存在 else "?"} 式）→ 幻觉引用')


def check_price(d, r, md_text=None):
    """C-PRICE：三数打架须标 price_mismatch；派生数值须有依据；A5 算式须算术自洽。"""
    pc = d.get('price_check')
    if not pc:
        return
    nums = {k: pc.get(k) for k in ('total_from_audio', 'total_from_caption', 'sum_of_dishes')}
    vals = [v for v in nums.values() if isinstance(v, (int, float))]
    if len(vals) >= 2 and len(set(vals)) > 1:
        if pc.get('consistent') is not False:
            r.block('PRICE_INCONSISTENT_FLAG',
                    f'价格三数不一致 {nums} 但 consistent != false')
        if not pc.get('mismatch_note'):
            r.block('PRICE_NO_NOTE', f'价格不一致 {nums} 但 mismatch_note 为空')
        elif 'price_mismatch' not in str(pc.get('mismatch_note')):
            r.warn('PRICE_NOTE_NO_TAG', 'mismatch_note 未标 price_mismatch 标记')

    meta = d.get('_meta') or {}
    for k in ('party_size', 'price_per_person'):
        if meta.get(k) is not None and not meta.get(f'{k}_basis'):
            r.warn('DERIVED_NO_BASIS',
                   f'_meta.{k}={meta.get(k)} 为派生/推断值但无 {k}_basis 说明依据'
                   f'（无依据应置 null）')

    # ★ A5 的存在意义是交叉校验，自身算术错误比没有校验更危险（v4.9 补）。
    # 实测 0032 曾写「六菜合计1083.9」，实算 1027.9，整体差 56 元却照常
    #给出「无法闭合」结论。判据：A5 文本中所有 a+b+…=s 算式逐个验算。
    if md_text:
        m5 = re.search(r'###\s*A5[^\n]*\n(.*?)(?=\n###|\n## |\Z)', md_text, re.S)
        if m5:
            for expr, total in re.findall(
                    r'(\d+(?:\.\d+)?(?:[+＋]\d+(?:\.\d+)?)+)[=＝](\d+(?:\.\d+)?)',
                    m5.group(1)):
                real = sum(float(x) for x in re.split(r'[+＋]', expr))
                if abs(real - float(total)) > 0.05:
                    r.block('A5_ARITHMETIC_MISMATCH',
                            f'A5 算式 {expr}={total} 验算实为 {round(real, 2)} → '
                            f'加总与总价数字必须算术自洽，先自算再落盘')


def check_reaction_types(d, r):
    """C-REACT：A2 不应清一色明确评论；无反应是负向证据。"""
    evs = d.get('dimension_events') or []
    if not evs:
        return
    c = Counter(e.get('reaction_type') for e in evs)
    if len(evs) >= 3 and c.get('明确评论', 0) == len(evs):
        r.warn('REACT_ALL_EXPLICIT',
               f'{len(evs)} 条事件全是「明确评论」→ 大概率漏了 微反应/无反应，'
               f'回去逐项过 5 个 B 档维度')
    for i, e in enumerate(evs):
        rt, es = e.get('reaction_type'), e.get('evidence_source')
        if rt in ('微反应', '无反应') and es == 'audio':
            r.block('REACT_SOURCE_CONFLICT',
                    f'dimension_events[{i}] reaction_type={rt} 却 evidence_source=audio'
                    f' → 微反应/无反应只可能来自画面')
        if rt == '无反应' and e.get('intensity') != '无':
            r.warn('REACT_INTENSITY',
                   f'dimension_events[{i}] 无反应 时 intensity 应为「无」')


def check_asr(md_text, r, tnorm=None):
    """C-ASR：关键信息不得只标存疑保留；依据不得编造帧号；原转写必须可溯源。"""
    if not md_text:
        return
    m = re.search(r'##\s*C\.\s*ASR\s*纠错清单\s*\n(.*?)(?=\n##|\Z)', md_text, re.S)
    if not m:
        return
    rows = [l for l in m.group(1).splitlines()
            if l.strip().startswith('|') and '---' not in l]
    # 表头定位「纠正后」列（列数因期而异：模板 4 列，实跑常见 5 列带序号）
    col = None
    if rows:
        head = [c.strip() for c in rows[0].strip('|').split('|')]
        for j, c in enumerate(head):
            if '纠正' in c:
                col = j
                break
    rows = rows[1:] if rows else []
    if not rows:
        return
    # ★ C 区「原转写」列必须能在本期转写稿中检索到原文（v4.9 补）。
    # 实测 0033 曾把 0035 的 ASR 噪声「一个穿满白海军的欧式宇天空镜」
    # 复制进自己的 C 区——素材串台/示例未清理。C 区的价值是
    # 「本期真实纠错过什么」，一条别期的噪声会让下游误以为本期
    # 视频里出现过这句话，属伪造证据链。
    # 判据：normalize 后长度>=4 的原转写在转写稿（+纠正后语料）中找不到。
    orig_col = None
    if rows:
        head = [c.strip() for c in (rows and [l for l in md_text[m.start():m.end()].splitlines()
                if l.strip().startswith('|')][0].strip('|').split('|') or [])]
    # 重新从含表头的原始行集合里定位「原转写」列
    all_rows = [l for l in m.group(1).splitlines()
                if l.strip().startswith('|') and '---' not in l]
    if all_rows:
        head = [c.strip() for c in all_rows[0].strip('|').split('|')]
        for j, c in enumerate(head):
            if '原转写' in c or '原始识别' in c or '原始' in c:
                orig_col = j
                break
        body = all_rows[1:]
    else:
        body = []
    if tnorm and orig_col is not None:
        for line in body:
            cells = [c.strip() for c in line.strip('|').split('|')]
            if orig_col >= len(cells):
                continue
            val = re.sub(r'[（(][^）)]*[）)]', '', cells[orig_col]).strip()
            nval = normalize(val)
            if len(nval) < 4:
                continue          # 过短（如单字词）无法可靠检索，跳过
            if nval not in tnorm:
                r.block('ASR_ROW_NOT_IN_TRANSCRIPT',
                        f'C 区「原转写」{val[:40]!r} 在本期转写稿中检索不到 → '
                        f'C 区只登记本期真实纠错；别期噪声/示例串台属伪造证据链，删除或改为本期原文')
    susp = [l for l in rows if '存疑保留' in l]
    if susp and len(susp) == len(rows) and len(rows) >= 5:
        r.block('ASR_ALL_SUSPECT',
                f'{len(rows)} 处纠错全部标「存疑保留」→ 等于没做；'
                f'须给最可能推断 + 低置信度')
    infer = re.compile(r'可能[为是指]|应为|疑为|推测|或["“]')
    key = re.compile(r'\d+\s*(块|元|斤)|价|菜名|店名')
    for l in susp:
        if key.search(l) and not infer.search(l):
            r.block('ASR_KEY_NO_GUESS',
                    f'关键信息（价格/菜名/店名）只标存疑保留未给推断：{l.strip()[:60]}')
    for ln, line in enumerate(m.group(1).splitlines(), 1):
        if re.search(r'\d{2}:\d{2}:\d{2}|frame_\d+\s*(可见|显示)', line):
            r.warn('ASR_FAKE_CITATION',
                   f'纠错依据疑似编造精确引用：{line.strip()[:60]}')

    # ★「纠正后」必须唯一确定（v4.4 补：文档三处都写了，从来没被强制过）。
    # 这不只是格式问题，而是一条**洗白通道**：C 区的「纠正后」值会被并入
    # 可溯源语料（asr_corrected_terms），于是 `剪发 → 碱发/化学发制` 这样一行
    # 就把两个博主没说过的工艺词注册成了"博主说过"，正文里再怎么用都不会被
    # TECH_TERM 拦住。实测 0001 正是靠这一行让「碱发」全份畅通。
    # 判据：纠正后列出现 / 或 、 分隔的多值，且其中含工艺术语。
    terms = ENUM['technical_attribution_terms']
    for line in rows:
        cells = [c.strip() for c in line.strip('|').split('|')]
        if col is None or col >= len(cells):
            continue
        val = cells[col]
        if not re.search(r'[/、]|或', val):
            continue
        # 括注里的存疑说明不算多值：`存疑保留（可能为红曲汤/红酱油汤底）`、
        # `呈现格调（或"呈现风格"）` 都是诚实标注不确定性，正是 prompt 要求的做法。
        # 只看括注**之外**的主值是否多值。
        bare = re.sub(r'[（(][^）)]*[）)]', '', val).strip()
        if not re.search(r'[/、]|或', bare):
            continue
        hit = [t for t in terms if t in val]
        if hit:
            r.block('ASR_CORRECTION_NOT_UNIQUE',
                    f'C 区「纠正后」给了多个候选值 {val[:40]!r}，其中含工艺术语 {hit}'
                    f' → 纠正后必须唯一确定。多值会把博主没说过的工艺词'
                    f'注册进可溯源语料，使 TECH_TERM 检查失效（这是洗白通道）。'
                    f'定不下来就只填最可能的一个 + 低置信度，扩展解释写进 A6')
        else:
            r.warn('ASR_CORRECTION_NOT_UNIQUE',
                   f'C 区「纠正后」非唯一值：{val[:40]!r} → 应只给一个确定值')


def check_self_reported_gate(d, r, gate_written):
    """C-GATE：产出里不得自带 quality_gate（v4.3）。

    实测 v4 的 10 份产出里 6 份手填了 quality_gate，0003 填 blocking_issues: []
    + 八项全 true，而它实际有 26 条 BLOCK。这与 v2 自检清单全打勾是同一个
    机制——生成者无法评价自己是否合规，因为它已经相信自己合规了。
    v4.3 把该字段移出输出契约，这条检查负责发现残留的自我声明。

    gate_written=True 时跳过：那是 --write-gate 自己刚写的，不是手填。
    """
    if gate_written:
        return
    g = d.get('quality_gate')
    if g is None:
        return
    # 已由本 validator 正式签发的 gate 是合法的持久状态，普通复核不得误判为自报。
    # 旧实现一律 BLOCK，导致刚 --write-gate 的记录下一次只读校验又变回不合格。
    if (isinstance(g, dict)
            and g.get('validator_version') == VALIDATOR_VERSION
            and g.get('validated_at')):
        return
    claims_clean = isinstance(g, dict) and not g.get('blocking_issues')
    msg = ('产出自带 quality_gate 对象 → 该字段只能由 --write-gate 写入。'
           '"我这份合规吗"在生成时无法自答')
    if claims_clean and r.blocks:
        r.block('GATE_SELF_REPORTED',
                f'{msg}；且它声明 blocking_issues 为空，而闸门实测 '
                f'{len(r.blocks)} 条 BLOCK——这是假的合规证明，'
                f'比没有证明更危险（合并准入会放它过去）')
    else:
        r.block('GATE_SELF_REPORTED',
                f'{msg} → 删掉该对象，重跑 --write-gate 生成')


def check_rich_structure(d, r):
    """C-RICH：新探店结构必须完整，引用必须可解析。

    这里只检查机器可判的契约，不检查视觉覆盖够不够深；后者由
    audit_richness.py 非阻塞诊断，避免模型通过少写来规避 BLOCK。
    """
    if d.get('content_type') != '探店':
        return
    required = [
        'visual_coverage', 'judgment_episodes', 'comparisons',
        'tensions_and_revisions', 'methodology_clues', 'expression_materials',
        'raw_sensory_descriptors', 'audiovisual_analysis', 'taste_lineage',
        'open_interpretations',
    ]
    # 旧产物兼容：完全没有新结构时不在安全闸门阻塞，由 richness audit 提醒迁移。
    if 'judgment_episodes' not in d:
        return
    missing = [key for key in required if key not in d]
    if missing:
        for key in missing:
            r.warn('RICH_FIELD_MISSING', f'探店产物缺丰富性字段 {key}；回原素材补齐，不要删除现有信息')
        # visual_coverage 是本轮视觉契约的启用标志。旧的高召回产物尚未有此键，
        # 不应因升级契约被安全闸门拒收；新增约束由 richness audit 明确诊断。
        if 'visual_coverage' not in d:
            return

    valid_status = set(ENUM.get('visual_status') or [])
    valid_level = set(ENUM.get('visual_evidence_level') or [])
    valid_caption = set(ENUM.get('caption_readability') or [])
    for i, item in enumerate(d.get('visual_coverage') or []):
        if not isinstance(item, dict):
            r.block('VISUAL_COVERAGE_INVALID', f'visual_coverage[{i}] 必须为对象')
            continue
        for key in ('timestamp', 'visual_status', 'visual_basis', 'caption_readability'):
            if key not in item:
                r.block('VISUAL_COVERAGE_INVALID', f'visual_coverage[{i}] 缺 {key}')
        if item.get('visual_status') not in valid_status:
            r.block('VISUAL_STATUS_INVALID',
                    f'visual_coverage[{i}].visual_status={item.get("visual_status")!r}')
        if item.get('caption_readability') not in valid_caption:
            r.block('CAPTION_STATUS_INVALID',
                    f'visual_coverage[{i}].caption_readability={item.get("caption_readability")!r}')

    episodes = d.get('judgment_episodes') or []
    ids = [x.get('episode_id') for x in episodes if isinstance(x, dict)]
    if len(ids) != len(episodes) or any(not x for x in ids) or len(ids) != len(set(ids)):
        r.block('EPISODE_ID_INVALID', 'judgment_episodes[].episode_id 缺失或重复')
    known = set(ids)
    av = d.get('audiovisual_analysis') or {}
    for section in ('shot_sound_relations', 'reaction_sequences', 'attention_distribution'):
        for i, item in enumerate(av.get(section) or []):
            w = f'audiovisual_analysis.{section}[{i}]'
            if not isinstance(item, dict):
                r.block('VISUAL_EVIDENCE_INVALID', f'{w} 必须为对象')
                continue
            if item.get('evidence_level') not in valid_level:
                r.block('VISUAL_EVIDENCE_INVALID', f'{w}.evidence_level 非法或缺失')
            refs = item.get('episode_refs')
            if not isinstance(refs, list) or not refs:
                r.block('EPISODE_REF_MISSING', f'{w}.episode_refs 缺失')
            else:
                broken = [x for x in refs if x not in known]
                if broken:
                    r.block('EPISODE_REF_BROKEN', f'{w} 引用不存在的 episode {broken}')


def check_status_consistency(d, r):
    """C-STATUS：有 BLOCK 时不得标「完整」。在所有检查之后调用。"""
    st = d.get('processing_status')
    if r.blocks and st == '完整':
        r.block('STATUS_OVERCLAIM',
                f'存在 {len(r.blocks)} 项 BLOCK 却标 processing_status=完整'
                f' → 生成时应固定写「完成待修订」，`完整` 由 --write-gate 写')


# ── 单期驱动 ──────────────────────────────────────────────────────────

def id_variants(vid):
    """产出物文件名可能带后缀（0004_csvrow91），而帧目录/视频用纯编号（frames_0004）。
    返回候选键，长者优先。"""
    out = [vid]
    m = re.match(r'^(\d+)', vid)
    if m and m.group(1) != vid:
        out.append(m.group(1))
    return out


def find_transcript(corpus, vid):
    import glob as _g
    for v in id_variants(vid):
        for pat in (f'{v}_audio_transcript.md', f'{v}*_audio_transcript.md',
                    f'{v}*transcript*.md'):
            hits = _g.glob(os.path.join(corpus, pat))
            if hits:
                return hits[0]
    return None


def find_video(corpus, vid):
    import glob as _g
    for v in id_variants(vid):
        for pat in (f'{v}.mp4', f'{v}*.mp4'):
            hits = _g.glob(os.path.join(corpus, pat))
            if hits:
                return hits[0]
    return None


def find_frames_dir(corpus, vid):
    for v in id_variants(vid):
        p = os.path.join(corpus, f'frames_{v}')
        if os.path.isdir(p):
            return p
    return os.path.join(corpus, f'frames_{vid}')


def validate_one(corpus, vid, gate_written=False, variant='root'):
    r = Report(vid)
    jp = output_file(corpus, 'data', variant, f'{vid}.json')
    if not os.path.exists(jp):
        r.block('JSON_MISSING', f'{os.path.relpath(jp, corpus)} 不存在')
        return r, None
    try:
        with open(jp, encoding='utf-8') as f:
            d = json.load(f)
    except json.JSONDecodeError as e:
        r.block('JSON_INVALID', f'{os.path.relpath(jp, corpus)} 解析失败：{e}')
        return r, None

    mp = output_file(corpus, 'understanding', variant, f'{vid}.md')
    md_text = None
    if os.path.exists(mp):
        with open(mp, encoding='utf-8') as f:
            md_text = f.read()

    tp = find_transcript(corpus, vid)
    tnorm = None
    if tp:
        with open(tp, encoding='utf-8') as f:
            raw = f.read()
        # 可溯源语料 = 原始转写稿 + C 区「纠正后」的值。
        # 两者都算「博主说过」：understand-prompt.md L113 要求正文保留纠正后的
        # 完整原话，所以 quote 里出现的本就是纠正后的词，拿原始 ASR 比对必然误报。
        # \x01 作分隔符——normalize 不会吃掉它，避免跨段拼出假命中。
        tnorm = normalize(raw) + '\x01' + normalize(asr_corrected_terms(md_text))

    video_path = find_video(corpus, vid)

    ct = d.get('content_type')
    if ct == '无关':
        return r, d

    check_enums(d, r)
    check_required_fields(d, r)
    check_causality(d, r)
    check_scope_upgrade(d, r, tnorm)
    check_quote_traceable(d, r, tnorm)
    check_technical_attribution(d, md_text, r, tnorm)
    check_atomic_layers(d, r)
    check_candidate_patterns(d, md_text, r)
    check_values_json(d, md_text, r)
    check_tags(d, r)
    check_flash_delivery_contract(corpus, vid, d, md_text, r, variant=variant)
    check_visual_inference(md_text, r)
    check_visual_cross_layer(d, md_text, r, corpus, vid)
    check_inference_lines(md_text, r)
    check_md_structure(md_text, r, ct)
    check_duration(d, r, video_path)
    check_frames(d, md_text, r, corpus, vid, video_path)
    check_price(d, r, md_text)
    check_reaction_types(d, r)
    check_asr(md_text, r, tnorm)
    check_rich_structure(d, r)
    check_self_reported_gate(d, r, gate_written)
    check_status_consistency(d, r)
    return r, d


def build_gate(r, stamp):
    """构造 quality_gate 对象。

    stamp 由 --write-gate 时的 --date 参数（或系统日期）提供。
    validated_at / validator_version 必须在这里写：merge-guide Step 1 与
    SKILL.md 的断点续跑判据都把 validated_at 非空作为准入条件，
    v3 的 build_gate 没有输出这两个键 —— 结果零 BLOCK 的记录也过不了合并准入。
    """
    codes = set(r.codes('BLOCK'))
    def ok(*prefixes):
        return not any(c.startswith(p) for c in codes for p in prefixes)
    return {
        'validated_at': stamp,
        'validator_version': VALIDATOR_VERSION,
        'schema_valid': ok('ENUM', 'FIELD', 'QUOTE_MISSING', 'JSON', 'RICH_', 'EPISODE_', 'VISUAL_STATUS', 'VISUAL_COVERAGE', 'VISUAL_EVIDENCE', 'CAPTION_STATUS'),
        'fact_boundary_valid': ok('CAUSAL', 'QUOTE_NOT_IN', 'TECH_TERM', 'LAYER'),
        'scope_valid': ok('SCOPE'),
        'candidate_pattern_valid': ok('B1_', 'D10_'),
        'tag_valid': ok('TAG_'),
        'visual_valid': ok('VISUAL', 'FRAME_SEQ'),
        'duration_valid': ok('DUR_', 'TS_'),
        'frame_valid': ok('FRAME'),
        'blocking_issues': sorted(codes),
        'warnings': sorted(set(r.codes('WARN'))),
    }


# ── 机械回修（--fix-safe）─────────────────────────────────────────────
#
# SKILL.md 把「自动回修」列为 v3 三大手段之一，但 v3 其实全靠人工定点修订。
# 这里只做**零语义判断**的修复：括号→tag_qualifier、组合枚举值→both、
# 全角标点归一。凡需要判断博主到底说了什么的（TECH_TERM / QUOTE / SCOPE），
# 一律不碰 —— 那些必须回到原始素材，脚本替你猜就是又一层折损。

_ENUM_ALIASES = {
    'evidence_source': {
        'visual+audio': 'both', 'audio+visual': 'both',
        'audio+vision': 'both', 'both+inference': 'both',
        '视听': 'both', 'audio,visual': 'both', 'visual,audio': 'both',
    },
}

# 标签的机械归一表：错前缀、简写、词典内某项的明确近义写法。
# 只放**无歧义**的映射——需要判断"他到底是什么意思"的一律不放，
# 那属于语义修订，得回原始素材。
_TAG_ALIASES = {
    '香-辣椒香': '香气-椒香',
    '香气-发酵椒香': '香气-发酵香',
    '口感-脆': '口感-脆嫩',
    '口感-嫩': '口感-滑嫩',
    '口感-软嫩': '口感-滑嫩',
    '口感-嫩滑': '口感-滑嫩',
    '口感-丝滑': '口感-细腻',
    '口感-细腻丝滑': '口感-细腻',
    '分量-偏少': '分量-小气',
    '分量-足': '分量-实诚',
    '功能-清口': '功能-解腻',
    '味道-无味': '味道-寡淡',
    '调味-纯粹': '其他-调味纯粹',
    '辣型-后返劲儿辣': '其他-后返劲辣',
    '味道-微甜不咸': '味道-甜',
}


def fix_one(d):
    """就地修复，返回 (修复条目描述列表)。"""
    fixes = []

    # ① 标签括号 → tag_qualifier
    qual_words = set(TAGDICT.get('qualifiers') or [])
    for i, dish in enumerate(d.get('dishes') or []):
        tags = dish.get('standard_tags')
        if not isinstance(tags, list):
            continue
        newtags, qmap = [], dict(dish.get('tag_qualifier') or {})
        for t in tags:
            t = str(t)
            m = re.match(r'^(.*?)[（(]\s*([^）)]*?)\s*[）)]\s*$', t)
            if not m:
                newtags.append(t)
                continue
            base, inner = m.group(1).strip(), m.group(2).strip()
            newtags.append(base)
            # 括号里是标准限定词 → 进 tag_qualifier；是别的说明（如"面包"、"5重"）
            # → 也进 tag_qualifier，但标注为原文，绝不丢弃信息。
            if inner:
                qmap[base] = inner if inner in qual_words else f'原括注：{inner}'
            fixes.append(f'dishes[{i}].standard_tags {t!r} → {base!r}'
                         f' + tag_qualifier[{base!r}]={qmap.get(base)!r}')
        # 括号剥完后，把词典外的明确近义写法归一（`口感-脆`→`口感-脆嫩`）。
        # 顺序很重要：先剥括号再归一，否则 `口感-脆(鱼泡嘎吱)` 匹配不上别名表。
        for j, t in enumerate(newtags):
            alias = _TAG_ALIASES.get(t)
            if alias:
                newtags[j] = alias
                if t in qmap:
                    qmap[alias] = qmap.pop(t)
                fixes.append(f'dishes[{i}].standard_tags {t!r} → {alias!r}（归一到词典）')
        if newtags != [str(t) for t in tags]:
            dish['standard_tags'] = newtags
            dish['tag_qualifier'] = qmap

    # ② 组合枚举值 → 规范值
    def fix_enum(obj, key, where):
        v = obj.get(key)
        if not isinstance(v, str):
            return
        if v in ENUM.get(key, []):
            return
        alias = _ENUM_ALIASES.get(key, {}).get(v.strip().lower())
        if alias:
            obj[key] = alias
            fixes.append(f'{where}.{key} {v!r} → {alias!r}')

    for i, dish in enumerate(d.get('dishes') or []):
        fix_enum(dish, 'evidence_source', f'dishes[{i}]')
    for i, e in enumerate(d.get('dimension_events') or []):
        fix_enum(e, 'evidence_source', f'dimension_events[{i}]')
    for i, v in enumerate(d.get('values_triggered') or []):
        fix_enum(v, 'evidence_source', f'values_triggered[{i}]')

    # ③ v3→v4 字段补全：缺 tag_qualifier / scope_quote 时补 null 结构。
    #    这是纯格式债，补它不引入任何新断言。
    for i, dish in enumerate(d.get('dishes') or []):
        if 'tag_qualifier' not in dish:
            dish['tag_qualifier'] = {}
            fixes.append(f'dishes[{i}] 补 tag_qualifier={{}}')
        if 'scope_quote' not in dish:
            dish['scope_quote'] = None
            fixes.append(f'dishes[{i}] 补 scope_quote=null')

    # ④ 剥掉产出自带的 quality_gate（v4.3）。这是纯粹的越权字段，
    #    删掉不损失任何信息——真正的闸门结论由 --write-gate 重新生成。
    if 'quality_gate' in d:
        g = d.pop('quality_gate')
        n = len((g or {}).get('blocking_issues') or [])
        fixes.append(f'删除产出自带的 quality_gate'
                     f'（它声明 blocking_issues={n} 条，非脚本所写，不可信）')
    # 生成期的 processing_status 只能是 完成待修订；自称 完整 的一律降回。
    if d.get('processing_status') == '完整':
        d['processing_status'] = '完成待修订'
        fixes.append('processing_status 完整 → 完成待修订'
                     '（`完整` 只能由 --write-gate 在零 BLOCK 时写）')

    # ⑤ cuisine 的机械可修变体：掺了店型或用斜杠组合的，取菜系部分。
    meta = d.get('_meta')
    if isinstance(meta, dict):
        cv = meta.get('cuisine')
        if isinstance(cv, str) and cv not in ENUM['cuisine']:
            head = re.split(r'[·/、（(]', cv)[0].strip()
            cand = head if head in ENUM['cuisine'] else None
            if cand is None and head:
                # `小吃` → `小吃综合`：闭集里有以它开头的唯一项时采用
                hits = [c for c in ENUM['cuisine'] if c.startswith(head)]
                cand = hits[0] if len(hits) == 1 else None
            if cand:
                meta['cuisine'] = cand
                fixes.append(f'_meta.cuisine {cv!r} → {cand!r}（取菜系级粒度）')

    # ⑥ 候选规律 sample_count → video_count / within_video_sample_count
    for i, p in enumerate(d.get('candidate_patterns') or []):
        if 'sample_count' in p and 'video_count' not in p:
            sc = p.pop('sample_count')
            p['video_count'] = 1
            p.setdefault('within_video_sample_count', sc)
            fixes.append(f'candidate_patterns[{i}] sample_count={sc!r} → '
                         f'video_count=1 + within_video_sample_count={sc!r}')
        if 'statement' in p and 'pattern' not in p:
            p['pattern'] = p.pop('statement')
            fixes.append(f'candidate_patterns[{i}] statement → pattern')

    return fixes


# ── 自检（--selftest）─────────────────────────────────────────────────
#
# 为什么需要这个：v3 把风险从「模型说谎」搬到了「校验器说谎」，而后者更隐蔽。
# 实测 v3 对 10 期语料报出 419 条问题，看起来很勤奋，但 B1_FORBIDDEN_PHRASE
# 因为读错字段名（statement vs pattern）**一次都没工作过** —— 而这恰恰是
# 「从单期偷渡稳定偏好」唯一的防线。规则存在但不生效，只是从 prompt 层
# 搬到了脚本层。所以每条规则都要有一对 should-fail / should-pass 样本。

_BASE_TRANSCRIPT = (
    '这个红烧肉非常的软非常的嫩，里边有马蹄儿，挺好吃。'
    '这个汤有点儿咸了，我觉得可能是酱油放多了。'
    '他们家这个东西一直都这样，每次来都一个味儿。'
)

_BASE_MD = """# 9001 · 测试馆

## 元信息

## A. 还原层

### A1 逐段记录

**[00:01 - 00:03]**
> [语音] 这个红烧肉非常的软非常的嫩，里边有马蹄儿，挺好吃。

【视觉覆盖】
- visual_status：reviewed_video
- visual_basis：连续观看 00:01-00:03
- caption_readability：not_present

【本段画面】
- [画面][evidence_level=direct_video][visual_basis=连续观看 00:01-00:03] 博主端起碗，用筷子夹起一块肉
- [推断][evidence_level=direct_video] 他对这道菜满意，依据是上一行的连续三次夹取动作

### A2 B档维度事件

| 维度 | 事件 | 客观描述 | 他的反应 | 反应类型 | 强度 | source_type | scope | evidence_source | 原话 | 时间戳 |
|---|---|---|---|---|---|---|---|---|---|---|
| D8服务 | 上菜 | 服务员上菜 | 无反应 | 无反应 | 无 | model_inference | this_serving | visual | — | 00:01-00:02 |

### A3 整体环境观感

普通小馆。

### A4 C档顺带记录

本期无。

### A5 价格交叉校验

| 项 | 值 | 来源 |
|----|-----|------|
| 语音报的总价 | 100 | 语音 |

### A6 附录·未定用途的画面观察

本期无。

### A7 无反应自检

D6/D8/D9/D11/D12 逐项过了一遍。

### A8 镜头时长分配

红烧肉 3s。

### A9 镜头与声画关系

本期已扫描，连续视频支持刺激到反应关系。

### A10 反应序列与可观察机会

本期已扫描，连续视频支持夹取到品尝序列。

### A11 三种注意力分配

本期已扫描，三种注意力分别记录。

### A12 判断弧线

品尝后形成正面判断。

### A13 本期判断事件

J1 红烧肉。

### A14 比较、转折与言行张力

本期未观察到比较或修正。

### A15 本期推理链

软嫩→正面评价。

## B. 提炼层

### B1 候选规律

#### 候选规律 1：本期他对这道平价家常菜评价偏正面（待验证）

### B2 价值观与红线

本期无。

### B3 方法论线索

### B4 表达DNA素材

### B5 原始感官措辞与细粒度描述

### B6 品味谱系与个人经验

### B7 开放解释与竞争性解释

## C. ASR 纠错清单

| 原转写 | 纠正后 | 依据类型 | 置信度 |
|---|---|---|---|
| 酱油 | 酱油 | 上下文 | 高 |
"""


def _base_record():
    """一份应当零 BLOCK 的探店记录。所有 should-fail 样本都由它变异而来。"""
    return {
        'id': '9001', 'content_type': '探店',
        # v4.3：生成时固定 完成待修订。基准样本用它，才能同时验证
        # ①干净产出不因状态被拦 ②STATUS_OVERCLAIM 只在写「完整」时触发。
        'processing_status': '完成待修订',
        'video_duration_sec': 5,
        '_meta': {'city': '北京', 'shop_name': '测试馆', 'cuisine': '本帮菜',
                  'shop_tier': '小馆', 'party_size': 2, 'price_total': 100,
                  'price_per_person': 50, 'price_tier': '<150',
                  'party_size_basis': '博主明说',
                  'price_per_person_basis': '总价÷人数'},
        'price_check': {'total_from_audio': 100, 'total_from_caption': None,
                        'sum_of_dishes': 100, 'consistent': True,
                        'mismatch_note': None, 'is_estimated': False},
        'dishes': [{
            'name': '红烧肉', 'object_level': '整道菜', 'price': 100,
            'sentiment': '正面', 'intensity': '中',
            'reason': '软嫩，有马蹄增加口感', 'standard_tags': ['口感-滑嫩'],
            'tag_qualifier': {}, 'blogger_attribution': None,
            'source_type': 'blogger_explicit', 'scope': 'this_serving',
            'scope_quote': None, 'evidence_source': 'audio',
            'confidence': 'high',
            'quote': '这个红烧肉非常的软非常的嫩，里边有马蹄儿，挺好吃',
            'timestamp': '00:01-00:03', 'shot_duration_sec': 3,
            'has_caption': False,
        }],
        'dimension_events': [{
            'dimension': 'D8服务', 'event': '上菜', 'description': '服务员上菜',
            'his_reaction': '无', 'reaction_type': '无反应', 'intensity': '无',
            'source_type': 'model_inference', 'scope': 'this_serving',
            'evidence_source': 'visual', 'quote': None,
            'timestamp': '00:01-00:02',
        }],
        'visual_coverage': [{
            'timestamp': '00:01-00:03',
            'visual_status': 'reviewed_video',
            'visual_basis': ['连续观看 00:01-00:03'],
            'caption_readability': 'not_present',
        }],
        'judgment_episodes': [{
            'episode_id': 'J1', 'object': '红烧肉',
            'initial_expectation': None, 'trigger': '入口品尝',
            'information_actions': ['夹取'], 'reaction_sequence': '夹取→品尝→评价',
            'reasoning_chain': '软嫩→正面', 'revision': None,
            'final_judgment': '正面', 'action_result': '继续吃',
            'comparison_refs': [], 'quote': '这个红烧肉非常的软非常的嫩',
            'timestamp': '00:01-00:03', 'confidence': 'high', 'open_questions': [],
        }],
        'comparisons': [],
        'tensions_and_revisions': [],
        'methodology_clues': {
            'information_acquisition': ['夹取品尝'], 'evaluation_order': [],
            'reasoning_logic': ['软嫩→正面'], 'anti_interference': [],
            'revision_mechanism': [], 'output_organization': [],
            'scan_notes': '六环节已扫描',
        },
        'expression_materials': [],
        'raw_sensory_descriptors': [],
        'audiovisual_analysis': {
            'shot_sound_relations': [{
                'episode_refs': ['J1'], 'timestamp': '00:01-00:03',
                'relation_type': '刺激→反应', 'evidence_level': 'direct_video',
                'visual_basis': ['连续观看 00:01-00:03'],
                'description': '夹取入口后评价', 'judgment_contribution': '保留顺序',
                'agency': '专家言行', 'uncertainty': None,
            }],
            'reaction_sequences': [{
                'episode_refs': ['J1'], 'object': '红烧肉',
                'evidence_level': 'direct_video',
                'visual_basis': ['连续观看 00:01-00:03'],
                'sequence': '夹取→品尝→评价',
                'observation_opportunity': '连续可见', 'interpretations': ['正面'],
                'resolved_by': '明确原话',
            }],
            'attention_distribution': [{
                'episode_refs': ['J1'], 'object': '红烧肉',
                'evidence_level': 'direct_video',
                'visual_basis': ['连续观看 00:01-00:03'],
                'expert_attention': '中', 'verbal_attention': '中',
                'editorial_attention': '中', 'alignment': '一致', 'basis': '连续视频',
            }],
            'judgment_arc': '品尝→正面评价', 'nonreaction_opportunities': [],
        },
        'taste_lineage': [],
        'open_interpretations': [],
        'shot_coverage_summary': {'shot_count': 1, 'covered_duration_sec': 2,
                                  'ledger_refs': ['S1']},
        'food_visual_evidence': [{'object': '红烧肉', 'observable': '夹起一块肉',
                                 'ledger_refs': ['S1:F1']}],
        'action_evidence': [{'episode_refs': ['J1'], 'observable': '夹取→品尝',
                            'ledger_refs': ['W1:A1']}],
        'microreaction_evidence': [],
        'sound_edit_evidence': [{'episode_refs': ['J1'], 'observable': '对白同步',
                                'ledger_refs': ['AU1']}],
        'audiovisual_claim_refs': [{'claim_id': 'C1', 'episode_refs': ['J1'],
                                   'ledger_refs': ['S1:F1', 'W1:A1', 'AU1']}],
        'candidate_patterns': [{
            'pattern': '本期他对这道平价家常菜评价偏正面',
            'video_count': 1, 'within_video_sample_count': 1,
            'confidence': 'low', 'not_stable_rule': True,
            'counter_example': None, 'next_verify': '看后续几期是否重复',
            'source_type': 'blogger_explicit',
            'scope': 'this_serving', 'scope_quote': None,
        }],
        # v4.6：探店类也要有 values_triggered。本期无触发写空数组——
        # 基准样本要是规范写法的范本（同 v4.5 修表态基准的 processing_status）。
        'values_triggered': [],
        'd10_ordering': {'worth_ordering_this_time': ['红烧肉'],
                         'avoid_this_time': None,
                         'strategy_notes': '本期只吃了 1 道菜（样本：1道，不足以成规律）',
                         'scope': 'this_serving'},
        'asr_corrections_count': 1,
    }


def _b2_only_in_md(d, md):
    """md 的 B2 写了价值观，json 的 values_triggered 为空——v3 时 B1 的同款洞。"""
    d['values_triggered'] = []
    # 注意要**替掉**基准里的"本期无"标注，否则 check_values_json 会正确豁免，
    # 这条断言就测不到东西了。
    return md.replace(
        '### B2 价值观与红线\n\n本期无。\n',
        '### B2 价值观与红线\n\n**红线：对预制菜的零容忍**\n'
        '- 原话："这个汤有点儿咸了"\n')


def _all_explicit_events(d, _md):
    """把 A2 换成清一色「明确评论」——REACT_ALL_EXPLICIT 需要 ≥3 条才触发。"""
    base = d['dimension_events'][0]
    d['dimension_events'] = [
        dict(base, event=f'事件{i}', reaction_type='明确评论', intensity='中',
             evidence_source='audio', source_type='blogger_explicit',
             quote='这个汤有点儿咸了')
        for i in range(3)]
    return None


def _mutations():
    """(检查码, 说明, 变异函数, md 覆写)。每项应当且只应当触发该码。"""
    def dish(f):
        def g(d, _md):
            f(d['dishes'][0])
            return None
        return g

    def ev(f):
        def g(d, _md):
            f(d['dimension_events'][0])
            return None
        return g

    def pat(f):
        def g(d, _md):
            f(d['candidate_patterns'][0])
            return None
        return g

    return [
        ('ENUM_INVALID', 'sentiment 填枚举外的值',
         dish(lambda x: x.update(sentiment='还不错'))),
        ('ENUM_INVALID', 'evidence_source 填组合变体 visual+audio',
         dish(lambda x: x.update(evidence_source='visual+audio'))),
        ('FIELD_MISSING', 'dishes 缺 object_level',
         dish(lambda x: x.pop('object_level'))),
        ('QUOTE_MISSING', 'quote 为空',
         dish(lambda x: x.update(quote=''))),
        ('QUOTE_NOT_IN_TRANSCRIPT', 'quote 改字（软嫩→软糯）',
         dish(lambda x: x.update(quote='这个红烧肉非常的软糯非常的嫩，里边有马蹄儿'))),
        ('QUOTE_ELIDED', 'quote 省略中间分句但未标省略号',
         dish(lambda x: x.update(quote='这个红烧肉非常的软，挺好吃'))),
        ('CAUSAL_IN_HYPOTHESIS', '推测类 reason 写成确定因果',
         dish(lambda x: x.update(source_type='blogger_hypothesis',
                                 quote='我觉得可能是酱油放多了',
                                 reason='因酱油放多导致偏咸'))),
        ('SCOPE_UPGRADE_NO_QUOTE', 'scope 升级但无 scope_quote',
         dish(lambda x: x.update(scope='dish_type'))),
        ('SCOPE_QUOTE_NOT_IN_TRANSCRIPT', 'scope 升级的原话是编的',
         dish(lambda x: x.update(scope='this_restaurant',
                                 scope_quote='他们家每次都这样从来没变过'))),
        ('D10_SCOPE_NOT_THIS_SERVING', 'd10 的 scope 被升级/写成自由文本',
         lambda d, _md: d['d10_ordering'].update(scope='本帮菜普遍如此')),
        ('TAG_QUALIFIER_INVALID', 'tag_qualifier 填了值域外的值',
         dish(lambda x: x.update(tag_qualifier={'口感-滑嫩': '很棒'}))),
        ('TAG_QUALIFIER_NONSTANDARD', 'tag_qualifier 用原括注过渡形态',
         dish(lambda x: x.update(tag_qualifier={'口感-滑嫩': '原括注：马蹄'}))),
        ('TAG_QUALIFIER_ORPHAN', 'tag_qualifier 的键不在 standard_tags 里',
         dish(lambda x: x.update(tag_qualifier={'口感-柴': '负面'}))),
        ('TAG_NOT_IN_DICT', '逃生口塞进超长描述（词典外）',
         dish(lambda x: x.update(
             standard_tags=['口感-其他-这个东西真好吃啊我简直了不知道怎么形容']))),
        ('B1_COUNT_MISMATCH', 'md 有 2 条候选规律而 json 只有 1 条',
         lambda d, md: md.replace(
             '#### 候选规律 1：本期他对这道平价家常菜评价偏正面（待验证）',
             '#### 候选规律 1：本期他对这道平价家常菜评价偏正面（待验证）\n\n'
             '#### 候选规律 2：本期他对分量的关注可能偏低（待验证）')),
        ('B1_COUNT_MISMATCH', 'md 用表格写候选规律而 json 为空（v2 实跑的主流写法）',
         lambda d, md: (d.__setitem__('candidate_patterns', []),
                        md.replace(
                            '#### 候选规律 1：本期他对这道平价家常菜评价偏正面（待验证）',
                            '| 编号 | 候选规律 | source_type |\n|---|---|---|\n'
                            '| R1 | 本期平价家常菜评价偏正面 | blogger_explicit |\n'
                            '| R2 | 本期他对分量关注偏低 | blogger_explicit |'))[1]),
        ('TECH_TERM_NOT_SPOKEN', '博主没说过的工艺词署名给博主',
         dish(lambda x: x.update(blogger_attribution='保水剂'))),
        ('LAYER_MIXED', 'model_inference 携带 blogger_attribution',
         dish(lambda x: x.update(source_type='model_inference',
                                 blogger_attribution='酱油放多'))),
        ('TAG_PAREN', '标签带括号',
         dish(lambda x: x.update(standard_tags=['口感-绵软（负面）']))),
        ('TAG_NO_PREFIX', '标签无前缀',
         dish(lambda x: x.update(standard_tags=['软嫩']))),
        ('TAG_NOT_IN_DICT', '标签不在闭词典内',
         dish(lambda x: x.update(standard_tags=['口感-齿颊生风']))),
        ('DUR_OVERFLOW', '镜头时长合计超实测时长',
         dish(lambda x: x.update(shot_duration_sec=999))),
        ('TS_DUPLICATE', '两道菜共用同一区间且都计了秒（真重复计入）',
         lambda d, _md: d['dishes'].append(dict(d['dishes'][0], name='另一道'))),
        ('TS_OVERLAP', '两道菜区间过半重叠且都计了秒',
         lambda d, _md: d['dishes'].append(
             dict(d['dishes'][0], name='另一道', timestamp='00:02-00:04',
                  shot_duration_sec=1))),
        ('TS_SHARED_NO_OWNER', '共用区间但双方都记 0 秒（该段无人认领）',
         lambda d, _md: (d['dishes'][0].update(shot_duration_sec=0),
                         d['dishes'].append(dict(d['dishes'][0], name='另一道',
                                                 shot_duration_sec=0)))[0]),
        ('B1_VIDEO_COUNT', '候选规律 video_count 不为 1',
         pat(lambda x: x.update(video_count=3))),
        ('B1_CONFIDENCE', '候选规律 confidence 不是 low',
         pat(lambda x: x.update(confidence='medium'))),
        ('B1_NO_NEXT_VERIFY', '候选规律缺 next_verify',
         pat(lambda x: x.pop('next_verify'))),
        ('B1_NO_DISCLAIMER', '候选规律缺 not_stable_rule',
         pat(lambda x: x.pop('not_stable_rule'))),
        ('B1_FORBIDDEN_PHRASE', '候选规律用 pattern 键写禁用表述（v3 漏检的那条）',
         pat(lambda x: x.update(pattern='他普遍厌恶技术处理牛肉，是标志性偏好'))),
        ('B1_FORBIDDEN_PHRASE', '禁用词的近义变体（核心标尺，差一字绕过 的标尺）',
         pat(lambda x: x.update(
             pattern='他可能以多层次口感作为评判的核心标尺'))),
        ('B1_MODEL_INFERENCE', '候选规律用 model_inference（v4.4 漏检的那条）',
         pat(lambda x: x.update(source_type='model_inference',
                                pattern='模型推测他通常更重视食材新鲜度',
                                quote=None))),
        ('VALUES_MODEL_INFERENCE', '价值观/红线用 model_inference（污染比 B1 更重）',
         lambda d, _md: d.__setitem__('values_triggered', [{
             'content': '模型推测他有食安零容忍红线', 'context': 'x',
             'intensity': '强', 'quote': None, 'timestamp': '00:01-00:03',
             'value_type': '红线', 'source_type': 'model_inference',
             'evidence_source': 'inference', 'confidence': 'low'}])),
        ('B2_NO_JSON', '探店 md 的 B2 有价值观而 json 没有 values_triggered',
         _b2_only_in_md),
        ('B1_NO_JSON', 'json 完全没有 candidate_patterns 键',
         lambda d, _md: (d.pop('candidate_patterns'), None)[1]),
        ('DERIVED_NO_BASIS', '人数/人均是派生值却无 basis 说明',
         lambda d, _md: d['_meta'].pop('party_size_basis')),
        ('REACT_ALL_EXPLICIT', 'A2 整表全是明确评论（漏了无反应）',
         _all_explicit_events),
        ('D10_FORBIDDEN_PHRASE', 'd10 策略写成通用规律',
         lambda d, _md: d['d10_ordering'].update(
             strategy_notes='本期样本：凡是便宜家常菜都是这样稳')),
        ('D10_READER_ADVICE', 'd10 策略写成面向读者的建议',
         lambda d, _md: d['d10_ordering'].update(
             strategy_notes='本期建议优先点红烧肉（样本：1道）')),
        ('REACT_SOURCE_CONFLICT', '无反应却标 evidence_source=audio',
         ev(lambda x: x.update(evidence_source='audio'))),
        ('PRICE_INCONSISTENT_FLAG', '价格三数打架却标 consistent',
         lambda d, _md: d['price_check'].update(total_from_caption=200)),
        ('STATUS_OVERCLAIM', '有 BLOCK 却自称完整',
         lambda d, _md: (d.update(processing_status='完整'),
                         d['dishes'][0].update(sentiment='瞎写'))[0]),
        ('GATE_SELF_REPORTED', '产出自带未签发 quality_gate（自我声明合规）',
         lambda d, _md: d.update(quality_gate={
             'validated_at': None, 'validator_version': 'self-reported',
             'schema_valid': True, 'blocking_issues': [], 'warnings': []})),
        ('MD_H2_MISSING', 'md 缺二级标题',
         lambda d, md: md.replace('## C. ASR 纠错清单', '## C.ASR纠错清单')),
        ('MD_H3_DIVERGED', 'md 小节编号挂了别的内容',
         lambda d, md: md.replace('### A3 整体环境观感', '### A3 无反应自检')),
        ('VISUAL_HAS_INFERENCE', '[画面] 行混入推断词',
         lambda d, md: md.replace(
             '- [画面][evidence_level=direct_video][visual_basis=连续观看 00:01-00:03] 博主端起碗，用筷子夹起一块肉',
             '- [画面][evidence_level=direct_video][visual_basis=连续观看 00:01-00:03] 博主表情明显不适，嘴角下撇')),
        ('VISUAL_HAS_INFERENCE', '[花字] 行「」外混入推断词（引用内豁免、引用外照拦）',
         lambda d, md: md.replace('### A3 整体环境观感',
                                  '### A3 整体环境观感\n\n'
                                  '- [花字][evidence_level=single_frame] 这画面明显像是店招')),
        ('VISUAL_STATUS_NO_MD_BASIS', 'JSON 声称看过画面但 A1 无客观观察',
         lambda d, md: md.replace(
             '- [画面][evidence_level=direct_video][visual_basis=连续观看 00:01-00:03] 博主端起碗，用筷子夹起一块肉',
             '- 已记录语音，未留下视觉观察')),
        ('FRAME_SEQ_NO_MD_OBSERVATION', 'frame_sequence 只有一个帧端点',
         lambda d, md: (d['audiovisual_analysis']['shot_sound_relations'][0].update(
             evidence_level='frame_sequence', visual_basis=['f_00001']), md)[1]),
        ('FRAME_SEQ_NO_MD_OBSERVATION', 'frame_sequence 与 A1 引用的帧不相交',
         lambda d, md: (d['audiovisual_analysis']['shot_sound_relations'][0].update(
             evidence_level='frame_sequence', visual_basis=['f_00002', 'f_00003']),
             md.replace('visual_basis=连续观看 00:01-00:03',
                        'visual_basis=f_00004-f_00005', 1))[1]),
        ('FRAME_REF_BROKEN', 'JSON visual_basis 引用不存在的帧',
         lambda d, _md: d['audiovisual_analysis']['shot_sound_relations'][0].update(
             evidence_level='frame_sequence', visual_basis=['f_00001', 'f_09999'])),
        ('ASR_CORRECTION_NOT_UNIQUE', 'C 区「纠正后」给多个候选且含工艺词（洗白通道）',
         lambda d, md: md.replace('| 酱油 | 酱油 | 上下文 | 高 |',
                                  '| 剪发 | 碱发/化学发制 | 上下文 | 高 |')),
        ('ASR_ROW_NOT_IN_TRANSCRIPT', 'C 区「原转写」在他期转写稿中才有（串台污染）',
         lambda d, md: md.replace('| 酱油 | 酱油 | 上下文 | 高 |',
                                  '| 一个穿满白海军的欧式宇天空镜 | 存疑保留 | 存疑保留 | 低 |')),
        ('A5_ARITHMETIC_MISMATCH', 'A5 加总算式与结果不符',
         lambda d, md: md.replace('| 语音报的总价 | 100 | 语音 |',
                                  '| 语音报的总价 | 100 | 语音 |\n| 合计 | 283+161+204+144+161.1=1027.9 | 计算 |')),
        ('INFERENCE_IS_INDUSTRY_KNOWLEDGE', '[推断] 行搬运行业常识',
         lambda d, md: md.replace(
             '- [推断][evidence_level=direct_video] 他对这道菜满意，依据是上一行的连续三次夹取动作',
             '- [推断] "微甜""香油重"为本帮菜典型特征')),
        ('TECH_TERM_INFERENCE_UNHEDGED', '[推断] 行写死工艺词等式而未划清界限',
         lambda d, md: md.replace(
             '- [推断][evidence_level=direct_video] 他对这道菜满意，依据是上一行的连续三次夹取动作',
             '- [推断] "剪发"=碱发处理海参，博主将异味归因于原料处理方式')),
        ('FRAME_REF_BROKEN', 'md 引用不存在的帧',
         lambda d, md: md.replace('### A3 整体环境观感',
                                  '### A3 整体环境观感\n\nf_09999 可见门头。')),
        ('RICH_FIELD_MISSING', '探店产物缺 visual_coverage（兼容期 WARN）',
         lambda d, _md: (d.pop('visual_coverage'), None)[1]),
        ('VISUAL_STATUS_INVALID', 'visual_status 枚举非法',
         lambda d, _md: d['visual_coverage'][0].update(visual_status='看过一点')),
        ('CAPTION_STATUS_INVALID', 'caption_readability 枚举非法',
         lambda d, _md: d['visual_coverage'][0].update(caption_readability='大概清楚')),
        ('EPISODE_ID_INVALID', 'episode_id 缺失',
         lambda d, _md: (d['judgment_episodes'][0].pop('episode_id'), None)[1]),
        ('VISUAL_EVIDENCE_INVALID', '视觉条目缺 evidence_level',
         lambda d, _md: (d['audiovisual_analysis']['shot_sound_relations'][0].pop('evidence_level'), None)[1]),
        ('EPISODE_REF_MISSING', '视觉条目缺 episode_refs',
         lambda d, _md: (d['audiovisual_analysis']['reaction_sequences'][0].pop('episode_refs'), None)[1]),
        ('EPISODE_REF_BROKEN', '视觉条目引用不存在 episode',
         lambda d, _md: d['audiovisual_analysis']['attention_distribution'][0].update(episode_refs=['J999'])),
    ]


def _write_fixture(root, d, md, n_frames=5):
    os.makedirs(os.path.join(root, 'data'), exist_ok=True)
    os.makedirs(os.path.join(root, 'understanding'), exist_ok=True)
    os.makedirs(os.path.join(root, 'run-manifests'), exist_ok=True)
    os.makedirs(os.path.join(root, 'shot-ledgers'), exist_ok=True)
    os.makedirs(os.path.join(root, 'visual-ledgers'), exist_ok=True)
    os.makedirs(os.path.join(root, 'reaction-windows'), exist_ok=True)
    os.makedirs(os.path.join(root, 'sound-edit-ledgers'), exist_ok=True)
    os.makedirs(os.path.join(root, 'assembly'), exist_ok=True)
    fdir = os.path.join(root, 'frames_9001')
    os.makedirs(fdir, exist_ok=True)
    for i in range(1, n_frames + 1):
        with open(os.path.join(fdir, f'f_{i:05d}.jpg'), 'wb') as f:
            f.write(b'\xff\xd8\xff')
    with open(os.path.join(root, 'data', '9001.json'), 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False)
    with open(os.path.join(root, 'understanding', '9001.md'), 'w', encoding='utf-8') as f:
        f.write(md)
    with open(os.path.join(root, '9001_audio_transcript.md'), 'w', encoding='utf-8') as f:
        f.write(_BASE_TRANSCRIPT)
    manifest = {
        'id': '9001', 'model_family': '5.3-flash',
        'inputs': {'video_supplied': True, 'video_files': ['9001.mp4'],
                   'base_frames': [],
                   'continuous_windows': [{'timestamp': '00:01-00:03',
                                           'assets': ['9001.mp4']}]},
        'phases': {
            'shot_ledger': {'status': 'complete', 'assets_supplied': ['9001.mp4']},
            'visual_ledger': {'status': 'complete', 'assets_supplied': ['9001.mp4']},
            'reaction_windows': {'status': 'complete', 'assets_supplied': ['9001.mp4']},
            'sound_edit': {'status': 'complete', 'assets_supplied': ['9001.mp4']},
            'assembly': {'status': 'complete', 'assets_supplied': []},
        },
    }
    with open(os.path.join(root, '9001.mp4'), 'wb') as f:
        f.write(b'fixture')
    with open(os.path.join(root, 'run-manifests', '9001.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f)
    with open(os.path.join(root, 'shot-ledgers', '9001.json'), 'w', encoding='utf-8') as f:
        json.dump({'id': '9001', 'shots': [{'shot_id': 'S1', 'timestamp': '00:01-00:03',
            'boundary': 'continuation', 'assets_reviewed': ['9001.mp4'],
            'shot_scale': 'medium', 'camera_angle': 'eye_level', 'composition': ['centered'],
            'depth_of_field': 'medium', 'camera_motion': 'static', 'lighting': {},
            'subjects': [], 'food_morphology': [], 'environment': {}, 'captions': [],
            'observation_result': 'observed', 'uncertainty': None}]}, f)
    with open(os.path.join(root, 'visual-ledgers', '9001.json'), 'w', encoding='utf-8') as f:
        json.dump({'id': '9001', 'segments': [{
            'timestamp': '00:01-00:03', 'input_mode': 'continuous_video',
            'assets_reviewed': ['9001.mp4'],
            'static_observations': ['博主端起碗'], 'observable_actions': ['夹起肉'],
            'captions': [], 'raw_detector_observations': [], 'not_observable': []}]}, f)
    with open(os.path.join(root, 'reaction-windows', '9001.json'), 'w', encoding='utf-8') as f:
        json.dump({'id': '9001', 'windows': [{
            'window_id': 'W1', 'episode_refs': ['J1'], 'timestamp': '00:01-00:03',
            'input_mode': 'continuous_video', 'sample_fps': 25,
            'assets_reviewed': ['9001.mp4', '9001.mp4'], 'face_visibility': 'full_clear',
            'baseline': {}, 'actions': [], 'microreactions': [], 'camera_motion': [],
            'observation_result': 'observed', 'not_observable': [], 'confidence': 'high'}]}, f)
    with open(os.path.join(root, 'sound-edit-ledgers', '9001.json'), 'w', encoding='utf-8') as f:
        json.dump({'id': '9001', 'shots': [], 'sound_events': [], 'editing_relations': []}, f)
    with open(os.path.join(root, 'assembly', '9001.json'), 'w', encoding='utf-8') as f:
        json.dump({'id': '9001', 'sections': {}}, f)


def selftest():
    """确认每条规则都能、且只在该情形下拦住。"""
    import copy, shutil, tempfile
    root = tempfile.mkdtemp(prefix='gvgate-selftest-')
    try:
        # ① 基准样本必须零 BLOCK。它若不干净，后面所有断言都无意义。
        _write_fixture(root, _base_record(), _BASE_MD)
        r, _ = validate_one(root, '9001')
        print('=== ① 基准样本（应零 BLOCK）===')
        if r.blocks:
            for _, c, m in r.blocks:
                print(f'  ❌ [{c}] {m}')
            print('\n基准样本不干净 —— 后续断言不可信，先修基准或规则。')
            return 2
        print('  ✅ 零 BLOCK'
              + (f'（{len(r.warns)} WARN：{r.codes("WARN")}）' if r.warns else ''))

        # ② 表态类样本也必须零 BLOCK（v3 在这里必然误杀）。
        stmt = {
            # 同探店基准：生成时固定 完成待修订（v4.5 修——原先写 完整，
            # 虽不影响零 BLOCK 判定，但基准样本就该是规范写法的范本）
            'id': '9001', 'content_type': '表态', 'processing_status': '完成待修订',
            'video_duration_sec': 5, 'topic': '回应质疑',
            'values_triggered': [{
                'content': '不收钱推广', 'context': '有人质疑',
                'intensity': '强', 'quote': '这个汤有点儿咸了',
                'timestamp': '00:01-00:03', 'value_type': '红线',
                'source_type': 'blogger_explicit', 'evidence_source': 'audio',
                'confidence': 'high'}],
            'expression_notes': '语速加快', 'asr_corrections_count': 0,
        }
        stmt_md = ('## A. 还原层\n\n### A1 逐段记录\n\n- [画面] 他直视镜头\n\n'
                   '## B. 提炼层\n\n### B1 价值观与红线\n\n- x\n\n'
                   '### B2 内在张力（如有）\n\n### B3 表达DNA素材\n\n'
                   '### B4 沉默边界（如有）\n\n### B5 其他观察\n\n'
                   '## C. ASR 纠错清单\n')
        _write_fixture(root, stmt, stmt_md)
        r2, _ = validate_one(root, '9001')
        print('\n=== ② 表态类基准样本（应零 BLOCK）===')
        if r2.blocks:
            for _, c, m in r2.blocks:
                print(f'  ❌ [{c}] {m}')
        else:
            print('  ✅ 零 BLOCK')

        # ③ 视觉跨层 should-pass：已检查但无判断相关信号合法；旧契约不误杀。
        no_signal = copy.deepcopy(_base_record())
        no_signal['audiovisual_analysis'] = {
            'shot_sound_relations': [], 'reaction_sequences': [],
            'attention_distribution': [], 'judgment_arc': None,
            'nonreaction_opportunities': [],
        }
        no_signal_md = _BASE_MD.replace(
            '- [画面][evidence_level=direct_video][visual_basis=连续观看 00:01-00:03] 博主端起碗，用筷子夹起一块肉',
            '- [视觉核验][visual_basis=连续观看 00:01-00:03] 已检查但无判断相关视觉信号')
        _write_fixture(root, no_signal, no_signal_md)
        r3, _ = validate_one(root, '9001')

        legacy = copy.deepcopy(_base_record())
        legacy.pop('visual_coverage')
        legacy.pop('judgment_episodes')
        legacy.pop('audiovisual_analysis')
        _write_fixture(root, legacy, _BASE_MD)
        r4, _ = validate_one(root, '9001')
        visual_codes = {'VISUAL_STATUS_NO_MD_BASIS', 'FRAME_SEQ_NO_MD_OBSERVATION'}
        pass_blocks = [x for x in r3.blocks if x[1] in visual_codes]
        legacy_blocks = [x for x in r4.blocks if x[1] in visual_codes]
        print('\n=== ③ 视觉跨层 should-pass（应零相关 BLOCK）===')
        if pass_blocks or legacy_blocks:
            for _, c, m in pass_blocks + legacy_blocks:
                print(f'  ❌ [{c}] {m}')
            return 2
        print('  ✅ 无信号留痕与旧契约均未误杀')

        # 专业账本引用摘要必须存在且每条高层 claim 能回指 ledger。
        missing_summary = copy.deepcopy(_base_record())
        missing_summary.pop('shot_coverage_summary')
        _write_fixture(root, missing_summary, _BASE_MD)
        summary_report, _ = validate_one(root, '9001')
        if 'FLASH_LEDGER_SUMMARY_MISSING' not in summary_report.codes('BLOCK'):
            print('  ❌ FLASH_LEDGER_SUMMARY_MISSING 未触发')
            return 2
        broken_claim = copy.deepcopy(_base_record())
        broken_claim['audiovisual_claim_refs'][0]['ledger_refs'] = []
        _write_fixture(root, broken_claim, _BASE_MD)
        claim_report, _ = validate_one(root, '9001')
        if 'FLASH_CLAIM_REF_MISSING' not in claim_report.codes('BLOCK'):
            print('  ❌ FLASH_CLAIM_REF_MISSING 未触发')
            return 2
        print('  ✅ 专业账本摘要与 claim refs 规则生效')

        # ④ Flash 专属契约：模板漂移、缺阶段产物、Markdown 单端点序列均须拦截。
        contract_cases = []
        freeform_md = _BASE_MD.replace(
            '### A9 镜头与声画关系',
            '### A9 镜头与声画关系\n\n```mermaid\ngraph LR\nA-->B\n```')
        _write_fixture(root, _base_record(), freeform_md)
        contract_cases.append(('FLASH_FREEFORM_DRIFT', validate_one(root, '9001')[0]))

        _write_fixture(root, _base_record(), _BASE_MD)
        os.remove(os.path.join(root, 'run-manifests', '9001.json'))
        contract_cases.append(('RUN_MANIFEST_MISSING', validate_one(root, '9001')[0]))

        single_endpoint_md = _BASE_MD.replace(
            '- [画面][evidence_level=direct_video][visual_basis=连续观看 00:01-00:03] 博主端起碗，用筷子夹起一块肉',
            '- [画面][evidence_level=frame_sequence][visual_basis=f_00001] 博主端起碗')
        _write_fixture(root, _base_record(), single_endpoint_md)
        contract_cases.append(('FRAME_SEQ_SINGLE_ENDPOINT', validate_one(root, '9001')[0]))

        print('\n=== ④ Flash 专属契约 should-fail ===')
        contract_failed = 0
        for code, report in contract_cases:
            got = set(report.codes('BLOCK')) | set(report.codes('WARN'))
            if code in got:
                print(f'  ✅ {code}')
            else:
                contract_failed += 1
                print(f'  ❌ {code} 未触发；实际：{sorted(got) or "无"}')

        # ⑤ 每条通用变异应触发指定码。
        print('\n=== ⑤ 逐规则 should-fail 断言 ===')
        passed = failed = 0
        for code, desc, mut in _mutations():
            d = copy.deepcopy(_base_record())
            md = mut(d, _BASE_MD) or _BASE_MD
            # 变异函数写错（例如 lambda 返回了 dict.pop 的结果而非 md 文本）
            # 不该炸掉整轮自检——那样只能看到一个 TypeError，看不出是哪条坏了。
            if not isinstance(md, str):
                failed += 1
                print(f'  ❌ {code:26s} {desc}\n'
                      f'       变异函数返回了 {type(md).__name__} 而非 md 文本；'
                      f'修改 json 的变异应返回 None')
                continue
            _write_fixture(root, d, md)
            rr, _ = validate_one(root, '9001')
            got = set(rr.codes('BLOCK')) | set(rr.codes('WARN'))
            if code in got:
                passed += 1
                print(f'  ✅ {code:26s} {desc}')
            else:
                failed += 1
                print(f'  ❌ {code:26s} {desc}\n'
                      f'       未触发！实际报出：{sorted(got) or "无"}')
        print(f'\n{"=" * 60}\n{passed} 条规则生效，{failed} 条未生效'
              f'（共 {passed + failed}）')
        if failed or contract_failed or r2.blocks or pass_blocks or legacy_blocks:
            print('\n有规则未生效或基准误杀 —— 这正是 v3 的失效方式：'
                  '闸门报了一堆问题，而最关键的那条其实从未运行。')
            return 1
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description='输出后验证闸门')
    ap.add_argument('corpus', nargs='?', help='语料目录（--selftest 时可省略）')
    ap.add_argument('--id', action='append', help='只校验指定编号，可重复')
    ap.add_argument('--variant', default=DEFAULT_VARIANT,
                    help=f'产物版本目录，默认 {DEFAULT_VARIANT}；root 表示旧根目录布局')
    ap.add_argument('--json', action='store_true', help='输出机器可读结果')
    ap.add_argument('--write-gate', action='store_true',
                    help='把 quality_gate 与降级后的 processing_status 回写 data/*.json')
    ap.add_argument('--date', default=None,
                    help='写入 quality_gate.validated_at 的日期（YYYY-MM-DD），默认取系统日期')
    ap.add_argument('--selftest', action='store_true',
                    help='自检各条规则是否真的生效（内置样本，不读语料目录）')
    ap.add_argument('--fix-safe', action='store_true',
                    help='机械回修零语义判断的问题（标签括号/组合枚举/v4新字段），'
                         '改写 data/*.json。需语义判断的问题不碰')
    ap.add_argument('--verbose', action='store_true',
                    help='显示默认静默的低价值 WARN（合法的拼接引用等）')
    ap.add_argument('--dry-run', action='store_true',
                    help='与 --fix-safe 合用：只列出将要修的内容，不落盘')
    a = ap.parse_args()

    global VERBOSE
    VERBOSE = a.verbose

    if a.selftest:
        return selftest()

    stamp = a.date or datetime.date.today().isoformat()

    if not a.corpus:
        print('[用法错误] 需指定语料目录（或用 --selftest）', file=sys.stderr)
        return 2
    corpus = os.path.abspath(a.corpus)
    try:
        variant = validate_variant(a.variant)
    except ValueError as exc:
        print(f'[用法错误] {exc}', file=sys.stderr)
        return 2
    ddir = output_dir(corpus, 'data', variant)
    if not os.path.isdir(ddir):
        print(f'[用法错误] {ddir} 不存在', file=sys.stderr)
        return 2

    ids = a.id or sorted(os.path.splitext(f)[0]
                         for f in os.listdir(ddir) if f.endswith('.json'))
    if not ids:
        print(f'[用法错误] {os.path.relpath(ddir, corpus)}/ 下没有 json', file=sys.stderr)
        return 2

    if a.fix_safe:
        total = 0
        for vid in ids:
            jp = os.path.join(ddir, f'{vid}.json')
            try:
                with open(jp, encoding='utf-8') as f:
                    d = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                print(f'跳过 {vid}：{e}')
                continue
            fixes = fix_one(d)
            if not fixes:
                continue
            total += len(fixes)
            print(f'\n=== {vid} ===  {len(fixes)} 项')
            for x in fixes:
                print(f'  · {x}')
            if not a.dry_run:
                with open(jp, 'w', encoding='utf-8') as f:
                    json.dump(d, f, ensure_ascii=False, indent=2)
        print(f'\n{"=" * 60}\n共 {total} 项'
              + ('（--dry-run，未落盘）' if a.dry_run else '已回修'))
        print('剩余问题需语义判断，回到原始素材定点修订后重跑闸门。')
        return 0

    results, gates, tally = [], {}, Counter()
    for vid in ids:
        # --write-gate 时不报 GATE_SELF_REPORTED：它正要覆盖那个字段，
        # 否则会成为死结（报错→无法通过→字段永远清不掉）。
        r, d = validate_one(corpus, vid, gate_written=a.write_gate, variant=variant)
        g = build_gate(r, stamp)
        results.append((r, d, g))
        gates[vid] = g
        for _, c, _ in r.items:
            tally[c] += 1

        if a.write_gate and d is not None:
            # 先剥掉产出自带的 quality_gate（若有），再写脚本自己的结论。
            # 不这么做的话，手填的字段会与脚本结论混在一个对象里，
            # 而 GATE_SELF_REPORTED 只在下一次校验才发现——太晚了。
            had_self = 'quality_gate' in d
            d['quality_gate'] = g
            # ★ processing_status 由闸门单向裁决，不看它原来写的是什么：
            # 无 BLOCK ⇒ 升为 完整；有 BLOCK ⇒ 降为 完成待修订。
            # v4 只做了后半句（且限于原值为 完整 时），于是"生成时固定写
            # 完成待修订"的新约定下，干净的产出永远升不上去。
            st = d.get('processing_status')
            if st not in ('降级-纯转写', '待确认', '失败', '无关'):
                d['processing_status'] = '完成待修订' if r.blocks else '完整'
            with open(os.path.join(ddir, f'{vid}.json'), 'w', encoding='utf-8') as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
            if had_self:
                print(f'  [{vid}] 已用脚本结论覆盖产出自带的 quality_gate')

    n_block = sum(1 for r, _, _ in results if r.blocks)

    if a.json:
        print(json.dumps({
            'total': len(results),
            'blocked': n_block,
            'issue_tally': dict(tally.most_common()),
            'per_video': {r.id: {'blocks': [f'{c}: {m}' for _, c, m in r.blocks],
                                 'warns': [f'{c}: {m}' for _, c, m in r.warns],
                                 'quality_gate': g}
                          for r, _, g in results},
        }, ensure_ascii=False, indent=2))
        return 1 if n_block else 0

    for r, _, _ in results:
        if not r.items:
            print(f'\n=== {r.id} ===  ✅ 通过')
            continue
        print(f'\n=== {r.id} ===  BLOCK {len(r.blocks)} / WARN {len(r.warns)}')
        for _, c, m in r.blocks:
            print(f'  ❌ [{c}] {m}')
        for _, c, m in r.warns:
            print(f'  ⚠️  [{c}] {m}')

    print('\n' + '=' * 60)
    print(f'共 {len(results)} 期，{n_block} 期存在 BLOCK，{len(results) - n_block} 期可标「完整」')
    if tally:
        print('\n问题类型计数（降序）：')
        for c, n in tally.most_common():
            print(f'  {n:4d}  {c}')
    print('\nBLOCK 未清零前，processing_status 一律写「完成待修订」，不得进入专家蒸馏。')
    return 1 if n_block else 0


if __name__ == '__main__':
    sys.exit(main())
