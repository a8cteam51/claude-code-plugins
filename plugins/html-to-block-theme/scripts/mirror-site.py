#!/usr/bin/env python3
"""Mirror pages of a live site into a design directory (references/live-site-guide.md).

    mirror-site.py --mirror <dir> --base-url <https://host/> --page <path>[=<file>] [...]
                   [--rules <rules.json>] [--refetch] [--delay <seconds>]

Each page is fetched once and kept as it came, under <mirror>/_h2bt-raw/. Its stylesheets,
scripts, fonts and images are fetched once each: a file that is already in the mirror is not
fetched again, so the command can be repeated, and repeated with new rules, without touching
the live site. Assets of the site's own host keep their root-relative paths; assets of other
hosts go under /_hosts/<host>/.

Three copies of each page are written:

    <mirror>/<file>                  the page, with the scripts that were kept
    <mirror>/_h2bt-noscript/<file>   the same with every script removed: the default state
    <mirror>/_h2bt-aids/<file>       body only, no script, no style, inline SVG as placeholders

and <mirror>/_h2bt-manifest.json records what was fetched, removed, kept, and what failed.

Scripts for analytics, statistics, search and consent are removed, and so are speculation
rules and tracking pixels: a local copy must not report to the live site's trackers. The
built-in rules know the common ones. Every script is printed with what was decided for it, and
a kept script that looks as if it loads or reports something is printed as REVIEW: read those
lines, and add a rule for anything that should go. --rules names a JSON file:

    { "remove": [ { "attr": "<regex on the tag's attributes>", "body": "<regex on its body>",
                    "why": "<reason>" } ],
      "keep":   [ { "attr": "...", "body": "..." } ] }

A rule needs "attr" or "body" (or both, and then both must match). "keep" wins over every
removal, the built-in ones included. A script's body is matched with JSON-escaped slashes
(\\/) read as plain ones.

--page takes a path of the site ("/", "/about/", "/pricing") or a full address on it. The
file it becomes is index.html, about/index.html, pricing.html; "=<file>" names another.

Last line: H2BT_MIRROR pages=<n> assets=<n> bytes=<n> removed=<n> review=<n> failed=<n>
skipped=<n> manifest=<path>, or H2BT_MIRROR_FAIL reason=<why> when a page could not be
captured. An asset that fails (a file the live site itself is missing) is listed and counted,
and does not fail the run.

Limits: attribute values without quotes are not rewritten, and nothing a script loads at run
time is fetched.
"""
import argparse
import gzip
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/126.0.0.0 Safari/537.36')
UNSAFE_EXT = {'php', 'phtml', 'phar', 'cgi', 'pl', 'py', 'rb', 'sh', 'asp', 'aspx', 'jsp', 'htaccess'}
CACHE_BUST = re.compile(r'^(ver|v|version|t)=[\w.\-]+$')

# Hosts that only measure, advertise or ask for consent. A script or an image from one is removed.
TRACKER_HOSTS = (
    r'google-analytics\.com|googletagmanager\.com|googlesyndication\.com|doubleclick\.net|googleadservices\.com|'
    r'stats\.wp\.com|pixel\.wp\.com|connect\.facebook\.net|facebook\.com/tr|hotjar\.com|clarity\.ms|'
    r'segment\.com|segment\.io|plausible\.io|matomo\.|piwik\.|mixpanel\.com|amplitude\.com|heap(?:analytics)?\.(?:io|com)|'
    r'fullstory\.com|rudderstack\.com|rudderlabs\.com|parsely\.com|parse\.ly|quantserve\.com|scorecardresearch\.com|'
    r'nr-data\.net|newrelic\.com|bugsnag\.com|sentry\.io|sentry-cdn\.com|linkedin\.com/px|snap\.licdn\.com|'
    r'analytics\.tiktok\.com|bat\.bing\.com|cookiebot\.com|cookielaw\.org|onetrust\.com|osano\.com|termly\.io|'
    r'iubenda\.com|cookieyes\.com|usercentrics\.eu|trustarc\.com'
)

# (regex on the tag's attributes, regex on the body, reason). First match wins.
BUILT_IN_RULES = [
    (r'type\s*=\s*["\']speculationrules["\']', None, 'speculation rules: they prefetch pages that do not exist locally'),
    (r'\b(?:src|id)\s*=\s*["\'][^"\']*(?:%s)' % TRACKER_HOSTS, None, 'analytics, advertising or consent: a tracker host'),
    (None, r'(?:%s)' % TRACKER_HOSTS, 'analytics, advertising or consent: names a tracker host'),
    (r'\bid\s*=\s*["\'](?:jetpack-stats|jp-tracks|wpcom-stats|woocommerce-google-analytics|google_gtagjs|gtm4wp|monsterinsights)', None, 'statistics'),
    (None, r'\b(?:_stq|_paq|_gaq|dataLayer|gtag|ga|fbq|_hsq|rudderanalytics|analytics)\s*(?:=\s*window\.|\.push\s*\(|\(\s*["\'](?:config|js|create|init|track|page)["\'])', 'analytics call'),
    (None, r'\ba8cAnalytics(?:Config)?\b|\bGoogleAnalyticsObject\b|"ga4Id"|\bparselySiteId\b', 'analytics configuration'),
    (r'\b(?:src|id)\s*=\s*["\'][^"\']*(?:cookie[-_]?(?:banner|consent|notice|law)|consent[-_]?(?:banner|manager|mode)|complianz|cmplz|borlabs)', None, 'consent'),
    (None, r'consent[\w./-]*\.js|cookie[-_]?(?:banner|consent|notice)[\w./-]*\.js|\bCookieConsent\b|\bcookieBanner\b', 'consent'),
    (r'\bid\s*=\s*["\'](?:jetpack-instant-search|jetpack-search|algolia|swiftype|searchwp-live)', None, 'search'),
    (r'\bsrc\s*=\s*["\'][^"\']*(?:instant-search|instantsearch|algoliasearch|swiftype)', None, 'search'),
    (None, r'\bJetpackInstantSearchOptions\b|\binstantsearch\s*\(|\balgoliasearch\s*\(', 'search'),
]
REMOVE_LINK_RELS = {'preconnect', 'dns-prefetch', 'prefetch', 'prerender', 'modulepreload', 'manifest'}
REVIEW = re.compile(r'createElement\(\s*["\']script["\']|\.src\s*=|\bfetch\s*\(|XMLHttpRequest|sendBeacon|new\s+Image\b|importScripts|\bimport\s*\(')
DATA_TYPES = re.compile(r'type\s*=\s*["\'](?:application/(?:ld\+)?json|text/template|text/html|importmap)["\']', re.I)


class PageError(Exception):
    pass


def unescape_slashes(text):
    return text.replace('\\/', '/')


def parse_srcset(value):
    """Candidates of a srcset as (url, descriptor). A URL may hold commas; a candidate ends at
    a comma that follows a descriptor or ends a URL."""
    out, pos, end = [], 0, len(value)
    while pos < end:
        while pos < end and (value[pos].isspace() or value[pos] == ','):
            pos += 1
        if pos >= end:
            break
        start = pos
        while pos < end and not value[pos].isspace():
            pos += 1
        url, descriptor = value[start:pos], ''
        if url.endswith(','):
            url = url.rstrip(',')
        else:
            start = pos
            while pos < end and value[pos] != ',':
                pos += 1
            descriptor = value[start:pos].strip()
        if url:
            out.append((url, descriptor))
    return out


class Mirror:
    def __init__(self, mirror_dir, base_url, delay, refetch, rules):
        self.dir = os.path.abspath(mirror_dir)
        self.base = urllib.parse.urlsplit(base_url)
        self.origin = '%s://%s' % (self.base.scheme, self.base.netloc)
        self.delay = delay
        self.refetch = refetch
        self.remove_rules = [(r.get('attr'), r.get('body'), r.get('why', 'a rule of this run')) for r in rules.get('remove', [])]
        self.keep_rules = [(r.get('attr'), r.get('body')) for r in rules.get('keep', [])]
        self.fetched = {}
        self.failed = []
        self.skipped = []
        self.css_done = set()
        self.decisions = []

    # ---- paths -------------------------------------------------------------------------
    def local_ref(self, url):
        """Root-relative reference in the mirror for an absolute URL, or None when unsafe."""
        u = urllib.parse.urlsplit(url)
        if u.scheme not in ('http', 'https'):
            return None
        path = u.path or '/'
        if path.endswith('/'):
            path += 'index'
        segments = [urllib.parse.unquote(s) for s in path.split('/') if s != '']
        if not segments:
            return None
        for segment in segments:
            if segment in ('.', '..') or segment.startswith('.') or '\\' in segment or '/' in segment or '\x00' in segment:
                return None
        if segments[0].startswith('_h2bt') or segments[0] == '_hosts':
            return None
        name = segments[-1]
        stem, dot, ext = name.rpartition('.')
        if not dot:
            stem, ext = name, ''
        if ext.lower() in UNSAFE_EXT:
            return None
        same_host = u.netloc == self.base.netloc
        if u.query and not (same_host and CACHE_BUST.match(u.query)):
            digest = hashlib.sha1(u.query.encode()).hexdigest()[:8]
            name = '%s__%s%s' % (stem, digest, ('.' + ext) if ext else '')
        segments[-1] = name
        if not same_host:
            if not re.match(r'^[a-z0-9.\-]+(?::\d+)?$', u.netloc, re.I):
                return None
            segments = ['_hosts', u.netloc.lower().replace(':', '_')] + segments
        return '/' + '/'.join(urllib.parse.quote(s) for s in segments)

    def fs_path(self, ref):
        path = os.path.normpath(os.path.join(self.dir, urllib.parse.unquote(ref).lstrip('/')))
        if not path.startswith(self.dir + os.sep):
            raise ValueError('path leaves the mirror: %s' % ref)
        return path

    # ---- fetching ----------------------------------------------------------------------
    def get(self, url):
        request = urllib.request.Request(url, headers={
            'User-Agent': UA, 'Accept': '*/*', 'Accept-Encoding': 'gzip', 'Referer': self.origin + '/'})
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
            if response.headers.get('Content-Encoding') == 'gzip':
                body = gzip.decompress(body)
            return body, response.status, response.headers.get('Content-Type', ''), response.geturl()

    def fetch(self, url, kind):
        """Fetch an asset into the mirror once. Returns its reference, or None."""
        url = urllib.parse.urldefrag(url)[0]
        if url in self.fetched:
            return self.fetched[url]['ref']
        ref = self.local_ref(url)
        if ref is None:
            if not any(entry['url'] == url for entry in self.skipped):
                self.skipped.append({'url': url, 'why': 'unsafe or unsupported path'})
            return None
        path = self.fs_path(ref)
        entry = {'url': url, 'ref': ref, 'kind': kind}
        if os.path.exists(path) and not self.refetch:
            entry.update(status='kept', bytes=os.path.getsize(path))
        else:
            if any(failure['url'] == url for failure in self.failed):
                return None
            try:
                body, status, content_type, _ = self.get(url)
                entry.update(status=status, type=content_type, bytes=len(body))
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, 'wb') as handle:
                    handle.write(body)
                time.sleep(self.delay)
            except (urllib.error.URLError, OSError, ValueError) as error:
                self.failed.append({'url': url, 'kind': kind, 'error': str(error)})
                return None
        self.fetched[url] = entry
        if kind == 'css' or ref.lower().endswith('.css'):
            self.rewrite_css_file(url, path)
        return ref

    # ---- CSS ---------------------------------------------------------------------------
    def rewrite_css_text(self, css, css_url):
        def one(target, kind):
            target = target.strip().strip('"\'')
            if not target or target.startswith(('data:', '#', 'about:', 'blob:')):
                return None
            # A stylesheet the mirror already held was rewritten by the run that fetched it.
            if target.startswith(('/_hosts/', '/_h2bt')):
                return None
            absolute = urllib.parse.urljoin(css_url, target)
            fragment = urllib.parse.urlsplit(absolute).fragment
            ref = self.fetch(absolute, kind)
            if ref is None:
                return None
            return ref + ('#' + fragment if fragment else '')

        def url_sub(match):
            new = one(match.group(2), 'css-asset')
            return match.group(0) if new is None else 'url(%s%s%s)' % (match.group(1), new, match.group(1))

        def import_sub(match):
            new = one(match.group(2), 'css')
            return match.group(0) if new is None else '@import %s%s%s' % (match.group(1), new, match.group(1))

        css = re.sub(r'@import\s+(["\'])([^"\']+)\1', import_sub, css)
        return re.sub(r'url\(\s*(["\']?)([^)"\']+)\1\s*\)', url_sub, css)

    def rewrite_css_file(self, css_url, path):
        if path in self.css_done:
            return
        self.css_done.add(path)
        with open(path, encoding='utf-8', errors='replace') as handle:
            css = handle.read()
        css = re.sub(r'/\*# sourceMappingURL=[^*]*\*/', '', css)
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(self.rewrite_css_text(css, css_url))

    # ---- HTML --------------------------------------------------------------------------
    @staticmethod
    def attr(tag, name):
        match = re.search(r'\s%s\s*=\s*("([^"]*)"|\'([^\']*)\')' % re.escape(name), tag, re.I)
        if not match:
            return None
        return html.unescape(match.group(2) if match.group(2) is not None else match.group(3))

    @staticmethod
    def set_attr(tag, name, value):
        value = html.escape(value, quote=True)
        return re.sub(r'(\s%s\s*=\s*)("[^"]*"|\'[^\']*\')' % re.escape(name),
                      lambda match: '%s"%s"' % (match.group(1), value), tag, count=1, flags=re.I)

    def asset(self, page_url, value, kind):
        value = value.strip()
        if not value or value.startswith(('data:', '#', 'javascript:', 'mailto:', 'tel:', 'about:', 'blob:')):
            return None
        return self.fetch(urllib.parse.urljoin(page_url, value), kind)

    def decide(self, attrs, body):
        """(remove?, reason) for one script."""
        plain = unescape_slashes(body)

        def matches(attr_re, body_re):
            if not attr_re and not body_re:
                return False
            return (not attr_re or re.search(attr_re, attrs, re.I)) and (not body_re or re.search(body_re, plain))

        for attr_re, body_re in self.keep_rules:
            if matches(attr_re, body_re):
                return False, 'kept by a rule of this run'
        for attr_re, body_re, why in self.remove_rules + BUILT_IN_RULES:
            if matches(attr_re, body_re):
                return True, why
        return False, ''

    def process_page(self, raw, page_url, rel):
        own = urllib.parse.urlsplit(page_url)
        rows = []

        def script_sub(match):
            attrs, body = match.group(1), match.group(2)
            tag = '<script' + attrs + '>'
            src = self.attr(tag, 'src')
            ident = self.attr(tag, 'id') or src or ('inline, %d bytes' % len(body))
            remove, why = self.decide(attrs, body)
            if remove:
                rows.append({'what': 'script', 'id': ident, 'decision': 'removed', 'why': why})
                return ''
            row = {'what': 'script', 'id': ident, 'decision': 'kept', 'why': why}
            if src:
                absolute = urllib.parse.urljoin(page_url, src)
                if urllib.parse.urlsplit(absolute).netloc != self.base.netloc:
                    row['review'] = 'from another host: %s' % urllib.parse.urlsplit(absolute).netloc
                ref = self.asset(page_url, src, 'script')
                if ref:
                    tag = self.set_attr(tag, 'src', ref)
            elif not DATA_TYPES.search(attrs) and REVIEW.search(body):
                row['review'] = 'may load or report something: %s' % re.sub(r'\s+', ' ', body.strip())[:100]
            rows.append(row)
            return tag + body + '</script>'

        page = re.sub(r'<script\b([^>]*)>(.*?)</script>', script_sub, raw, flags=re.S | re.I)

        def link_sub(match):
            tag = match.group(0)
            rels = set((self.attr(tag, 'rel') or '').lower().split())
            href = self.attr(tag, 'href')
            if rels & REMOVE_LINK_RELS:
                rows.append({'what': 'link', 'id': '%s %s' % (' '.join(sorted(rels)), href), 'decision': 'removed',
                             'why': 'opens a connection to another host, or names a file the mirror does not hold'})
                return ''
            if not href:
                return tag
            if 'stylesheet' in rels:
                ref = self.asset(page_url, href, 'css')
            elif rels & {'icon', 'apple-touch-icon', 'mask-icon'} or ('preload' in rels and (self.attr(tag, 'as') or '') in ('image', 'font', 'style')):
                ref = self.asset(page_url, href, 'css' if (self.attr(tag, 'as') or '') == 'style' else 'image')
            elif 'preload' in rels:
                rows.append({'what': 'link', 'id': 'preload %s' % href, 'decision': 'removed', 'why': 'preloads a script'})
                return ''
            else:
                return tag
            return self.set_attr(tag, 'href', ref) if ref else tag

        page = re.sub(r'<link\b[^>]*>', link_sub, page, flags=re.I)
        page = re.sub(r'<base\b[^>]*>', lambda match: rows.append({'what': 'base', 'id': match.group(0)[:80], 'decision': 'removed', 'why': 'points relative addresses at the live site'}) or '', page, flags=re.I)

        def media_sub(match):
            tag = match.group(0)
            source = self.attr(tag, 'src') or ''
            if source and re.search(TRACKER_HOSTS, urllib.parse.urljoin(page_url, source), re.I):
                rows.append({'what': match.group(1).lower(), 'id': source[:120], 'decision': 'removed', 'why': 'a tracking pixel'})
                return ''
            for name in ('src', 'poster', 'data-src', 'data-lazy-src'):
                value = self.attr(tag, name)
                if value:
                    ref = self.asset(page_url, value, 'image')
                    if ref:
                        tag = self.set_attr(tag, name, ref)
            for name in ('srcset', 'data-srcset', 'imagesrcset'):
                value = self.attr(tag, name)
                if value:
                    parts = []
                    for url, descriptor in parse_srcset(value):
                        ref = self.asset(page_url, url, 'image')
                        parts.append(' '.join(part for part in (ref or url, descriptor) if part))
                    tag = self.set_attr(tag, name, ', '.join(parts))
            return tag

        page = re.sub(r'<(img|source|video|audio|input|embed|track)\b[^>]*>', media_sub, page, flags=re.I)

        def use_sub(match):
            tag = match.group(0)
            for name in ('href', 'xlink:href'):
                value = self.attr(tag, name)
                if value and not value.startswith('#'):
                    target, _, fragment = value.partition('#')
                    ref = self.asset(page_url, target, 'image')
                    if ref:
                        tag = self.set_attr(tag, name, ref + ('#' + fragment if fragment else ''))
            return tag

        page = re.sub(r'<use\b[^>]*>', use_sub, page, flags=re.I)

        page = re.sub(r'<style\b([^>]*)>(.*?)</style>',
                      lambda match: '<style%s>%s</style>' % (match.group(1), self.rewrite_css_text(match.group(2), page_url)),
                      page, flags=re.S | re.I)

        def style_attr_sub(match):
            value = html.unescape(match.group(2))
            if 'url(' not in value:
                return match.group(0)
            return '%s"%s"' % (match.group(1), html.escape(self.rewrite_css_text(value, page_url), quote=True))

        page = re.sub(r'(\sstyle\s*=\s*)"([^"]*)"', style_attr_sub, page, flags=re.I)

        # In-page links written with the page's own address become fragments.
        def anchor_sub(match):
            tag = match.group(0)
            href = self.attr(tag, 'href')
            if not href or '#' not in href or href.startswith('#'):
                return tag
            target = urllib.parse.urlsplit(urllib.parse.urljoin(page_url, href))
            if target.netloc == own.netloc and target.path.rstrip('/') == own.path.rstrip('/') and target.fragment and not target.query:
                return self.set_attr(tag, 'href', '#' + target.fragment)
            return tag

        page = re.sub(r'<a\b[^>]*>', anchor_sub, page, flags=re.I)

        # A kept inline script must not point the page's own scripts back at the live host for a
        # file the mirror holds: the site's origin is dropped where the path is in the mirror.
        held = sorted(name for name in os.listdir(self.dir) if not name.startswith('_') and os.path.isdir(os.path.join(self.dir, name)))

        def inline_sub(match):
            attrs, body = match.group(1), match.group(2)
            if re.search(r'\ssrc\s*=', attrs, re.I) or not held:
                return match.group(0)
            for form, slash in ((self.origin, '/'), (self.origin.replace('/', '\\/'), '\\/')):
                body = re.sub(re.escape(form + slash) + r'(?=(?:%s)(?:%s|["\']))' % ('|'.join(re.escape(name) for name in held), re.escape(slash)),
                              lambda _: slash, body)
            return '<script%s>%s</script>' % (attrs, body)

        page = re.sub(r'<script\b([^>]*)>(.*?)</script>', inline_sub, page, flags=re.S | re.I)

        noscript = re.sub(r'<script\b[^>]*>.*?</script>', '', page, flags=re.S | re.I)

        body = re.search(r'<body\b.*?</body>', noscript, flags=re.S | re.I)
        aid = body.group(0) if body else noscript
        aid = re.sub(r'<style\b[^>]*>.*?</style>', '', aid, flags=re.S | re.I)
        count = [0]

        def svg_sub(match):
            count[0] += 1
            tag = re.match(r'<svg\b[^>]*>', match.group(0)).group(0)
            keep = []
            for name in ('class', 'viewBox', 'width', 'height', 'aria-label', 'aria-hidden', 'role'):
                value = self.attr(tag, name)
                if value is not None:
                    keep.append('%s="%s"' % (name, html.escape(value, quote=True)))
            title = re.search(r'<title[^>]*>(.*?)</title>', match.group(0), flags=re.S | re.I)
            if title:
                keep.append('data-title="%s"' % html.escape(title.group(1).strip(), quote=True))
            return '<svg data-h2bt-placeholder="inline svg %d, %d bytes" %s></svg>' % (count[0], len(match.group(0)), ' '.join(keep))

        aid = re.sub(r'<svg\b[^>]*>.*?</svg>', svg_sub, aid, flags=re.S | re.I)
        aid = re.sub(r'\n\s*\n+', '\n', aid)

        for sub, text in (('', page), ('_h2bt-noscript', noscript), ('_h2bt-aids', aid)):
            path = self.fs_path('/' + '/'.join(part for part in (sub, rel) if part))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as handle:
                handle.write(text)
        self.decisions.append({'page': rel, 'elements': rows})
        return {'page': rel, 'url': page_url, 'bytes': len(page), 'noscript_bytes': len(noscript), 'aid_bytes': len(aid),
                'inline_svgs': count[0]}

    # ---- pages -------------------------------------------------------------------------
    def page_file(self, spec):
        """(address, file in the mirror) for a --page value."""
        target, _, name = spec.partition('=')
        address = urllib.parse.urljoin(self.origin + '/', target)
        parts = urllib.parse.urlsplit(address)
        if parts.netloc != self.base.netloc:
            raise PageError('%s is not on %s' % (target, self.base.netloc))
        if not name:
            path = urllib.parse.unquote(parts.path)
            if path.endswith('/') or path == '':
                name = path.strip('/') + '/index.html' if path.strip('/') else 'index.html'
            elif re.search(r'\.html?$', path, re.I):
                name = path.lstrip('/')
            else:
                name = path.lstrip('/') + '.html'
        segments = name.split('/')
        if any(s in ('', '.', '..') or s.startswith(('.', '_h2bt')) for s in segments) or segments[0] == '_hosts' or not name.endswith(('.html', '.htm')):
            raise PageError('%s is not a file name the mirror can hold' % name)
        return address, name

    def capture(self, spec):
        address, name = self.page_file(spec)
        raw_path = self.fs_path('/_h2bt-raw/' + name)
        fetched_at = None
        if os.path.exists(raw_path) and not self.refetch:
            with open(raw_path, 'rb') as handle:
                body = handle.read()
        else:
            try:
                body, status, _, final = self.get(address)
            except (urllib.error.URLError, OSError, ValueError) as error:
                raise PageError('%s: %s' % (address, error))
            if urllib.parse.urlsplit(final).netloc != self.base.netloc:
                raise PageError('%s redirects to another host: %s' % (address, final))
            os.makedirs(os.path.dirname(raw_path), exist_ok=True)
            with open(raw_path, 'wb') as handle:
                handle.write(body)
            fetched_at = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            with open(raw_path + '.fetched-at', 'w') as handle:
                handle.write(fetched_at + '\n')
            time.sleep(self.delay)
        if fetched_at is None and os.path.exists(raw_path + '.fetched-at'):
            with open(raw_path + '.fetched-at') as handle:
                fetched_at = handle.read().strip()
        charset = re.search(rb'<meta[^>]+charset=["\']?([\w-]+)', body[:4096], re.I)
        text = body.decode(charset.group(1).decode('ascii', 'replace') if charset else 'utf-8', errors='replace')
        result = self.process_page(text, address, name)
        result['captured_at'] = fetched_at
        return result


def main():
    parser = argparse.ArgumentParser(description='Mirror pages of a live site into a design directory.')
    parser.add_argument('--mirror', required=True)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--page', action='append', required=True)
    parser.add_argument('--rules')
    parser.add_argument('--refetch', action='store_true')
    parser.add_argument('--delay', type=float, default=0.15)
    args = parser.parse_args()

    def cannot(reason, message):
        print(message, file=sys.stderr)
        print('H2BT_MIRROR_FAIL reason=%s' % reason)
        return 1

    base = urllib.parse.urlsplit(args.base_url)
    if base.scheme not in ('http', 'https') or not base.netloc:
        return cannot('bad-base-url', '--base-url must be an http(s) address: %s' % args.base_url)
    rules = {}
    if args.rules:
        try:
            with open(args.rules, encoding='utf-8') as handle:
                rules = json.load(handle)
            for group in ('remove', 'keep'):
                for rule in rules.get(group, []):
                    if not (rule.get('attr') or rule.get('body')):
                        raise ValueError('a "%s" rule needs "attr" or "body"' % group)
                    for key in ('attr', 'body'):
                        if rule.get(key):
                            re.compile(rule[key])
        except (OSError, ValueError, re.error, AttributeError) as error:
            return cannot('bad-rules', 'The rules file could not be used: %s' % error)
    os.makedirs(args.mirror, exist_ok=True)

    mirror = Mirror(args.mirror, args.base_url, args.delay, args.refetch, rules)
    pages = []
    for spec in args.page:
        try:
            pages.append(mirror.capture(spec))
        except PageError as error:
            return cannot('page-not-captured', 'Could not capture a page: %s' % error)

    removed = review = 0
    for page in mirror.decisions:
        print('== %s' % page['page'])
        for row in page['elements']:
            if row['decision'] == 'removed':
                removed += 1
                print('  REMOVED  %-7s %s  (%s)' % (row['what'], row['id'][:90], row['why']))
            elif row.get('review'):
                review += 1
                print('  REVIEW   %-7s %s  (%s)' % (row['what'], row['id'][:90], row['review']))
            else:
                print('  KEPT     %-7s %s' % (row['what'], row['id'][:90]))
    for failure in mirror.failed:
        print('  FAILED   %s  (%s)' % (failure['url'], failure['error']))
    for skip in mirror.skipped:
        print('  SKIPPED  %s  (%s)' % (skip['url'], skip['why']))

    manifest_path = os.path.join(mirror.dir, '_h2bt-manifest.json')
    with open(manifest_path, 'w', encoding='utf-8') as handle:
        json.dump({
            'source': args.base_url,
            'pages': pages,
            'decisions': mirror.decisions,
            'fetched': sorted(mirror.fetched.values(), key=lambda entry: entry['ref']),
            'failed': mirror.failed,
            'skipped': mirror.skipped,
        }, handle, indent=1)
        handle.write('\n')
    print('H2BT_MIRROR pages=%d assets=%d bytes=%d removed=%d review=%d failed=%d skipped=%d manifest=%s' % (
        len(pages), len(mirror.fetched), sum(entry.get('bytes', 0) for entry in mirror.fetched.values()),
        removed, review, len(mirror.failed), len(mirror.skipped), manifest_path))
    return 0


if __name__ == '__main__':
    sys.exit(main())
