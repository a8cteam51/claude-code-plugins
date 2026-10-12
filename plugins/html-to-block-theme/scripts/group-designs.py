#!/usr/bin/env python3
"""Group the HTML files of a design directory before they are analysed.

    group-designs.py --dir <design-dir> [--out <groups.json>]

Analysing every file on its own reads the same stylesheets once per file and gives twenty
analyses to twenty posts of one template. This script reads only what tells files apart:

  name         a name for each file's report, unique in the set and made from its path, so
               that a/index.html and b/index.html do not write the same report
  stylesheets  every stylesheet file the set links, with how many files use it. The design's
               tokens are read from these once, not once per file.
  inline_styles  the CSS that pages carry in <style> blocks, by content, with the files that
               hold each. A design that links no stylesheet keeps its tokens here.
  css_set      the stylesheets one file links, by content
  template     files with the same body classes and the same landmark structure are taken
               to be one template. One of them is the representative.
  role         representative; same (its sections and its stylesheets match the
               representative's: it needs no analysis of its own); or differs, with
               differs_by saying whether its sections, its stylesheets or both do.

The groups are a proposal, made from markup alone. What sits inside a post-content
container is content and is not compared. The orchestrator decides what to merge.

Directories whose name starts with _h2bt or a dot are skipped: a mirror keeps its reading
aids and script-free copies there.

Last line: H2BT_GROUPS files=<n> stylesheets=<n> inline_styles=<n> templates=<n> analyse=<n> out=<path|->
analyse is the number of files that are not "same": the analyses the set needs.
"""
import argparse
import collections
import hashlib
import html.parser
import json
import os
import re
import sys
import urllib.parse

LANDMARKS = {'header', 'nav', 'main', 'footer', 'section', 'article', 'aside', 'form'}
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}
# Where a page's own content starts: what is inside differs from page to page of one template.
CONTENT_CONTAINER = re.compile(r'(^|[-_])(entry|post|page|the)[-_]content($|[-_])|wp-block-post-content')
# Classes that name one page, not a kind of page.
PAGE_SPECIFIC = re.compile(r'\d|^(logged-in|admin-bar|customize-support|no-js|js)$')


def digest(text):
    return hashlib.sha1(text.encode('utf-8', 'replace')).hexdigest()[:8]


def stable(classes, limit=None):
    kept = [name for name in classes if not PAGE_SPECIFIC.search(name)]
    return kept[:limit] if limit else kept


class Reader(html.parser.HTMLParser):
    """Collects stylesheets, scripts, body classes, landmarks and the sections of main."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stylesheets, self.scripts, self.body_classes = [], [], []
        self.inline_css = []
        self.landmarks = []
        self.main_sections, self.body_sections = [], []
        self.stack = []
        self.in_style = False
        self.main_depth = self.body_depth = self.content_depth = None
        self.main_open = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = (attrs.get('class') or '').split()
        if tag == 'link' and 'stylesheet' in (attrs.get('rel') or '').lower().split() and attrs.get('href'):
            self.stylesheets.append(attrs['href'])
        elif tag == 'script' and attrs.get('src'):
            self.scripts.append(attrs['src'])
        elif tag == 'style':
            self.in_style = True
        elif tag == 'body':
            self.body_classes = classes

        depth = len(self.stack)
        inside_content = self.content_depth is not None
        if not inside_content:
            if tag in LANDMARKS and depth <= 6:
                self.landmarks.append('%s.%s' % (tag, '.'.join(stable(classes, 2))))
            # The sections of a page: the first two levels inside main, or inside body when
            # the page has no main element.
            for container, found, open_ in ((self.main_depth, self.main_sections, self.main_open), (self.body_depth, self.body_sections, True)):
                if container is not None and open_ and 0 < depth - container <= 2:
                    found.append('%d:%s.%s' % (depth - container, tag, '.'.join(stable(classes, 3))))
        if tag in VOID:
            return
        if tag == 'main' and self.main_depth is None:
            self.main_depth, self.main_open = depth, True
        elif tag == 'body' and self.body_depth is None:
            self.body_depth = depth
        opens_content = not inside_content and any(CONTENT_CONTAINER.search(name) for name in classes)
        if opens_content:
            self.content_depth = depth
        self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag == 'style':
            self.in_style = False
        if tag in VOID or tag not in self.stack:
            return
        while self.stack:
            closed = self.stack.pop()
            depth = len(self.stack)
            if self.content_depth is not None and depth == self.content_depth:
                self.content_depth = None
            if closed == 'main' and depth == self.main_depth:
                self.main_open = False
            if closed == tag:
                break

    def handle_data(self, data):
        if self.in_style:
            self.inline_css.append(data)


def local_path(href, file_dir, root):
    """The file a link points at inside the design directory, or None for another host."""
    parts = urllib.parse.urlsplit(href)
    if parts.scheme or parts.netloc or href.startswith('//'):
        return None
    path = urllib.parse.unquote(parts.path)
    if not path:
        return None
    target = os.path.join(root, path.lstrip('/')) if path.startswith('/') else os.path.join(file_dir, path)
    return os.path.normpath(target)


def report_name(relative, taken):
    """about/index.html -> about, a/b.html -> a--b; the full path when that is already taken."""
    # Letters, digits, hyphens and underscores, starting with a letter or digit: a name is also
    # a file name, a sink name and an argument of wait-for-result.sh.
    def clean(text):
        return re.sub(r'[^A-Za-z0-9_-]+', '-', text.replace('/', '--')).strip('-_') or 'index'

    stem = re.sub(r'\.html?$', '', relative, flags=re.I)
    full = clean(stem)
    short = clean(stem[:-len('/index')] if stem.lower().endswith('/index') else stem)
    for candidate in (short, full):
        if candidate not in taken:
            return candidate
    number = 2
    while '%s-%d' % (full, number) in taken:
        number += 1
    return '%s-%d' % (full, number)


def main():
    parser = argparse.ArgumentParser(description='Group the HTML files of a design directory before analysis.')
    parser.add_argument('--dir', required=True)
    parser.add_argument('--out')
    args = parser.parse_args()

    root = os.path.realpath(args.dir)
    if not os.path.isdir(root):
        sys.exit('Directory not found: %s' % args.dir)

    paths = []
    for folder, folders, names in os.walk(root):
        folders[:] = sorted(name for name in folders if not name.startswith(('_h2bt', '.')) and name != 'node_modules')
        for name in sorted(names):
            if name.lower().endswith(('.html', '.htm')):
                paths.append(os.path.join(folder, name))
    if not paths:
        sys.exit('No .html file under %s' % root)

    content_hashes = {}

    def content_hash(path):
        if path not in content_hashes:
            try:
                with open(path, 'rb') as handle:
                    content_hashes[path] = hashlib.sha1(handle.read()).hexdigest()[:8]
            except OSError:
                content_hashes[path] = 'missing'
        return content_hashes[path]

    files, taken = [], set()
    css_sets = collections.OrderedDict()
    stylesheets = collections.OrderedDict()
    inline_styles = collections.OrderedDict()
    for path in paths:
        relative = os.path.relpath(path, root).replace(os.sep, '/')
        reader = Reader()
        try:
            with open(path, encoding='utf-8', errors='replace') as handle:
                reader.feed(handle.read())
        except OSError as error:
            sys.exit('Cannot read %s: %s' % (relative, error))

        sheets, outside = [], []
        for href in reader.stylesheets:
            target = local_path(href, os.path.dirname(path), root)
            if target is None:
                outside.append(href)
            else:
                sheets.append(os.path.relpath(target, root).replace(os.sep, '/'))
        key = sorted('%s@%s' % (sheet, content_hash(os.path.join(root, sheet))) for sheet in sheets) + sorted(outside)
        css_set = digest('\n'.join(key))
        css_sets.setdefault(css_set, {'stylesheets': sheets, 'other_hosts': outside, 'files': 0})['files'] += 1
        for sheet in dict.fromkeys(sheets):
            full = os.path.join(root, sheet)
            entry = stylesheets.setdefault(sheet, {'bytes': os.path.getsize(full) if os.path.isfile(full) else None, 'used_by': 0})
            entry['used_by'] += 1

        inline = ''.join(reader.inline_css)
        inline_key = digest(inline) if inline.strip() else None
        if inline_key:
            inline_styles.setdefault(inline_key, {'bytes': len(inline), 'files': []})['files'].append(relative)

        body = stable(reader.body_classes)
        sections = reader.main_sections if reader.main_depth is not None else reader.body_sections
        name = report_name(relative, taken)
        taken.add(name)
        files.append({
            'path': relative,
            'name': name,
            'css_set': css_set,
            'inline_css': inline_key,
            'scripts': len(reader.scripts),
            'body_classes': body,
            'template': 't-' + digest('\n'.join([' '.join(sorted(body)), '|'.join(reader.landmarks)])),
            'sections': digest('|'.join(sections)),
            'section_count': len(sections),
        })

    templates = collections.OrderedDict()
    for entry in files:
        templates.setdefault(entry['template'], []).append(entry)
    summary = collections.OrderedDict()
    for key, members in templates.items():
        # The representative is the first file with the commonest section structure.
        commonest = collections.Counter(member['sections'] for member in members).most_common(1)[0][0]
        representative = next(member for member in members if member['sections'] == commonest)
        for member in members:
            if member is representative:
                member['role'] = 'representative'
                continue
            by = [what for what, key in (('sections', 'sections'), ('stylesheets', 'css_set')) if member[key] != representative[key]]
            member['role'] = 'differs' if by else 'same'
            member['like'] = representative['name']
            if by:
                member['differs_by'] = by
        summary[key] = {
            'representative': representative['path'],
            'same': [member['path'] for member in members if member['role'] == 'same'],
            'differs': [member['path'] for member in members if member['role'] == 'differs'],
        }

    analyse = sum(1 for entry in files if entry['role'] != 'same')
    document = {'dir': root, 'files': files, 'stylesheets': stylesheets, 'inline_styles': inline_styles, 'css_sets': css_sets, 'templates': summary}
    text = json.dumps(document, indent=2) + '\n'
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, 'w', encoding='utf-8') as handle:
            handle.write(text)
        for key, group in summary.items():
            extra = ''
            if group['same'] or group['differs']:
                extra = '  (+%d same, %d differ)' % (len(group['same']), len(group['differs']))
            print('%s  %s%s' % (key, group['representative'], extra))
    else:
        sys.stdout.write(text)
    print('H2BT_GROUPS files=%d stylesheets=%d inline_styles=%d templates=%d analyse=%d out=%s' % (len(files), len(stylesheets), len(inline_styles), len(summary), analyse, args.out or '-'))


if __name__ == '__main__':
    main()
