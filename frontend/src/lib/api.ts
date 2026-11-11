// Dynamic (not static) public env: the API base URL differs per deploy
// (dev/local-test/prod) and is only known at container runtime, not at
// `npm run build` time inside the Docker image -- see docker-compose.yml.
import { env } from '$env/dynamic/public';

const PUBLIC_API_BASE_URL = env.PUBLIC_API_BASE_URL;

export class ApiError extends Error {
	status: number;
	constructor(status: number, message: string) {
		super(message);
		this.status = status;
	}
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
	const res = await fetch(`${PUBLIC_API_BASE_URL}${path}`, {
		...options,
		credentials: 'include',
		headers: {
			...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
			...(options.headers ?? {})
		}
	});

	if (!res.ok) {
		let message = `Request failed (${res.status})`;
		try {
			const body = await res.json();
			message = body.detail ?? message;
		} catch {
			/* ignore non-JSON error bodies */
		}
		throw new ApiError(res.status, message);
	}

	if (res.status === 204) return undefined as T;
	return (await res.json()) as T;
}

export interface User {
	id: string;
	email: string;
	is_verified: boolean;
	created_at: string;
}

export interface Job {
	id: string;
	status: 'queued' | 'running' | 'done' | 'failed';
	input_type: 'vcf' | 'bgen';
	snp_overlap_count: number | null;
	snp_overlap_total: number | null;
	is_reliable: boolean | null;
	error_message: string | null;
	created_at: string;
	started_at: string | null;
	completed_at: string | null;
}

export interface JobDetail extends Job {
	predictions: { rows: Record<string, string | number>[] } | null;
	// Only present while status === 'queued' -- 1-based position in the
	// FCFS processing queue (see DEPLOYMENT.md's concurrency cap).
	queue_position: number | null;
}

export const api = {
	signup: (email: string, password: string, captcha_token: string, consent: boolean) =>
		request<User>('/auth/signup', {
			method: 'POST',
			body: JSON.stringify({ email, password, captcha_token, consent })
		}),

	verifyEmail: (token: string) => request<User>(`/auth/verify?token=${encodeURIComponent(token)}`),

	login: (email: string, password: string, captcha_token: string) =>
		request<User>('/auth/login', {
			method: 'POST',
			body: JSON.stringify({ email, password, captcha_token })
		}),

	logout: () => request('/auth/logout', { method: 'POST' }),

	me: () => request<User>('/auth/me'),

	listJobs: () => request<Job[]>('/jobs'),

	getJob: (id: string) => request<JobDetail>(`/jobs/${id}`),

	upload: (
		genotypeFile: File,
		consent: boolean,
		sampleFile?: File,
		bimFile?: File,
		famFile?: File
	) => {
		const form = new FormData();
		form.append('genotype_file', genotypeFile);
		form.append('consent', String(consent));
		if (sampleFile) form.append('sample_file', sampleFile);
		if (bimFile) form.append('bim_file', bimFile);
		if (famFile) form.append('fam_file', famFile);
		return request<Job>('/uploads', { method: 'POST', body: form });
	},

	// Zips everything infer.sh produced (predictions, SNP overlap lists,
	// hdf5 dataset, per-model .npz outputs) -- see README's "Output files".
	downloadUrl: (jobId: string) => `${PUBLIC_API_BASE_URL}/jobs/${jobId}/download`
};
