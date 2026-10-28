#!/usr/bin/env python3
"""Resolve version-scoped corpus output paths."""

import os
import re

DEFAULT_VARIANT = '5.3-flash'


def validate_variant(variant):
    if variant == 'root':
        return variant
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', variant or '') or variant in ('.', '..'):
        raise ValueError(f'非法 variant：{variant!r}')
    return variant


def output_dir(corpus, kind, variant):
    variant = validate_variant(variant)
    base = os.path.join(corpus, kind)
    return base if variant == 'root' else os.path.join(base, variant)


def output_file(corpus, kind, variant, filename):
    return os.path.join(output_dir(corpus, kind, variant), filename)


def index_file(corpus, variant):
    variant = validate_variant(variant)
    return os.path.join(corpus, 'corpus-index.json' if variant == 'root'
                        else f'corpus-index.{variant}.json')


def report_file(corpus, name, variant):
    variant = validate_variant(variant)
    return os.path.join(corpus, f'{name}.json' if variant == 'root'
                        else f'{name}.{variant}.json')
