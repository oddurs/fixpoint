// the page is the readme, rendered at build time. the readme's head (title, tagline,
// intro) is replaced by the post's own; everything from its first section on is the
// body. nothing here runs in the browser: the page ships no javascript.

import { execSync } from 'node:child_process';
import { readFileSync, statSync } from 'node:fs';
import { Marked } from 'marked';
import { markedHighlight } from 'marked-highlight';
import readme from '../../../README.md?raw';

const repo = 'https://github.com/oddurs/fixpoint';
const root = process.cwd() + '/../'; // the build runs in site/

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
				(comment && `<span class="com">${escape(comment)}</span>`) +
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
				.replace(/(^|[\s(\[{—–])"/g, '$1“')
				.replace(/"/g, '”')
				.replace(/(^|[\s(\[{—–])'/g, '$1‘')
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

/** the date git last touched a path (the pages workflow fetches full history) */
function touched(path, format = '%cI') {
	try {
		const out = execSync(`git log -1 --format=${format} -- ${path}`, { cwd: root }).toString().trim();
		if (out) return out;
	} catch {}
	return new Date().toISOString();
}

/** a file's size, the way a 2003 directory listing would print it */
function size(path) {
	const n = statSync(root + path).size;
	return n < 1024 ? `${n}` : n < 1048576 ? `${Math.round(n / 1024)}K` : `${(n / 1048576).toFixed(1)}M`;
}

/** the readme's svg figures, inlined: their own css lights up an instruction's bytes when
    you point at it (see demo/figures.py), and that only works in the page, not in an <img> */
function inline(html) {
	return html.replace(/<p><img src="([^"]+\.svg)" alt="([^"]*)"\s*\/?><\/p>/g, (_, src, alt) => {
		const svg = readFileSync(root + src, 'utf8').trim().replace('<svg ', `<svg aria-label="${alt}" `);
		const full = `<a class="full" href="/${src}">open figure 1 on its own, full size</a>`;
		const point = '<span class="point">point at an instruction or a byte of the path to find the other.</span>';
		return `<p class="figure">${svg}</p>\n<p class="hint">${point}${full}</p>`;
	});
}

export function load() {
	const cut = readme.indexOf('\n## ');
	const head = readme.slice(0, cut);
	const body = readme
		.slice(cut + 1)
		.replace(/\n## license[\s\S]*$/, '\n') // the footer has the license
		.replace(/\n## build\n[\s\S]*?(?=\n## )/, '\n') // how to build it is the repo's business, not the post's
		.replace(/(?<!!)\[([^\]]*)\]\((?!https?:|#)([^)]+)\)/g, `[$1](${repo}/blob/main/$2)`); // repo links

	const html = inline(smart(marked.parse(body))).replace(
		/<h([23])>([\s\S]*?)<\/h\1>/g,
		(_, level, text) => `<h${level} id="${slug(text)}">${text}</h${level}>`
	);

	const files = [
		['fixpoint.bmp', 'fixpoint.bmp', 'the image, the disk, the archive'],
		['main.asm', `${repo}/blob/main/main.asm`, 'the program, 130 bytes of it'],
		['stub.asm', `${repo}/blob/main/stub.asm`, 'the bootloader, woven into the palette'],
		['build.py', `${repo}/blob/main/build.py`, 'lays out the file, places the stub'],
		['verify.py', `${repo}/blob/main/verify.py`, 'checks every claim, then boots it'],
		['demo/record.py', `${repo}/blob/main/demo/record.py`, 'records the video under gdb'],
		['demo/figures.py', `${repo}/blob/main/demo/figures.py`, 'draws figure 1 from the file'],
		['docs/anatomy.svg', 'docs/anatomy.svg', 'figure 1'],
		['site/static/demo.mp4', 'demo.mp4', 'the video']
	].map(([path, href, what]) => ({
		name: path.replace('site/static/', ''),
		href,
		what,
		date: touched(path, '%cs'),
		size: size(path)
	}));

	const modified = new Date(touched('.'));
	return {
		tagline: smart(head.match(/^\*(.+)\*$/m)[1]),
		commands: head.match(/```\n([\s\S]*?)```/)[1].trim().split('\n'),
		html,
		files,
		iso: modified.toISOString(),
		date: modified
			.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC' })
			.toLowerCase(),
		modified: modified.toUTCString().replace('GMT', 'UTC'),
		video: size('site/static/demo.mp4'),
		bmp: statSync(root + 'fixpoint.bmp').size.toLocaleString('en-US')
	};
}
