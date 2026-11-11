<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import { goto } from '$app/navigation';
	import SupportLink from '$lib/components/SupportLink.svelte';
	import { t } from '$lib/i18n';

	const MAX_MB = 1024; // combined total across genotype + sample/bim/fam files, not per-file
	const MAX_SAMPLES = 10000; // checked server-side after PLINK conversion -- can't be known client-side for VCF/bgen
	const GENOTYPE_EXTENSIONS = ['.vcf', '.vcf.gz', '.bgen', '.bed'];

	let genotypeFile: File | null = null;
	let sampleFile: File | null = null;
	let bimFile: File | null = null;
	let famFile: File | null = null;
	let consent = false;
	let dragOver = false;
	let submitting = false;
	let error = '';

	$: isBgen = genotypeFile?.name.toLowerCase().endsWith('.bgen') ?? false;
	$: isPlink = genotypeFile?.name.toLowerCase().endsWith('.bed') ?? false;
	// Combined size of every file that will actually be uploaded for this job --
	// mirrors the backend's job-wide cap (see uploads.py's running_total), not
	// just the genotype file's own size.
	$: totalBytes = [genotypeFile, sampleFile, bimFile, famFile].reduce(
		(sum, f) => sum + (f?.size ?? 0),
		0
	);

	function validateGenotypeFile(file: File): string | null {
		const name = file.name.toLowerCase();
		if (!GENOTYPE_EXTENSIONS.some((ext) => name.endsWith(ext))) {
			return $t('upload.errors.unsupportedType');
		}
		return null;
	}

	function handleFiles(files: FileList | null) {
		error = '';
		if (!files || files.length === 0) return;
		// Dropping/selecting a full PLINK set at once (.bed + .bim + .fam)
		// auto-assigns each by extension instead of only looking at the
		// first file, since PLINK uploads need all three.
		const list = Array.from(files);
		const bed = list.find((f) => f.name.toLowerCase().endsWith('.bed'));
		if (bed) {
			const validationError = validateGenotypeFile(bed);
			if (validationError) {
				error = validationError;
				genotypeFile = null;
				return;
			}
			genotypeFile = bed;
			bimFile = list.find((f) => f.name.toLowerCase().endsWith('.bim')) ?? bimFile;
			famFile = list.find((f) => f.name.toLowerCase().endsWith('.fam')) ?? famFile;
			sampleFile = null;
			return;
		}

		const file = list[0];
		const validationError = validateGenotypeFile(file);
		if (validationError) {
			error = validationError;
			genotypeFile = null;
			return;
		}
		genotypeFile = file;
		if (!file.name.toLowerCase().endsWith('.bgen')) sampleFile = null;
		bimFile = null;
		famFile = null;
	}

	function onDrop(e: DragEvent) {
		e.preventDefault();
		dragOver = false;
		handleFiles(e.dataTransfer?.files ?? null);
	}

	async function handleSubmit() {
		error = '';
		if (!genotypeFile) {
			error = $t('upload.errors.chooseFile');
			return;
		}
		if (isBgen && !sampleFile) {
			error = $t('upload.errors.sampleRequired');
			return;
		}
		if (isPlink && (!bimFile || !famFile)) {
			error = $t('upload.errors.bimFamRequired');
			return;
		}
		if (totalBytes > MAX_MB * 1024 * 1024) {
			error = $t('upload.errors.tooLarge', {
				size: (totalBytes / (1024 * 1024)).toFixed(0),
				max: MAX_MB
			});
			return;
		}
		if (!consent) {
			error = $t('upload.errors.consentRequired');
			return;
		}
		submitting = true;
		try {
			const job = await api.upload(
				genotypeFile,
				consent,
				sampleFile ?? undefined,
				bimFile ?? undefined,
				famFile ?? undefined
			);
			goto(`/jobs/${job.id}`);
		} catch (e) {
			error = e instanceof ApiError ? e.message : $t('upload.errors.uploadFailed');
		} finally {
			submitting = false;
		}
	}
</script>

<div class="form-wrap">
	<h1>{$t('upload.title')}</h1>
	<p class="muted">
		{$t('upload.buildNoticePrefix')} <strong>GRCh38</strong>{$t('upload.buildNoticeSuffix')}
	</p>
	<p class="muted">
		{$t('upload.limits.intro')} <strong>{MAX_MB} MB</strong> {$t('upload.limits.combined')}
		<strong>{MAX_SAMPLES.toLocaleString()}</strong>
		{$t('upload.limits.samplesRest')}
	</p>

	<form class="card stack" on:submit|preventDefault={handleSubmit}>
		{#if error}
			<div class="error-banner">{error}</div>
			<SupportLink />
		{/if}

		<div
			class="dropzone"
			class:drag={dragOver}
			role="button"
			tabindex="0"
			on:dragover|preventDefault={() => (dragOver = true)}
			on:dragleave={() => (dragOver = false)}
			on:drop={onDrop}
		>
			{#if genotypeFile}
				<p><strong>{genotypeFile.name}</strong></p>
				<p class="muted">{(genotypeFile.size / (1024 * 1024)).toFixed(1)} MB</p>
			{:else}
				<p>{$t('upload.dropzone.prompt')}</p>
				<p class="muted">{$t('upload.dropzone.or')}</p>
			{/if}
			<label class="btn-secondary file-btn">
				{$t('upload.dropzone.browse')}
				<input
					type="file"
					accept=".vcf,.vcf.gz,.bgen,.bed,.bim,.fam"
					multiple
					on:change={(e) => handleFiles(e.currentTarget.files)}
					hidden
				/>
			</label>
			<p class="muted">{$t('upload.dropzone.maxCombined', { mb: MAX_MB })}</p>
		</div>

		{#if isBgen}
			<div>
				<label for="sample">{$t('upload.bgen.label')}</label>
				<input
					id="sample"
					type="file"
					accept=".sample"
					on:change={(e) => (sampleFile = e.currentTarget.files?.[0] ?? null)}
					required
				/>
				<p class="muted">{$t('upload.bgen.hint')}</p>
			</div>
		{/if}

		{#if isPlink}
			<div>
				<label for="bim">{$t('upload.plink.bimLabel')}</label>
				<input
					id="bim"
					type="file"
					accept=".bim"
					on:change={(e) => (bimFile = e.currentTarget.files?.[0] ?? null)}
					required
				/>
				{#if bimFile}<p class="muted">{bimFile.name}</p>{/if}
			</div>
			<div>
				<label for="fam">{$t('upload.plink.famLabel')}</label>
				<input
					id="fam"
					type="file"
					accept=".fam"
					on:change={(e) => (famFile = e.currentTarget.files?.[0] ?? null)}
					required
				/>
				{#if famFile}<p class="muted">{famFile.name}</p>{/if}
				<p class="muted">{$t('upload.plink.hint')}</p>
			</div>
		{/if}

		<label class="checkbox">
			<input type="checkbox" bind:checked={consent} required />
			<span>
				{$t('upload.consent.prefix')}
				<a href="/privacy">{$t('upload.consent.link')}</a>{$t('upload.consent.suffix')}
			</span>
		</label>

		<button type="submit" disabled={submitting}>
			{submitting ? $t('upload.submitting') : $t('upload.submit')}
		</button>
	</form>
</div>

<style>
	.form-wrap {
		max-width: 560px;
		margin: 0 auto;
	}
	.dropzone {
		border: 2px dashed var(--border);
		border-radius: var(--radius);
		padding: 2rem 1rem;
		text-align: center;
		transition: border-color 0.15s ease, background 0.15s ease;
	}
	/* Genotype filenames are long, unbroken (no spaces) strings -- without
	   this they overflow the card instead of wrapping. */
	.card p {
		overflow-wrap: break-word;
		word-break: break-word;
	}
	.dropzone.drag {
		border-color: var(--primary);
		background: #eff6ff;
	}
	.file-btn {
		display: inline-block;
		margin-top: 0.5rem;
		cursor: pointer;
	}
	.checkbox {
		display: flex;
		align-items: flex-start;
		gap: 0.5rem;
		font-weight: 400;
		font-size: 0.9rem;
	}
	.checkbox input {
		margin-top: 0.2rem;
	}
</style>
