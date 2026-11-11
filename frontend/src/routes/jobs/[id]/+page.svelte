<script lang="ts">
	import { page } from '$app/stores';
	import { onMount, onDestroy } from 'svelte';
	import { api, type JobDetail, ApiError } from '$lib/api';
	import StatusBadge from '$lib/components/StatusBadge.svelte';
	import SupportLink from '$lib/components/SupportLink.svelte';
	import { t } from '$lib/i18n';

	let job: JobDetail | null = null;
	let error = '';
	let interval: ReturnType<typeof setInterval>;

	async function refresh() {
		try {
			job = await api.getJob($page.params.id);
			error = '';
			if (job.status === 'done' || job.status === 'failed') clearInterval(interval);
		} catch (e) {
			error = e instanceof ApiError ? e.message : $t('jobDetail.loadError');
			clearInterval(interval);
		}
	}

	onMount(() => {
		refresh();
		interval = setInterval(refresh, 4000);
	});
	onDestroy(() => clearInterval(interval));
</script>

<a href="/dashboard" class="muted">{$t('jobDetail.back')}</a>

{#if error}
	<div class="error-banner" style="margin-top:1rem">{error}</div>
	<SupportLink />
{:else if !job}
	<p class="muted">{$t('jobDetail.loading')}</p>
{:else}
	<div class="header-row">
		<h1>{$t('jobDetail.heading')} <code>{job.id.slice(0, 8)}</code></h1>
		<StatusBadge status={job.status} />
	</div>

	{#if job.status === 'queued' || job.status === 'running'}
		<div class="card">
			{#if job.status === 'queued'}
				<p>
					{$t('jobDetail.queued')}{job.queue_position
						? ` (${job.queue_position} ${$t(
								job.queue_position === 1 ? 'jobDetail.aheadSingular' : 'jobDetail.aheadPlural'
						  )})`
						: ''}. {$t('jobDetail.queuedEmailNotice')}
				</p>
			{:else}
				<p>{$t('jobDetail.running')}</p>
			{/if}
			<p class="muted">{$t('jobDetail.autoUpdate')}</p>
		</div>
	{:else if job.status === 'failed'}
		<div class="card">
			<p class="error-banner">{job.error_message ?? $t('jobDetail.failedGeneric')}</p>
			<p class="muted">{$t('jobDetail.failedHint')}</p>
			<SupportLink />
		</div>
	{:else if job.status === 'done'}
		<div class="stack">
			<a class="btn" href={api.downloadUrl(job.id)} target="_blank" rel="noreferrer">
				{$t('jobDetail.download')}
			</a>

			{#if job.is_reliable === false}
				<div class="warn-banner">
					⚠️ <strong
						>{$t('jobDetail.lowOverlapPrefix')} ({job.snp_overlap_count} / {job.snp_overlap_total}).</strong
					>
					{$t('jobDetail.lowOverlapBody')}
				</div>
			{:else}
				<div class="card">
					{$t('jobDetail.overlapGood')} <strong>{job.snp_overlap_count} / {job.snp_overlap_total}</strong> ✅
				</div>
			{/if}
		</div>
	{/if}
{/if}

<style>
	.header-row {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin: 1rem 0 1.5rem;
	}
</style>
