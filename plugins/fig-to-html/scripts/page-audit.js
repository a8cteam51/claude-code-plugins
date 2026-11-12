// Measures a rendered page against the standards a file check cannot see. Run it in the page, at each
// width, with whatever browser tool is to hand: paste the file's text as the script to evaluate. It
// returns an object and changes nothing.
//
//   sidewaysScroll  pixels the document is wider than the window; must be 0
//   smallTargets    links and controls under 44px in either direction
//   closeTargets    pairs of targets under 8px apart
//   smallText       text under 12px, and body text under 16px
//   tightLines      paragraphs with a line height under 1.5
//   headings        the heading outline, to read for order
//   unlabelled      form fields with no label
//   noAlt           images with no alt attribute
//   moving          elements with a running animation that never ends, to check for a pause control
(() => {
	const doc = document;
	const px = (value) => Number.parseFloat(value) || 0;
	const shown = (el) => {
		const style = getComputedStyle(el);
		const box = el.getBoundingClientRect();
		return style.display !== 'none' && style.visibility !== 'hidden' && box.width > 0 && box.height > 0;
	};
	const name = (el) => {
		const text = (el.getAttribute('aria-label') || el.textContent || el.querySelector('img')?.alt || '').trim().replace(/\s+/g, ' ').slice(0, 40);
		return `${el.tagName.toLowerCase()}${el.className && typeof el.className === 'string' ? `.${el.className.split(/\s+/)[0]}` : ''}${text ? ` "${text}"` : ''}`;
	};
	const box = (el) => {
		const r = el.getBoundingClientRect();
		return { x: Math.round(r.left), y: Math.round(r.top + scrollY), w: Math.round(r.width * 10) / 10, h: Math.round(r.height * 10) / 10 };
	};

	// A link inside a sentence is exempt from the target size: its line is its target.
	const inProse = (el) => el.tagName === 'A' && getComputedStyle(el).display === 'inline' && [...el.parentElement.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim().length > 1);
	const targets = [...doc.querySelectorAll('a[href], button, input:not([type=hidden]), select, textarea, summary, [role=button], [tabindex]:not([tabindex="-1"])')].filter((el) => shown(el) && !el.closest('[aria-hidden=true]') && !inProse(el));
	const smallTargets = targets.map((el) => ({ el, b: box(el) })).filter(({ b }) => b.w < 44 || b.h < 44).map(({ el, b }) => ({ what: name(el), ...b }));

	const closeTargets = [];
	const boxes = targets.map((el) => ({ el, r: el.getBoundingClientRect() }));
	for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
		const a = boxes[i].r;
		const b = boxes[j].r;
		if (boxes[i].el.contains(boxes[j].el) || boxes[j].el.contains(boxes[i].el)) continue;
		const gapX = Math.max(a.left - b.right, b.left - a.right);
		const gapY = Math.max(a.top - b.bottom, b.top - a.bottom);
		const gap = Math.max(gapX, gapY);
		if (gap < 8 && Math.min(gapX, gapY) < 0 && closeTargets.length < 40) closeTargets.push({ a: name(boxes[i].el), b: name(boxes[j].el), gap: Math.round(gap * 10) / 10 });
	}

	const smallText = [];
	const tightLines = [];
	const walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_TEXT);
	const seen = new Set();
	for (let node = walker.nextNode(); node; node = walker.nextNode()) {
		const el = node.parentElement;
		if (!node.textContent.trim() || seen.has(el) || !shown(el) || el.closest('script, style, [aria-hidden=true], .visually-hidden')) continue;
		seen.add(el);
		const style = getComputedStyle(el);
		const size = px(style.fontSize);
		const isBody = el.matches('p, li, blockquote, dd, figcaption') && node.textContent.trim().length > 60;
		if (size <= 12 || (isBody && size < 16)) smallText.push({ what: name(el), size });
		if (isBody && style.lineHeight !== 'normal' && px(style.lineHeight) / size < 1.495) tightLines.push({ what: name(el), lineHeight: Math.round((px(style.lineHeight) / size) * 100) / 100 });
	}

	const labelled = (field) => field.labels?.length || field.getAttribute('aria-label') || field.getAttribute('aria-labelledby');
	return {
		width: innerWidth,
		documentHeight: doc.documentElement.scrollHeight,
		sidewaysScroll: Math.max(0, doc.documentElement.scrollWidth - doc.documentElement.clientWidth),
		smallTargets,
		closeTargets,
		smallText,
		tightLines,
		headings: [...doc.querySelectorAll('h1, h2, h3, h4, h5, h6')].filter(shown).map((h) => `${h.tagName.toLowerCase()} ${h.textContent.trim().replace(/\s+/g, ' ').slice(0, 50)}`),
		unlabelled: [...doc.querySelectorAll('input:not([type=hidden]):not([type=submit]):not([type=button]), select, textarea')].filter((f) => shown(f) && !labelled(f)).map(name),
		noAlt: [...doc.images].filter((img) => !img.hasAttribute('alt')).map((img) => img.getAttribute('src')),
		moving: doc.getAnimations().filter((a) => a.playState === 'running' && a.effect?.getComputedTiming().iterations === Infinity).map((a) => name(a.effect.target)),
	};
})();
