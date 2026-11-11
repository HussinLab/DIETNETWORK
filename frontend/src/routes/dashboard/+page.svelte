<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { api, type Job } from '$lib/api';
	import StatusBadge from '$lib/components/StatusBadge.svelte';
	import { t } from '$lib/i18n';

	let jobs: Job[] = [];
	let loading = true;
	let error = '';
	let interval: ReturnType<typeof setInterval>;

	async function refresh() {
		try {
			jobs = await api.listJobs();
			error = '';
		} catch {
			error = $t('dashboard.loadError');
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		refresh();
		// Poll while any job is queued/running -- avoids the user having to
		// manually refresh to see a job move to done/failed.
		interval = setInterval(() => {
			if (jobs.some((j) => j.status === 'queued' || j.status === 'running')) refresh();
		}, 5000);
	});

	onDestroy(() => clearInterval(interval));
</script>

<div class="header-row">
	<h1>{$t('dashboard.title')}</h1>
	<a href="/upload" class="btn">{$t('dashboard.newAnalysis')}</a>
</div>

{#if loading}
	<p class="muted">{$t('dashboard.loading')}</p>
{:else if error}
	<div class="error-banner">{error}</div>
{:else if jobs.length === 0}
	<div class="card empty-state">
		<p>{$t('dashboard.emptyNotice')}</p>
		<a href="/upload" class="btn">{$t('dashboard.emptyCta')}</a>
	</div>
{:else}
	<div class="card" style="padding: 0;">
		<table>
			<thead>
				<tr>
					<th>{$t('dashboard.table.job')}</th>
					<th>{$t('dashboard.table.type')}</th>
					<th>{$t('dashboard.table.status')}</th>
					<th>{$t('dashboard.table.overlap')}</th>
					<th>{$t('dashboard.table.submitted')}</th>
					<th></th>
				</tr>
			</thead>
			<tbody>
				{#each jobs as job}
					<tr>
						<td><code>{job.id.slice(0, 8)}</code></td>
						<td>{job.input_type.toUpperCase()}</td>
						<td><StatusBadge status={job.status} /></td>
						<td>
							{#if job.snp_overlap_count !== null}
								{job.snp_overlap_count} / {job.snp_overlap_total}
								{#if job.is_reliable === false}<span title={$t('dashboard.overlapWarningTitle')}
										>⚠️</span
									>{/if}
							{:else}
								—
							{/if}
						</td>
						<td class="muted">{new Date(job.created_at).toLocaleString()}</td>
						<td><a href="/jobs/{job.id}">{$t('dashboard.table.view')}</a></td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
{/if}

<style>
	.header-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 1.5rem;
	}
</style>
