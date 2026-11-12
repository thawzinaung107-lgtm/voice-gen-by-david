export type VoiceId = 'roger' | 'brian' | 'daniel' | 'adam' | 'lily';
export type StudioTool = 'tts' | 'dialogue' | 'srt';

export type Result = {
  id: number;
  voice: string;
  voiceId: VoiceId;
  mode: StudioTool;
  text: string;
  cost: number;
  at: string;
  audioUrl?: string;
  lines?: { text: string; voice: VoiceId }[];
};

const VOICES: { id: VoiceId; name: string }[] = [
  { id: 'roger', name: 'Roger' },
  { id: 'brian', name: 'Brian' },
  { id: 'daniel', name: 'Daniel' },
  { id: 'adam', name: 'Adam' },
  { id: 'lily', name: 'Lily' },
];

export function EmptyState({ children }: { children: string }) {
  return <div className="empty-note">{children}</div>;
}

export function MobileNav({ open, items, onNavigate }: {
  open: boolean;
  items: { id: string; label: string }[];
  onNavigate: (id: string) => void;
}) {
  return <nav id="mobile-nav" className={`mobile-nav glass ${open ? 'open' : ''}`} aria-label="Mobile" hidden={!open}>
    {items.map(item => <a key={item.id} href={`#${item.id}`} onClick={event => { event.preventDefault(); onNavigate(item.id); }}>{item.label}</a>)}
  </nav>;
}

export function DialogueCast({ a, b, setA, setB, labelA, labelB }: {
  a: VoiceId;
  b: VoiceId;
  setA: (id: VoiceId) => void;
  setB: (id: VoiceId) => void;
  labelA: string;
  labelB: string;
}) {
  return <div className="cast">
    {([[labelA, a, setA], [labelB, b, setB]] as const).map(([label, selected, set]) => <div className="cast-row" key={label}>
      <span className="cast-label">{label}</span>
      <div className="voice-chips" role="group" aria-label={label}>
        {VOICES.map(item => <button key={item.id} type="button" className="vchip" aria-pressed={selected === item.id} onClick={() => set(item.id)}>{item.name}</button>)}
      </div>
    </div>)}
  </div>;
}

export function AudioPlayer({ src, label }: { src: string; label: string }) {
  return <audio className="audio-player" controls preload="none" src={src} aria-label={label} />;
}

export function ResultList({ items, empty, listenLabel, srtLabel, copyLabel, downloadLabel, subtitle, onListen, onSrt, onCopy }: {
  items: Result[];
  empty: string;
  listenLabel: string;
  srtLabel: string;
  copyLabel: string;
  downloadLabel: string;
  subtitle: (item: Result) => string;
  onListen: (item: Result) => void;
  onSrt: (item: Result) => void;
  onCopy: (item: Result) => void;
}) {
  if (!items.length) return <EmptyState>{empty}</EmptyState>;
  return <>{items.map(item => <div className="result-item glass" key={item.id}>
    <div className="r-meta">
      <b>{item.voice} · {item.mode === 'tts' ? 'TTS' : item.mode === 'dialogue' ? 'Dialogue' : 'SRT'}</b>
      <span className="r-sub">{subtitle(item)}</span>
      <div className="r-text">{item.text.replace(/\s+/g, ' ').slice(0, 140)}</div>
      {item.audioUrl && <AudioPlayer src={item.audioUrl} label={item.voice} />}
    </div>
    <div className="r-actions">
      {!item.audioUrl && <button type="button" className="mini-btn" onClick={() => onListen(item)}>{listenLabel}</button>}
      {item.audioUrl && <a className="mini-btn" href={item.audioUrl} download={`voicegen-${item.id}.wav`}>{downloadLabel}</a>}
      <button type="button" className="mini-btn" onClick={() => onSrt(item)}>{srtLabel}</button>
      <button type="button" className="mini-btn" onClick={() => onCopy(item)}>{copyLabel}</button>
    </div>
  </div>)}</>;
}
