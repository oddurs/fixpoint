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

const repo = 'https://github.com/oddurs/fixpoint/blob/main/';

export function load() {
	const body = readme
		// the readme opens with a link here and a still of the image; the site shows the video instead
		.replace(/^\*\*\[watch it boot[^\n]*\n+/m, '')
		.replace(/^!\[[^\]]*\]\(preview\.png\)\n+/m, '')
		// relative links in the readme point at files in the repo; images stay relative,
		// because the site serves them itself
		.replace(/(?<!!)\[([^\]]*)\]\((?!https?:|#)([^)]+)\)/g, `[$1](${repo}$2)`);
	return { html: marked.parse(body) };
}
