import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import '@fontsource/marcellus/latin-400.css';
import './gold.css';
import { GoldDesign } from './design';
import type { Locale } from './types';

const KEY = 'voicegen.v2.locale';

function readLocale(): Locale {
  try {
    const stored: unknown = JSON.parse(localStorage.getItem(KEY) ?? 'null');
    if (stored === 'en' || stored === 'mm') return stored;
  } catch { /* storage blocked */ }
  return 'mm';
}

function App() {
  const [locale, setLocale] = useState<Locale>(readLocale);
  useEffect(() => {
    try { localStorage.setItem(KEY, JSON.stringify(locale)); } catch { /* storage blocked */ }
  }, [locale]);
  return <GoldDesign locale={locale} setLocale={setLocale} />;
}

createRoot(document.getElementById('root')!).render(<App />);
