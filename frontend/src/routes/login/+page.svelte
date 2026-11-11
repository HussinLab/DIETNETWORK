<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import { user } from '$lib/stores/auth';
	import Turnstile from '$lib/components/Turnstile.svelte';
	import { goto } from '$app/navigation';
	import { t } from '$lib/i18n';

	let email = '';
	let password = '';
	let captchaToken = '';
	let submitting = false;
	let error = '';

	async function handleSubmit() {
		error = '';
		if (!captchaToken) {
			error = $t('auth.errorCaptcha');
			return;
		}
		submitting = true;
		try {
			const loggedInUser = await api.login(email, password, captchaToken);
			user.set(loggedInUser);
			goto('/dashboard');
		} catch (e) {
			error = e instanceof ApiError ? e.message : $t('auth.errorGeneric');
		} finally {
			submitting = false;
		}
	}
</script>

<div class="form-wrap">
	<h1>{$t('login.title')}</h1>

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
				autocomplete="current-password"
			/>
		</div>

		<Turnstile bind:token={captchaToken} />

		<button type="submit" disabled={submitting}
			>{submitting ? $t('login.submitting') : $t('login.submit')}</button
		>

		<p class="muted">{$t('login.noAccount')} <a href="/signup">{$t('login.signupLink')}</a></p>
	</form>
</div>

<style>
	.form-wrap {
		max-width: 420px;
		margin: 0 auto;
	}
</style>
