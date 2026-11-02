import js from '@eslint/js';
import svelte from 'eslint-plugin-svelte';
import globals from 'globals';

export default [
	{ ignores: ['build/', '.svelte-kit/', 'static/'] },
	js.configs.recommended,
	...svelte.configs.recommended,
	// the page renders on node at build time; the svelte files also describe browser markup
	{ languageOptions: { globals: { ...globals.node, ...globals.browser } } },
	// {'\n'} is how a newline gets into the <pre> of commands
	{ rules: { 'svelte/no-useless-mustaches': ['error', { ignoreStringEscape: true }] } }
];
