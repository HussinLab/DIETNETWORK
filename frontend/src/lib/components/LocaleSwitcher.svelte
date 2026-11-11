<script lang="ts">
	import { locale, t } from '$lib/i18n';
</script>

<div class="locale-switcher" role="group" aria-label={$t('localeSwitcher.label')}>
	<button
		type="button"
		class:active={$locale === 'en'}
		aria-pressed={$locale === 'en'}
		on:click={() => locale.set('en')}
	>
		EN
	</button>
	<button
		type="button"
		class:active={$locale === 'fr'}
		aria-pressed={$locale === 'fr'}
		on:click={() => locale.set('fr')}
	>
		FR
	</button>
</div>

<style>
	.locale-switcher {
		display: inline-flex;
		border: 1px solid var(--border);
		border-radius: var(--radius);
		overflow: hidden;
	}
	.locale-switcher button {
		background: none;
		border: none;
		padding: 0.3rem 0.6rem;
		font-size: 0.8rem;
		font-weight: 600;
		color: var(--text-muted);
		cursor: pointer;
	}
	.locale-switcher button.active {
		background: var(--primary);
		color: white;
	}
	.locale-switcher button:not(.active):hover {
		background: var(--surface);
	}
</style>
