#!/usr/bin/env python3
"""Gate each 5.3-Flash stage before the next stage may run."""

import argparse
import json
import os
import sys
import tempfile

from output_paths import DEFAULT_VARIANT, output_dir, validate_variant

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(os.path.dirname(HERE), 'references')
STAGES = ['shot_ledger', 'visual_ledger', 'reaction_windows', 'sound_edit', 'assembly']
FILES = {
    'shot_ledger': ('shot-ledgers', 'shot-ledger.schema.json'),
    'visual_ledger': ('visual-ledgers', 'visual-ledger.schema.json'),
    'reaction_windows': ('reaction-windows', 'action-reaction.schema.json'),
    'sound_edit': ('sound-edit-ledgers', 'sound-edit.schema.json'),
    'assembly': ('assembly', None),
}
TAXONOMY = None


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def basic_schema_check(data, schema, path='$'):
    errors = []
    expected = schema.get('type')
    types = expected if isinstance(expected, list) else [expected]
    matches = (expected is None or
               ('object' in types and isinstance(data, dict)) or
               ('array' in types and isinstance(data, list)) or
               ('string' in types and isinstance(data, str)) or
               ('number' in types and isinstance(data, (int, float)) and not isinstance(data, bool)) or
               ('integer' in types and isinstance(data, int) and not isinstance(data, bool)) or
               ('null' in types and data is None))
    if not matches:
        return [f'{path} 应为 {expected}']
    if 'enum' in schema and data not in schema['enum']:
        errors.append(f'{path} 非枚举值：{data!r}')
    if isinstance(data, str) and schema.get('pattern') and not __import__('re').match(schema['pattern'], data):
        errors.append(f'{path} 不匹配 {schema["pattern"]}')
    if isinstance(data, (int, float)) and 'minimum' in schema and data < schema['minimum']:
        errors.append(f'{path}={data} 小于 minimum={schema["minimum"]}')
    if isinstance(data, list) and len(data) < schema.get('minItems', 0):
        errors.append(f'{path} 至少需要 {schema["minItems"]} 项')
    if isinstance(data, dict):
        for key in schema.get('required', []):
            if key not in data:
                errors.append(f'{path}.{key} 缺失')
        if schema.get('additionalProperties') is False:
            allowed = set(schema.get('properties', {}))
            for key in set(data) - allowed:
                errors.append(f'{path}.{key} 非法字段')
        for key, subschema in schema.get('properties', {}).items():
            if key in data:
                errors.extend(basic_schema_check(data[key], subschema, f'{path}.{key}'))
    if isinstance(data, list) and 'items' in schema:
        for index, item in enumerate(data):
            errors.extend(basic_schema_check(item, schema['items'], f'{path}[{index}]'))
    return errors


def taxonomy_check(stage, data):
    global TAXONOMY
    if TAXONOMY is None:
        TAXONOMY = load(os.path.join(REF, 'visual-observation-taxonomy.json'))
    errors = []
    if stage == 'shot_ledger':
        for index, shot in enumerate(data.get('shots') or []):
            for key, taxonomy_key in (('shot_scale', 'shot_scale'), ('camera_angle', 'camera_angle'),
                                      ('depth_of_field', 'depth_of_field'), ('camera_motion', 'camera_motion')):
                if shot.get(key) not in TAXONOMY[taxonomy_key]:
                    errors.append(f'shots[{index}].{key} 非闭集值：{shot.get(key)!r}')
    if stage == 'reaction_windows':
        for wi, window in enumerate(data.get('windows') or []):
            fps = window.get('sample_fps') or 0
            if window.get('actions') and fps < 8:
                errors.append(f'windows[{wi}] 有动作但 fps={fps}<8')
            if window.get('microreactions') and fps < 15:
                errors.append(f'windows[{wi}] 有微反应但 fps={fps}<15')
            for mi, event in enumerate(window.get('microreactions') or []):
                if event.get('intensity') not in TAXONOMY['movement_intensity']:
                    errors.append(f'windows[{wi}].microreactions[{mi}].intensity 非法')
                if event.get('visibility') not in TAXONOMY['face_visibility']:
                    errors.append(f'windows[{wi}].microreactions[{mi}].visibility 非法')
    return errors


def validate_stage(corpus, vid, target, variant='root'):
    errors = []
    target_index = STAGES.index(target)
    manifest_path = os.path.join(output_dir(corpus, 'run-manifests', variant), f'{vid}.json')
    if not os.path.isfile(manifest_path):
        return ['run manifest 缺失']
    manifest = load(manifest_path)
    for stage in STAGES[:target_index + 1]:
        directory, schema_name = FILES[stage]
        path = os.path.join(output_dir(corpus, directory, variant), f'{vid}.json')
        if not os.path.isfile(path):
            errors.append(f'{stage}: {path} 缺失')
            continue
        try:
            data = load(path)
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f'{stage}: JSON无效 {exc}')
            continue
        if schema_name:
            schema = load(os.path.join(REF, schema_name))
            errors.extend(f'{stage}: {message}' for message in basic_schema_check(data, schema))
        errors.extend(f'{stage}: {message}' for message in taxonomy_check(stage, data))
        phase = (manifest.get('phases') or {}).get(stage) or {}
        if phase.get('status') != 'complete':
            errors.append(f'{stage}: manifest status 不是 complete')
    return errors


def selftest():
    root = tempfile.mkdtemp(prefix='gourmet-flash-stage-')
    os.makedirs(os.path.join(root, 'run-manifests'))
    with open(os.path.join(root, 'run-manifests', '9001.json'), 'w') as f:
        json.dump({'phases': {}}, f)
    assert validate_stage(root, '9001', 'shot_ledger') == [
        f'shot_ledger: {root}/shot-ledgers/9001.json 缺失']
    print('check_stage selftest: PASS')
    return 0


def main():
    parser = argparse.ArgumentParser(description='检查Flash阶段状态')
    parser.add_argument('corpus', nargs='?')
    parser.add_argument('--id')
    parser.add_argument('--variant', default=DEFAULT_VARIANT,
                        help=f'产物版本目录，默认 {DEFAULT_VARIANT}；root 表示旧根目录布局')
    parser.add_argument('--target', choices=STAGES)
    parser.add_argument('--selftest', action='store_true')
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if not args.corpus or not args.id or not args.target:
        parser.error('需指定 corpus、--id、--target')
    try:
        variant = validate_variant(args.variant)
    except ValueError as exc:
        parser.error(str(exc))
    errors = validate_stage(os.path.abspath(args.corpus), args.id, args.target, variant)
    for error in errors:
        print(f'[BLOCK] {error}')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
