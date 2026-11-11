// Minimal hand-rolled i18n: this app is fully client-rendered (no
// hooks.server.ts/`load` functions -- see src/lib/stores/auth.ts for the
// same pattern), so a plain client-side store is all persistence needs,
// with no SSR locale-detection to wire up. Kept dependency-free rather
// than pulling in a library, matching the rest of this small app.
import { derived, writable } from 'svelte/store';
import { en, type TranslationKey } from './en';
import { fr } from './fr';

export type Locale = 'en' | 'fr';
export const locales: Locale[] = ['en', 'fr'];

const dictionaries: Record<Locale, Record<TranslationKey, string>> = { en, fr };
const STORAGE_KEY = 'dietnet_locale';

function isLocale(value: unknown): value is Locale {
	return value === 'en' || value === 'fr';
}

function detectInitialLocale(): Locale {
	if (typeof window === 'undefined') return 'en';
	try {
		const stored = localStorage.getItem(STORAGE_KEY);
		if (isLocale(stored)) return stored;
	} catch {
		/* localStorage unavailable (private mode, blocked storage, ...) */
	}
	// navigator.language is e.g. "fr-CA" or "fr" -- match on the base tag.
	if (typeof navigator !== 'undefined' && navigator.language?.toLowerCase().startsWith('fr')) return 'fr';
	return 'en';
}

export const locale = writable<Locale>(detectInitialLocale());

locale.subscribe((value) => {
	if (typeof window === 'undefined') return;
	try {
		localStorage.setItem(STORAGE_KEY, value);
	} catch {
		/* ignore -- per-viewer convenience only, not required to persist */
	}
	document.documentElement.lang = value;
});

function interpolate(template: string, vars?: Record<string, string | number>): string {
	if (!vars) return template;
	return template.replace(/\{(\w+)\}/g, (match, key) => {
		const value = vars[key];
		return value === undefined ? match : String(value);
	});
}

// `$t('key')` in a component; `$t('key', { name: 'x' })` for interpolation.
// Falls back to the English string (then the bare key) so a key present in
// en.ts but momentarily missing from fr.ts never renders blank.
export const t = derived(locale, ($locale) => {
	const dict = dictionaries[$locale];
	return (key: TranslationKey, vars?: Record<string, string | number>): string =>
		interpolate(dict[key] ?? en[key] ?? key, vars);
});
