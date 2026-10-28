#!/usr/bin/env python3
"""Prepare 5.3-Flash visual assets at full-film, event, and microreaction scales."""

import argparse
import json
import os
import re
import subprocess
import sys

from output_paths import DEFAULT_VARIANT, output_dir, validate_variant


def parse_window(value):
    match = re.fullmatch(r'([^=]+)=(\d{1,3}:\d{2})-(\d{1,3}:\d{2})', value)
    if not match:
        raise ValueError(f'窗口格式应为 ID=MM:SS-MM:SS：{value}')
    def seconds(text):
        minute, second = text.split(':')
        return int(minute) * 60 + int(second)
    start, end = seconds(match.group(2)), seconds(match.group(3))
    if end <= start:
        raise ValueError(f'窗口结束必须晚于开始：{value}')
    return {'id': match.group(1), 'start': start, 'end': end,
            'timestamp': f'{match.group(2)}-{match.group(3)}'}


def run(command):
    subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def reset_images(output_dir):
    os.makedirs(output_dir, exist_ok=True)
    for name in os.listdir(output_dir):
        if name.lower().endswith(('.jpg', '.jpeg', '.png')):
            os.remove(os.path.join(output_dir, name))


def extract(video, output_dir, fps, start=None, end=None):
    if os.path.isdir(output_dir):
        existing = [os.path.join(output_dir, name) for name in sorted(os.listdir(output_dir))
                    if name.lower().endswith(('.jpg', '.jpeg', '.png'))]
        if existing:
            return existing
    reset_images(output_dir)
    command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-threads', '4']
    if start is not None:
        command += ['-ss', str(start)]
    command += ['-i', video]
    if end is not None:
        command += ['-t', str(end - start)]
    command += ['-vf', f'fps={fps}', os.path.join(output_dir, 'f_%06d.jpg')]
    run(command)
    return [os.path.join(output_dir, name) for name in sorted(os.listdir(output_dir))
            if name.lower().endswith(('.jpg', '.jpeg', '.png'))]


def relative(corpus, paths):
    return [os.path.relpath(path, corpus) for path in paths]


def prepare(corpus, vid, events, micros, model_family, variant=DEFAULT_VARIANT):
    video = os.path.join(corpus, f'{vid}.mp4')
    transcript = os.path.join(corpus, f'{vid}_audio_transcript.md')
    if not os.path.isfile(video):
        raise FileNotFoundError(video)
    if not os.path.isfile(transcript):
        raise FileNotFoundError(transcript)

    base = extract(video, os.path.join(corpus, f'frames_{vid}_flash2'), 2)
    continuous = []
    phase_assets = {'shot_ledger': list(base), 'visual_ledger': list(base),
                    'reaction_windows': [], 'sound_edit': [video], 'assembly': []}
    for window in events:
        assets = extract(video, os.path.join(corpus, f'frames_{vid}_dense', window['id']),
                         8, window['start'], window['end'])
        phase_assets['reaction_windows'].extend(assets)
        phase_assets['sound_edit'].append(video)
        continuous.append(dict(window, kind='event', sample_fps=8, assets=relative(corpus, assets)))
    for window in micros:
        if window['end'] - window['start'] > 5:
            raise ValueError(f'微反应窗口不得超过5秒：{window["id"]}')
        assets = extract(video, os.path.join(corpus, f'frames_{vid}_micro', window['id']),
                         25, window['start'], window['end'])
        phase_assets['reaction_windows'].extend(assets)
        continuous.append(dict(window, kind='microreaction', sample_fps=25,
                               assets=relative(corpus, assets)))

    manifest = {
        'id': vid,
        'model_family': model_family,
        'inputs': {
            'video_supplied': True,
            'video_files': [os.path.relpath(video, corpus)],
            'transcript_files': [os.path.relpath(transcript, corpus)],
            'base_frames': relative(corpus, base),
            'base_sample_fps': 2,
            'continuous_windows': continuous,
        },
        'phases': {
            key: {'status': 'pending', 'assets_supplied': relative(corpus, value)}
            for key, value in phase_assets.items()
        },
    }
    directory = output_dir(corpus, 'run-manifests', variant)
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f'{vid}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return path


def selftest():
    assert DEFAULT_VARIANT == '5.3-flash'
    assert parse_window('J1=00:03-00:11')['end'] == 11
    assert parse_window('M1=01:00-01:04')['start'] == 60
    try:
        parse_window('bad')
        raise AssertionError('bad window should fail')
    except ValueError:
        pass
    print('prepare_visual_assets selftest: PASS')
    return 0


def main():
    parser = argparse.ArgumentParser(description='生成Flash.2三尺度视频资产和run manifest')
    parser.add_argument('corpus', nargs='?')
    parser.add_argument('--id')
    parser.add_argument('--event', action='append', default=[])
    parser.add_argument('--micro', action='append', default=[])
    parser.add_argument('--model-family', default='5.3-flash')
    parser.add_argument('--variant', default=DEFAULT_VARIANT,
                        help=f'产物版本目录，默认 {DEFAULT_VARIANT}；root 表示旧根目录布局')
    parser.add_argument('--selftest', action='store_true')
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if not args.corpus or not args.id:
        parser.error('需指定 corpus 与 --id')
    try:
        variant = validate_variant(args.variant)
    except ValueError as exc:
        parser.error(str(exc))
    path = prepare(os.path.abspath(args.corpus), args.id,
                   [parse_window(x) for x in args.event],
                   [parse_window(x) for x in args.micro], args.model_family, variant)
    print(path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
