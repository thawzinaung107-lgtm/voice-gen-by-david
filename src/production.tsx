import { useEffect, useRef, useState } from 'react';
import { X } from 'lucide-react';
import { authenticateSupabase, logout, getAccount, createTopup, listTopups, uploadEvidence, listAdminTopups, approveTopup, listSessions, revokeSession, revokeOtherSessions, fetchAdminEvidence, isRateLimited } from './services';
import type { Health, UserProfile, Wallet, Topup, SessionInfo, EvidenceBlob } from './services';

// Keeps the triggering button disabled for the server-provided Retry-After window after a 429.
export function useRateLimit() {
  const [until, setUntil] = useState(0);
  useEffect(() => {
    if (until <= Date.now()) return;
    const timer = window.setTimeout(() => setUntil(0), until - Date.now());
    return () => window.clearTimeout(timer);
  }, [until]);
  const capture = (failure: unknown) => { if (isRateLimited(failure)) setUntil(Date.now() + failure.retryAfter * 1000); };
  return { limited: until > Date.now(), capture };
}

export function CustomerWallet({ wallet }: { wallet: Wallet | null }) {
  return <section className="studio-card"><h2>Customer wallet</h2>{wallet ? <dl className="wallet-values"><div><dt>Available credits</dt><dd>{wallet.available ?? 'Unavailable'}</dd></div><div><dt>Reserved credits</dt><dd>{wallet.reserved ?? 'Unavailable'}</dd></div></dl> : <p>Sign in to view your wallet.</p>}</section>;
}

export function ManualTopup({ enabled }: { enabled: boolean }) {
  const [amount, setAmount] = useState('');
  const [reference, setReference] = useState('');
  const [topups, setTopups] = useState<Topup[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const guard = useRef(false);
  const rate = useRateLimit();
  const request = useRef<{payload: string; id: string; topupId?: string}>();
  useEffect(() => { if (enabled) void listTopups().then(setTopups).catch(failure => setError(failure instanceof Error ? failure.message : 'Unable to load top-ups.')); }, [enabled]);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (guard.current) return;
    guard.current = true; setBusy(true); setError(''); setNotice('');
    try {
      if (!Number.isSafeInteger(Number(amount)) || Number(amount) < 1 || !reference.trim()) throw new Error('Enter a positive whole credit amount and payment reference.');
      if (file && (!['image/png', 'image/jpeg', 'application/pdf'].includes(file.type) || file.size > 5 * 1024 * 1024)) throw new Error('Evidence must be PNG, JPEG, or PDF, no larger than 5 MiB.');
      const payload = JSON.stringify({amount: Number(amount), reference: reference.trim()});
      if (request.current?.payload !== payload) request.current = {payload, id: crypto.randomUUID()};
      const current = request.current;
      if (!current.topupId) current.topupId = (await createTopup({request_id: current.id, ...JSON.parse(payload)})).id;
      if (file) await uploadEvidence(current.topupId!, file);
      const records = await listTopups();
      if (!records.some(item => item.id === current.topupId && (!file || !!item.evidence_key))) throw new Error('Submission could not be verified. Retry to check the same request.');
      setTopups(records); setAmount(''); setReference(''); setFile(null); request.current = undefined;
      setNotice('Top-up request received. Credits are added only after independent payment verification.');
    } catch (failure) { rate.capture(failure); setError(failure instanceof Error ? failure.message : 'Top-up submission failed.'); }
    finally { guard.current = false; setBusy(false); }
  };
  if (!enabled) return <section className="studio-card"><h2>Manual top-up</h2><p>Manual payments are not enabled. No payment request was submitted.</p></section>;
  return <section className="studio-card"><h2>Manual top-up</h2><p>Submit your payment reference and optional evidence. Credits remain pending until independently verified.</p>
    <form onSubmit={event => void submit(event)}><label htmlFor="topup-amount">Amount<input id="topup-amount" type="number" min="1" max="10000000" step="1" required value={amount} onChange={event => setAmount(event.target.value)} /></label><label htmlFor="topup-reference">Payment reference<input id="topup-reference" minLength={3} maxLength={200} required value={reference} onChange={event => setReference(event.target.value)} /></label><label htmlFor="topup-evidence">Evidence (PNG, JPEG, or PDF; max 5 MiB)<input id="topup-evidence" type="file" accept="image/png,image/jpeg,application/pdf" onChange={event => setFile(event.target.files?.[0] ?? null)} /></label><button className="select-btn" type="submit" disabled={busy || rate.limited}>{busy ? 'Submitting…' : 'Submit top-up'}</button></form>
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}<ul aria-label="Top-up requests">{topups.map(item => <li key={item.id}>#{item.id} · {item.amount} · {item.status || item.state || 'pending'}{item.evidence_key ? ' · evidence uploaded' : ''}</li>)}</ul>
  </section>;
}

function EvidenceDialog({ item, evidence, onClose }: { item: Topup; evidence: EvidenceBlob; onClose: () => void }) {
  const [url, setUrl] = useState('');
  useEffect(() => {
    const objectUrl = URL.createObjectURL(evidence.blob);
    setUrl(objectUrl);
    return () => { URL.revokeObjectURL(objectUrl); setUrl(''); };
  }, [evidence]);
  return <div className="modal-backdrop" onMouseDown={onClose}><section className="detail-dialog evidence-dialog" role="dialog" aria-modal="true" aria-label={`Payment evidence for ${item.id}`} onMouseDown={event => event.stopPropagation()}>
    <button className="dialog-close" aria-label="Close" onClick={onClose}><X size={19} /></button>
    <div className="detail-dialog__body">
      <p className="evidence-warning" role="alert">Evidence is user-submitted and unverified. Independently confirm payment before approving.</p>
      {evidence.kind === 'image' ? (url ? <img className="evidence-preview" src={url} alt={`Payment evidence submitted for ${item.id}`} /> : <p role="status">Loading evidence…</p>)
        : evidence.kind === 'pdf' ? (url ? <iframe className="evidence-preview evidence-preview--pdf" sandbox="allow-same-origin" title={`Payment evidence submitted for ${item.id}`} src={url} /> : <p role="status">Loading evidence…</p>)
        : <p>This evidence type cannot be previewed. Download it to inspect the file.</p>}
      {url && <a className="select-btn" href={url} download={evidence.filename}>Download evidence</a>}
    </div>
  </section></div>;
}

export function AdminTopups({user}: {user: UserProfile | null}) {
  const [items, setItems] = useState<Topup[]>([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [verification, setVerification] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const guard = useRef(false);
  const rate = useRateLimit();
  const [evidence, setEvidence] = useState<{item: Topup; data: EvidenceBlob} | null>(null);
  const [evidenceBusy, setEvidenceBusy] = useState('');
  const [evidenceError, setEvidenceError] = useState<Record<string, string>>({});
  useEffect(() => { if (user?.isAdmin) void listAdminTopups().then(setItems).catch(failure => setError(failure instanceof Error ? failure.message : 'Unable to load review queue.')); }, [user?.id, user?.isAdmin]);
  if (!user?.isAdmin) return <section className="studio-card"><h2>Administrator access required</h2><p>Sign in with an authorized administrator account.</p></section>;
  const approve = async (item: Topup) => {
    if (guard.current || item.user_id === user.id) return;
    guard.current = true; setBusy(true); setError(''); setNotice('');
    try {
      await approveTopup(item.id, verification[item.id].trim());
      const records = await listAdminTopups(); setItems(records);
      if (!records.some(record => record.id === item.id && (record.status === 'approved' || record.state === 'approved'))) throw new Error('Approval could not be verified. Refresh the queue before retrying.');
      setNotice('Payment approval verified.');
    } catch (failure) { rate.capture(failure); setError(failure instanceof Error ? failure.message : 'Approval failed.'); }
    finally { guard.current = false; setBusy(false); }
  };
  const viewEvidence = async (item: Topup) => {
    if (evidenceBusy) return;
    setEvidenceBusy(item.id); setError('');
    try { setEvidence({item, data: await fetchAdminEvidence(item.id)}); }
    catch (failure) { setEvidenceError(values => ({...values, [item.id]: failure instanceof Error ? failure.message : 'Evidence could not be loaded.'})); }
    finally { setEvidenceBusy(''); }
  };
  return <section className="studio-card"><h2>Payment review</h2><p>Verify the payment independently with your bank or processor. Evidence alone does not confirm a payment. You cannot approve your own request.</p>{error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}{items.map(item => <article className="topup-review" key={item.id}><p>{item.id} · {item.amount} credits · {item.status || item.state}</p>{item.evidence_key && <button type="button" className="select-btn" disabled={evidenceBusy === item.id} onClick={() => void viewEvidence(item)}>{evidenceBusy === item.id ? 'Loading evidence…' : 'View evidence'}</button>}{evidenceError[item.id] && <p role="alert">{evidenceError[item.id]}</p>}{(item.status || item.state) === 'pending' && <><label htmlFor={`verify-${item.id}`}>Independent bank or processor reference<input id={`verify-${item.id}`} minLength={8} maxLength={200} value={verification[item.id] || ''} onChange={event => setVerification(values => ({...values, [item.id]: event.target.value}))} /></label><button className="select-btn" disabled={busy || rate.limited || !item.evidence_key || item.user_id === user.id || (verification[item.id]?.trim().length ?? 0) < 8} onClick={() => void approve(item)}>Approve verified payment</button></>}</article>)}{evidence && <EvidenceDialog item={evidence.item} evidence={evidence.data} onClose={() => setEvidence(null)} />}</section>;
}

export function ActiveSessions({ user }: { user: UserProfile | null }) {
  const [sessions, setSessions] = useState<SessionInfo[] | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState<string | 'others' | ''>('');
  const rate = useRateLimit();
  const load = async () => { try { setSessions(await listSessions()); setError(''); } catch (failure) { setSessions(null); setError(failure instanceof Error ? failure.message : 'Unable to load sessions.'); } };
  useEffect(() => { if (user) void load(); else { setSessions(null); setError(''); setNotice(''); } }, [user?.id]);
  if (!user) return null;
  const revoke = async (id: string) => {
    if (busy) return;
    setBusy(id); setError(''); setNotice('');
    try { await revokeSession(id); setSessions(current => current?.filter(session => session.id !== id) ?? current); setNotice('Session revoked.'); }
    catch (failure) { rate.capture(failure); setError(failure instanceof Error ? failure.message : 'Session could not be revoked.'); }
    finally { setBusy(''); }
  };
  const revokeOthers = async () => {
    if (busy) return;
    setBusy('others'); setError(''); setNotice('');
    try { await revokeOtherSessions(); setSessions(current => current?.filter(session => session.current) ?? current); setNotice('All other sessions revoked.'); }
    catch (failure) { rate.capture(failure); setError(failure instanceof Error ? failure.message : 'Sessions could not be revoked.'); }
    finally { setBusy(''); }
  };
  const others = sessions?.some(session => !session.current) ?? true;
  return <section className="studio-card"><h2>Active sessions</h2>
    <p>Sign out devices you do not recognize. Revoking never ends this session.</p>
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    {sessions === null ? <p>Loading sessions…</p> : sessions.length === 0 ? <p>No active sessions found.</p> : <ul aria-label="Active sessions">{sessions.map(session => <li key={session.id}><span>{session.id}{session.current ? ' · This device' : ''}</span><small>{session.created_at ? `Created ${new Date(session.created_at).toLocaleString()}` : 'Creation time unavailable'}{session.expires_at ? ` · Expires ${new Date(session.expires_at).toLocaleString()}` : ''}</small>{!session.current && <button type="button" className="select-btn" disabled={!!busy || rate.limited} onClick={() => void revoke(session.id)}>{busy === session.id ? 'Revoking…' : 'Revoke'}</button>}</li>)}</ul>}
    <button type="button" className="select-btn" disabled={!!busy || rate.limited || !others} onClick={() => void revokeOthers()}>{busy === 'others' ? 'Revoking…' : 'Revoke all other sessions'}</button>
  </section>;
}

export function ProductionAccount({ health, user, wallet, onAccount, onLogout }: {
  health: Health; user: UserProfile | null; wallet: Wallet | null;
  onAccount: (account: {user: UserProfile; wallet: Wallet}) => void; onLogout: () => void;
}) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [signup, setSignup] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const guard = useRef(false);
  const rate = useRateLimit();
  const configured = health.capabilities?.auth !== false && !!(health.auth?.url || health.auth?.supabase_url) && !!(health.auth?.anonKey || health.auth?.supabase_anon_key);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (guard.current || !configured) return;
    guard.current = true; setBusy(true); setError(''); setNotice('');
    const secret = password; setPassword('');
    try {
      const session = await authenticateSupabase(health, email, secret, signup);
      if (session) onAccount(await getAccount());
      else setNotice('Check your email to confirm your account, then sign in.');
    } catch (failure) { rate.capture(failure); setError(failure instanceof Error ? failure.message : 'Authentication failed.'); }
    finally { guard.current = false; setBusy(false); }
  };
  const signOut = async () => {
    if (guard.current) return;
    guard.current = true; setBusy(true); setError('');
    try { await logout(); onLogout(); }
    catch (failure) { rate.capture(failure); setError(failure instanceof Error ? failure.message : 'Sign out failed.'); }
    finally { guard.current = false; setBusy(false); }
  };
  return <>
    <section className="studio-card production-account"><h2>{user ? 'Signed in' : signup ? 'Create account' : 'Sign in'}</h2>
      {user ? <><p>{user.displayName || user.email || user.id}</p><button className="select-btn" disabled={busy || rate.limited} onClick={() => void signOut()}>Sign out</button></> : configured ? <form onSubmit={event => void submit(event)}>
        <label htmlFor="account-email">Email<input id="account-email" type="email" autoComplete="email" required value={email} onChange={event => setEmail(event.target.value)} disabled={busy} /></label>
        <label htmlFor="account-password">Password<input id="account-password" type="password" autoComplete={signup ? 'new-password' : 'current-password'} minLength={signup ? 8 : undefined} required value={password} onChange={event => setPassword(event.target.value)} disabled={busy} /></label>
        <button type="submit" className="select-btn" disabled={busy || rate.limited}>{busy ? 'Please wait…' : signup ? 'Create account' : 'Sign in'}</button>
        <button type="button" className="select-btn" disabled={busy} onClick={() => { setSignup(!signup); setPassword(''); setError(''); setNotice(''); }}>{signup ? 'Already have an account? Sign in' : 'Create an account'}</button>
      </form> : <p>Account sign-in is not configured. Contact support.</p>}
      {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    </section>
    <CustomerWallet wallet={wallet} />
  </>;
}
