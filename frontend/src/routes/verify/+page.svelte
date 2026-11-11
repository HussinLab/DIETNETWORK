<script lang="ts">
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import { api, ApiError } from '$lib/api';
	import { t } from '$lib/i18n';

	let status: 'checking' | 'ok' | 'error' = 'checking';
	let message = '';

	onMount(async () => {
		const token = $page.url.searchParams.get('token');
		if (!token) {
			status = 'error';
			message = $t('verify.missingToken');
			return;
		}
		try {
			await api.verifyEmail(token);
			status = 'ok';
		} catch (e) {
			status = 'error';
			message = e instanceof ApiError ? e.message : $t('verify.failedGeneric');
		}
	});
</script>

<div class="form-wrap card">
	{#if status === 'checking'}
		<p>{$t('verify.checking')}</p>
	{:else if status === 'ok'}
		<h2>{$t('verify.successTitle')}</h2>
		<p class="muted">
			{$t('verify.successPrefix')} <a href="/login">{$t('verify.loginLink')}</a>
			{$t('verify.successSuffix')}
		</p>
	{:else}
		<h2>{$t('verify.failedTitle')}</h2>
		<p class="error-banner">{message}</p>
		<p class="muted">{$t('verify.failedHint')}</p>
	{/if}
</div>

<style>
	.form-wrap {
		max-width: 420px;
		margin: 0 auto;
		text-align: center;
	}
</style>
