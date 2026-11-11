<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import Turnstile from '$lib/components/Turnstile.svelte';
	import { t } from '$lib/i18n';

	let email = '';
	let password = '';
	let consent = false;
	let captchaToken = '';
	let submitting = false;
	let error = '';
	let done = false;

	async function handleSubmit() {
		error = '';
		if (!captchaToken) {
			error = $t('auth.errorCaptcha');
			return;
		}
		submitting = true;
		try {
			await api.signup(email, password, captchaToken, consent);
			done = true;
		} catch (e) {
			error = e instanceof ApiError ? e.message : $t('auth.errorGeneric');
		} finally {
			submitting = false;
		}
	}
</script>

<div class="form-wrap">
	<h1>{$t('signup.title')}</h1>

	{#if done}
		<div class="card">
			<p>{$t('signup.doneNoticePrefix')} <strong>{email}</strong> {$t('signup.doneNoticeSuffix')}</p>
		</div>
	{:else}
		<form class="card stack" on:submit|preventDefault={handleSubmit}>
			{#if error}<div class="error-banner">{error}</div>{/if}

			<div>
				<label for="email">{$t('auth.email')}</label>
				<input id="email" type="email" bind:value={email} required autocomplete="email" />
			</div>

			<div>
				<label for="password">{$t('auth.password')}</label>
				<input
					id="password"
					type="password"
					bind:value={password}
					required
					minlength="12"
					autocomplete="new-password"
				/>
				<p class="muted">{$t('signup.passwordHint')}</p>
			</div>

			<label class="checkbox">
				<input type="checkbox" bind:checked={consent} required />
				<span>
					{$t('signup.consentPrefix')}
					<a href="/privacy">{$t('signup.consentLink')}</a>{$t('signup.consentSuffix')}
				</span>
			</label>

			<Turnstile bind:token={captchaToken} />

			<button type="submit" disabled={submitting}>
				{submitting ? $t('signup.submitting') : $t('signup.submit')}
			</button>

			<p class="muted">{$t('signup.hasAccount')} <a href="/login">{$t('signup.loginLink')}</a></p>
		</form>
	{/if}
</div>

<style>
	.form-wrap {
		max-width: 420px;
		margin: 0 auto;
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
