export type TaskState = 'queued' | 'dispatching' | 'uncertain' | 'pending' | 'processing' | 'succeeded' | 'completed' | 'failed' | 'expired';
export interface GenerationRecord { id: string; kind: 'tts' | 'dialogue' | 'srt'; taskId: string; state: TaskState; voiceIds: string[]; audioUrl?: string | null; createdAt: number; error?: string; issue?: string | null }
export interface Wallet { balance?: number | null; available?: number | null; reserved?: number | null }
export interface UserProfile { id: string; email?: string; displayName?: string; isAdmin?: boolean; role?: string; capabilities?: string[] }
export interface VoiceOption { id: string; name: string; provider?: string }
export interface Health { mode?: 'production' | 'staging'; configured?: boolean; ok?: boolean; auth?: { provider?: string; url?: string; anonKey?: string; supabase_url?: string; supabase_anon_key?: string }; capabilities?: { auth?: boolean; manual_topups?: boolean; tts?: boolean; generation?: boolean; dialogue?: boolean; srt?: boolean } }
export interface GenerationInput { request_id: string; kind: 'tts'; text: string; voice_id: string; provider: string; model_id: string; language_code: 'en' | 'my'; voice_settings: Record<string, unknown> }
export class ApiError extends Error { constructor(message: string, public status: number, public retryAfter = 0) { super(message); } }
// Rate-limit notice: views subscribe so any 429 surfaces a toast and cools the triggering button down.
const rateLimitListeners = new Set<(retryAfter: number) => void>();
export function onRateLimit(listener: (retryAfter: number) => void) { rateLimitListeners.add(listener); return () => { rateLimitListeners.delete(listener); }; }
export function reportRateLimit(response: Response) {
  const header = Number(response.headers.get('retry-after'));
  const retryAfter = Number.isFinite(header) && header > 0 ? Math.min(header, 3600) : 5;
  rateLimitListeners.forEach(listener => { try { listener(retryAfter); } catch { /* listener errors must not break the request path */ } });
  return retryAfter;
}
export function isRateLimited(error: unknown): error is ApiError { return error instanceof ApiError && error.status === 429; }
async function call<T>(path: string, opts?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, { ...opts, credentials: 'same-origin', headers: { 'content-type': 'application/json', ...opts?.headers } });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const retryAfter = response.status === 429 ? reportRateLimit(response) : 0;
    throw new ApiError(typeof data?.error === 'string' ? data.error : data?.error?.message || data?.message || (typeof data?.detail === 'string' ? data.detail : '') || `Request failed (HTTP ${response.status})`, response.status, retryAfter);
  }
  if (!data) throw new Error('The server returned an invalid response.');
  return data as T;
}
// Capture and erase access links synchronously, before any request or render.
const accessParams = new URLSearchParams(window.location.hash.slice(1));
let accessToken = accessParams.get('access');
if (accessToken !== null) window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}#/settings`);
let sessionPromise: Promise<unknown> | undefined;
export function establishAccessLink(production = false): Promise<unknown> {
  if (production) { accessToken = null; return Promise.resolve(); }
  if (!sessionPromise) { const token = accessToken; accessToken = null; sessionPromise = token ? login(token).catch(error => { sessionPromise = Promise.resolve(); throw error; }) : Promise.resolve(); }
  return sessionPromise;
}
export function login(token: string) { return call('/session', { method: 'POST', body: JSON.stringify({ token }) }); }
export interface Topup { id: string; amount: number; reference?: string; status?: string; state?: string; evidence_key?: string | null; user_id?: string }
export async function listTopups() { const data = await call<{items?: Topup[]; topups?: Topup[]}>('/topups'); const items = data.items ?? data.topups; if (!Array.isArray(items)) throw new Error('Invalid top-up list response.'); return items; }
export async function createTopup(input: {request_id: string; amount: number; reference: string}) { return (await call<{topup: Topup}>('/topups', {method: 'POST', body: JSON.stringify(input)})).topup; }
export async function listAdminTopups() { return (await call<{items: Topup[]}>('/admin/topups')).items; }
export function approveTopup(id: string, verification_reference: string) { return call(`/admin/topups/${encodeURIComponent(id)}/approve`, {method: 'POST', body: JSON.stringify({verification_reference})}); }
export async function uploadEvidence(id: string, file: File) {
  const response = await fetch(`/api/topups/${encodeURIComponent(id)}/evidence`, {method: 'PUT', credentials: 'same-origin', headers: {'content-type': file.type}, body: file});
  if (!response.ok) { if (response.status === 429) reportRateLimit(response); const data = await response.json().catch(() => null); throw new Error(data?.error?.message || data?.error || data?.detail || `Evidence upload failed (HTTP ${response.status}).`); }
}
export interface SessionInfo { id: string; created_at?: string | null; expires_at?: string | null; current?: boolean }
export async function listSessions() { const data = await call<{items?: SessionInfo[]; sessions?: SessionInfo[]}>('/sessions'); const items = data.items ?? data.sessions; if (!Array.isArray(items)) throw new Error('Invalid session list response.'); return items; }
export function revokeSession(id: string) { return call(`/sessions/${encodeURIComponent(id)}`, {method: 'DELETE'}); }
export function revokeOtherSessions() { return call('/sessions', {method: 'DELETE'}); }
export interface EvidenceBlob { blob: Blob; kind: 'image' | 'pdf' | 'other'; filename: string }
export async function fetchAdminEvidence(id: string): Promise<EvidenceBlob> {
  const response = await fetch(`/api/admin/topups/${encodeURIComponent(id)}/evidence`, {credentials: 'same-origin'});
  if (!response.ok) { if (response.status === 429) reportRateLimit(response); const data = await response.json().catch(() => null); throw new Error(data?.error?.message || data?.error || data?.detail || `Evidence could not be loaded (HTTP ${response.status}).`); }
  const type = (response.headers.get('content-type') ?? '').split(';')[0].trim().toLowerCase();
  const disposition = response.headers.get('content-disposition') ?? '';
  const match = /filename\*?=(?:UTF-8''|")?([^";]+)/i.exec(disposition);
  const filename = match ? decodeURIComponent(match[1].replace(/"$/, '')) : 'evidence';
  const blob = await response.blob();
  const kind = type.startsWith('image/') ? 'image' : type === 'application/pdf' ? 'pdf' : 'other';
  return {blob: blob.type === type ? blob : new Blob([blob], {type}), kind, filename};
}
export async function logout() {
  await call('/session', { method: 'DELETE' });
  try { await getAccount(); } catch (error) { if (error instanceof ApiError && error.status === 401) return; throw error; }
  throw new Error('Sign out could not be verified. Retry.');
}
export async function authenticateSupabase(health: Health, email: string, password: string, signup: boolean): Promise<boolean> {
  const publicUrl = health.auth?.url || health.auth?.supabase_url;
  const publicKey = health.auth?.anonKey || health.auth?.supabase_anon_key;
  if (health.mode !== 'production' || health.capabilities?.auth === false || !publicUrl || !publicKey) throw new Error('Authentication is not configured.');
  const url = new URL(publicUrl);
  if (url.protocol !== 'https:') throw new Error('Authentication requires a secure Supabase URL.');
  const response = await fetch(`${url.origin}/auth/v1/${signup ? 'signup' : 'token?grant_type=password'}`, { method: 'POST', credentials: 'omit', referrerPolicy: 'no-referrer', headers: { apikey: publicKey, 'content-type': 'application/json' }, body: JSON.stringify({ email, password }) });
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(data?.msg || data?.error_description || data?.message || `Authentication failed (HTTP ${response.status}).`);
  if (typeof data?.access_token !== 'string' || !data.access_token) {
    if (signup && data?.user) return false;
    throw new Error('Authentication did not return a session.');
  }
  await call('/session', { method: 'POST', body: JSON.stringify({ access_token: data.access_token }) });
  return true;
}
export function getHealth() { return call<Health>('/health'); }
export function getAccount() { return call<{user: UserProfile; wallet: Wallet}>('/me'); }
export async function listVoices() { return (await call<{voices: VoiceOption[]}>('/voices')).voices; }
export async function submitGeneration(input: GenerationInput) { return (await call<{generation: GenerationRecord}>('/generate', { method: 'POST', body: JSON.stringify(input) })).generation; }
export async function listHistory() { return (await call<{items: GenerationRecord[]}>('/history')).items; }
export async function rePoll(id: string) { const data = await call<{generation?: GenerationRecord} & Partial<GenerationRecord>>(`/history/${encodeURIComponent(id)}`); return data.generation ?? data as GenerationRecord; }
export function audioUrl(id: string) { return `/api/audio/${encodeURIComponent(id)}`; }
export function isProcessing(record: GenerationRecord) { return ['queued', 'dispatching', 'uncertain', 'pending', 'processing'].includes(record.state); }
