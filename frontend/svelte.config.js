import adapter from '@sveltejs/adapter-node';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),
	kit: {
		// Node adapter: builds to a standalone server run in the frontend
		// container behind Caddy (see docker-compose.yml / Caddyfile).
		adapter: adapter()
	}
};

export default config;
