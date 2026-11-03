// the post's body is site/src/post.md, rendered at build time. it is the page's own
// text, not the readme's: the two say the same thing for different readers and are
// edited separately. nothing here runs in the browser: the page ships no javascript.

import { readFileSync, statSync } from 'node:fs';
import { Marked } from 'marked';
import { markedHighlight } from 'marked-highlight';
import { root, touched } from '../lib/touched.js';
import post from '../post.md?raw';

const PUBLISHED = '2026-10-31'; // the byline's date: the day the page went up, not the last edit

const escape = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

/** nasm the way the listings package sets it: mnemonics bold, labels quiet, comments
    in italic roman, and one span per line so css can number them. */
function nasm(code) {
	return code
		.replace(/\n$/, '')
		.split('\n')
		.map((line) => {
			const at = line.indexOf(';');
			const [src, comment] = at < 0 ? [line, ''] : [line.slice(0, at), line.slice(at)];
			const [, indent, label = '', gap, op = '', rest] = src.match(/^(\s*)(\.?[\w.]+:)?(\s*)([a-z]+\b)?(.*)$/i);
			return (
				'<span class="ln">' +
				escape(indent) +
				(label && `<span class="label">${escape(label)}</span>`) +
				escape(gap) +
				(op && `<b class="op">${op}</b>`) +
				escape(rest) +
				(comment && `<span class="com">${escape(comment).replace(/&amp;/g, '<span class="amp">&amp;</span>')}</span>`) +
				'</span>'
			);
		})
		.join('\n');
}

/** a shell block: comments set like the assembly's */
const shell = (code) =>
	code
		.split('\n')
		.map((line) => escape(line).replace(/(\s#.*)$/, '<span class="com">$1</span>'))
		.join('\n');

const marked = new Marked(
	{ gfm: true },
	markedHighlight({
		langPrefix: 'language-',
		highlight: (code, lang) => (lang === 'nasm' ? nasm(code) : shell(code))
	})
);

/** tex quotes: curly quotes and apostrophes in prose, never inside code */
function smart(html) {
	let code = 0;
	return html
		.split(/(<[^>]+>)/)
		.map((part) => {
			if (part.startsWith('<')) {
				if (/^<(code|pre)\b/.test(part)) code++;
				if (/^<\/(code|pre)>/.test(part)) code--;
				return part;
			}
			if (code) return part;
			return part
				.replace(/&quot;/g, '"')
				.replace(/&#39;/g, "'")
				.replace(/(^|[\s([{—–])"/g, '$1“')
				.replace(/"/g, '”')
				.replace(/(^|[\s([{—–])'/g, '$1‘')
				.replace(/'/g, '’');
		})
		.join('');
}

const slug = (s) =>
	s
		.replace(/<[^>]+>|&[^;]+;/g, '')
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, '-')
		.replace(/^-|-$/g, '');

/** a file's size, the way a 2003 directory listing would print it */
function size(path) {
	const n = statSync(root + path).size;
	return n < 1024 ? `${n}` : n < 1048576 ? `${Math.round(n / 1024)}K` : `${(n / 1048576).toFixed(1)}M`;
}

/** what pointing does in each figure; the css that does it is in the svg (demo/figures.py) */
const hints = {
	'docs/fieldguide.svg': 'point at a name to see where it lives in the picture.',
	'docs/anatomy.svg': 'point at an instruction or a byte of the path to find the other.'
};

/** the post's svg figures, inlined: their own css responds to the pointer, and that only
    works in the page, not in an <img> */
function inline(html) {
	return html.replace(/<p><img src="([^"]+\.svg)" alt="([^"]*)"\s*\/?><\/p>/g, (_, src, alt) => {
		const svg = readFileSync(root + src, 'utf8')
			.trim()
			.replace('<svg ', `<svg aria-label="${alt}" `);
		const figure = alt.match(/^figure \d+/)[0];
		const full = `<a class="full" href="/${src}">open ${figure} on its own, full size</a>`;
		const point = `<span class="point">${hints[src]}</span>`;
		return `<p class="figure">${svg}</p>\n<p class="hint">${point}${full}</p>`;
	});
}

export function load() {
	const html = inline(smart(marked.parse(post))).replace(
		/<h([23])>([\s\S]*?)<\/h\1>/g,
		(_, level, text) => `<h${level} id="${slug(text)}">${text}</h${level}>`
	);

	const modified = new Date(touched('.'));
	return {
		html,
		published: PUBLISHED,
		iso: modified.toISOString(),
		date: new Date(PUBLISHED)
			.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC' })
			.toLowerCase(),
		modified: modified.toUTCString().replace('GMT', 'UTC').toLowerCase(),
		video: size('site/static/demo.mp4'),
		bmp: statSync(root + 'fixpoint.bmp').size.toLocaleString('en-US')
	};
}
