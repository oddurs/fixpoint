import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		sveltekit({
			adapter: adapter(),
			// BASE_PATH is set by the pages workflow ("/fixpoint"); empty for local dev
			paths: { base: process.env.BASE_PATH ?? '', relative: false }, // absolute, so inlined css finds its fonts
			// the stylesheet is small: inline it, so the first paint needs one request
			inlineStyleThreshold: Infinity
		})
	],
	server: { fs: { allow: ['..'] } }
});
