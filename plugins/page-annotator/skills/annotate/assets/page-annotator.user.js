// ==UserScript==
// @name         Claude Page Annotator
// @namespace    https://github.com/a8cteam51/claude-code-plugins
// @version      0.3.0
// @description  Point at elements on any page, leave notes, and have Claude Code file each one as a GitHub issue with a screenshot. Armed on demand by the page-annotator plugin; idle otherwise.
// @author       Automattic Special Projects
// @match        *://*/*
// @run-at       document-start
// @grant        GM_registerMenuCommand
// @grant        GM_setValue
// @grant        GM_getValue
// @noframes
// ==/UserScript==

/**
 * Claude page annotator — the canonical overlay, installed as a userscript.
 *
 * The plugin (page-annotator) owns this file. Claude never injects the overlay
 * source; it only stamps commands onto <html> and reads the resulting DOM node
 * back. See skills/annotate/SKILL.md.
 *
 * Each annotation becomes one GitHub issue. The overlay collects the note, an
 * optional issue title, the target repository and everything mechanically
 * knowable about the element and the browser; Claude captures the screenshot
 * and files the issues, because this script makes no network requests.
 *
 * Contract with the plugin — four attributes on <html>, two each direction:
 *
 *   script -> Claude
 *     data-claude-annotator      version stamp, set at document-start
 *     data-claude-annotator-ack  echo of the last command handled, so Claude
 *                                can confirm rather than guess at timing
 *
 *   Claude -> script
 *     data-claude-annotate         "on" | "off" | "shot:<id>" | "shot:end"
 *     data-claude-annotate-config  JSON: { repo, issues: { <id>: {number,url} } }
 *
 * "shot:<id>" enters capture mode: scroll that annotation's element into view,
 * hide the overlay's own chrome, and ring the element so a plain viewport
 * screenshot shows the problem in context. "shot:end" restores.
 *
 * The config attribute both prefills the repository and stamps filed issue
 * numbers back onto annotations — which is what stops a second batch from
 * re-filing the first one.
 *
 * Annotations are serialized into a hidden
 * <script type="application/json" id="__claude_annotations__"> node, which
 * Claude polls. The DOM is the only channel: this script runs in the userscript
 * sandbox while Claude's javascript_tool runs in the page's main world, and the
 * DOM is all they share. Never move the channel to a window global — the two
 * worlds do not share one.
 *
 * Constraints:
 * - No network requests.
 * - Never call alert()/confirm()/prompt() — modal dialogs freeze the Claude in
 *   Chrome extension bridge.
 * - The only page mutations are the <html> attributes, the overlay host
 *   element, and the state node. The saved repository lives in the userscript
 *   manager's own storage (GM_setValue), not the page's.
 * - Captured markup is now published to an issue tracker, not just read into a
 *   conversation, so the capture-time scrubbing below matters more, not less.
 * - Chrome-only (the Claude in Chrome extension is Chrome-only), so modern
 *   APIs (CSS.escape, system-ui) are safe without fallbacks.
 */
(() => {
  'use strict';

  const VERSION = '0.3.0';
  const TAG = '[claude-page-annotator]';
  const STATE_ID = '__claude_annotations__';
  const HOST_ID = '__claude_annotator_host__';
  const MARK_ATTR = 'data-claude-annotator'; // version stamp, set at start
  const ACK_ATTR = 'data-claude-annotator-ack'; // command echo, for Claude
  const CMD_ATTR = 'data-claude-annotate'; // "on" | "off" | "shot:*"
  const CFG_ATTR = 'data-claude-annotate-config'; // JSON, set by Claude

  const REPO_RE = /^[\w.-]+\/[\w.-]+$/;

  const doc = document;
  const now = () => new Date().toISOString();
  const round = Math.round;
  const rectOf = (el) => el.getBoundingClientRect();
  const textOf = (el, n) => (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, n);

  // Captured data is read back through the extension bridge, whose safety
  // filters can block payloads that look like credentials or session data, and
  // then published to a GitHub issue. Redact token-looking strings — the
  // lookahead requires an uppercase letter or digit in the run, so plain
  // hyphenated slugs survive.
  const TOKEN_RE = /(?=[A-Za-z0-9_-]*[A-Z0-9])[A-Za-z0-9_-]{24,}/g;
  const redact = (s) => (s || '').replace(TOKEN_RE, '…');

  // The repository is remembered per-origin: one site maps to one repo. Kept in
  // the userscript manager's storage so the page's own localStorage is left
  // alone (and so it survives origins that block storage).
  const repoKey = () => `repo:${location.origin}`;
  const loadRepo = () => {
    try {
      return typeof GM_getValue === 'function' ? GM_getValue(repoKey(), '') : '';
    } catch (_) { return ''; }
  };
  const saveRepo = (v) => {
    try {
      if (typeof GM_setValue === 'function') GM_setValue(repoKey(), v);
    } catch (_) { /* storage unavailable — the field still works for this page */ }
  };

  const ack = (value) => doc.documentElement.setAttribute(ACK_ATTR, value);

  // Set while the overlay is up; holds its teardown and command handlers.
  // Module-scoped rather than a window global because the page's main world
  // cannot see either — but this one at least stays private to the sandbox.
  let active = null;

  /* =========================== the overlay =========================== */

  function boot() {
    if (active) return `${TAG} already armed on ${location.href}`;

    const mq = (q) => matchMedia(q).matches;

    const state = {
      version: 3,
      script: VERSION,
      status: 'annotating', // annotating | sent | cancelled
      repo: loadRepo(),
      page: {
        url: redact(location.href),
        title: doc.title,
        referrer: redact(doc.referrer),
        viewport: { width: innerWidth, height: innerHeight, dpr: devicePixelRatio },
        capturedAt: now(),
      },
      env: {
        userAgent: navigator.userAgent,
        platform: (navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform,
        language: navigator.language,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        screen: { width: screen.width, height: screen.height },
        colorScheme: mq('(prefers-color-scheme: dark)') ? 'dark' : 'light',
        reducedMotion: mq('(prefers-reduced-motion: reduce)'),
      },
      annotations: [],
    };

    // Monotonic, never reused: ids key the issue numbers Claude stamps back, so
    // recycling one after a delete would attach the wrong issue to a note.
    let nextId = 1;

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

    // The issue needs structure and stable attributes, not live values: strip
    // form values and inline handlers, drop URL query strings, redact data:
    // URIs and token-looking strings. class/id stay verbatim — they are what
    // makes the markup recognisable to whoever picks the issue up.
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

    function capture(el, note, title) {
      const rect = rectOf(el);
      const cs = getComputedStyle(el);
      const styles = {};
      for (const p of STYLE_PROPS) styles[p] = cs.getPropertyValue(p);
      return {
        id: nextId++,
        title,
        note,
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
        scroll: { x: round(scrollX), y: round(scrollY) },
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
      /* Capture mode: everything of ours disappears except the ring, so a plain
         viewport screenshot shows the page, not the tool. */
      :host(.capturing) .toolbar,
      :host(.capturing) .panel,
      :host(.capturing) .hl,
      :host(.capturing) #pins { display: none !important; }
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
      input { background: #2b2a28; color: #faf9f5; border: 1px solid #4a4947; border-radius: 7px;
        padding: 6px 8px; font-size: 13px; }
      input:focus { outline: 2px solid #d97757; border-color: transparent; }
      input.bad { border-color: #e08b7d; }
      #repo { width: 168px; }
      .hl { position: fixed; border: 2px solid #d97757; background: rgba(217,119,87,.12); border-radius: 3px;
        pointer-events: none; }
      .hl-label { position: absolute; top: -22px; left: -2px; background: #d97757; color: #fff; font-size: 11px;
        padding: 2px 6px; border-radius: 4px; white-space: nowrap; }
      /* The ring for a screenshot: a spotlight that dims the rest of the page
         just enough to point the eye without hiding the context. */
      .shot { position: fixed; border: 3px solid #d97757; border-radius: 4px; pointer-events: none;
        box-shadow: 0 0 0 9999px rgba(0,0,0,.28); }
      .shot-badge { position: absolute; top: -27px; left: -3px; background: #d97757; color: #fff;
        font-size: 12px; font-weight: 700; padding: 3px 8px; border-radius: 5px; white-space: nowrap; }
      .pin { position: fixed; width: 22px; height: 22px; border-radius: 999px; background: #d97757; color: #fff;
        display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700;
        pointer-events: auto; cursor: pointer; box-shadow: 0 2px 8px rgba(0,0,0,.3); transform: translate(-50%, -50%); }
      .pin:hover { outline: 2px solid #faf9f5; }
      .pin.filed { background: #3f9c5a; }
      .panel { position: fixed; width: 320px; background: #1f1e1d; color: #faf9f5; border-radius: 10px;
        box-shadow: 0 4px 24px rgba(0,0,0,.4); padding: 12px; pointer-events: auto; }
      .target { font-size: 12px; color: #b8b5ad; margin-bottom: 8px; overflow: hidden; text-overflow: ellipsis;
        white-space: nowrap; }
      #title { width: 100%; margin-bottom: 6px; }
      textarea { width: 100%; background: #2b2a28; color: #faf9f5; border: 1px solid #4a4947; border-radius: 7px;
        padding: 8px; font-size: 13px; resize: vertical; min-height: 64px; }
      textarea:focus { outline: 2px solid #d97757; border-color: transparent; }
      .filed-note { font-size: 12px; color: #8fbf9f; margin-top: 8px; }
      .actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 8px; }
      #del { margin-right: auto; color: #e08b7d; }
      #del:hover { background: #4a2b25; color: #ffb4a5; }
      [hidden] { display: none !important; }
    </style>
    <div class="toolbar">
      <span class="brand">Claude</span>
      <span class="count" id="count">0</span>
      <input id="repo" placeholder="owner/repo" spellcheck="false" title="GitHub repository to file issues in">
      <button id="pick">Annotate element</button>
      <button id="send" class="primary" disabled>Create GitHub issues</button>
      <button id="cancel" class="ghost" title="Close without filing">✕</button>
    </div>
    <div class="hl" id="hl" hidden><span class="hl-label" id="hlLabel"></span></div>
    <div class="shot" id="shot" hidden><span class="shot-badge" id="shotBadge"></span></div>
    <div id="pins"></div>
    <div class="panel" id="panel" hidden>
      <div class="target" id="target"></div>
      <input id="title" placeholder="Issue title (optional)" spellcheck="false">
      <textarea id="note" placeholder="Describe the problem — this becomes the issue body"></textarea>
      <div class="filed-note" id="filed" hidden></div>
      <div class="actions">
        <button id="del" class="ghost" hidden>Delete</button>
        <button id="discard" class="ghost">Discard</button>
        <button id="save" class="primary">Save note</button>
      </div>
    </div>`;

    // Element ids double as the ui-map keys.
    const ui = {};
    for (const id of ('pick,send,cancel,count,repo,hl,hlLabel,shot,shotBadge,pins,panel,' +
      'target,title,note,filed,save,discard,del').split(',')) {
      ui[id] = root.getElementById(id);
    }

    let picking = false;
    let hoverEl = null;
    let pendingEl = null;
    let editingAnn = null; // annotation being edited via its pin, else null
    const pinned = []; // { el, pin, ann }

    const pinClass = (ann) => 'pin' + (ann.issue ? ' filed' : '');
    const pending = () => state.annotations.filter((a) => !a.issue);

    const describe = (el) => {
      let d = el.localName;
      if (el.id) d += '#' + el.id;
      const cls = stableClasses(el);
      if (cls.length) d += '.' + cls.join('.');
      const text = textOf(el, 40);
      return text ? `${d} — “${text}”` : d;
    };

    /* --------------------------- repository --------------------------- */

    ui.repo.value = state.repo;

    function setRepo(value) {
      state.repo = value.trim();
      ui.repo.classList.toggle('bad', !!state.repo && !REPO_RE.test(state.repo));
      saveRepo(state.repo);
      writeState();
      syncSend();
    }

    // Send needs both a valid repo and something left to file.
    function syncSend() {
      const left = pending().length;
      ui.count.textContent = String(state.annotations.length);
      ui.send.disabled = left === 0 || !REPO_RE.test(state.repo || '');
      ui.send.textContent =
        state.status === 'sent' ? 'Filing…'
          : left === 0 && state.annotations.length ? 'All filed ✓'
            : 'Create GitHub issues';
    }

    /* ------------------------------ panel ------------------------------ */

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
      ui.title.value = existing ? (existing.title || '') : '';
      ui.note.value = existing ? existing.note : '';
      ui.save.textContent = existing ? 'Update note' : 'Save note';
      ui.del.hidden = !existing;
      // An already-filed note can still be edited, but the issue is out the
      // door — say so rather than implying the edit propagates.
      const filed = existing && existing.issue;
      ui.filed.hidden = !filed;
      if (filed) ui.filed.textContent = `Filed as #${existing.issue.number} — edits here won't update the issue.`;
      ui.panel.hidden = false;
      const r = rectOf(el);
      const pw = 320;
      const ph = filed ? 275 : 250;
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
    // "filed" resets too: a note added to a fully-filed batch must not leave a
    // status that tells Claude there is nothing left to do.
    function markDirty() {
      if (state.status === 'sent' || state.status === 'filed') state.status = 'annotating';
      syncSend();
    }

    // Persist a mutation and resync the toolbar.
    function commit() {
      markDirty();
      writeState();
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
      const title = ui.title.value.trim();
      if (!pendingEl || !note) { closePanel(); return; }
      if (editingAnn) {
        editingAnn.note = note;
        editingAnn.title = title;
        editingAnn.updatedAt = now();
      } else {
        const ann = capture(pendingEl, note, title);
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

    /* -------------------- commands from Claude -------------------- */

    // Where the user was looking before a capture run started, so their view
    // isn't left parked on the last annotated element.
    let shotReturn = null;

    // Capture mode. Scrolling is instant so the rect is stable, but the ring is
    // positioned on the next frame and only then acknowledged — Claude waits
    // for the ack rather than guessing how long a scroll takes.
    function beginShot(id) {
      const entry = pinned.find((p) => p.ann.id === id);
      if (!entry || !entry.el.isConnected) return ack(`shot:${id}:missing`);
      closePanel();
      setPicking(false);
      if (!shotReturn) shotReturn = { x: scrollX, y: scrollY };
      host.classList.add('capturing');
      entry.el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });
      requestAnimationFrame(() => {
        const r = rectOf(entry.el);
        Object.assign(ui.shot.style, {
          left: (r.left - 3) + 'px',
          top: (r.top - 3) + 'px',
          width: (r.width + 6) + 'px',
          height: (r.height + 6) + 'px',
        });
        ui.shotBadge.textContent = `#${id}`;
        ui.shot.hidden = false;
        ack(`shot:${id}:ok`);
      });
    }

    function endShot() {
      ui.shot.hidden = true;
      host.classList.remove('capturing');
      if (shotReturn) {
        scrollTo({ left: shotReturn.x, top: shotReturn.y, behavior: 'instant' });
        shotReturn = null;
      }
      layoutPins();
      ack('shot:end:ok');
    }

    // Prefills the repository (only if the user hasn't set one) and stamps
    // filed issue numbers onto annotations so a later batch skips them.
    function applyConfig(cfg) {
      if (cfg.repo && REPO_RE.test(cfg.repo) && !state.repo) {
        ui.repo.value = cfg.repo;
        setRepo(cfg.repo);
      }
      for (const [id, issue] of Object.entries(cfg.issues || {})) {
        if (!issue || !issue.url) continue;
        const entry = pinned.find((p) => String(p.ann.id) === String(id));
        if (!entry) continue;
        entry.ann.issue = { number: issue.number, url: issue.url };
        entry.pin.className = pinClass(entry.ann);
        entry.pin.title = `Filed as #${issue.number} — click to view the note`;
      }
      // Everything filed => terminal state. Anything left (a partial batch, or
      // notes added while Claude worked) goes back to being an open batch.
      if (state.status === 'sent') state.status = pending().length ? 'annotating' : 'filed';
      writeState();
      syncSend();
      ack('config:ok');
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
    ui.repo.addEventListener('input', () => setRepo(ui.repo.value));
    ui.del.addEventListener('click', deleteNote);
    ui.save.addEventListener('click', saveNote);
    ui.discard.addEventListener('click', closePanel);
    for (const field of [ui.note, ui.title]) {
      field.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) saveNote();
      });
    }

    ui.send.addEventListener('click', () => {
      if (ui.send.disabled) return;
      state.status = 'sent';
      state.page.title = doc.title;
      writeState();
      console.log(`${TAG} filing ${pending().length} annotation(s) into ${state.repo}`);
      setPicking(false);
      closePanel();
      ui.send.textContent = 'Filing…';
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

    syncSend();
    active = { destroy, beginShot, endShot, applyConfig };

    console.log(TAG + ' overlay ready');
    return `${TAG} ready on ${location.href}`;
  }

  function shutdown() {
    if (active) active.destroy(true);
  }

  /* ========================= arming / plumbing ========================= */

  // Every write Claude makes into the page is one of these two attributes;
  // everything else it does is a read. Setting an attribute to its current
  // value still fires a mutation record, and boot() is idempotent, so repeat
  // arms are harmless.
  function applyCommand() {
    const cmd = doc.documentElement.getAttribute(CMD_ATTR);
    if (cmd === 'on') return void boot();
    if (cmd === 'off') return void shutdown();
    if (!cmd || !cmd.startsWith('shot:')) return;
    if (!active) return ack(`${cmd}:no-overlay`);
    const arg = cmd.slice(5);
    if (arg === 'end') return active.endShot();
    const id = Number(arg);
    if (!Number.isInteger(id)) return ack(`${cmd}:bad-id`);
    active.beginShot(id);
  }

  function applyConfigAttr() {
    const raw = doc.documentElement.getAttribute(CFG_ATTR);
    if (!raw) return;
    if (!active) return ack('config:no-overlay');
    let cfg;
    try { cfg = JSON.parse(raw); } catch (_) { return ack('config:parse-error'); }
    active.applyConfig(cfg);
  }

  function start() {
    doc.documentElement.setAttribute(MARK_ATTR, VERSION);
    new MutationObserver((records) => {
      for (const r of records) {
        if (r.attributeName === CMD_ATTR) applyCommand();
        else if (r.attributeName === CFG_ATTR) applyConfigAttr();
      }
    }).observe(doc.documentElement, {
      attributes: true,
      attributeFilter: [CMD_ATTR, CFG_ATTR],
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
