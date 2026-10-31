import { execSync } from 'node:child_process';
import { statSync } from 'node:fs';
import { Marked } from 'marked';
import { markedHighlight } from 'marked-highlight';
import hljs from 'highlight.js/lib/core';
import x86asm from 'highlight.js/lib/languages/x86asm';
import readme from '../../../README.md?raw';

hljs.registerLanguage('x86asm', x86asm);

const marked = new Marked(
	{ gfm: true },
	markedHighlight({
		emptyLangClass: 'hljs',
		langPrefix: 'hljs language-',
		highlight(code, lang) {
			const language = lang === 'nasm' ? 'x86asm' : lang;
			return hljs.getLanguage(language) ? hljs.highlight(code, { language }).value : code;
		}
	})
);

const repo = 'https://github.com/oddurs/fixpoint';
const root = process.cwd() + '/../'; // the build runs in site/

/** the date git last touched a path, or the date of the build */
function touched(path, format = '%cI') {
	try {
		const out = execSync(`git log -1 --format=${format} -- ${path}`, { cwd: root }).toString().trim();
		if (out) return out;
	} catch {}
	return new Date().toISOString();
}

/** sizes the way a 2003 directory listing would print them */
function size(path) {
	const n = statSync(root + path).size;
	return n < 1024 ? `${n}` : n < 1024 * 1024 ? `${Math.round(n / 1024)}K` : `${(n / 1024 / 1024).toFixed(1)}M`;
}

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
				.replace(/(^|[\s(\[{—–])"/g, '$1\u201c')
				.replace(/"/g, '\u201d')
				.replace(/(^|[\s(\[{—–])'/g, '$1\u2018')
				.replace(/'/g, '\u2019');
		})
		.join('');
}

const slug = (s) =>
	s
		.toLowerCase()
		.replace(/<[^>]+>/g, '')
		.replace(/&[^;]+;/g, '')
		.replace(/[^a-z0-9]+/g, '-')
		.replace(/^-|-$/g, '');

export function load() {
	// the readme's head becomes the title matter; everything from the first section on is the paper
	const cut = readme.indexOf('\n## ');
	const head = readme.slice(0, cut);
	const body = readme
		.slice(cut + 1)
		// the license is in the footer, and appendix a lists the files
		.replace(/\n## license[\s\S]*$/, '\n')
		.replace(/\n\| file \| what it is \|\n(\|.*\n)+/, '\n')
		// relative links point at files in the repo; images stay relative, the site serves them
		.replace(/(?<!!)\[([^\]]*)\]\((?!https?:|#)([^)]+)\)/g, `[$1](${repo}/blob/main/$2)`);

	const epigraph = head.match(/^\*(.+)\*$/m)[1];
	const abstract = smart(
		marked.parseInline(head.match(/^`fixpoint\.bmp` is .*$/m)[0].replace('the picture above', 'the picture in figure 0'))
	);
	const commands = head.match(/```\n([\s\S]*?)```/)[1];

	// number the sections the way latex would, and give them anchors for the contents
	const toc = [];
	let n = 0,
		m = 0;
	const html = smart(marked.parse(body)).replace(/<h([23])>([\s\S]*?)<\/h\1>/g, (_, level, text) => {
		const id = slug(text);
		const num = level === '2' ? `${++n}` : `${n}.${++m}`;
		if (level === '2') m = 0;
		toc.push({ level: +level, num, id, text });
		return `<h${level} id="${id}"><span class="secnum">${num}</span>${text}</h${level}>`;
	});

	const files = [
		['fixpoint.bmp', 'fixpoint.bmp', 'the image, the disk, the archive'],
		['main.asm', `${repo}/blob/main/main.asm`, 'the program, 130 bytes of it'],
		['stub.asm', `${repo}/blob/main/stub.asm`, 'the bootloader, woven into the palette'],
		['build.py', `${repo}/blob/main/build.py`, 'lays out the file, places the stub'],
		['verify.py', `${repo}/blob/main/verify.py`, 'checks every claim, then boots it'],
		['demo/record.py', `${repo}/blob/main/demo/record.py`, 'records figure 0 under gdb'],
		['demo/figures.py', `${repo}/blob/main/demo/figures.py`, 'draws figure 1 from the file'],
		['docs/anatomy.svg', 'docs/anatomy.svg', 'figure 1'],
		['site/static/demo.mp4', 'demo.mp4', 'figure 0']
	].map(([path, href, what]) => ({
		name: path.replace('site/static/', ''),
		href,
		what,
		date: touched(path, '%cs'),
		size: size(path)
	}));

	const modified = new Date(touched('.'));
	return {
		epigraph: smart(epigraph),
		abstract,
		commands,
		html,
		toc,
		files,
		date: modified.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC' }),
		modified: modified.toUTCString().replace(' GMT', ' UTC'),
		video: size('site/static/demo.mp4'),
		bmp: statSync(root + 'fixpoint.bmp').size.toLocaleString('en-US')
	};
}
