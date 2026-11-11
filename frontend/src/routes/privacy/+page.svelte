<script lang="ts">
	import { t } from '$lib/i18n';
</script>

<h1>{$t('privacy.title')}</h1>

<div class="stack">
	<div class="card">
		<h3>{$t('privacy.collect.title')}</h3>
		<p class="muted">{$t('privacy.collect.body')}</p>
	</div>
	<div class="card">
		<h3>{$t('privacy.why.title')}</h3>
		<p class="muted">{$t('privacy.why.body')}</p>
	</div>
	<div class="card">
		<h3>{$t('privacy.where.title')}</h3>
		<p class="muted">{$t('privacy.where.body')}</p>
	</div>
	<div class="card">
		<h3>{$t('privacy.retention.title')}</h3>
		<p class="muted">
			{$t('privacy.retention.body1')} <strong>{$t('privacy.retention.days')}</strong>
			{$t('privacy.retention.body2')}
		</p>
	</div>
	<div class="card">
		<h3>{$t('privacy.rights.title')}</h3>
		<p class="muted">{$t('privacy.rights.body')}</p>
	</div>
</div>
