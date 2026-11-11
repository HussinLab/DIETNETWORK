<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { user, loadUser, logout } from '$lib/stores/auth';
	import { goto } from '$app/navigation';
	import { t } from '$lib/i18n';
	import LocaleSwitcher from '$lib/components/LocaleSwitcher.svelte';

	onMount(loadUser);

	async function handleLogout() {
		await logout();
		goto('/login');
	}
</script>

<header>
	<div class="container nav">
		<a href="/" class="brand">🧬 Diet Network Ancestry</a>
		<nav>
			{#if $user}
				<a href="/dashboard">{$t('layout.nav.dashboard')}</a>
				<a href="/upload">{$t('layout.nav.newAnalysis')}</a>
				<button class="btn-secondary" on:click={handleLogout}>{$t('layout.nav.logout')}</button>
			{:else}
				<a href="/login">{$t('layout.nav.login')}</a>
				<a href="/signup" class="btn">{$t('layout.nav.signup')}</a>
			{/if}
			<LocaleSwitcher />
		</nav>
	</div>
</header>

<main class="container">
	<slot />
</main>

<footer class="container">
	<p class="muted">
		{$t('layout.footer.notice')}
		<a href="/privacy">{$t('layout.footer.privacyLink')}</a>.
	</p>
</footer>

<style>
	header {
		border-bottom: 1px solid var(--border);
		background: var(--surface);
	}
	.nav {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 1rem 1.5rem;
	}
	.brand {
		font-weight: 700;
		font-size: 1.1rem;
		color: var(--text);
		text-decoration: none;
	}
	nav {
		display: flex;
		align-items: center;
		gap: 1rem;
	}
	main {
		padding: 2.5rem 1.5rem 4rem;
		min-height: 60vh;
	}
	footer {
		padding: 1.5rem;
		border-top: 1px solid var(--border);
	}
</style>
