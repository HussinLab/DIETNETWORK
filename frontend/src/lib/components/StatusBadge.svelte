<script lang="ts">
	import { t } from '$lib/i18n';

	export let status: 'queued' | 'running' | 'done' | 'failed';

	const labelKeys = {
		queued: 'status.queued',
		running: 'status.running',
		done: 'status.done',
		failed: 'status.failed'
	} as const;
</script>

<span class="badge {status}">{$t(labelKeys[status])}</span>

<style>
	.badge {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		padding: 0.2rem 0.65rem;
		border-radius: 999px;
		font-size: 0.8rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.02em;
	}
	.queued {
		background: #e5e7eb;
		color: #374151;
	}
	.running {
		background: #dbeafe;
		color: #1d4ed8;
	}
	.done {
		background: #dcfce7;
		color: #15803d;
	}
	.failed {
		background: #fee2e2;
		color: #b91c1c;
	}
</style>
