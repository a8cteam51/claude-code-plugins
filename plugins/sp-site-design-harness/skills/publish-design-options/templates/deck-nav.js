/* Presentation navigator for the design-options deck.
 *
 * Floats in the lower right of every page in a published presentation (the index, each option,
 * and the side-by-side page when there is one): previous and next, a "02 / 04" counter, and a
 * Contents panel that jumps to any page. It wears the Automattic deck's colors and type, never an
 * option's, so it looks the same in every presentation.
 *
 * Isolation: everything renders inside a shadow root on an unknown element (<sp-deck-nav>), and
 * the host's own box is pinned with inline !important declarations, so an option's CSS can't
 * restyle the navigator and the navigator's CSS can't reach the option.
 *
 * Filled by /publish-design-options: the SLIDES token below becomes a JSON array of
 * {"href", "title", "group"} objects, hrefs relative to this file. Each page loads it with one tag before
 * </body>, its src relative to that page: <script src="deck-nav.js" defer></script>.
 */
(() => {
  'use strict';
  if (window.top !== window.self) return; // stay out of framed copies
  const me = document.currentScript;
  if (!me || document.querySelector('sp-deck-nav')) return;

  const SLIDES = {{SLIDES}};
  if (!Array.isArray(SLIDES) || SLIDES.length < 2) return;

  /* Match the page we're on. Spacefast serves clean URLs (/01-slug/, /compare) and local files
     keep the extension (01-slug/index.html, compare.html), so compare without either. */
  const norm = u => {
    const url = new URL(u, me.src);
    return (url.origin + url.pathname).replace(/\/index\.html$/i, '/').replace(/\.html$/i, '').replace(/\/$/, '');
  };
  const here = norm(location.href);
  const slides = SLIDES.map(s => ({...s, url: new URL(s.href, me.src).href}));
  let n = slides.findIndex(s => norm(s.url) === here);
  if (n < 0) n = 0;

  const pad = i => String(i).padStart(2, '0');
  const esc = s => String(s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const icon = d => `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="${d}"/></svg>`;
  const last = pad(slides.length - 1);

  const CSS = `
    :host{all:initial}
    *,*::before,*::after{box-sizing:border-box}
    .nav{
      --blue:#2e72f5;--ink:#101010;--panel:#1b1b1b;--paper:#fff;--muted:#b5b5b5;
      --line:rgb(255 255 255 / .16);--hover:rgb(255 255 255 / .1);
      --ease:cubic-bezier(.16,1,.3,1);
      position:relative;
      font:500 14px/1.3 -apple-system,BlinkMacSystemFont,"Helvetica Neue","Inter",Helvetica,Arial,sans-serif;
      color:var(--paper);letter-spacing:0;text-transform:none;text-align:left;
      -webkit-font-smoothing:antialiased;
    }
    a,button{font:inherit;color:inherit;margin:0}
    .bar{
      position:relative;display:flex;align-items:center;gap:2px;padding:4px;
      background:var(--ink);border:1px solid var(--line);border-radius:999px;
      box-shadow:0 14px 40px rgb(0 0 0 / .35);overflow:hidden;
    }
    .progress{position:absolute;left:0;top:0;height:3px;background:var(--blue);pointer-events:none}
    .btn{
      min-width:44px;height:44px;padding:0 12px;border:0;border-radius:999px;background:none;cursor:pointer;
      display:inline-flex;align-items:center;justify-content:center;gap:8px;text-decoration:none;
    }
    .btn svg{width:18px;height:18px;flex:none;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
    .btn:hover:not([aria-disabled="true"]){background:var(--hover)}
    .btn[aria-disabled="true"]{color:var(--muted);opacity:.5;cursor:default}
    .counter{font-variant-numeric:tabular-nums;font-size:13px;min-width:64px;text-align:center;white-space:nowrap}
    .counter .of{color:var(--muted)}
    .menu{padding:0 14px 0 12px;border-left:1px solid var(--line);border-radius:0 999px 999px 0}
    .menu[aria-expanded="true"]{background:var(--blue)}
    .menu[aria-expanded="true"] .chev{transform:rotate(180deg)}
    :focus{outline:none}
    :focus-visible{outline:3px solid var(--paper);outline-offset:-3px;box-shadow:inset 0 0 0 6px var(--blue)}
    .panel{
      position:absolute;right:0;bottom:calc(100% + 10px);width:min(340px,calc(100vw - 32px));
      max-height:calc(100vh - 120px);overflow:auto;overscroll-behavior:contain;
      background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:8px;
      box-shadow:0 14px 40px rgb(0 0 0 / .35);transform-origin:bottom right;
    }
    .panel[hidden]{display:none}
    .brand{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 12px 8px;color:var(--muted);font-size:11px;font-weight:700;letter-spacing:.18em;text-transform:uppercase}
    .group{margin:0;padding:10px 12px 6px;font-size:11px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;color:var(--muted)}
    .list{list-style:none;margin:0;padding:0}
    .list + .group{border-top:1px solid var(--line);margin-top:6px;padding-top:14px}
    .link{display:flex;gap:12px;align-items:center;min-height:44px;padding:8px 12px;border-radius:10px;text-decoration:none}
    .link:hover{background:var(--hover)}
    .num{font-variant-numeric:tabular-nums;font-size:12px;color:var(--muted);width:20px;flex:none}
    .link[aria-current="page"]{background:var(--blue)}
    .link[aria-current="page"] .num{color:var(--paper)}
    .sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);clip-path:inset(50%);white-space:nowrap}
    @media (prefers-reduced-motion:no-preference){
      .chev{transition:transform .25s var(--ease)}
      .panel{animation:pop .26s var(--ease)}
      @keyframes pop{from{opacity:0;transform:scale(.96) translateY(6px)}}
    }
    @media (max-width:30rem){
      .label{display:none}
      .counter{min-width:54px}
    }
    @media (forced-colors:active){
      .bar,.panel{border:1px solid CanvasText}
      .link[aria-current="page"]{outline:2px solid Highlight}
    }
  `;

  const step = (s, label, d) => s
    ? `<a class="btn" href="${esc(s.url)}" aria-label="${label}: ${esc(s.title)}">${icon(d)}</a>`
    : `<a class="btn" role="link" aria-disabled="true" aria-label="${label}: none">${icon(d)}</a>`;

  let list = '', group = null;
  slides.forEach((s, i) => {
    if (s.group !== group) {
      list += (group !== null ? '</ul>' : '') + (s.group ? `<p class="group">${esc(s.group)}</p>` : '') + '<ul class="list">';
      group = s.group;
    }
    list += `<li><a class="link" href="${esc(s.url)}"${i === n ? ' aria-current="page"' : ''}><span class="num">${pad(i)}</span>${esc(s.title)}</a></li>`;
  });
  list += '</ul>';

  const host = document.createElement('sp-deck-nav');
  /* Pin the host's own box. Inline !important beats anything an option's stylesheet can say. */
  const pin = {
    all: 'initial', display: 'block', position: 'fixed', 'z-index': '2147483000',
    right: 'max(16px, env(safe-area-inset-right))',
    bottom: 'calc(max(16px, env(safe-area-inset-bottom)) + var(--sp-deck-nav-lift, 0px))',
    margin: '0', padding: '0', border: '0', width: 'auto', height: 'auto', transform: 'none', filter: 'none',
    opacity: '1', visibility: 'visible', 'pointer-events': 'auto',
  };
  Object.entries(pin).forEach(([k, v]) => host.style.setProperty(k, v, 'important'));
  const root = host.attachShadow({mode: 'open'});
  root.innerHTML = `<style>${CSS}</style>
    <nav class="nav" aria-label="Presentation">
      <div class="panel" id="panel" hidden>
        <p class="brand">Contents</p>
        ${list}
      </div>
      <div class="bar">
        <span class="progress" style="width:${(n + 1) / slides.length * 100}%"></span>
        ${step(slides[n - 1], 'Previous page', 'M15 18l-6-6 6-6')}
        <span class="counter"><span class="sr">Page </span>${pad(n)} <span class="of"><span aria-hidden="true">/</span><span class="sr"> of </span> ${last}</span></span>
        ${step(slides[n + 1], 'Next page', 'M9 18l6-6-6-6')}
        <button class="btn menu" type="button" aria-expanded="false" aria-controls="panel">
          <span class="label">Contents</span><span class="sr"> of the presentation</span>
          <svg class="chev" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M6 15l6-6 6 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </button>
      </div>
    </nav>`;
  document.body.appendChild(host);

  const panel = root.getElementById('panel');
  const toggle = root.querySelector('.menu');
  const bar = root.querySelector('.bar');
  const setOpen = (open, focusBack) => {
    panel.hidden = !open;
    toggle.setAttribute('aria-expanded', String(open));
    if (open) (panel.querySelector('[aria-current]') || panel.querySelector('a')).focus();
    else if (focusBack) toggle.focus();
  };
  toggle.addEventListener('click', () => setOpen(panel.hidden));
  document.addEventListener('click', e => { if (!panel.hidden && !e.composedPath().includes(host)) setOpen(false); });
  root.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !panel.hidden) { e.stopPropagation(); setOpen(false, true); return; }
    if (panel.hidden || !['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(e.key)) return;
    const links = [...panel.querySelectorAll('a')];
    let i = links.indexOf(root.activeElement);
    i = e.key === 'Home' ? 0 : e.key === 'End' ? links.length - 1 : i + (e.key === 'ArrowDown' ? 1 : -1);
    links[(i + links.length) % links.length].focus();
    e.preventDefault();
  });
  root.addEventListener('focusout', e => { if (!panel.hidden && !root.contains(e.relatedTarget)) setOpen(false); });

  /* Keep clear of the page's own controls. If a button-sized link or button sits under the bar
     (a sticky "Book now", carousel arrows), lift the navigator just above it rather than cover it.
     Big focusable regions, like a scrolling window, aren't controls to dodge. */
  const CONTROL = 'a[href],button,input,select,textarea,[role="button"],[tabindex]:not([tabindex="-1"])';
  let raf = 0;
  function avoid(){
    raf = 0;
    host.style.setProperty('--sp-deck-nav-lift', '0px');
    const r = bar.getBoundingClientRect();
    let lift = 0;
    const xs = [r.left + 6, r.left + r.width / 2, r.right - 6], ys = [r.top + 6, r.bottom - 6];
    for (const x of xs) for (const y of ys) {
      for (const el of document.elementsFromPoint(x, y)) {
        if (el === host || el === document.body || el === document.documentElement) continue;
        const hit = el.closest(CONTROL);
        if (!hit) continue;
        const h = hit.getBoundingClientRect();
        if (h.height > 160 || h.width > innerWidth / 2) continue;
        lift = Math.max(lift, r.bottom - h.top + 12);
        break;
      }
    }
    if (lift > 0 && lift < innerHeight * .4) host.style.setProperty('--sp-deck-nav-lift', Math.ceil(lift) + 'px');
  }
  const queue = () => { if (!raf) raf = requestAnimationFrame(avoid); };
  addEventListener('scroll', queue, {passive: true});
  addEventListener('resize', queue);
  addEventListener('load', queue);
  if (document.fonts) document.fonts.ready.then(queue);
  queue();

  matchMedia('print').addEventListener?.('change', e => host.style.setProperty('display', e.matches ? 'none' : 'block', 'important'));
})();
