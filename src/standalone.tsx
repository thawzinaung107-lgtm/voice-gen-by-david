import { useEffect, useState } from 'react';
import { audioUrl } from './services';
import type { GenerationRecord, Health, UserProfile, Wallet } from './services';
import { ProductionAccount, CustomerWallet, ManualTopup, AdminTopups, ActiveSessions } from './production';

export const routes = ['home', 'library', 'studio', 'projects', 'history', 'pricing', 'settings', 'admin'] as const;
export type Page = typeof routes[number];
type Locale = 'en' | 'mm';
export const COPY = {
  en: {
    labels: ['Overview', 'Voice Library', 'Voice Studio', 'My Projects', 'History', 'Pricing & Credits', 'Settings', 'Admin'],
    status: 'Services not configured',
    home: 'Prepare your next voice project.', homeHelp: 'Explore browser voice demos and keep a local draft. Sign in in Settings to generate supplier audio. Cloud projects are unavailable.',
    projects: 'No saved projects', projectsHelp: 'Cloud projects need an account and storage connection. Your Studio draft is stored only in this browser.',
    history: 'Generation history unavailable', historyHelp: 'Generation and storage services are not configured. No audio files or generation records have been created.',
    pricing: 'Pricing unavailable', pricingHelp: 'Credit rates, wallet balances and purchases will be available after billing is configured. No rate or balance is estimated here.',
    settings: 'Local preferences', settingsHelp: 'These settings and your Studio draft are saved on this device when browser storage is available. They are not synced. Owner access is managed below.',
    admin: 'Admin access unavailable', adminHelp: 'This owner studio has no administrator management interface.',
    account: 'Account not connected', accountHelp: 'Sign-in is unavailable until authentication is configured.',
    language: 'Interface language', theme: 'Appearance', dark: 'Dark', light: 'Light', openStudio: 'Open Studio', openLibrary: 'Explore voices',
    draft: 'Local Studio draft', noDraft: 'No local script yet.', saved: 'Draft is kept on this device when browser storage is available.',
  },
  mm: {
    labels: ['ပင်မ', 'အသံစာရင်း', 'အသံဖန်တီးခန်း', 'ကျွန်ုပ်၏ ပရောဂျက်များ', 'မှတ်တမ်း', 'ခရက်ဒစ်နှင့် ဈေးနှုန်း', 'ဆက်တင်များ', 'စီမံခန့်ခွဲမှု'],
    status: 'ဝန်ဆောင်မှုများ မချိတ်ဆက်ရသေးပါ',
    home: 'သင့်အသံပရောဂျက်ကို ပြင်ဆင်ပါ။', homeHelp: 'Browser အသံနမူနာကို လေ့လာပြီး စာမူကို ဒီစက်မှာ သိမ်းပါ။ Supplier အသံထုတ်ရန် ဆက်တင်များတွင် အကောင့်ဝင်ပါ။',
    projects: 'သိမ်းထားသော ပရောဂျက် မရှိပါ', projectsHelp: 'Cloud ပရောဂျက်များအတွက် အကောင့်နှင့် Storage ချိတ်ဆက်ရန်လိုသည်။ Studio စာမူကို ဒီ Browser မှာသာ သိမ်းထားပါသည်။',
    history: 'အသံထုတ်လုပ်မှု မှတ်တမ်း မရနိုင်သေးပါ', historyHelp: 'အသံထုတ်လုပ်မှုနှင့် Storage မချိတ်ဆက်ရသေးပါ။ အသံဖိုင် သို့မဟုတ် ထုတ်လုပ်မှုမှတ်တမ်း မဖန်တီးထားပါ။',
    pricing: 'ဈေးနှုန်း မရနိုင်သေးပါ', pricingHelp: 'ငွေပေးချေမှုစနစ် ချိတ်ဆက်ပြီးမှ ခရက်ဒစ်နှုန်း၊ လက်ကျန်နှင့် ဝယ်ယူမှု ရနိုင်ပါမည်။ ခန့်မှန်းနှုန်း သို့မဟုတ် လက်ကျန် မပြထားပါ။',
    settings: 'ဒီစက်အတွက် ဆက်တင်များ', settingsHelp: 'Browser Storage ရနိုင်ပါက ဆက်တင်များနှင့် Studio စာမူကို ဒီစက်မှာ သိမ်းပါသည်။ ဒီစက်တွင်သာ သိမ်းပါသည်။',
    admin: 'စီမံခန့်ခွဲခွင့် မရနိုင်သေးပါ', adminHelp: 'ဒီ Studio တွင် စီမံခန့်ခွဲမှုစနစ် မရှိပါ။',
    account: 'အကောင့် မချိတ်ဆက်ရသေးပါ', accountHelp: 'အကောင့်စနစ် ချိတ်ဆက်ပြီးမှ ဝင်ရောက်နိုင်ပါမည်။',
    language: 'ဘာသာစကား', theme: 'အသွင်အပြင်', dark: 'အမှောင်', light: 'အလင်း', openStudio: 'Studio ဖွင့်ရန်', openLibrary: 'အသံများ လေ့လာရန်',
    draft: 'ဒီစက်ရှိ Studio စာမူ', noDraft: 'စာမူ မရှိသေးပါ။', saved: 'Browser Storage ရနိုင်ပါက စာမူကို ဒီစက်မှာ သိမ်းထားပါသည်။',
  },
};

export function readRoute(): Page {
  const value = window.location.hash.replace(/^#\/?/, '');
  return routes.includes(value as Page) ? value as Page : 'library';
}

export function useLocalSetting<T>(key: string, fallback: T, valid: (value: unknown) => value is T) {
  const [value, setValue] = useState<T>(() => {
    try {
      const stored: unknown = JSON.parse(localStorage.getItem(`voicegen.v2.${key}`) ?? 'null');
      return valid(stored) ? stored : fallback;
    } catch { return fallback; }
  });
  useEffect(() => {
    try { localStorage.setItem(`voicegen.v2.${key}`, JSON.stringify(value)); } catch { /* Storage may be blocked or full. */ }
  }, [key, value]);
  return [value, setValue] as const;
}

export function StandaloneView({ page, locale, navigate, script, lightMode, setLightMode, setLocale, history, wallet, user, serviceReady, error, busy, signIn, refreshHistory, pollRecord, health, onAccount, onLogout }: {
  health: Health | null; onAccount: (account: {user: UserProfile; wallet: Wallet}) => void; onLogout: () => void;
  page: Exclude<Page, 'library' | 'studio'>; locale: Locale; navigate: (page: Page) => void;
  script: string; lightMode: boolean; setLightMode: (value: boolean) => void; setLocale: (value: Locale) => void;
  history: GenerationRecord[]; wallet: Wallet | null; user: UserProfile | null; serviceReady: boolean; error: string; busy: boolean; signIn: (token: string) => Promise<void>; refreshHistory: () => Promise<void>; pollRecord: (id: string) => Promise<void>;
}) {
  const s = COPY[locale];
  const production = health?.mode === 'production';
  const [token, setToken] = useState('');
  const [signingIn, setSigningIn] = useState(false);
  const status = user ? (serviceReady ? 'Supplier available' : 'Supplier unavailable') : 'Sign-in required';
  const stateMM: Record<string,string> = { queued:'တန်းစီ', pending:'စောင့်ဆိုင်း', processing:'လုပ်ဆောင်နေ', succeeded:'ပြီးစီး', completed:'ပြီးစီး', failed:'မအောင်မြင်' };
  const stat = (st: string) => locale === 'mm' ? (stateMM[st] ?? st) : st;
  return <section className="standalone-page" data-page={page}>
    <p className="overline">{status}</p>
    <h1>{page === 'history' ? 'Generation history' : page === 'pricing' ? production ? 'Wallet & top-ups' : 'Supplier credits' : production && page === 'admin' ? 'Payment administration' : s[page]}</h1><p className="standalone-lead">{page === 'history' ? 'Tasks submitted through this app. Refreshing task status does not submit a new generation.' : page === 'pricing' ? production ? 'Your available and reserved credits are provided by your account.' : 'Balance comes from your supplier account. Local purchases and per-generation price estimates are unavailable.' : production && page === 'admin' ? 'Payment review is available only to authorized administrators.' : production && page === 'settings' ? 'Manage your account and local preferences. Your Studio draft stays on this device.' : s[`${page}Help`]}</p>
    {page === 'admin' && production ? <AdminTopups user={user} /> : page === 'settings' ? <div className="standalone-grid">
      <section className="studio-card"><h2>{s.language}</h2><select aria-label={s.language} value={locale} onChange={e => setLocale(e.target.value as Locale)}><option value="en">English</option><option value="mm">မြန်မာ</option></select></section>
      <section className="studio-card"><h2>{s.theme}</h2><select aria-label={s.theme} value={lightMode ? 'light' : 'dark'} onChange={e => setLightMode(e.target.value === 'light')}><option value="dark">{s.dark}</option><option value="light">{s.light}</option></select></section>
      {!health ? <section className="studio-card"><h2>Account connection</h2><p>Waiting for account configuration. Retry the connection if it is unavailable.</p></section> : production ? <><ProductionAccount health={health} user={user} wallet={wallet} onAccount={onAccount} onLogout={onLogout} /><ActiveSessions user={user} /></> : <section className="studio-card"><h2>{user ? 'Signed in' : 'Sign in'}</h2>{user ? <p>{user.displayName || user.email || 'Owner session active'}</p> : <form onSubmit={async event => { event.preventDefault(); if (signingIn || !token.trim()) return; setSigningIn(true); const value = token; setToken(''); try { await signIn(value); } finally { setSigningIn(false); } }}><label>Access token<input type="password" autoComplete="off" value={token} onChange={e => setToken(e.target.value)} aria-label="Access token" /></label><button className="select-btn" disabled={signingIn || !token.trim()} type="submit">{signingIn ? 'Signing in…' : 'Sign in'}</button></form>}<p>Access is kept in a secure session cookie. Tokens are never saved in browser storage.</p>{wallet?.balance != null && <p>Supplier credits: {wallet.balance}</p>}</section>}
    </div> : (page === 'home' || page === 'projects') ? <div className="standalone-grid">
      <section className="studio-card"><h2>{s.draft}</h2><p className="local-draft">{script || s.noDraft}</p><button className="select-btn" onClick={() => navigate('studio')}>{s.openStudio}</button></section>
      <section className="studio-card"><h2>{s.labels[1]}</h2><p>{STRIP_DEMO[locale]}</p><button className="select-btn" onClick={() => navigate('library')}>{s.openLibrary}</button></section>
    </div> : page === 'history' ? <div className="history-list"><button className="select-btn" disabled={!user || busy} onClick={() => void refreshHistory()}>Refresh history</button>
      {history.length === 0 && <div className="no-results"><p>{error ? 'History could not be loaded. Retry above.' : user ? 'No tasks submitted through this app yet.' : 'Sign in to load your tasks.'}</p><button onClick={() => navigate('studio')}>{s.openStudio}</button></div>}
      {history.map(r => <article key={r.id || r.taskId} className="history-item">
        <div className="history-item__head"><span className={`history-state history-state--${r.state}`}>{stat(r.state)}</span><small>{r.createdAt ? new Date(r.createdAt).toLocaleString() : ''}</small></div>
        <div className="history-item__body"><strong>{(r.kind || 'tts').toUpperCase()}</strong><p className="history-item__task">{r.taskId}</p>
          <button className="select-btn" onClick={() => void pollRecord(r.id)}>Check status</button>
          {r.audioUrl && (r.state === 'succeeded' || r.state === 'completed') && <div className="history-audio"><audio aria-label="Generated speech" controls preload="none" src={audioUrl(r.id)} onError={e => { const message = e.currentTarget.parentElement?.querySelector<HTMLElement>('.audio-error'); if (message) message.hidden = false; }} /><a className="select-btn" href={audioUrl(r.id)} download={`voice-${r.id}.mp3`}>{locale === 'mm' ? 'ဒေါင်းလုဒ်' : 'Download'}</a><p className="audio-error" hidden>Audio could not be loaded. Check your session and retry.</p></div>}
          {(r.error || r.issue || r.state === 'uncertain') && <p role="alert" className="history-item__err">{r.error || r.issue || 'Submission status is uncertain. Status checks do not submit again. Keep this draft unchanged when retrying.'}</p>}</div>
      </article>)}
    </div> : page === 'pricing' && production ? <div className="standalone-grid"><CustomerWallet wallet={wallet} /><ManualTopup enabled={!!user && health?.capabilities?.manual_topups === true} /></div> : page === 'pricing' ? <section className="studio-card"><h2>Supplier balance</h2><p>{wallet?.balance != null ? `${wallet.balance} supplier credits` : 'Sign in to view the supplier balance.'}</p></section> : <div className="no-results"><p>{status}</p></div>}
  </section>;
}
const STRIP_DEMO = { en: 'Compare device speech demos. These are not supplier voice samples.', mm: 'စက်၏ အသံနမူနာများကို နှိုင်းယှဉ်ပါ။ Supplier အသံနမူနာများ မဟုတ်ပါ။' };
