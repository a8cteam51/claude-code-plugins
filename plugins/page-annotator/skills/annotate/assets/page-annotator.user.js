// ==UserScript==
// @name         Claude Page Annotator
// @namespace    https://github.com/a8cteam51/claude-code-plugins
// @version      0.2.0
// @description  Point at elements on any page and leave notes for Claude Code. Armed on demand by the page-annotator plugin; idle otherwise.
// @author       Automattic Special Projects
// @match        *://*/*
// @run-at       document-start
// @grant        GM_registerMenuCommand
// @noframes
// ==/UserScript==

/**
 * Claude page annotator — the canonical overlay, installed as a userscript.
 *
 * The plugin (page-annotator) owns this file. Claude never injects the overlay
 * source; it only stamps a one-attribute command onto <html> and reads the
 * resulting DOM node back. See skills/annotate/SKILL.md.
 *
 * Contract with the plugin:
 * - At document-start the script stamps <html data-claude-annotator="VERSION">
 *   so Claude can detect presence and compare against the version the plugin
 *   ships. A mismatch means the user should reinstall from the plugin's copy.
 * - Claude arms the overlay by setting <html data-claude-annotate="on"> and
 *   tears it down with "off". The user can also arm it from the Tampermonkey
 *   menu ("Annotate this page for Claude").
 * - Annotations are serialized into a hidden
 *   <script type="application/json" id="__claude_annotations__"> node, which
 *   Claude polls. The DOM is the only channel: this script runs in the
 *   userscript sandbox while Claude's javascript_tool runs in the page's main
 *   world, and the DOM is all they share. Never move the channel to a window
 *   global — the two worlds do not share one.
 *
 * Constraints:
 * - No network requests.
 * - Never call alert()/confirm()/prompt() — modal dialogs freeze the Claude in
 *   Chrome extension bridge.
 * - The only page mutations are the two <html> attributes, the overlay host
 *   element, and the state node.
 * - Chrome-only (the Claude in Chrome extension is Chrome-only), so modern
 *   APIs (CSS.escape, system-ui) are safe without fallbacks.
 */
(() => {
  'use strict';

  const VERSION = '0.2.0';
  const TAG = '[claude-page-annotator]';
  const STATE_ID = '__claude_annotations__';
  const HOST_ID = '__claude_annotator_host__';
  const MARK_ATTR = 'data-claude-annotator'; // version stamp, set at start
  const CMD_ATTR = 'data-claude-annotate'; // "on" | "off", set by Claude

  const doc = document;
  const now = () => new Date().toISOString();
  const round = Math.round;
  const rectOf = (el) => el.getBoundingClientRect();
  const textOf = (el, n) => (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, n);

  // Set while the overlay is up; holds its teardown. Module-scoped rather than
  // a window global because the page's main world cannot see either — but this
  // one at least stays private to the userscript sandbox.
  let active = null;

  /* =========================== the overlay =========================== */

  function boot() {
    if (active) return `${TAG} already armed on ${location.href}`;

    // Captured data is read back through the extension bridge, whose safety
    // filters can block payloads that look like credentials or session data.
    // Redact token-looking strings — the lookahead requires an uppercase letter
    // or digit in the run, so plain hyphenated slugs survive.
    const TOKEN_RE = /(?=[A-Za-z0-9_-]*[A-Z0-9])[A-Za-z0-9_-]{24,}/g;

    const state = {
      version: 2,
      script: VERSION,
      status: 'annotating', // annotating | sent | cancelled
      page: {
        url: location.href.replace(TOKEN_RE, '…'),
        title: doc.title,
        viewport: { width: innerWidth, height: innerHeight, dpr: devicePixelRatio },
        capturedAt: now(),
      },
      annotations: [],
    };

    let stateEl = doc.getElementById(STATE_ID);
    if (!stateEl) {
      stateEl = doc.createElement('script');
      stateEl.type = 'application/json';
      stateEl.id = STATE_ID;
      doc.documentElement.appendChild(stateEl);
    }
    const writeState = () => { stateEl.textContent = JSON.stringify(state); };
    writeState();

    /* ------------------- selector + capture helpers ------------------- */

    const esc = CSS.escape;

    // Filter out generated class names (CSS modules, styled-components, hashes)
    // that will not exist in the source tree.
    const stableClass = (c) =>
      !!c && c.length <= 40 && !c.startsWith('__claude') &&
      !/^(css|sc|jsx|svelte|emotion)-/.test(c) && !/[0-9a-f]{6,}/i.test(c) &&
      // CSS-modules suffixes like "Button_root__x7f2a"; BEM "card__title"
      // survives because its suffix has no digits or uppercase.
      !/__(?=[a-zA-Z0-9]*[A-Z0-9])[a-zA-Z0-9]{4,10}$/.test(c);

    const stableClasses = (el) => [...el.classList].filter(stableClass).slice(0, 2);

    const uniquelyMatches = (sel, el) => {
      try {
        const found = doc.querySelectorAll(sel);
        return found.length === 1 && found[0] === el;
      } catch (_) { return false; }
    };

    // Same-tag siblings of a node, for :nth-of-type computation.
    const sameTag = (node) =>
      [...node.parentElement.children].filter((s) => s.localName === node.localName);

    function fullPath(el) {
      const parts = [];
      let node = el;
      while (node && node.nodeType === 1 && node !== doc.documentElement) {
        const idx = node.parentElement ? sameTag(node).indexOf(node) + 1 : 1;
        parts.unshift(`${node.localName}:nth-of-type(${idx})`);
        node = node.parentElement;
      }
      return 'html > ' + parts.join(' > ');
    }

    function selectorFor(el) {
      if (el.id && uniquelyMatches('#' + esc(el.id), el)) return '#' + esc(el.id);
      const parts = [];
      let node = el;
      while (node && node.nodeType === 1 && node !== doc.body && node !== doc.documentElement) {
        if (node.id) {
          parts.unshift('#' + esc(node.id));
          break;
        }
        let part = node.localName;
        const classes = stableClasses(node);
        if (classes.length) part += '.' + classes.map(esc).join('.');
        if (node.parentElement) {
          const same = sameTag(node);
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

    const STYLE_PROPS = ('display,position,z-index,width,height,margin,padding,' +
      'font-family,font-size,font-weight,line-height,text-align,' +
      'color,background-color,border,border-radius,opacity,' +
      'overflow,flex-direction,justify-content,align-items,gap').split(',');

    // Source mapping needs structure and stable attributes, not live values:
    // strip form values and inline handlers, drop URL query strings, redact
    // data: URIs and token-looking strings. class/id stay verbatim — they are
    // the mapping keys.
    const URL_ATTRS = 'href,src,srcset,action,poster,formaction'.split(',');

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

    function capture(el, note, action) {
      const rect = rectOf(el);
      const cs = getComputedStyle(el);
      const styles = {};
      for (const p of STYLE_PROPS) styles[p] = cs.getPropertyValue(p);
      return {
        id: state.annotations.length + 1,
        note,
        action,
        selector: selectorFor(el),
        tag: el.localName,
        classes: [...el.classList].filter((c) => !c.startsWith('__claude')),
        text: textOf(el, 200),
        outerHTML: sanitizedOuterHTML(el),
        styles,
        rect: {
          x: round(rect.x + scrollX),
          y: round(rect.y + scrollY),
          width: round(rect.width),
          height: round(rect.height),
        },
        createdAt: now(),
      };
    }

    /* ------------------------------ UI ------------------------------ */

    const host = doc.createElement('div');
    host.id = HOST_ID;
    host.style.cssText = 'all:initial; position:fixed; top:0; left:0; width:0; height:0; z-index:2147483647;';
    doc.documentElement.appendChild(host);
    const root = host.attachShadow({ mode: 'open' });
    root.innerHTML = `
    <style>
      * { box-sizing: border-box; margin: 0; font-family: system-ui, sans-serif; }
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
        pointer-events: auto; cursor: pointer; box-shadow: 0 2px 8px rgba(0,0,0,.3); transform: translate(-50%, -50%); }
      .pin:hover { outline: 2px solid #faf9f5; }
      .pin.review { background: #5f7fbf; }
      .panel { position: fixed; width: 320px; background: #1f1e1d; color: #faf9f5; border-radius: 10px;
        box-shadow: 0 4px 24px rgba(0,0,0,.4); padding: 12px; pointer-events: auto; }
      .target { font-size: 12px; color: #b8b5ad; margin-bottom: 8px; overflow: hidden; text-overflow: ellipsis;
        white-space: nowrap; }
      textarea { width: 100%; background: #2b2a28; color: #faf9f5; border: 1px solid #4a4947; border-radius: 7px;
        padding: 8px; font-size: 13px; resize: vertical; min-height: 64px; }
      textarea:focus { outline: 2px solid #d97757; border-color: transparent; }
      .mode { display: flex; gap: 6px; margin-top: 8px; }
      .mode button { flex: 1; background: #2b2a28; border: 1px solid #4a4947; color: #b8b5ad; }
      #actReview.active { background: #5f7fbf; border-color: #5f7fbf; color: #fff; }
      #actFix.active { background: #d97757; border-color: #d97757; color: #fff; }
      .actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 8px; }
      #del { margin-right: auto; color: #e08b7d; }
      #del:hover { background: #4a2b25; color: #ffb4a5; }
      [hidden] { display: none !important; }
    </style>
    <div class="toolbar">
      <span class="brand">Claude</span>
      <span class="count" id="count">0</span>
      <button id="pick">Annotate element</button>
      <button id="send" class="primary" disabled>Send to Claude</button>
      <button id="cancel" class="ghost" title="Close without sending">✕</button>
    </div>
    <div class="hl" id="hl" hidden><span class="hl-label" id="hlLabel"></span></div>
    <div id="pins"></div>
    <div class="panel" id="panel" hidden>
      <div class="target" id="target"></div>
      <textarea id="note" placeholder="What should Claude fix or check here?"></textarea>
      <div class="mode">
        <button id="actReview" title="Claude proposes a fix and asks first">Review</button>
        <button id="actFix" title="Claude applies the fix immediately">Fix</button>
      </div>
      <div class="actions">
        <button id="del" class="ghost" hidden>Delete</button>
        <button id="discard" class="ghost">Discard</button>
        <button id="save" class="primary">Save note</button>
      </div>
    </div>`;

    // Element ids double as the ui-map keys.
    const ui = {};
    for (const id of 'pick,send,cancel,count,hl,hlLabel,pins,panel,target,note,save,discard,actReview,actFix,del'.split(',')) {
      ui[id] = root.getElementById(id);
    }

    let picking = false;
    let hoverEl = null;
    let pendingEl = null;
    let pendingAction = 'review'; // sticky: remembers the last choice
    let editingAnn = null; // annotation being edited via its pin, else null
    const pinned = []; // { el, pin, ann }

    function setAction(a) {
      pendingAction = a;
      ui.actReview.classList.toggle('active', a === 'review');
      ui.actFix.classList.toggle('active', a === 'fix');
    }

    const pinClass = (ann) => 'pin ' + (ann.action === 'fix' ? 'fix' : 'review');

    const describe = (el) => {
      let d = el.localName;
      if (el.id) d += '#' + el.id;
      const cls = stableClasses(el);
      if (cls.length) d += '.' + cls.join('.');
      const text = textOf(el, 40);
      return text ? `${d} — “${text}”` : d;
    };

    function setPicking(on) {
      picking = on;
      ui.pick.textContent = on ? 'Click an element… (Esc)' : 'Annotate element';
      ui.pick.classList.toggle('picking', on);
      if (!on) { ui.hl.hidden = true; hoverEl = null; }
    }

    function positionHl(el) {
      const r = rectOf(el);
      Object.assign(ui.hl.style, {
        left: (r.left - 2) + 'px',
        top: (r.top - 2) + 'px',
        width: (r.width + 4) + 'px',
        height: (r.height + 4) + 'px',
      });
      ui.hlLabel.textContent = describe(el);
      ui.hl.hidden = false;
    }

    function openPanel(el, existing) {
      pendingEl = el;
      editingAnn = existing || null;
      ui.target.textContent = describe(el);
      ui.note.value = existing ? existing.note : '';
      setAction(existing ? (existing.action || 'review') : pendingAction);
      ui.save.textContent = existing ? 'Update note' : 'Save note';
      ui.del.hidden = !existing;
      ui.panel.hidden = false;
      const r = rectOf(el);
      const pw = 320;
      const ph = 210;
      const left = Math.min(Math.max(8, r.left), Math.max(8, innerWidth - pw - 8));
      let top = r.bottom + 8;
      if (top + ph > innerHeight - 8) top = Math.max(8, r.top - ph - 8);
      Object.assign(ui.panel.style, { left: left + 'px', top: top + 'px' });
      ui.note.focus();
    }

    function closePanel() {
      ui.panel.hidden = true;
      pendingEl = null;
      editingAnn = null;
    }

    // Any change after a Send starts a new batch and re-arms the Send button.
    function markDirty() {
      if (state.status === 'sent') {
        state.status = 'annotating';
        ui.send.textContent = 'Send to Claude';
      }
      ui.send.disabled = state.annotations.length === 0;
    }

    // Persist a mutation and resync the toolbar.
    function commit() {
      markDirty();
      writeState();
      ui.count.textContent = String(state.annotations.length);
      closePanel();
    }

    function layoutPins() {
      for (const { el, pin } of pinned) {
        if (!el.isConnected) { pin.hidden = true; continue; }
        const r = rectOf(el);
        pin.hidden = false;
        pin.style.left = r.left + 'px';
        pin.style.top = r.top + 'px';
      }
    }

    function addPin(el, ann) {
      const pin = doc.createElement('div');
      pin.className = pinClass(ann);
      pin.textContent = ann.id;
      pin.title = 'Edit note';
      pin.addEventListener('click', (e) => {
        e.stopPropagation();
        setPicking(false);
        openPanel(el, ann);
      });
      ui.pins.appendChild(pin);
      pinned.push({ el, pin, ann });
      layoutPins();
    }

    function saveNote() {
      const note = ui.note.value.trim();
      if (!pendingEl || !note) { closePanel(); return; }
      if (editingAnn) {
        editingAnn.note = note;
        editingAnn.action = pendingAction;
        editingAnn.updatedAt = now();
        const entry = pinned.find((p) => p.ann === editingAnn);
        if (entry) entry.pin.className = pinClass(editingAnn);
      } else {
        const ann = capture(pendingEl, note, pendingAction);
        state.annotations.push(ann);
        addPin(pendingEl, ann);
      }
      commit();
    }

    function deleteNote() {
      if (!editingAnn) { closePanel(); return; }
      const idx = state.annotations.indexOf(editingAnn);
      if (idx !== -1) state.annotations.splice(idx, 1);
      const pIdx = pinned.findIndex((p) => p.ann === editingAnn);
      if (pIdx !== -1) { pinned[pIdx].pin.remove(); pinned.splice(pIdx, 1); }
      commit();
    }

    /* --------------------------- events --------------------------- */

    const overlayTargeted = (e) => e.composedPath().includes(host);

    function onMove(e) {
      if (!picking || overlayTargeted(e)) return;
      const el = doc.elementFromPoint(e.clientX, e.clientY);
      if (!el || el === host || el === doc.documentElement || el === doc.body) {
        ui.hl.hidden = true;
        hoverEl = null;
        return;
      }
      hoverEl = el;
      positionHl(el);
    }

    // While picking, keep the page from reacting to the exploratory pointer
    // activity (menus opening on mousedown, links navigating, etc.). Returns
    // whether the event was ours to swallow.
    function suppress(e) {
      if (!picking || overlayTargeted(e)) return false;
      e.preventDefault();
      e.stopPropagation();
      return true;
    }

    function onClick(e) {
      if (!suppress(e) || !hoverEl) return;
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
      [doc, 'mousemove', onMove, true],
      [doc, 'pointerdown', suppress, true],
      [doc, 'mousedown', suppress, true],
      [doc, 'mouseup', suppress, true],
      [doc, 'click', onClick, true],
      [doc, 'keydown', onKey, true],
      [window, 'scroll', layoutPins, true],
      [window, 'resize', layoutPins, false],
    ];
    for (const [t, ev, fn, cap] of listeners) t.addEventListener(ev, fn, cap);

    // Keep keystrokes typed into the note box away from page-level hotkeys.
    for (const ev of 'keydown,keyup,keypress'.split(',')) {
      host.addEventListener(ev, (e) => e.stopPropagation());
    }

    ui.pick.addEventListener('click', () => { closePanel(); setPicking(!picking); });
    ui.actReview.addEventListener('click', () => setAction('review'));
    ui.actFix.addEventListener('click', () => setAction('fix'));
    ui.del.addEventListener('click', deleteNote);
    ui.save.addEventListener('click', saveNote);
    ui.discard.addEventListener('click', closePanel);
    ui.note.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) saveNote();
    });

    ui.send.addEventListener('click', () => {
      if (!state.annotations.length) return;
      state.status = 'sent';
      state.page.title = doc.title;
      writeState();
      console.log(`${TAG} sent ${state.annotations.length} annotation(s)`);
      setPicking(false);
      closePanel();
      ui.send.textContent = 'Sent ✓';
      ui.send.disabled = true;
    });

    ui.cancel.addEventListener('click', () => {
      state.status = 'cancelled';
      writeState();
      console.log(TAG + ' cancelled');
      destroy(false);
    });

    function destroy(removeState) {
      for (const [t, ev, fn, cap] of listeners) t.removeEventListener(ev, fn, cap);
      host.remove();
      if (removeState) {
        const el = doc.getElementById(STATE_ID);
        if (el) el.remove();
      }
      active = null;
    }

    active = { destroy };

    console.log(TAG + ' overlay ready');
    return `${TAG} ready on ${location.href}`;
  }

  function shutdown() {
    if (active) active.destroy(true);
  }

  /* ========================= arming / plumbing ========================= */

  // Claude's only write into the page is CMD_ATTR on <html>; everything else
  // it does is a read. Setting the attribute to its current value still fires
  // a mutation record, and boot() is idempotent, so repeat arms are harmless.
  function applyCommand() {
    const cmd = doc.documentElement.getAttribute(CMD_ATTR);
    if (cmd === 'on') boot();
    else if (cmd === 'off') shutdown();
  }

  function start() {
    doc.documentElement.setAttribute(MARK_ATTR, VERSION);
    new MutationObserver(applyCommand).observe(doc.documentElement, {
      attributes: true,
      attributeFilter: [CMD_ATTR],
    });
    // Honour an attribute that was already present (server-rendered, or set
    // before this observer attached).
    applyCommand();
  }

  if (doc.documentElement) start();
  else doc.addEventListener('readystatechange', start, { once: true });

  if (typeof GM_registerMenuCommand === 'function') {
    GM_registerMenuCommand('Annotate this page for Claude', boot);
    GM_registerMenuCommand('Close annotator', shutdown);
  }
})();
