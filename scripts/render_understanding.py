#!/usr/bin/env python3
"""Render fixed A1-A15/B1-B7 Markdown from a structured assembly payload."""

import argparse
import json
import os
import sys
import tempfile

from output_paths import DEFAULT_VARIANT, output_file, validate_variant

SECTIONS = [
    ('A', 'A1', '逐段记录'),
    ('A', 'A2', 'B档维度事件'),
    ('A', 'A3', '整体环境观感'),
    ('A', 'A4', 'C档顺带记录'),
    ('A', 'A5', '价格交叉校验'),
    ('A', 'A6', '附录·未定用途的画面观察'),
    ('A', 'A7', '无反应自检'),
    ('A', 'A8', '镜头时长分配'),
    ('A', 'A9', '镜头与声画关系'),
    ('A', 'A10', '反应序列与可观察机会'),
    ('A', 'A11', '三种注意力分配'),
    ('A', 'A12', '判断弧线'),
    ('A', 'A13', '本期判断事件'),
    ('A', 'A14', '比较、转折与言行张力'),
    ('A', 'A15', '本期推理链'),
    ('B', 'B1', '候选规律'),
    ('B', 'B2', '价值观与红线'),
    ('B', 'B3', '方法论线索'),
    ('B', 'B4', '表达DNA素材'),
    ('B', 'B5', '原始感官措辞与细粒度描述'),
    ('B', 'B6', '品味谱系与个人经验'),
    ('B', 'B7', '开放解释与竞争性解释'),
]
FORBIDDEN = ('```mermaid', '专家人格侧写', '叙事弧光与判断轨迹',
             '深度理解 (5V)', '深度理解 (Flash)')


def render(payload):
    if not isinstance(payload, dict):
        raise ValueError('assembly payload 必须是对象')
    vid = str(payload.get('id') or '').strip()
    title = str(payload.get('title') or '').strip()
    meta = payload.get('metadata') or []
    sections = payload.get('sections') or {}
    corrections = str(payload.get('asr_corrections') or '').strip()
    if not vid or not title:
        raise ValueError('id/title 必填')
    expected = {key for _, key, _ in SECTIONS}
    unknown = sorted(set(sections) - expected)
    missing = sorted(expected - set(sections))
    if unknown or missing:
        raise ValueError(f'sections 不匹配：missing={missing}, unknown={unknown}')
    if not isinstance(meta, list) or not all(isinstance(x, str) for x in meta):
        raise ValueError('metadata 必须是字符串数组')

    parts = [f'# {vid} · {title}', '', '## 元信息']
    parts.extend(f'- {line}' for line in meta)
    current = None
    for group, key, heading in SECTIONS:
        if group != current:
            current = group
            parts.extend(['', '## A. 还原层' if group == 'A' else '## B. 提炼层'])
        body = str(sections[key] or '').strip()
        if any(marker in body for marker in FORBIDDEN):
            raise ValueError(f'{key} 含自由文章禁用结构')
        parts.extend(['', f'### {key} {heading}', '', body or '本期已扫描，未观察到可记录信号。'])
    parts.extend(['', '## C. ASR 纠错清单', '', corrections or '本期无纠错。', ''])
    return '\n'.join(parts)


def selftest():
    payload = {'id': '9001', 'title': '测试馆', 'metadata': ['内容类型：探店'],
               'sections': {key: '已扫描。' for _, key, _ in SECTIONS},
               'asr_corrections': '本期无纠错。'}
    text = render(payload)
    assert all(f'### {key} ' in text for _, key, _ in SECTIONS)
    bad = json.loads(json.dumps(payload, ensure_ascii=False))
    bad['sections'].pop('A9')
    try:
        render(bad)
        raise AssertionError('缺 A9 应失败')
    except ValueError:
        pass
    print('render_understanding selftest: PASS')
    return 0


def main():
    ap = argparse.ArgumentParser(description='机械渲染固定结构理解 Markdown')
    ap.add_argument('payload', nargs='?')
    ap.add_argument('--output')
    ap.add_argument('--corpus')
    ap.add_argument('--id')
    ap.add_argument('--variant', default=DEFAULT_VARIANT,
                    help=f'产物版本目录，默认 {DEFAULT_VARIANT}；root 表示旧根目录布局')
    ap.add_argument('--selftest', action='store_true')
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not args.payload:
        ap.error('需指定 assembly payload')
    output = args.output
    if not output:
        if not args.corpus or not args.id:
            ap.error('未指定 --output 时需同时指定 --corpus 与 --id')
        try:
            variant = validate_variant(args.variant)
        except ValueError as exc:
            ap.error(str(exc))
        output = output_file(os.path.abspath(args.corpus), 'understanding', variant,
                             f'{args.id}.md')
    with open(args.payload, encoding='utf-8') as f:
        payload = json.load(f)
    text = render(payload)
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    with open(output, 'w', encoding='utf-8') as f:
        f.write(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
