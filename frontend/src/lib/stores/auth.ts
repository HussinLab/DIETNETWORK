import { writable } from 'svelte/store';
import { api, type User, ApiError } from '$lib/api';

export const user = writable<User | null>(null);
export const authLoading = writable(true);

export async function loadUser() {
	authLoading.set(true);
	try {
		user.set(await api.me());
	} catch (e) {
		if (!(e instanceof ApiError) || e.status !== 401) console.error(e);
		user.set(null);
	} finally {
		authLoading.set(false);
	}
}

export async function logout() {
	await api.logout();
	user.set(null);
}
