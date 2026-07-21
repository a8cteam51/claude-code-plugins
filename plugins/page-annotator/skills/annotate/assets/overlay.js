/**
 * Claude page annotator — injected into the target tab by the page-annotator
 * plugin via the Claude in Chrome javascript_tool.
 *
 * Adds a floating toolbar. The user picks elements on the page and attaches
 * notes; every saved annotation is serialized into a hidden
 * <script type="application/json" id="__claude_annotations__"> node that
 * Claude polls from outside the page.
 *
 * Constraints:
 * - The overlay persists after Send so the user can run further rounds;
 *   removal is user-initiated (the ✕ button, a refresh, or closing the
 *   tab) or happens implicitly on re-injection.
 * - No network requests; the DOM node is the only channel out.
 * - Never call alert()/confirm()/prompt() — modal dialogs freeze the
 *   Claude in Chrome extension bridge.
 * - The only page mutations are the overlay host element and the state node.
 */
(() => {
  'use strict';

  const STATE_ID = '__claude_annotations__';
  const HOST_ID = '__claude_annotator_host__';
  const GLOBAL = '__claudePageAnnotator';

  // Re-injection tears down any previous instance first.
  if (window[GLOBAL] && typeof window[GLOBAL].destroy === 'function') {
    try { window[GLOBAL].destroy(true); } catch (_) { /* ignore */ }
  }

  // Captured data is read back through the extension bridge, whose safety
  // filters can block payloads that look like credentials or session data.
  // Redact token-looking strings — the lookahead requires an uppercase letter
  // or digit in the run, so plain hyphenated slugs survive.
  const TOKEN_RE = /(?=[A-Za-z0-9_-]*[A-Z0-9])[A-Za-z0-9_-]{24,}/g;

  const state = {
    version: 1,
    status: 'annotating', // annotating | sent | cancelled
    page: {
      url: location.href.replace(TOKEN_RE, '…'),
      title: document.title,
      viewport: { width: innerWidth, height: innerHeight, dpr: devicePixelRatio },
      capturedAt: new Date().toISOString(),
    },
    annotations: [],
  };

  let stateEl = document.getElementById(STATE_ID);
  if (!stateEl) {
    stateEl = document.createElement('script');
    stateEl.type = 'application/json';
    stateEl.id = STATE_ID;
    document.documentElement.appendChild(stateEl);
  }
  const writeState = () => { stateEl.textContent = JSON.stringify(state); };
  writeState();

  /* ------------------- selector + capture helpers ------------------- */

  const esc = (s) => (window.CSS && CSS.escape)
    ? CSS.escape(s)
    : s.replace(/([^a-zA-Z0-9_-])/g, '\\$1');

  // Filter out generated class names (CSS modules, styled-components, hashes)
  // that will not exist in the source tree.
  const stableClass = (c) =>
    !!c && c.length <= 40 && !c.startsWith('__claude') &&
    !/^(css|sc|jsx|svelte|emotion)-/.test(c) && !/[0-9a-f]{6,}/i.test(c) &&
    // CSS-modules suffixes like "Button_root__x7f2a"; BEM "card__title"
    // survives because its suffix has no digits or uppercase.
    !/__(?=[a-zA-Z0-9]*[A-Z0-9])[a-zA-Z0-9]{4,10}$/.test(c);

  const uniquelyMatches = (sel, el) => {
    try {
      const found = document.querySelectorAll(sel);
      return found.length === 1 && found[0] === el;
    } catch (_) { return false; }
  };

  function fullPath(el) {
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && node !== document.documentElement) {
      const parent = node.parentElement;
      let idx = 1;
      if (parent) {
        idx = [...parent.children].filter((s) => s.localName === node.localName).indexOf(node) + 1;
      }
      parts.unshift(`${node.localName}:nth-of-type(${idx})`);
      node = parent;
    }
    return 'html > ' + parts.join(' > ');
  }

  function selectorFor(el) {
    if (el.id && uniquelyMatches('#' + esc(el.id), el)) return '#' + esc(el.id);
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && node !== document.body && node !== document.documentElement) {
      if (node.id) {
        parts.unshift('#' + esc(node.id));
        break;
      }
      let part = node.localName;
      const classes = [...node.classList].filter(stableClass).slice(0, 2);
      if (classes.length) part += '.' + classes.map(esc).join('.');
      const parent = node.parentElement;
      if (parent) {
        const same = [...parent.children].filter((s) => s.localName === node.localName);
        if (same.length > 1) part += `:nth-of-type(${same.indexOf(node) + 1})`;
      }
      parts.unshift(part);
      const candidate = parts.join(' > ');
      if (uniquelyMatches(candidate, el)) return candidate;
      node = node.parentElement;
    }
    const candidate = parts.join(' > ');
    if (candidate && uniquelyMatches(candidate, el)) return candidate;
    return fullPath(el);
  }

  const STYLE_PROPS = [
    'display', 'position', 'z-index', 'width', 'height', 'margin', 'padding',
    'font-family', 'font-size', 'font-weight', 'line-height', 'text-align',
    'color', 'background-color', 'border', 'border-radius', 'opacity',
    'overflow', 'flex-direction', 'justify-content', 'align-items', 'gap',
  ];

  // Source mapping needs structure and stable attributes, not live values:
  // strip form values and inline handlers, drop URL query strings, redact
  // data: URIs and token-looking strings. class/id stay verbatim — they are
  // the mapping keys.
  const URL_ATTRS = ['href', 'src', 'srcset', 'action', 'poster', 'formaction'];

  function sanitizedOuterHTML(el) {
    const clone = el.cloneNode(true);
    const nodes = [clone, ...clone.querySelectorAll('*')];
    for (const node of nodes) {
      if (node.localName === 'script' || node.localName === 'style') node.textContent = '';
      if (!node.attributes) continue;
      for (const attr of [...node.attributes]) {
        const name = attr.name;
        if (name === 'value' || name.startsWith('on')) { node.removeAttribute(name); continue; }
        if (name === 'class' || name === 'id') continue;
        let v = attr.value;
        if (URL_ATTRS.includes(name)) v = v.split(/[?#]/)[0];
        if (v.startsWith('data:')) v = 'data:…';
        v = v.replace(TOKEN_RE, '…');
        if (v !== attr.value) node.setAttribute(name, v);
      }
    }
    return clone.outerHTML.slice(0, 1500);
  }

  function capture(el, note) {
    const rect = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    const styles = {};
    for (const p of STYLE_PROPS) styles[p] = cs.getPropertyValue(p);
    return {
      id: state.annotations.length + 1,
      note,
      selector: selectorFor(el),
      tag: el.localName,
      classes: [...el.classList].filter((c) => !c.startsWith('__claude')),
      text: (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 200),
      outerHTML: sanitizedOuterHTML(el),
      styles,
      rect: {
        x: Math.round(rect.x + scrollX),
        y: Math.round(rect.y + scrollY),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
      },
      createdAt: new Date().toISOString(),
    };
  }

  /* ------------------------------ UI ------------------------------ */

  const host = document.createElement('div');
  host.id = HOST_ID;
  host.style.cssText = 'all:initial; position:fixed; top:0; left:0; width:0; height:0; z-index:2147483647;';
  document.documentElement.appendChild(host);
  const root = host.attachShadow({ mode: 'open' });
  root.innerHTML = `
  <style>
    * { box-sizing: border-box; margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    .toolbar { position: fixed; top: 16px; right: 16px; display: flex; gap: 8px; align-items: center;
      background: #1f1e1d; color: #faf9f5; padding: 8px 10px; border-radius: 10px;
      box-shadow: 0 4px 24px rgba(0,0,0,.35); font-size: 13px; pointer-events: auto; }
    .brand { font-weight: 600; margin-right: 2px; }
    .count { background: #d97757; border-radius: 999px; min-width: 20px; height: 20px; display: inline-flex;
      align-items: center; justify-content: center; padding: 0 6px; font-size: 12px; font-weight: 600; }
    button { border: 0; border-radius: 7px; padding: 6px 10px; font-size: 13px; cursor: pointer;
      background: #3a3937; color: #faf9f5; }
    button:hover { background: #4a4947; }
    button.primary { background: #d97757; }
    button.primary:hover { background: #c5674a; }
    button.primary:disabled { opacity: .45; cursor: default; }
    button.ghost { background: transparent; color: #b8b5ad; }
    button.ghost:hover { color: #faf9f5; background: #3a3937; }
    button.picking { outline: 2px solid #d97757; }
    .hl { position: fixed; border: 2px solid #d97757; background: rgba(217,119,87,.12); border-radius: 3px;
      pointer-events: none; }
    .hl-label { position: absolute; top: -22px; left: -2px; background: #d97757; color: #fff; font-size: 11px;
      padding: 2px 6px; border-radius: 4px; white-space: nowrap; }
    .pin { position: fixed; width: 22px; height: 22px; border-radius: 999px; background: #d97757; color: #fff;
      display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700;
      pointer-events: none; box-shadow: 0 2px 8px rgba(0,0,0,.3); transform: translate(-50%, -50%); }
    .panel { position: fixed; width: 320px; background: #1f1e1d; color: #faf9f5; border-radius: 10px;
      box-shadow: 0 4px 24px rgba(0,0,0,.4); padding: 12px; pointer-events: auto; }
    .target { font-size: 12px; color: #b8b5ad; margin-bottom: 8px; overflow: hidden; text-overflow: ellipsis;
      white-space: nowrap; }
    textarea { width: 100%; background: #2b2a28; color: #faf9f5; border: 1px solid #4a4947; border-radius: 7px;
      padding: 8px; font-size: 13px; resize: vertical; min-height: 64px; }
    textarea:focus { outline: 2px solid #d97757; border-color: transparent; }
    .actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 8px; }
    [hidden] { display: none !important; }
  </style>
  <div class="toolbar" part="toolbar">
    <span class="brand">Claude</span>
    <span class="count" id="count">0</span>
    <button id="pick">Annotate element</button>
    <button id="send" class="primary" disabled>Send to Claude</button>
    <button id="cancel" class="ghost" title="Close without sending">&#10005;</button>
  </div>
  <div class="hl" id="hl" hidden><span class="hl-label" id="hl-label"></span></div>
  <div id="pins"></div>
  <div class="panel" id="panel" hidden>
    <div class="target" id="target"></div>
    <textarea id="note" placeholder="What should Claude fix or check here?"></textarea>
    <div class="actions">
      <button id="discard" class="ghost">Discard</button>
      <button id="save" class="primary">Save note</button>
    </div>
  </div>`;

  const $ = (id) => root.getElementById(id);
  const ui = {
    pick: $('pick'), send: $('send'), cancel: $('cancel'), count: $('count'),
    hl: $('hl'), hlLabel: $('hl-label'), pins: $('pins'), panel: $('panel'),
    target: $('target'), note: $('note'), save: $('save'), discard: $('discard'),
  };

  let picking = false;
  let hoverEl = null;
  let pendingEl = null;
  const pinned = []; // { el, pin }

  const describe = (el) => {
    let d = el.localName;
    if (el.id) d += '#' + el.id;
    const cls = [...el.classList].filter(stableClass).slice(0, 2);
    if (cls.length) d += '.' + cls.join('.');
    const text = (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 40);
    return text ? `${d} — “${text}”` : d;
  };

  function setPicking(on) {
    picking = on;
    ui.pick.textContent = on ? 'Click an element… (Esc)' : 'Annotate element';
    ui.pick.classList.toggle('picking', on);
    if (!on) { ui.hl.hidden = true; hoverEl = null; }
  }

  function positionHl(el) {
    const r = el.getBoundingClientRect();
    Object.assign(ui.hl.style, {
      left: (r.left - 2) + 'px',
      top: (r.top - 2) + 'px',
      width: (r.width + 4) + 'px',
      height: (r.height + 4) + 'px',
    });
    ui.hlLabel.textContent = describe(el);
    ui.hl.hidden = false;
  }

  function openPanel(el) {
    pendingEl = el;
    ui.target.textContent = describe(el);
    ui.note.value = '';
    ui.panel.hidden = false;
    const r = el.getBoundingClientRect();
    const pw = 320;
    const ph = 170;
    const left = Math.min(Math.max(8, r.left), Math.max(8, innerWidth - pw - 8));
    let top = r.bottom + 8;
    if (top + ph > innerHeight - 8) top = Math.max(8, r.top - ph - 8);
    Object.assign(ui.panel.style, { left: left + 'px', top: top + 'px' });
    ui.note.focus();
  }

  function closePanel() {
    ui.panel.hidden = true;
    pendingEl = null;
  }

  function layoutPins() {
    for (const { el, pin } of pinned) {
      if (!el.isConnected) { pin.hidden = true; continue; }
      const r = el.getBoundingClientRect();
      pin.hidden = false;
      pin.style.left = r.left + 'px';
      pin.style.top = r.top + 'px';
    }
  }

  function addPin(el, n) {
    const pin = document.createElement('div');
    pin.className = 'pin';
    pin.textContent = n;
    ui.pins.appendChild(pin);
    pinned.push({ el, pin });
    layoutPins();
  }

  function saveNote() {
    const note = ui.note.value.trim();
    if (!pendingEl || !note) { closePanel(); return; }
    const ann = capture(pendingEl, note);
    state.annotations.push(ann);
    // A save after a Send starts a new batch.
    if (state.status === 'sent') {
      state.status = 'annotating';
      ui.send.textContent = 'Send to Claude';
    }
    writeState();
    addPin(pendingEl, ann.id);
    ui.count.textContent = String(state.annotations.length);
    ui.send.disabled = state.annotations.length === 0;
    closePanel();
  }

  /* --------------------------- events --------------------------- */

  const overlayTargeted = (e) => e.composedPath().includes(host);

  function onMove(e) {
    if (!picking || overlayTargeted(e)) return;
    const el = document.elementFromPoint(e.clientX, e.clientY);
    if (!el || el === host || el === document.documentElement || el === document.body) {
      ui.hl.hidden = true;
      hoverEl = null;
      return;
    }
    hoverEl = el;
    positionHl(el);
  }

  // While picking, keep the page from reacting to the exploratory pointer
  // activity (menus opening on mousedown, links navigating, etc.).
  function suppress(e) {
    if (!picking || overlayTargeted(e)) return;
    e.preventDefault();
    e.stopPropagation();
  }

  function onClick(e) {
    if (!picking || overlayTargeted(e)) return;
    e.preventDefault();
    e.stopPropagation();
    if (!hoverEl) return;
    const el = hoverEl;
    setPicking(false);
    openPanel(el);
  }

  function onKey(e) {
    if (e.key !== 'Escape') return;
    if (!ui.panel.hidden) { e.stopPropagation(); closePanel(); return; }
    if (picking) { e.stopPropagation(); setPicking(false); }
  }

  const listeners = [
    [document, 'mousemove', onMove, true],
    [document, 'pointerdown', suppress, true],
    [document, 'mousedown', suppress, true],
    [document, 'mouseup', suppress, true],
    [document, 'click', onClick, true],
    [document, 'keydown', onKey, true],
    [window, 'scroll', layoutPins, true],
    [window, 'resize', layoutPins, false],
  ];
  for (const [t, ev, fn, cap] of listeners) t.addEventListener(ev, fn, cap);

  // Keep keystrokes typed into the note box away from page-level hotkeys.
  for (const ev of ['keydown', 'keyup', 'keypress']) {
    host.addEventListener(ev, (e) => e.stopPropagation());
  }

  ui.pick.addEventListener('click', () => { closePanel(); setPicking(!picking); });
  ui.save.addEventListener('click', saveNote);
  ui.discard.addEventListener('click', closePanel);
  ui.note.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) saveNote();
  });

  ui.send.addEventListener('click', () => {
    if (!state.annotations.length) return;
    state.status = 'sent';
    state.page.title = document.title;
    writeState();
    console.log(`[claude-page-annotator] sent ${state.annotations.length} annotation(s)`);
    setPicking(false);
    closePanel();
    ui.send.textContent = 'Sent ✓';
    ui.send.disabled = true;
  });

  ui.cancel.addEventListener('click', () => {
    state.status = 'cancelled';
    writeState();
    console.log('[claude-page-annotator] cancelled');
    destroy(false);
  });

  function destroy(removeState) {
    for (const [t, ev, fn, cap] of listeners) t.removeEventListener(ev, fn, cap);
    host.remove();
    if (removeState) {
      const el = document.getElementById(STATE_ID);
      if (el) el.remove();
    }
    delete window[GLOBAL];
  }

  window[GLOBAL] = { destroy, version: 1 };

  console.log('[claude-page-annotator] overlay ready');
  return `[claude-page-annotator] ready on ${location.href}`;
})();
