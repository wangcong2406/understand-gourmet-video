#!/usr/bin/env python3
"""更新 run-manifest 阶段状态（工具脚本，保留供流程使用）"""
import json
import sys

from output_paths import output_dir


def main():
    corpus, vid, stage = sys.argv[1], sys.argv[2], sys.argv[3]
    variant = sys.argv[4] if len(sys.argv) > 4 else '5.3-flash'
    path = output_dir(corpus, 'run-manifests', variant) + f'/{vid}.json'
    with open(path, encoding='utf-8') as f:
        manifest = json.load(f)
    manifest['phases'][stage]['status'] = 'complete'
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f'{stage} -> complete')


if __name__ == '__main__':
    main()
