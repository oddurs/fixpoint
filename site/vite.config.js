import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

// BASE_PATH is set by the pages workflow ("/fixpoint"); empty for local dev.
export default defineConfig({
	plugins: [
		sveltekit({
			adapter: adapter(),
			paths: { base: process.env.BASE_PATH ?? '' }
		})
	],
	server: { fs: { allow: ['..'] } }
});
