#!/usr/bin/env python3
"""Non-blocking richness audit for gourmet-video understanding outputs.

This script diagnoses likely omissions. It never changes corpus files and never decides
whether content is true. Metrics are normalized by video duration and should be compared
with same-genre golden records rather than treated as quotas.
"""

import argparse
import json
import os
import re
import sys
import tempfile
from collections import Counter
from output_paths import DEFAULT_VARIANT, output_dir, validate_variant


RICH_JSON_FIELDS = [
    'visual_coverage',
    'judgment_episodes',
    'comparisons',
    'tensions_and_revisions',
    'methodology_clues',
    'expression_materials',
    'raw_sensory_descriptors',
    'audiovisual_analysis',
    'taste_lineage',
    'open_interpretations',
]

REQUIRED_RICH_H3 = [
    'A9 镜头与声画关系',
    'A10 反应序列与可观察机会',
    'A11 三种注意力分配',
    'A12 判断弧线',
    'A13 本期判断事件',
    'A14 比较、转折与言行张力',
    'A15 本期推理链',
    'B3 方法论线索',
    'B4 表达DNA素材',
    'B5 原始感官措辞与细粒度描述',
    'B6 品味谱系与个人经验',
    'B7 开放解释与竞争性解释',
]

ACTION_WORDS = (
    '掰开', '拨开', '翻面', '凑近', '闻', '捏', '按压', '对光', '数', '复尝',
    '再尝', '询问', '问同伴', '看向同伴', '放下筷子', '停吃', '退菜', '打包',
    '夹起', '入口', '咀嚼中断', '起身', '递给同伴',
)
COMPARISON_WORDS = ('不如', '相比', '比', '更', '以前', '小时候', '外面', '北京', '预期')
TURN_WORDS = ('但是', '不过', '其实', '反而', '还是我个人', '可能是', '虽然')
EXPRESSION_WORDS = ('类比', '反问', '口头禅', '推荐句', '否定句', '语速', '停顿', '重复')
GENERIC_VISUAL = (
    '中景', '近景', '特写', '正常咀嚼', '表情自然', '菜品画面',
    '人物出现在画面中', '画面中出现餐具', '画面中出现食物',
    '画面中出现建筑结构', '户外环境，含天空区域', '室内环境',
    '场景分类以', '分类含 people', '分类含 adult', '分类含 tableware',
    '分类含 utensil', '分类含 food',
)
SEMANTIC_VISUAL_WORDS = (
    '内部', '断面', '挂汁', '肥瘦', '色泽', '形状', '颗粒', '分层', '焦边',
    '气泡', '菜单', '店招', '包装', '挤压', '变形',
)

# 2026-08-27 实测 0011–0030（20期、75.42分钟）的批次基线。
# 它们是召回下限而非逐条配额；不同题材应看同类金标，不得为过线注水。
RICH_BASELINE_0011_0030 = {
    'md_chars_per_min': 1878.18,
    'visual_lines_per_min': 5.21,
}

HERE = os.path.dirname(os.path.abspath(__file__))
REF_DIR = os.path.join(os.path.dirname(HERE), 'references')


def prefix_id(name):
    m = re.match(r'(\d{4})', name)
    return m.group(1) if m else name


def find_output(directory, vid, suffix):
    """Find the matching sibling without mixing pure IDs and csvrow variants."""
    if not os.path.isdir(directory):
        return None
    exact = os.path.join(directory, f'{vid}{suffix}')
    if os.path.isfile(exact):
        return exact
    # Compatibility fallback only when the exact stem is absent. Prefer the same full
    # stem before considering numeric-prefix variants, because one corpus may contain
    # both 0001.json and 0001_csvrow2.json.
    matches = sorted(
        os.path.join(directory, name)
        for name in os.listdir(directory)
        if os.path.splitext(name)[0] == vid and name.endswith(suffix)
    )
    if matches:
        return matches[0]
    variants = sorted(
        os.path.join(directory, name)
        for name in os.listdir(directory)
        if prefix_id(name) == prefix_id(vid) and name.endswith(suffix)
    )
    return variants[0] if len(variants) == 1 else None


def section_body(md, heading):
    m = re.search(rf'^###\s+{re.escape(heading)}[^\n]*\n(.*?)(?=^###\s+|^##\s+|\Z)',
                  md, re.M | re.S)
    return m.group(1).strip() if m else None


def a1_segments(md):
    """Return timestamped A1 blocks; later analytical sections cannot supply evidence."""
    m = re.search(r'^###\s+A1\s+逐段记录[^\n]*\n(.*?)(?=^###\s+|^##\s+|\Z)',
                  md or '', re.M | re.S)
    if not m:
        return []
    body = m.group(1)
    heads = list(re.finditer(
        r'^\*\*\[\s*(\d{1,3}:\d{2})\s*[-–~]\s*(\d{1,3}:\d{2})\s*\]\*\*\s*$',
        body, re.M))
    out = []
    for i, head in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
        text = body[head.end():end]
        out.append({
            'range': parse_range_seconds(f'{head.group(1)}-{head.group(2)}'),
            'visual_lines': [line.strip() for line in text.splitlines()
                             if '[画面]' in line or '[花字]' in line],
            'no_signal': '已检查但无判断相关视觉信号' in text,
        })
    return out


def overlapping_segments(segments, timestamp):
    rng = parse_range_seconds(timestamp)
    if not rng:
        return []
    return [seg for seg in segments if seg['range'] and
            min(rng[1], seg['range'][1]) > max(rng[0], seg['range'][0])]


def nonempty(value):
    if value is None or value == '' or value == [] or value == {}:
        return False
    return True


def parse_range_seconds(value):
    if not isinstance(value, str):
        return None
    parts = re.split(r'\s*[-–~]\s*', value.strip())
    if len(parts) != 2:
        return None
    def one(text):
        m = re.match(r'^(\d{1,3}):(\d{2})$', text)
        return int(m.group(1)) * 60 + int(m.group(2)) if m else None
    start, end = one(parts[0]), one(parts[1])
    if start is None or end is None or end < start:
        return None
    return start, end


def union_duration(ranges):
    merged = []
    for start, end in sorted(ranges):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return sum(end - start for start, end in merged)


def audit_one(corpus, json_path, variant='root'):
    vid = os.path.splitext(os.path.basename(json_path))[0]
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)
    md_path = find_output(output_dir(corpus, 'understanding', variant), vid, '.md')
    md = open(md_path, encoding='utf-8').read() if md_path else ''
    duration = data.get('video_duration_sec') or data.get('video_duration_seconds') or 0
    minutes = max(float(duration or 0) / 60, 1 / 60)

    segments = a1_segments(md)
    visual_lines = [line for seg in segments for line in seg['visual_lines']]
    picture_lines = [line for line in visual_lines if '[画面]' in line]
    caption_lines = [line for line in visual_lines if '[花字]' in line]
    meaningful_visual = [line for line in picture_lines if any(w in line for w in ACTION_WORDS)]
    generic_only = [line for line in picture_lines
                    if any(w in line for w in GENERIC_VISUAL)
                    and not any(w in line for w in ACTION_WORDS)]
    semantic_visual = [line for line in picture_lines
                       if line not in generic_only and
                       (any(w in line for w in SEMANTIC_VISUAL_WORDS) or
                        not any(w in line for w in GENERIC_VISUAL))]

    sections = {h: section_body(md, h) for h in REQUIRED_RICH_H3}
    missing_sections = [h for h, body in sections.items() if body is None]
    blank_sections = [h for h, body in sections.items() if body is not None and not body]
    missing_json = [k for k in RICH_JSON_FIELDS if k not in data]

    dishes = data.get('dishes') or []
    episodes = data.get('judgment_episodes') or []
    raw_desc = data.get('raw_sensory_descriptors') or []
    methodology = data.get('methodology_clues')
    method_scanned = isinstance(methodology, dict) and bool(methodology.get('scan_notes'))

    visual_coverage = data.get('visual_coverage') or []
    valid_status = {'reviewed_video', 'reviewed_frames', 'audio_only', 'unreadable'}
    status_counts = Counter(x.get('visual_status') for x in visual_coverage
                            if isinstance(x, dict) and x.get('visual_status'))
    covered_ranges = [x for x in visual_coverage if isinstance(x, dict)
                      and x.get('visual_status') in ('reviewed_video', 'reviewed_frames')]
    parsed_coverage = [(x.get('visual_status'), parse_range_seconds(x.get('timestamp')))
                       for x in visual_coverage if isinstance(x, dict)]
    parseable = [(status, span) for status, span in parsed_coverage if span]
    if parseable and duration:
        coverage_ratio = min(1.0, union_duration([span for _, span in parseable
                                                  if _ in ('reviewed_video', 'reviewed_frames')])
                             / float(duration))
    else:
        coverage_ratio = len(covered_ranges) / len(visual_coverage) if visual_coverage else 0

    reviewed_with_md = 0
    for item in covered_ranges:
        matched = overlapping_segments(segments, item.get('timestamp'))
        if any(seg['visual_lines'] or seg['no_signal'] for seg in matched):
            reviewed_with_md += 1
    visual_md_coverage_ratio = (reviewed_with_md / len(covered_ranges)
                                if covered_ranges else None)

    episodes = data.get('judgment_episodes') or []
    episode_ids = [x.get('episode_id') for x in episodes if isinstance(x, dict)]
    known_episode_ids = {x for x in episode_ids if x}
    audiovisual = data.get('audiovisual_analysis') or {}

    def load_stage(directory):
        path = os.path.join(output_dir(corpus, directory, variant), f'{vid}.json')
        if not os.path.isfile(path):
            return {}
        try:
            with open(path, encoding='utf-8') as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

    shots_doc = load_stage('shot-ledgers')
    reactions_doc = load_stage('reaction-windows')
    sound_doc = load_stage('sound-edit-ledgers')
    shots = shots_doc.get('shots') or []
    reaction_windows = reactions_doc.get('windows') or []
    sound_events = sound_doc.get('sound_events') or []
    editing_relations = sound_doc.get('editing_relations') or []
    food_visual = data.get('food_visual_evidence') or []
    action_evidence = data.get('action_evidence') or []
    micro_evidence = data.get('microreaction_evidence') or []
    claim_refs = data.get('audiovisual_claim_refs') or []
    main_objects = {x.get('name') for x in dishes if isinstance(x, dict) and x.get('name')}
    food_objects = {x.get('object') for x in food_visual if isinstance(x, dict) and x.get('object')}
    morphology_coverage = len(main_objects & food_objects) / len(main_objects) if main_objects else None
    action_episodes = {ref for x in action_evidence if isinstance(x, dict)
                       for ref in (x.get('episode_refs') or [])}
    action_coverage = len(known_episode_ids & action_episodes) / len(known_episode_ids) if known_episode_ids else None
    continuous_windows = [x for x in reaction_windows if isinstance(x, dict) and
                          x.get('input_mode') in ('dense_frames', 'continuous_video')]
    reaction_coverage = len(continuous_windows) / len(known_episode_ids) if known_episode_ids else None
    face_opportunities = [x for x in continuous_windows if x.get('face_visibility') == 'full_clear']
    coded_faces = [x for x in face_opportunities if x.get('microreactions')]
    micro_coverage = len(coded_faces) / len(face_opportunities) if face_opportunities else None
    shot_language = [x for x in shots if isinstance(x, dict) and
                     x.get('shot_scale') and x.get('camera_angle') and x.get('lighting')]
    shot_coverage = len(shot_language) / len(shots) if shots else None
    video_unique_count = len(semantic_visual) + len(meaningful_visual) + len(sound_events) + len(editing_relations)
    total_evidence_count = video_unique_count + len(caption_lines)
    video_unique_ratio = video_unique_count / total_evidence_count if total_evidence_count else 0
    duplicate_refs = [ref for x in claim_refs if isinstance(x, dict)
                      for ref in (x.get('ledger_refs') or [])]
    duplicate_ratio = 1 - len(set(duplicate_refs)) / len(duplicate_refs) if duplicate_refs else 0
    av_items = []
    for key in ('shot_sound_relations', 'reaction_sequences', 'attention_distribution'):
        for item in audiovisual.get(key) or []:
            if isinstance(item, dict):
                av_items.append((key, item))

    # 触发词只扫描正文内容；标题本身含“比较/转折/表达DNA”，不能反过来
    # 证明正文出现了相应信号，否则一份只有空模板的文件也会产生假阳性。
    prose = '\n'.join(line for line in md.splitlines() if not line.startswith('#'))

    warnings = []
    if data.get('content_type') == '探店':
        if missing_sections:
            warnings.append(f'RICH_SECTION_MISSING: {len(missing_sections)}个丰富性小节缺失')
        if missing_json:
            warnings.append(f'RICH_JSON_MISSING: {len(missing_json)}个丰富性字段缺失')
        if dishes and len(episodes) < max(1, len(dishes) // 2):
            warnings.append('RICH_EPISODE_LOW: 判断事件少于主要评价对象的一半')
        if dishes and not raw_desc:
            warnings.append('RICH_RAW_LANGUAGE_EMPTY: 有菜品但无原始感官措辞')
        if not method_scanned:
            warnings.append('RICH_METHOD_SCAN_MISSING: 六环节无明确机会扫描记录')
        if covered_ranges and not visual_lines:
            warnings.append('RICH_VISUAL_LINES_ZERO: JSON声称已检查画面，但A1没有[画面]/[花字]客观观察')
        if (visual_md_coverage_ratio is not None and visual_md_coverage_ratio < 0.5):
            warnings.append(
                f'RICH_VISUAL_MD_COVERAGE_LOW: JSON reviewed段只有 '
                f'{visual_md_coverage_ratio:.0%} 在A1留下视觉观察或无信号留痕')
        if picture_lines and len(generic_only) / len(picture_lines) > 0.5:
            warnings.append(
                f'RICH_VISUAL_GENERIC: 泛化检测式画面占 {len(generic_only) / len(picture_lines):.0%}，'
                '人物/餐具/食物分类不能替代判断相关视觉')
        if caption_lines and not semantic_visual and not meaningful_visual:
            warnings.append('RICH_OCR_ONLY: 有大量花字但无语义画面或判断动作，OCR覆盖不能替代视觉理解')
        if not shots:
            warnings.append('RICH_SHOT_LEDGER_MISSING: 缺逐镜头空间/摄影编码')
        if not reaction_windows:
            warnings.append('RICH_REACTION_LEDGER_MISSING: 缺连续动作/微反应窗口')
        if not sound_events and not editing_relations:
            warnings.append('RICH_SOUND_EDIT_MISSING: 缺声音与剪辑账本')
        if morphology_coverage is not None and morphology_coverage < 0.8:
            warnings.append(f'RICH_FOOD_MORPHOLOGY_LOW: 主要菜品形态覆盖 {morphology_coverage:.0%}')
        if action_coverage is not None and action_coverage < 0.8:
            warnings.append(f'RICH_ACTION_COVERAGE_LOW: 判断事件动作覆盖 {action_coverage:.0%}')
        if reaction_coverage is not None and reaction_coverage < 0.8:
            warnings.append(f'RICH_CONTINUOUS_REACTION_LOW: 连续反应窗口覆盖 {reaction_coverage:.0%}')
        if video_unique_ratio < 0.5:
            warnings.append(f'RICH_VIDEO_UNIQUE_LOW: 视频独有证据占比 {video_unique_ratio:.0%}')
        if any(w in prose for w in COMPARISON_WORDS) and not data.get('comparisons'):
            warnings.append('RICH_COMPARISON_UNCAPTURED: 正文有比较信号但comparisons为空/缺失')
        if any(w in prose for w in TURN_WORDS) and not data.get('tensions_and_revisions'):
            warnings.append('RICH_TURN_UNCAPTURED: 正文有转折信号但修正/张力为空')
        if any(w in prose for w in EXPRESSION_WORDS) and not data.get('expression_materials'):
            warnings.append('RICH_EXPRESSION_UNCAPTURED: 正文有表达信号但结构化素材为空')

        if not visual_coverage:
            warnings.append('VISUAL_STATUS_MISSING: 缺 visual_coverage，无法区分已看画面与纯音频')
        else:
            invalid = [s for s in status_counts if s not in valid_status]
            if invalid:
                warnings.append(f'VISUAL_STATUS_INVALID: 非法状态 {invalid}')
            if coverage_ratio < 0.5:
                warnings.append(f'VISUAL_COVERAGE_LOW: 实际检查画面的段落占比 {coverage_ratio:.0%}')

        if len(episode_ids) != len(set(episode_ids)) or any(not x for x in episode_ids):
            warnings.append('EPISODE_ID_INVALID: episode_id 缺失或重复')
        for key, item in av_items:
            refs = item.get('episode_refs') or []
            broken = [ref for ref in refs if ref not in known_episode_ids]
            if broken:
                warnings.append(f'EPISODE_REF_BROKEN: {key} 引用不存在的 {broken}')
            level = item.get('evidence_level')
            basis = item.get('visual_basis')
            if not level or level not in {'direct_video', 'frame_sequence', 'single_frame',
                                          'audio_timeline', 'editorial_inference'}:
                warnings.append(f'VISUAL_CLAIM_NO_BASIS: {key} 缺合法 evidence_level')
            if level in ('direct_video', 'frame_sequence', 'single_frame', 'editorial_inference') and not basis:
                warnings.append(f'VISUAL_CLAIM_NO_BASIS: {key} 的 {level} 缺 visual_basis')
            if level in ('direct_video', 'frame_sequence', 'single_frame') and not covered_ranges:
                warnings.append(f'VISUAL_CLAIM_NO_BASIS: {key} 声称 {level}，但 visual_coverage 无已检查画面段')
            text = ' '.join(str(item.get(k) or '') for k in
                            ('description', 'sequence', 'expert_attention', 'editorial_attention'))
            if level == 'single_frame' and any(w in text for w in
                                               ('停顿', '复尝', '看向', '转身', '走向', '变化', '先', '随后')):
                warnings.append(f'ACTION_FROM_SINGLE_FRAME: {key} 用单帧证明连续动作')
            if level == 'audio_timeline' and any(
                    w in text for w in ('镜头', '剪辑', '特写', '回放', '蒙太奇', '花字', 'BGM')):
                warnings.append(f'MONTAGE_FROM_AUDIO_ONLY: {key} 从音频时间线推出镜头/剪辑')
            if key == 'reaction_sequences' and level not in ('direct_video', 'frame_sequence'):
                warnings.append('REACTION_WINDOW_NOT_REVIEWED: 反应序列无连续视觉证据')

        # Markdown 有对应丰富性章节而 JSON 缺键时，直接指出跨层静默丢失。
        md_json_map = {
            'B3 方法论线索': 'methodology_clues',
            'B4 表达DNA素材': 'expression_materials',
            'B5 原始感官措辞与细粒度描述': 'raw_sensory_descriptors',
            'B6 品味谱系与个人经验': 'taste_lineage',
            'B7 开放解释与竞争性解释': 'open_interpretations',
        }
        mismatch = [field for heading, field in md_json_map.items()
                    if sections.get(heading) and field not in data]
        if mismatch:
            warnings.append(f'RICH_JSON_MD_MISMATCH: Markdown有内容但JSON缺 {mismatch}')

        caption_lines = [line for line in md.splitlines() if '[花字]' in line]
        verified_captions = sum(x.get('caption_readability') == 'verified'
                                for x in visual_coverage if isinstance(x, dict))
        if caption_lines and not verified_captions:
            warnings.append('CAPTION_NOT_VERIFIED: 存在花字声明但无 verified 覆盖记录')

    return {
        'id': vid,
        'duration_min': round(minutes, 2),
        'metrics': {
            'md_chars_per_min': round(len(md) / minutes, 2),
            'visual_lines_per_min': round(len(visual_lines) / minutes, 2),
            'raw_caption_lines_per_min': round(len(caption_lines) / minutes, 2),
            'raw_detector_lines_per_min': round(len(generic_only) / minutes, 2),
            'semantic_visual_lines_per_min': round(len(semantic_visual) / minutes, 2),
            'judgment_action_lines_per_min': round(len(meaningful_visual) / minutes, 2),
            'generic_visual_ratio': round(len(generic_only) / len(picture_lines), 2) if picture_lines else None,
            'main_dish_food_morphology_coverage': round(morphology_coverage, 2) if morphology_coverage is not None else None,
            'judgment_event_action_coverage': round(action_coverage, 2) if action_coverage is not None else None,
            'reaction_window_continuous_coverage': round(reaction_coverage, 2) if reaction_coverage is not None else None,
            'face_visible_microreaction_coverage': round(micro_coverage, 2) if micro_coverage is not None else None,
            'shot_language_coverage': round(shot_coverage, 2) if shot_coverage is not None else None,
            'sound_event_count': len(sound_events),
            'editing_relation_count': len(editing_relations),
            'video_unique_fact_ratio': round(video_unique_ratio, 2),
            'duplicate_episode_weight_ratio': round(duplicate_ratio, 2),
            'judgment_episodes': len(episodes),
            'dishes': len(dishes),
            'episode_object_coverage': round(len(episodes) / len(dishes), 2) if dishes else None,
            'comparisons': len(data.get('comparisons') or []),
            'tensions_and_revisions': len(data.get('tensions_and_revisions') or []),
            'expression_materials': len(data.get('expression_materials') or []),
            'raw_sensory_descriptors': len(raw_desc),
            'open_interpretations': len(data.get('open_interpretations') or []),
            'visual_coverage_ratio': round(coverage_ratio, 2),
            'visual_md_coverage_ratio': (round(visual_md_coverage_ratio, 2)
                                         if visual_md_coverage_ratio is not None else None),
            'visual_reviewed_segments': len(covered_ranges),
            'visual_reviewed_segments_with_md_trace': reviewed_with_md,
            'visual_status_counts': dict(status_counts),
            'direct_video_evidence': sum(item.get('evidence_level') == 'direct_video'
                                         for _, item in av_items),
            'frame_sequence_evidence': sum(item.get('evidence_level') == 'frame_sequence'
                                           for _, item in av_items),
            'single_frame_evidence': sum(item.get('evidence_level') == 'single_frame'
                                         for _, item in av_items),
            'audio_timeline_evidence': sum(item.get('evidence_level') == 'audio_timeline'
                                           for _, item in av_items),
            'editorial_inference_evidence': sum(item.get('evidence_level') == 'editorial_inference'
                                                for _, item in av_items),
            'rich_sections_present': len(REQUIRED_RICH_H3) - len(missing_sections),
            'rich_json_fields_present': len(RICH_JSON_FIELDS) - len(missing_json),
        },
        'missing_sections': missing_sections,
        'blank_sections': blank_sections,
        'missing_json_fields': missing_json,
        'warnings': warnings,
    }


def summarize(rows):
    tally = Counter(w.split(':', 1)[0] for row in rows for w in row['warnings'])
    total_minutes = sum(row['duration_min'] for row in rows)
    weighted = {}
    if total_minutes:
        for key in ('md_chars_per_min', 'visual_lines_per_min'):
            weighted[key] = round(
                sum(row['metrics'][key] * row['duration_min'] for row in rows) / total_minutes,
                2,
            )
    baseline_comparison = {
        key: {
            'actual': weighted.get(key),
            'baseline_0011_0030': value,
            'ratio': round(weighted[key] / value, 2) if weighted.get(key) is not None else None,
        }
        for key, value in RICH_BASELINE_0011_0030.items()
    }
    return {
        'total': len(rows),
        'with_richness_warnings': sum(bool(row['warnings']) for row in rows),
        'warning_tally': dict(tally.most_common()),
        'batch_density': weighted,
        'baseline_comparison': baseline_comparison,
        'per_video': {row['id']: row for row in rows},
        'note': '诊断结果不阻塞、不改文件；0011–0030是批次召回下限而非逐条配额，低密度时应回原视频补理解，不能靠凑数。',
    }


def selftest():
    with open(os.path.join(REF_DIR, 'richness-golden.json'), encoding='utf-8') as f:
        golden = json.load(f)
    assert golden['batch_baseline_0011_0030']['video_count'] == 20
    assert len(golden['representative_ids']) >= 5
    assert all(golden['semantic_anchors'].get(vid) for vid in golden['representative_ids'])

    rich = '''## A. 还原层
### A9 镜头与声画关系
刺激→反应
### A10 反应序列与可观察机会
入口→停顿→复尝
### A11 三种注意力分配
三者一致
### A12 判断弧线
预期→转折→结论
### A13 本期判断事件
判断事件 1
### A14 比较、转折与言行张力
本店比旧店更好，但是更贵
### A15 本期推理链
观察→比较→结论
## B. 提炼层
### B3 方法论线索
六环节已扫描
### B4 表达DNA素材
类比原话
### B5 原始感官措辞与细粒度描述
绵粘嘴
### B6 品味谱系与个人经验
以前在北京吃过
### B7 开放解释与竞争性解释
解释A/解释B
'''
    assert not [h for h in REQUIRED_RICH_H3 if section_body(rich, h) is None]
    thin = '## A. 还原层\n### A1 逐段记录\n- [画面] 中景，表情自然\n'
    assert len([h for h in REQUIRED_RICH_H3 if section_body(thin, h) is None]) == len(REQUIRED_RICH_H3)
    assert prefix_id('0011_csvrow98.json') == '0011'
    with tempfile.TemporaryDirectory() as root:
        os.makedirs(os.path.join(root, 'understanding'))
        open(os.path.join(root, 'understanding', '0001.md'), 'w').write('pure')
        open(os.path.join(root, 'understanding', '0001_csvrow2.md'), 'w').write('csvrow')
        assert open(find_output(os.path.join(root, 'understanding'), '0001', '.md')).read() == 'pure'
        assert open(find_output(os.path.join(root, 'understanding'), '0001_csvrow2', '.md')).read() == 'csvrow'

    with tempfile.TemporaryDirectory() as root:
        os.makedirs(os.path.join(root, 'data'))
        os.makedirs(os.path.join(root, 'understanding'))
        md = ('## A. 还原层\n### A1 逐段记录\n'
              '**[00:00 - 01:00]**\n> [语音] 测试。\n\n'
              '【视觉覆盖】\n- visual_status：audio_only\n'
              '- visual_basis：未检查画面\n- caption_readability：not_reviewed\n\n'
              + rich + '\n## C. ASR 纠错清单\n')
        data = {
            'id': '9002', 'content_type': '探店', 'video_duration_sec': 60,
            'dishes': [], 'visual_coverage': [{
                'timestamp': '00:00-01:00', 'visual_status': 'audio_only',
                'visual_basis': ['未检查画面'], 'caption_readability': 'not_reviewed'}],
            'judgment_episodes': [{'episode_id': 'J1'}], 'comparisons': [],
            'tensions_and_revisions': [],
            'methodology_clues': {'scan_notes': '六环节已扫描'},
            'expression_materials': [], 'raw_sensory_descriptors': [],
            'taste_lineage': [], 'open_interpretations': [],
            'audiovisual_analysis': {
                'shot_sound_relations': [{
                    'episode_refs': ['J1'], 'evidence_level': 'audio_timeline',
                    'description': '口播先报价后总结'}],
                'reaction_sequences': [], 'attention_distribution': []},
        }
        jp = os.path.join(root, 'data', '9002.json')
        open(jp, 'w').write(json.dumps(data, ensure_ascii=False))
        open(os.path.join(root, 'understanding', '9002.md'), 'w').write(md)
        row = audit_one(root, jp)
        assert any(x.startswith('VISUAL_COVERAGE_LOW:') for x in row['warnings'])
        assert any(x.startswith('RICH_SHOT_LEDGER_MISSING:') for x in row['warnings'])
        assert any(x.startswith('RICH_REACTION_LEDGER_MISSING:') for x in row['warnings'])
        assert any(x.startswith('RICH_SOUND_EDIT_MISSING:') for x in row['warnings'])
        assert row['metrics']['video_unique_fact_ratio'] == 0
        assert not any(x.startswith('MONTAGE_FROM_AUDIO_ONLY:') for x in row['warnings'])
        assert not any(x.startswith('RICH_VISUAL_LINES_ZERO:') for x in row['warnings'])
        data['audiovisual_analysis']['shot_sound_relations'][0]['description'] = '口播后出现镜头特写'
        open(jp, 'w').write(json.dumps(data, ensure_ascii=False))
        row = audit_one(root, jp)
        assert any(x.startswith('MONTAGE_FROM_AUDIO_ONLY:') for x in row['warnings'])
        data['audiovisual_analysis']['shot_sound_relations'][0].update(
            episode_refs=['J404'], evidence_level='single_frame',
            visual_basis=['f_00001'], description='先停顿随后复尝')
        open(jp, 'w').write(json.dumps(data, ensure_ascii=False))
        row = audit_one(root, jp)
        assert any(x.startswith('EPISODE_REF_BROKEN:') for x in row['warnings'])
        assert any(x.startswith('ACTION_FROM_SINGLE_FRAME:') for x in row['warnings'])

        # JSON 声称 reviewed 但 A1 零视觉，必须显式报警；audio_only 不误报。
        data['visual_coverage'][0].update(
            visual_status='reviewed_frames', visual_basis=['f_00001', 'f_00002'])
        open(jp, 'w').write(json.dumps(data, ensure_ascii=False))
        row = audit_one(root, jp)
        assert any(x.startswith('RICH_VISUAL_LINES_ZERO:') for x in row['warnings'])
        assert any(x.startswith('RICH_VISUAL_MD_COVERAGE_LOW:') for x in row['warnings'])

        # 两个 reviewed 段只有一个留下 A1 观察，50% 不应触发“低于一半”。
        md_with_visual = md.replace(
            '> [语音] 测试。',
            '> [语音] 测试。\n- [画面][visual_basis=f_00001] 菜品静态特写')
        data['visual_coverage'].append({
            'timestamp': '01:00-02:00', 'visual_status': 'reviewed_frames',
            'visual_basis': ['f_00060'], 'caption_readability': 'not_present'})
        open(os.path.join(root, 'understanding', '9002.md'), 'w').write(md_with_visual)
        open(jp, 'w').write(json.dumps(data, ensure_ascii=False))
        row = audit_one(root, jp)
        assert not any(x.startswith('RICH_VISUAL_LINES_ZERO:') for x in row['warnings'])
        assert not any(x.startswith('RICH_VISUAL_MD_COVERAGE_LOW:') for x in row['warnings'])
        assert row['metrics']['visual_md_coverage_ratio'] == 0.5
    print('richness audit selftest: golden + pairing + visual evidence assertions passed')
    return 0


def main():
    ap = argparse.ArgumentParser(description='非阻塞丰富性审计')
    ap.add_argument('corpus', nargs='?')
    ap.add_argument('--id', action='append', help='只审计指定编号，可重复')
    ap.add_argument('--variant', default=DEFAULT_VARIANT,
                    help=f'产物版本目录，默认 {DEFAULT_VARIANT}；root 表示旧根目录布局')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--selftest', action='store_true')
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not args.corpus:
        print('需指定语料目录或使用 --selftest', file=sys.stderr)
        return 2
    corpus = os.path.abspath(args.corpus)
    try:
        variant = validate_variant(args.variant)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    data_dir = output_dir(corpus, 'data', variant)
    if not os.path.isdir(data_dir):
        print(f'{data_dir} 不存在', file=sys.stderr)
        return 2
    wanted = {os.path.splitext(x)[0] for x in (args.id or [])}
    paths = sorted(os.path.join(data_dir, n) for n in os.listdir(data_dir)
                   if n.endswith('.json') and (not wanted or os.path.splitext(n)[0] in wanted))
    rows = [audit_one(corpus, p, variant=variant) for p in paths]
    result = summarize(rows)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for row in rows:
            print(f"\n=== {row['id']} ===")
            for key, value in row['metrics'].items():
                print(f'  {key}: {value}')
            for warning in row['warnings']:
                print(f'  ⚠️  {warning}')
        print(f"\n共 {result['total']} 期，{result['with_richness_warnings']} 期需复核丰富性")
        if result['batch_density']:
            print('批次密度（0011–0030 基线仅作召回下限参考）：')
            for key, comparison in result['baseline_comparison'].items():
                print(f"  {key}: {comparison['actual']} / {comparison['baseline_0011_0030']} "
                      f"({comparison['ratio']}x)")
        print('本审计不阻塞、不改文件；不能以安全闸门零 BLOCK 替代丰富性验收。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
