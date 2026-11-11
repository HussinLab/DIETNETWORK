<script lang="ts">
	import { user } from '$lib/stores/auth';
	import { t } from '$lib/i18n';
</script>

<div class="hero">
	<h1>{$t('home.title')}</h1>
	<p class="muted">{$t('home.subtitle')}</p>
	<div class="cta">
		{#if $user}
			<a href="/upload" class="btn">{$t('home.cta.start')}</a>
		{:else}
			<a href="/signup" class="btn">{$t('home.cta.createAccount')}</a>
			<a href="/login" class="btn btn-secondary">{$t('home.cta.login')}</a>
		{/if}
	</div>
</div>

<div class="grid">
	<div class="card">
		<h3>{$t('home.feature1.title')}</h3>
		<p class="muted">
			{$t('home.feature1.prefix')}
			<strong>GRCh38</strong>.
		</p>
	</div>
	<div class="card">
		<h3>{$t('home.feature2.title')}</h3>
		<p class="muted">{$t('home.feature2.body')}</p>
	</div>
	<div class="card">
		<h3>{$t('home.feature3.title')}</h3>
		<p class="muted">
			{$t('home.feature3.prefix')} <a href="/privacy">{$t('home.feature3.privacyLink')}</a>.
		</p>
	</div>
</div>

<style>
	.hero {
		max-width: 640px;
		margin-bottom: 2.5rem;
	}
	h1 {
		font-size: 2rem;
		line-height: 1.2;
		margin-bottom: 0.75rem;
	}
	.cta {
		display: flex;
		gap: 0.75rem;
		margin-top: 1.5rem;
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
		gap: 1.25rem;
	}
	.grid h3 {
		margin-top: 0;
	}
</style>
