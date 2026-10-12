/*
 * AI Canvas preview report. canvas.sh copies this next to every preview page.
 * aiCanvasReport() returns one JSON string describing the page as rendered: structure, overflow,
 * images, targets, and (on theme.html) which hostile theme styles reached the block.
 * Empty lists and zero counts mean nothing was found.
 */
(function () {
  var MARK = 'rgb(255, 0, 170)';

  function words(el) {
    var t = el.getAttribute('aria-label') || el.textContent || el.getAttribute('alt') || '';
    return t.replace(/\s+/g, ' ').trim().slice(0, 32);
  }

  function name(el) {
    var t = words(el);
    return el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (t ? ' "' + t + '"' : '');
  }

  function shown(el) {
    var r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden';
  }

  function hasOwnText(el) {
    for (var n = el.firstChild; n; n = n.nextSibling) {
      if (n.nodeType === 3 && n.nodeValue.trim() !== '') return true;
    }
    return false;
  }

  function list(nodes) { return Array.prototype.slice.call(nodes); }

  function first(items, max) { return items.slice(0, max || 8); }

  function themeLeaks(root) {
    var found = [];
    list(root.querySelectorAll('*')).forEach(function (el) {
      if (el.closest('svg') || !shown(el)) return;
      var control = /^(BUTTON|INPUT|SELECT|TEXTAREA)$/.test(el.tagName);
      if (!control && !hasOwnText(el)) return;
      var cs = getComputedStyle(el);
      var size = parseFloat(cs.fontSize) || 16;
      var why = [];
      if (cs.color === MARK) why.push('color');
      if (cs.fontFamily.indexOf('Courier New') !== -1) why.push('font-family');
      if (cs.fontStyle.indexOf('oblique') === 0) why.push('font-style');
      if (cs.textTransform === 'capitalize') why.push('text-transform');
      if (Math.abs(parseFloat(cs.letterSpacing) / size - 0.37) < 0.02) why.push('letter-spacing');
      if (parseFloat(cs.lineHeight) / size > 2.9) why.push('line-height');
      if (el.tagName === 'A' && cs.textDecorationLine.indexOf('line-through') !== -1) why.push('text-decoration');
      if (control) {
        if (cs.backgroundColor === MARK) why.push('background');
        if (cs.borderTopStyle === 'dashed') why.push('border');
        if (cs.borderTopLeftRadius === '33px') why.push('border-radius');
        if (cs.boxShadow.indexOf(MARK) !== -1) why.push('box-shadow');
      }
      if (why.length) found.push(name(el) + ': ' + why.join(', '));
    });
    return found;
  }

  window.aiCanvasReport = function () {
    var phone = document.getElementById('ai-canvas-phone');
    if (phone) return phone.contentWindow.aiCanvasReport();

    var doc = document.documentElement;
    var root = document.querySelector('[class|="canvas"]');
    var out = { page: location.pathname.split('/').pop() || 'index.html', width: doc.clientWidth };
    if (!root) {
      out.problem = 'no root element whose class starts with canvas-';
      return JSON.stringify(out);
    }

    out.root = root.className.split(' ')[0];
    out.scriptRan = root.classList.contains('is-js');
    out.errors = window.__aiCanvasErrors || [];

    var headings = list(root.querySelectorAll('h1, h2, h3, h4, h5, h6')).filter(shown);
    out.h1 = headings.filter(function (h) { return h.tagName === 'H1'; }).length;
    out.headingLevels = headings.map(function (h) { return h.tagName.charAt(1); }).join('');
    out.headingJumps = [];
    headings.forEach(function (h, i) {
      if (i === 0) return;
      if (Number(h.tagName.charAt(1)) - Number(headings[i - 1].tagName.charAt(1)) > 1) out.headingJumps.push(name(h));
    });
    out.mainElements = document.querySelectorAll('main').length;

    out.overflowX = Math.max(0, doc.scrollWidth - doc.clientWidth);
    out.pastEdge = first(list(root.querySelectorAll('*')).filter(function (el) {
      if (!shown(el)) return false;
      var r = el.getBoundingClientRect();
      return r.right > doc.clientWidth + 1 || -1 > r.left;
    }).map(name), 5);

    var images = list(root.querySelectorAll('img'));
    out.images = images.length;
    out.imagesWithoutAlt = first(images.filter(function (i) { return !i.hasAttribute('alt'); }).map(function (i) { return i.getAttribute('src'); }));
    out.imagesWithoutSize = first(images.filter(function (i) { return !i.hasAttribute('width') || !i.hasAttribute('height'); }).map(function (i) { return i.getAttribute('src'); }));
    out.imagesNotLoaded = first(images.filter(function (i) { return i.complete && i.naturalWidth === 0; }).map(function (i) { return i.getAttribute('src'); }));

    var controls = list(root.querySelectorAll('a[href], button, input:not([type="hidden"]), select, textarea, summary, [role="button"], [role="tab"]')).filter(shown);
    out.smallTargets = first(controls.filter(function (el) {
      if (el.tagName === 'A' && getComputedStyle(el).display === 'inline') return false;
      var r = el.getBoundingClientRect();
      return 44 > Math.round(r.width) || 44 > Math.round(r.height);
    }).map(function (el) {
      var r = el.getBoundingClientRect();
      return name(el) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height);
    }));
    out.unnamedControls = first(controls.filter(function (el) {
      if (el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') || el.getAttribute('title')) return false;
      if (/^(INPUT|SELECT|TEXTAREA)$/.test(el.tagName)) return !el.labels || el.labels.length === 0;
      return el.textContent.trim() === '' && !el.querySelector('img[alt]:not([alt=""])');
    }).map(name));

    out.smallText = first(list(root.querySelectorAll('*')).filter(function (el) {
      return !el.closest('svg') && shown(el) && hasOwnText(el) && 12.5 > parseFloat(getComputedStyle(el).fontSize);
    }).map(function (el) { return name(el) + ' ' + getComputedStyle(el).fontSize; }), 5);

    var seen = {};
    out.duplicateIds = [];
    list(root.querySelectorAll('[id]')).forEach(function (el) {
      if (seen[el.id] && out.duplicateIds.indexOf(el.id) === -1) out.duplicateIds.push(el.id);
      seen[el.id] = true;
    });

    if (doc.hasAttribute('data-ai-canvas-theme')) out.themeLeaks = first(themeLeaks(root), 12);
    return JSON.stringify(out);
  };
})();
