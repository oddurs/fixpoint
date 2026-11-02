import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		sveltekit({
			adapter: adapter(),
			// served at the root of fixpoint.oddurs.com. absolute paths, so inlined css finds its fonts
			paths: { relative: false },
			// the stylesheet is small: inline it, so the first paint needs one request
			inlineStyleThreshold: Infinity
		})
	],
	server: { fs: { allow: ['..'] } }
});
