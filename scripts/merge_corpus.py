#!/usr/bin/env python3
"""Merge and group one version-scoped gourmet-video corpus."""

import argparse
import glob
import json
import os
import re
from collections import Counter, defaultdict

from output_paths import DEFAULT_VARIANT, index_file, output_dir, validate_variant

REQUIRED_DISH = ['name', 'object_level', 'price', 'sentiment', 'intensity', 'reason',
                 'standard_tags', 'tag_qualifier', 'blogger_attribution',
                 'source_type', 'scope', 'scope_quote',
                 'evidence_source', 'confidence', 'quote', 'timestamp',
                 'shot_duration_sec', 'has_caption']
BLOGGER_SOURCES = ('blogger_explicit', 'blogger_hypothesis', 'externally_verified')


def blogger_only(dishes):
    return [x for x in (dishes or []) if x.get('source_type') in BLOGGER_SOURCES]


def step1_index(corpus, variant):
    rows, rejected = [], []
    data_dir = output_dir(corpus, 'data', variant)
    for path in sorted(glob.glob(os.path.join(data_dir, '*.json'))):
        try:
            with open(path, encoding='utf-8') as handle:
                data = json.load(handle)
        except json.JSONDecodeError as exc:
            rejected.append((os.path.basename(path), 'JSON解析失败', 0, str(exc)[:60]))
            continue
        data = {key: value for key, value in data.items() if not key.startswith('_comment')}
        gate = data.get('quality_gate') or {}
        accepted = (data.get('processing_status') == '完整'
                    and not gate.get('blocking_issues')
                    and gate.get('validated_at')
                    and data.get('content_type') in ('探店', '表态'))
        if not accepted:
            rejected.append((data.get('id'), data.get('processing_status'),
                             len(gate.get('blocking_issues') or []),
                             '无 quality_gate' if not gate else ''))
            continue
        rows.append(data)

    destination = index_file(corpus, variant)
    with open(destination, 'w', encoding='utf-8') as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=2)

    print('纳入', len(rows), ' 拒收', len(rejected))
    for item in rejected:
        print('  拒收', item)
    print('类型', Counter(row['content_type'] for row in rows))
    print('品类', Counter((row.get('_meta') or {}).get('cuisine') for row in rows).most_common())

    missing, noquote = Counter(), []
    for row in rows:
        for dish in row.get('dishes') or []:
            for key in REQUIRED_DISH:
                if key not in dish:
                    missing[key] += 1
            if not dish.get('quote'):
                noquote.append(f"{row['id']}/{dish.get('name')}")
        for event in row.get('dimension_events') or []:
            for key in ['evidence_source', 'source_type', 'scope', 'intensity']:
                if key not in event:
                    missing[f'event.{key}'] += 1
    print('缺失字段计数:', dict(missing) or '无')
    print('无原话的菜:', len(noquote), noquote[:10])
    print('无 price_check:', [row['id'] for row in rows if not row.get('price_check')])
    return rows


def step2_group(corpus, variant, rows):
    restaurants = [row for row in rows if row.get('content_type') == '探店' and row.get('_meta')]
    statements = [row for row in rows if row.get('content_type') == '表态']
    counts = Counter((row.get('_meta') or {}).get('cuisine') or '未标注' for row in restaurants)
    small = {cuisine for cuisine, count in counts.items() if count < 5}
    groups = defaultdict(list)
    for row in restaurants:
        cuisine = (row.get('_meta') or {}).get('cuisine') or '未标注'
        groups['其他-地方菜系' if cuisine in small else cuisine].append(row)

    grouped_dir = output_dir(corpus, 'grouped', variant)
    understanding_dir = output_dir(corpus, 'understanding', variant)
    os.makedirs(grouped_dir, exist_ok=True)
    for name, items in groups.items():
        items.sort(key=lambda row: (row.get('_meta') or {}).get('price_per_person') or 0)
        parts = [f'# {name}（{len(items)} 期）\n', '> 组内按人均升序排列。完整 Markdown 拼接，未做语义压缩。\n']
        for row in items:
            path = os.path.join(understanding_dir, f"{row['id']}.md")
            if not os.path.exists(path):
                print(f'  ⚠️ {name}: 缺 {os.path.relpath(path, corpus)}')
                continue
            with open(path, encoding='utf-8') as handle:
                parts.append(f"\n\n{'=' * 60}\n## {row['id']}\n{handle.read()}")
        safe = re.sub(r'[\\/:*?"<>|]', '_', name)
        with open(os.path.join(grouped_dir, f'{safe}.md'), 'w', encoding='utf-8') as handle:
            handle.write('\n'.join(parts))

    if statements:
        parts = [f'# 表态类（{len(statements)} 条）\n']
        for row in statements:
            path = os.path.join(understanding_dir, f"{row['id']}.md")
            parts.append(open(path, encoding='utf-8').read() if os.path.exists(path)
                         else f'⚠️ 缺 {os.path.relpath(path, corpus)}')
        with open(os.path.join(grouped_dir, '_表态.md'), 'w', encoding='utf-8') as handle:
            handle.write('\n'.join(parts))
    print('分组完成:', {key: len(value) for key, value in groups.items()})


def main():
    parser = argparse.ArgumentParser(description='按版本合并与分组语料')
    parser.add_argument('corpus')
    parser.add_argument('--variant', default=DEFAULT_VARIANT,
                        help=f'产物版本目录，默认 {DEFAULT_VARIANT}；root 表示旧根目录布局')
    args = parser.parse_args()
    try:
        variant = validate_variant(args.variant)
    except ValueError as exc:
        parser.error(str(exc))
    corpus = os.path.abspath(args.corpus)
    rows = step1_index(corpus, variant)
    if not rows:
        print('⚠️ 无放行记录，中止分组')
        return 1
    step2_group(corpus, variant, rows)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
