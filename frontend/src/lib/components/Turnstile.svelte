<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	// Dynamic (not static): see comment in src/lib/api.ts.
	import { env } from '$env/dynamic/public';

	const PUBLIC_TURNSTILE_SITE_KEY = env.PUBLIC_TURNSTILE_SITE_KEY;

	export let token = '';

	let container: HTMLDivElement;
	let widgetId: string | undefined;

	declare global {
		interface Window {
			turnstile?: {
				render: (el: HTMLElement, opts: Record<string, unknown>) => string;
				remove: (id: string) => void;
			};
		}
	}

	function renderWidget() {
		if (!window.turnstile || !container) return;
		widgetId = window.turnstile.render(container, {
			sitekey: PUBLIC_TURNSTILE_SITE_KEY,
			callback: (t: string) => (token = t),
			'expired-callback': () => (token = ''),
			'error-callback': () => (token = '')
		});
	}

	onMount(() => {
		if (window.turnstile) {
			renderWidget();
			return;
		}
		const script = document.createElement('script');
		script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js';
		script.async = true;
		script.defer = true;
		script.onload = renderWidget;
		document.head.appendChild(script);
	});

	onDestroy(() => {
		if (widgetId && window.turnstile) window.turnstile.remove(widgetId);
	});
</script>

<div bind:this={container} class="turnstile"></div>

<style>
	.turnstile {
		margin: 0.75rem 0;
	}
</style>
