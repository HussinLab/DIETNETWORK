// English strings. Keys are namespaced by route/component so a translator
// can find the surrounding context from the key alone. Where original
// English text had inline markup (a link, a <strong>), the sentence is
// split into separate keys around that element rather than smuggling HTML
// into a translation string -- see the .svelte files for how these compose.
export const en = {
	'layout.nav.dashboard': 'Dashboard',
	'layout.nav.newAnalysis': 'New analysis',
	'layout.nav.logout': 'Log out',
	'layout.nav.login': 'Log in',
	'layout.nav.signup': 'Sign up',
	'layout.footer.notice': 'Research tool — inference only, not a diagnostic or clinical service. See our',
	'layout.footer.privacyLink': 'privacy & data retention policy',

	'home.title': 'Genetic ancestry inference, powered by Diet Network',
	'home.subtitle':
		"Upload your VCF or bgen genotype file and get ancestry predictions from HussinLab's pretrained Diet Network ensemble — 15 models trained on 1000 Genomes, covering 24 populations.",
	'home.cta.start': 'Start a new analysis',
	'home.cta.createAccount': 'Create a free account',
	'home.cta.login': 'Log in',
	'home.feature1.title': 'Bring your own genotypes',
	'home.feature1.prefix': 'Accepts .vcf, .vcf.gz, and .bgen (with a .sample file). Genotypes must be harmonized to',
	'home.feature2.title': 'Async, ensemble inference',
	'home.feature2.body':
		'Each job runs 15 models sequentially — typically a few minutes. Track status live from your dashboard and get an email when results are ready.',
	'home.feature3.title': 'Privacy by design',
	'home.feature3.prefix': 'Raw genotype files are deleted immediately after inference succeeds. All results auto-delete after 30 days. See our',
	'home.feature3.privacyLink': 'privacy policy',

	'auth.email': 'Email',
	'auth.password': 'Password',
	'auth.errorCaptcha': 'Please complete the CAPTCHA challenge.',
	'auth.errorGeneric': 'Something went wrong. Please try again.',

	'login.title': 'Log in',
	'login.submit': 'Log in',
	'login.submitting': 'Logging in…',
	'login.noAccount': "Don't have an account?",
	'login.signupLink': 'Sign up',

	'signup.title': 'Create your account',
	'signup.doneNoticePrefix': 'Check',
	'signup.doneNoticeSuffix':
		'for a verification link. You must verify your email before you can log in or upload data.',
	'signup.passwordHint': 'At least 12 characters, with upper, lower, and a digit.',
	'signup.consentPrefix': 'I consent to the processing of my genetic data as described in the',
	'signup.consentLink': 'privacy policy',
	'signup.consentSuffix': ', including 30-day automatic deletion.',
	'signup.submit': 'Create account',
	'signup.submitting': 'Creating account…',
	'signup.hasAccount': 'Already have an account?',
	'signup.loginLink': 'Log in',

	'verify.missingToken': 'Missing verification token.',
	'verify.checking': 'Verifying your email…',
	'verify.successTitle': 'Email verified 🎉',
	'verify.successPrefix': 'You can now',
	'verify.loginLink': 'log in',
	'verify.successSuffix': 'and start an analysis.',
	'verify.failedTitle': 'Verification failed',
	'verify.failedGeneric': 'Verification failed.',
	'verify.failedHint': 'The link may have expired. Try signing up again to request a new one.',

	'dashboard.title': 'Your analyses',
	'dashboard.newAnalysis': 'New analysis',
	'dashboard.loading': 'Loading…',
	'dashboard.loadError': 'Could not load your jobs. Try refreshing.',
	'dashboard.emptyNotice': "You haven't run an ancestry analysis yet.",
	'dashboard.emptyCta': 'Upload your first genotype file',
	'dashboard.table.job': 'Job',
	'dashboard.table.type': 'Type',
	'dashboard.table.status': 'Status',
	'dashboard.table.overlap': 'SNP overlap',
	'dashboard.table.submitted': 'Submitted',
	'dashboard.table.view': 'View',
	'dashboard.overlapWarningTitle': 'Below reliability threshold',

	'upload.title': 'New ancestry analysis',
	'upload.buildNoticePrefix': 'Genotypes must be harmonized to',
	'upload.buildNoticeSuffix':
		'. The platform cannot re-map genome builds — mismatched builds will show as a very low SNP overlap.',
	'upload.limits.intro': 'Limits:',
	'upload.limits.combined': 'combined upload size and',
	'upload.limits.samplesRest':
		'samples. Data below 1000 overlapping SNPs with the Diet Network reference panel is rejected — consider imputing first. Alleles must be harmonized to the reference panel’s strand/coding; a systematic swap or strand flip is also rejected with an explanation.',
	'upload.dropzone.prompt': 'Drag & drop your .vcf, .vcf.gz, .bgen, or PLINK (.bed/.bim/.fam) files here',
	'upload.dropzone.or': 'or',
	'upload.dropzone.browse': 'Browse files',
	'upload.dropzone.maxCombined': 'Max {mb} MB combined',
	'upload.bgen.label': 'Sample file (.sample)',
	'upload.bgen.hint': 'Required to convert bgen genotypes to PLINK format.',
	'upload.plink.bimLabel': 'Variant file (.bim)',
	'upload.plink.famLabel': 'Sample file (.fam)',
	'upload.plink.hint':
		'PLINK genotypes are used as-is (no conversion needed) but still pass through the same missingness filter as VCF/bgen uploads.',
	'upload.consent.prefix': 'I consent to processing this genetic data for ancestry inference, per the',
	'upload.consent.link': 'privacy policy',
	'upload.consent.suffix':
		'. I understand the raw file is deleted immediately after successful inference, and derived results auto-delete after 30 days.',
	'upload.submit': 'Run ancestry inference',
	'upload.submitting': 'Uploading…',
	'upload.errors.chooseFile': 'Please choose a genotype file.',
	'upload.errors.unsupportedType': 'Unsupported file type. Please upload a .vcf, .vcf.gz, .bgen, or .bed file.',
	'upload.errors.sampleRequired': 'A .sample file is required alongside a .bgen upload.',
	'upload.errors.bimFamRequired': 'A .bim and a .fam file are required alongside a .bed upload.',
	'upload.errors.tooLarge': 'Combined upload size ({size} MB) exceeds the {max} MB limit.',
	'upload.errors.consentRequired': 'You must consent to processing before uploading.',
	'upload.errors.uploadFailed': 'Upload failed. Please try again.',

	'jobDetail.back': '← Back to dashboard',
	'jobDetail.loading': 'Loading…',
	'jobDetail.loadError': 'Could not load this job.',
	'jobDetail.heading': 'Analysis',
	'jobDetail.queued': 'Your job is queued',
	'jobDetail.aheadSingular': 'job ahead of you',
	'jobDetail.aheadPlural': 'jobs ahead of you',
	'jobDetail.queuedEmailNotice': "We'll email you once it starts.",
	'jobDetail.running':
		'Your job is running. The Diet Network ensemble runs 15 models sequentially, so this can take a few minutes.',
	'jobDetail.autoUpdate': 'This page updates automatically.',
	'jobDetail.failedGeneric': 'The job failed.',
	'jobDetail.failedHint':
		'This is usually caused by malformed input or a genome build mismatch. You can start a new analysis from the dashboard.',
	'jobDetail.download': 'Download all output files (.zip)',
	'jobDetail.lowOverlapPrefix': 'Low SNP overlap',
	'jobDetail.lowOverlapBody':
		"Diet Network's authors recommend discarding predictions when overlap with the reference SNP panel is under 1000 SNPs. Treat these results as unreliable — a common cause is a genome build other than GRCh38.",
	'jobDetail.overlapGood': 'SNP overlap with Diet Network reference panel:',

	'support.prefix': 'If this looks wrong,',
	'support.link': 'open an issue on GitHub',

	'status.queued': 'Queued',
	'status.running': 'Running',
	'status.done': 'Done',
	'status.failed': 'Failed',

	'privacy.title': 'Privacy & data retention',
	'privacy.collect.title': 'What we collect',
	'privacy.collect.body':
		'Your account email, and the genotype file (VCF or bgen) you choose to upload for ancestry inference, plus the derived ancestry predictions.',
	'privacy.why.title': 'Why',
	'privacy.why.body':
		'Solely to run the Diet Network ancestry inference model on your behalf and show you the results. We do not use your data for any other purpose, and we do not sell or share it.',
	'privacy.where.title': 'Where it is stored',
	'privacy.where.body':
		'On encrypted storage within Canadian research-cloud infrastructure (Arbutus / Digital Research Alliance of Canada). All processing happens in Canada.',
	'privacy.retention.title': 'Retention',
	'privacy.retention.body1':
		'Your raw uploaded genotype file is deleted immediately once inference completes successfully — it is the most sensitive artifact and is not needed after predictions exist. Derived results (predictions and SNP-overlap counts) are kept for',
	'privacy.retention.days': '30 days',
	'privacy.retention.body2':
		'from upload, then permanently deleted by an automated daily job. You can also request earlier deletion.',
	'privacy.rights.title': 'Your rights',
	'privacy.rights.body':
		"You may only ever access your own uploads and results. Under Quebec's Law 25 and PIPEDA, you may request access to, correction of, or deletion of your personal information at any time by contacting the platform operator.",

	'localeSwitcher.label': 'Change language'
};

export type TranslationKey = keyof typeof en;
