#!/usr/bin/env python3
"""Collate the builders' hand-backs into the tables a run's report needs.

    collate-results.py --site-path <site> [--out <file>]

Each builder writes its hand-back to <site>/.h2bt/results/<name>.json. A run lasts hours and
its orchestrator's context is summarised along the way, so the report is built from those
files and not from memory: the validation totals, the residual drift, every custom CSS rule,
the blocks beyond core, what was changed outside a view, the defects fixed and the TODOs.

The output is Markdown. Nothing is judged here: what a difference means is for the report's
author. A result that cannot be read is listed, not skipped.

Last line: H2BT_RESULTS views=<n> success=<n> partial=<n> failed=<n> unreadable=<n>
"""
import argparse
import glob
import json
import os
import sys


def cell(value):
    """One table cell: a short string with nothing that breaks the row."""
    if isinstance(value, (list, tuple)):
        value = ', '.join(str(item) for item in value)
    return str(value if value is not None else '').replace('|', '\\|').replace('\n', ' ').strip()


def table(headers, rows):
    lines = ['| ' + ' | '.join(headers) + ' |', '|' + '|'.join('---' for _ in headers) + '|']
    lines += ['| ' + ' | '.join(cell(value) for value in row) + ' |' for row in rows]
    return lines


def entries(result, key):
    """A list under a key, whatever a builder made of it."""
    value = result.get(key)
    if isinstance(value, list):
        return value
    return [] if value in (None, '', {}) else [value]


def field(entry, key):
    return entry.get(key, '') if isinstance(entry, dict) else (entry if key == 'text' else '')


def main():
    parser = argparse.ArgumentParser(description="Collate the builders' results into the report's tables.")
    parser.add_argument('--site-path', required=True)
    parser.add_argument('--out')
    args = parser.parse_args()

    folder = os.path.join(os.path.abspath(args.site_path), '.h2bt', 'results')
    paths = sorted(glob.glob(os.path.join(folder, '*.json')))
    results, unreadable = [], []
    for path in paths:
        name = os.path.splitext(os.path.basename(path))[0]
        try:
            with open(path, encoding='utf-8') as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                raise ValueError('not a JSON object')
        except (OSError, ValueError) as error:
            unreadable.append((name, str(error)))
            continue
        results.append((name, data))

    out = ['# Results of the builders', '']
    if not paths:
        out += ['No result file in %s.' % folder, '']

    counts = {'success': 0, 'partial': 0, 'failed': 0}
    totals = {'validated_ok': 0, 'auto_fixed': 0, 'downgraded': 0}
    rows = []
    for name, result in results:
        status = str(result.get('status', 'unknown'))
        counts[status] = counts.get(status, 0) + 1
        validation = result.get('validation') if isinstance(result.get('validation'), dict) else {}
        for key in totals:
            try:
                totals[key] += int(validation.get(key, 0) or 0)
            except (TypeError, ValueError):
                pass
        checks = result.get('checks') if isinstance(result.get('checks'), dict) else {}
        rows.append((name, result.get('target', ''), status, result.get('failure_reason') or '',
                     '%s / %s / %s' % (validation.get('validated_ok', '?'), validation.get('auto_fixed', '?'), validation.get('downgraded', '?')),
                     checks.get('widths_swept', ''), checks.get('overflow_at_narrowest', ''), checks.get('first_screen_image_loading', '')))
    if rows:
        out += ['## Views', ''] + table(['View', 'Target', 'Status', 'Reason', 'Valid / fixed / rebuilt', 'Widths swept', 'Overflow at narrowest', 'First-screen image'], rows) + ['']
        out += ['Validation in all: %d valid, %d fixed by the validator, %d rebuilt.' % (totals['validated_ok'], totals['auto_fixed'], totals['downgraded']), '']
    if unreadable:
        out += ['## Results that could not be read', ''] + table(['View', 'Why'], unreadable) + ['']

    sections = (
        ('Residual drift', 'drift', ['View', 'Section', 'Difference', 'Viewport', 'Rung to fix', 'Why left'], ('section', 'diff', 'viewport', 'rung_to_fix', 'why_left')),
        ('Custom CSS', 'custom_css', ['View', 'File', 'Selector', 'Reason'], ('file', 'selector', 'reason')),
        ('Blocks beyond core', 'blocks_used', ['View', 'Block', 'Source'], ('name', 'source')),
        ('Changed outside the view', 'changed_outside_view', ['View', 'File', 'Change', 'Reason'], ('file', 'change', 'reason')),
        ('Defects of the original that were fixed', 'quirks_fixed', ['View', 'What', 'Evidence', 'Fix', 'Visible difference'], ('what', 'evidence', 'fix', 'visible_difference')),
    )
    for title, key, headers, fields in sections:
        rows = [[name] + [field(entry, part) for part in fields] for name, result in results for entry in entries(result, key) if isinstance(entry, dict)]
        loose = [(name, entry) for name, result in results for entry in entries(result, key) if not isinstance(entry, dict)]
        if rows or loose:
            out += ['## ' + title, '']
            if rows:
                out += table(headers, rows) + ['']
            out += ['- %s: %s' % (name, cell(entry)) for name, entry in loose] + ([''] if loose else [])

    for title, key in (('TODOs', 'todos'), ('Findings for the plugin', 'plugin_findings')):
        items = [(name, entry) for name, result in results for entry in entries(result, key)]
        if items:
            out += ['## ' + title, ''] + ['- %s: %s' % (name, cell(entry if not isinstance(entry, dict) else json.dumps(entry))) for name, entry in items] + ['']

    text = '\n'.join(out).rstrip() + '\n'
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as handle:
            handle.write(text)
    else:
        sys.stdout.write(text)
    print('H2BT_RESULTS views=%d success=%d partial=%d failed=%d unreadable=%d' % (
        len(results), counts.get('success', 0), counts.get('partial', 0), counts.get('failed', 0), len(unreadable)))


if __name__ == '__main__':
    main()
