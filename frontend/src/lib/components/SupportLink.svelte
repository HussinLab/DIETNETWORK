<script lang="ts">
	// Shown alongside every user-facing error/rejection -- see the "redirect
	// to GitHub on error" requirement. Falls back to the public repo if the
	// env var isn't set (dev / not yet configured).
	import { env } from '$env/dynamic/public';
	import { t } from '$lib/i18n';

	const GITHUB_ISSUES_URL = env.PUBLIC_GITHUB_ISSUES_URL || 'https://github.com/HussinLab/DIETNETWORK/issues';
</script>

<p class="support-link">
	{$t('support.prefix')} <a href={GITHUB_ISSUES_URL} target="_blank" rel="noreferrer"
		>{$t('support.link')}</a
	>.
</p>

<style>
	.support-link {
		font-size: 0.85rem;
		margin: 0.35rem 0 0;
	}
</style>
