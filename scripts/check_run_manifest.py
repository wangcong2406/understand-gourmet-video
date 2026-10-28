#!/usr/bin/env python3
"""Validate 5.3-Flash run manifests and staged visual evidence artifacts."""

import argparse
import json
import os
import sys
import tempfile

from output_paths import DEFAULT_VARIANT, output_dir, validate_variant

VISUAL_MODES = {'sampled_frames', 'dense_frames', 'continuous_video'}


def load_json(path, label, issues):
    if not os.path.isfile(path):
        issues.append(('BLOCK', f'{label}_MISSING', f'{path} 不存在'))
        return None
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        issues.append(('BLOCK', f'{label}_INVALID', f'{path} 无法解析：{e}'))
        return None


def normalize_asset(path):
    normalized = os.path.normpath(str(path))
    return normalized if os.path.isabs(normalized) else normalized.removeprefix('./')


def manifest_assets(manifest):
    out = set()
    inputs = manifest.get('inputs') or {}
    for key in ('base_frames', 'video_files', 'transcript_files'):
        out.update(normalize_asset(x) for x in inputs.get(key) or [])
    for window in inputs.get('continuous_windows') or []:
        if isinstance(window, dict):
            out.update(normalize_asset(x) for x in window.get('assets') or [])
    for phase in (manifest.get('phases') or {}).values():
        if isinstance(phase, dict):
            out.update(normalize_asset(x) for x in phase.get('assets_supplied') or [])
    return out


def staged_assets(doc):
    out = set()
    containers = []
    if isinstance(doc, dict):
        containers.extend(doc.get('shots') or [])
        containers.extend(doc.get('segments') or [])
        containers.extend(doc.get('evidence') or [])
        containers.extend(doc.get('windows') or [])
        containers.extend(doc.get('sound_events') or [])
    for item in containers:
        if isinstance(item, dict):
            out.update(normalize_asset(x) for x in item.get('assets_reviewed') or [])
    return out


def validate_manifest(corpus, vid, variant='root'):
    issues = []
    manifest_path = os.path.join(output_dir(corpus, 'run-manifests', variant), f'{vid}.json')
    manifest = load_json(manifest_path, 'RUN_MANIFEST', issues)
    if not manifest:
        return issues

    if str(manifest.get('id')) != vid:
        issues.append(('BLOCK', 'RUN_MANIFEST_ID',
                       f'run manifest id={manifest.get("id")!r}，应为 {vid!r}'))
    if str(manifest.get('model_family') or '').lower() != '5.3-flash':
        issues.append(('BLOCK', 'RUN_MANIFEST_MODEL',
                       'model_family 必须明确记录 5.3-flash'))

    inputs = manifest.get('inputs') or {}
    video_supplied = bool(inputs.get('video_supplied'))
    frames = inputs.get('base_frames') or []
    windows = inputs.get('continuous_windows') or []
    if not video_supplied and not frames:
        issues.append(('BLOCK', 'VISUAL_INPUT_NOT_SUPPLIED',
                       '既未提供视频，也未登记实际输入的基础帧'))
    if video_supplied and not inputs.get('video_files'):
        issues.append(('BLOCK', 'VIDEO_INPUT_UNLISTED',
                       'video_supplied=true 但 video_files 为空'))

    supplied = manifest_assets(manifest)
    for asset in supplied:
        full = asset if os.path.isabs(asset) else os.path.join(corpus, asset)
        if not os.path.isfile(full):
            issues.append(('BLOCK', 'MANIFEST_ASSET_MISSING',
                           f'manifest 登记的输入资产不存在：{asset}'))

    phases = manifest.get('phases') or {}
    for name in ('shot_ledger', 'visual_ledger', 'reaction_windows', 'sound_edit', 'assembly'):
        phase = phases.get(name)
        if not isinstance(phase, dict) or phase.get('status') not in ('complete', 'not_required'):
            issues.append(('BLOCK', 'RUN_PHASE_INCOMPLETE', f'{name} 阶段未登记 complete/not_required'))

    shots = load_json(os.path.join(output_dir(corpus, 'shot-ledgers', variant), f'{vid}.json'),
                      'SHOT_LEDGER', issues)
    ledger = load_json(os.path.join(output_dir(corpus, 'visual-ledgers', variant), f'{vid}.json'),
                       'VISUAL_LEDGER', issues)
    reactions = load_json(os.path.join(output_dir(corpus, 'reaction-windows', variant), f'{vid}.json'),
                          'REACTION_WINDOWS', issues)
    sound_edit = load_json(os.path.join(output_dir(corpus, 'sound-edit-ledgers', variant), f'{vid}.json'),
                           'SOUND_EDIT_LEDGER', issues)
    for label, doc in (('shot ledger', shots), ('visual ledger', ledger),
                       ('reaction windows', reactions), ('sound/edit ledger', sound_edit)):
        if not doc:
            continue
        unlisted = sorted(staged_assets(doc) - supplied)
        if unlisted:
            issues.append(('BLOCK', 'STAGED_ASSET_NOT_SUPPLIED',
                           f'{label} 声称读取了未在 manifest 登记的资产：{unlisted[:8]}'))

    for item in (reactions or {}).get('windows') or []:
        if not isinstance(item, dict):
            continue
        mode = item.get('input_mode')
        sequence = item.get('observable_sequence') or item.get('actions') or []
        if sequence and mode not in ('dense_frames', 'continuous_video'):
            issues.append(('BLOCK', 'ACTION_WITHOUT_CONTINUOUS_INPUT',
                           f'{item.get("episode_id") or item.get("window_id") or item.get("timestamp")} 有连续动作，但 input_mode={mode!r}'))
        fps = item.get('sample_fps') or 0
        if mode == 'dense_frames' and fps < 8:
            issues.append(('BLOCK', 'DENSE_FPS_LOW',
                           f'{item.get("window_id") or item.get("timestamp")} 判断窗口 fps={fps} < 8'))
        micro = item.get('microreactions') or []
        if micro and fps < 15:
            issues.append(('BLOCK', 'MICRO_FPS_LOW',
                           f'{item.get("window_id") or item.get("timestamp")} 有微反应但 fps={fps} < 15'))
        for event in micro:
            if not isinstance(event, dict):
                continue
            required = ('onset', 'apex', 'offset', 'intensity', 'visibility', 'support', 'limits')
            missing = [key for key in required if key not in event]
            if missing:
                issues.append(('BLOCK', 'MICRO_TEMPORAL_FIELDS_MISSING',
                               f'{item.get("window_id")} 微反应缺 {missing}'))

    if not windows and any(((item or {}).get('observable_sequence') or (item or {}).get('actions'))
                           for item in (reactions or {}).get('windows') or []):
        issues.append(('BLOCK', 'CONTINUOUS_WINDOW_UNLISTED',
                       'reaction windows 有连续动作，但 manifest 未登记 continuous_windows'))
    return issues


def selftest():
    root = tempfile.mkdtemp(prefix='gourmet-flash-manifest-')
    vid = '9001'
    for directory in ('run-manifests', 'shot-ledgers', 'visual-ledgers', 'reaction-windows',
                      'sound-edit-ledgers', 'frames_9001'):
        os.makedirs(os.path.join(root, directory), exist_ok=True)
    frame = os.path.join(root, 'frames_9001', 'f_00001.jpg')
    open(frame, 'wb').close()
    manifest = {
        'id': vid, 'model_family': '5.3-flash',
        'inputs': {'video_supplied': False, 'base_frames': ['frames_9001/f_00001.jpg'],
                   'continuous_windows': []},
        'phases': {
            'shot_ledger': {'status': 'complete', 'assets_supplied': ['frames_9001/f_00001.jpg']},
            'visual_ledger': {'status': 'complete', 'assets_supplied': ['frames_9001/f_00001.jpg']},
            'reaction_windows': {'status': 'not_required', 'assets_supplied': []},
            'sound_edit': {'status': 'complete', 'assets_supplied': []},
            'assembly': {'status': 'complete', 'assets_supplied': []}}
    }
    with open(os.path.join(root, 'run-manifests', f'{vid}.json'), 'w') as f:
        json.dump(manifest, f)
    with open(os.path.join(root, 'shot-ledgers', f'{vid}.json'), 'w') as f:
        json.dump({'id': vid, 'shots': [{'assets_reviewed': ['frames_9001/f_00001.jpg']}]}, f)
    with open(os.path.join(root, 'visual-ledgers', f'{vid}.json'), 'w') as f:
        json.dump({'id': vid, 'segments': [{'assets_reviewed': ['frames_9001/f_00001.jpg']}]}, f)
    with open(os.path.join(root, 'reaction-windows', f'{vid}.json'), 'w') as f:
        json.dump({'id': vid, 'windows': []}, f)
    with open(os.path.join(root, 'sound-edit-ledgers', f'{vid}.json'), 'w') as f:
        json.dump({'id': vid, 'shots': [], 'sound_events': [], 'editing_relations': []}, f)
    assert not validate_manifest(root, vid), validate_manifest(root, vid)
    manifest['model_family'] = 'glm-5v'
    with open(os.path.join(root, 'run-manifests', f'{vid}.json'), 'w') as f:
        json.dump(manifest, f)
    assert any(x[1] == 'RUN_MANIFEST_MODEL' for x in validate_manifest(root, vid))
    manifest['model_family'] = '5.3-flash'
    with open(os.path.join(root, 'run-manifests', f'{vid}.json'), 'w') as f:
        json.dump(manifest, f)
    os.remove(frame)
    assert any(x[1] == 'MANIFEST_ASSET_MISSING' for x in validate_manifest(root, vid))
    print('check_run_manifest selftest: PASS')
    return 0


def main():
    ap = argparse.ArgumentParser(description='校验 5.3-Flash 分阶段输入清单')
    ap.add_argument('corpus', nargs='?')
    ap.add_argument('--id')
    ap.add_argument('--variant', default=DEFAULT_VARIANT,
                    help=f'产物版本目录，默认 {DEFAULT_VARIANT}；root 表示旧根目录布局')
    ap.add_argument('--selftest', action='store_true')
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not args.corpus or not args.id:
        ap.error('需同时指定 corpus 与 --id')
    try:
        variant = validate_variant(args.variant)
    except ValueError as exc:
        ap.error(str(exc))
    issues = validate_manifest(os.path.abspath(args.corpus), args.id, variant)
    for level, code, message in issues:
        print(f'[{level}] {code}: {message}')
    return 1 if any(level == 'BLOCK' for level, _, _ in issues) else 0


if __name__ == '__main__':
    sys.exit(main())
