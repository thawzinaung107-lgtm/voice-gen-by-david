import { useEffect, useRef, useState } from 'react';
import type { Locale } from './types';
import { DialogueCast, MobileNav, ResultList } from './studio-ui';
import type { Result } from './studio-ui';

type VoiceId = 'roger' | 'brian' | 'daniel' | 'adam' | 'lily';
type StudioTool = 'tts' | 'dialogue' | 'srt';

type Voice = {
  id: VoiceId;
  initial: string;
  name: string;
  isNew?: boolean;
  role: Record<Locale, string>;
  desc: Record<Locale, string>;
  tags: string[];
  sample: string;
};

export const DESIGN_VOICES: Voice[] = [
  {
    id: 'roger', initial: 'R', name: 'Roger', isNew: true,
    role: { mm: 'Signature အသံ', en: 'Signature Voice' },
    desc: {
      mm: 'နက်ရှိုင်းပြီး ယုံကြည်စိတ်ချရတဲ့ အမျိုးသား အသံ။ ကြော်ငြာ၊ brand narration နဲ့ ဇာတ်လမ်းပြောပြချက်တွေအတွက် အကောင်းဆုံး ရွေးချယ်မှု ဖြစ်ပါတယ်။',
      en: 'A deep, trustworthy male voice — the top pick for ads, brand narration and long-form storytelling.',
    },
    tags: ['t_narration', 't_ads', 't_trust'],
    sample: 'မင်္ဂလာပါ၊ Voice Gen By David မှ ကြိုဆိုပါတယ်။',
  },
  {
    id: 'brian', initial: 'B', name: 'Brian',
    role: { mm: 'ပြောပြချက် အသံ', en: 'Narration Voice' },
    desc: {
      mm: 'တည်ငြိမ်ပြီး နက်နဲတဲ့ အသံနေအသံထား။ အသံစာအုပ်နဲ့ မှတ်တမ်းရုပ်ရှင် ပြောပြချက်တွေအတွက် အထူး သင့်တော်ပါတယ်။',
      en: 'A calm, resonant tone made for audiobooks and documentary narration.',
    },
    tags: ['t_audiobook', 't_docu'],
    sample: 'ဒီအကြောင်းအရာကို အစအဆုံး သေချာ နားထောင်ကြည့်ပါ။',
  },
  {
    id: 'daniel', initial: 'D', name: 'Daniel',
    role: { mm: 'ဇာတ်လမ်း အသံ', en: 'Storytelling Voice' },
    desc: {
      mm: 'နွေးထွေးပြီး ခံစားမှု ပါဝင်တဲ့ အသံ။ ဇာတ်လမ်းတိုနဲ့ စိတ်လှုပ်ရှားဖွယ် အကြောင်းအရာတွေကို အသက်သွင်းပေးပါတယ်။',
      en: 'A warm, expressive voice that brings stories and emotional content to life.',
    },
    tags: ['t_story', 't_narration'],
    sample: 'တစ်ခါတုန်းက ရွာလေးတစ်ရွာမှာ ဖြစ်ခဲ့တဲ့ အကြောင်းပါ။',
  },
  {
    id: 'adam', initial: 'A', name: 'Adam',
    role: { mm: 'ပရိုမို အသံ', en: 'Promo Voice' },
    desc: {
      mm: 'စွမ်းအင်ပြည့်ပြီး စွဲမက်ဖွယ် အသံ။ ပရိုမိုးရှင်းနဲ့ အရောင်းကြော်ငြာ တိုတိုတွေအတွက် အားကောင်းထိရောက်ပါတယ်။',
      en: 'An energetic, punchy voice built for promotions and short sales ads.',
    },
    tags: ['t_promo', 't_sales'],
    sample: 'အခုပဲ မှာယူလိုက်ပါ၊ အထူး လျှော့ဈေး ရရှိနိုင်ပါတယ်။',
  },
  {
    id: 'lily', initial: 'L', name: 'Lily',
    role: { mm: 'နူးညံ့တဲ့ အသံ', en: 'Soft Voice' },
    desc: {
      mm: 'နူးညံ့ပြီး ကြည်လင်တဲ့ အမျိုးသမီး အသံ။ ရှင်းပြချက် ဗီဒီယိုနဲ့ ဖုန်းအကြောင်းကြား စနစ်တွေအတွက် သင့်တော်ပါတယ်။',
      en: 'A soft, clear female voice, ideal for explainers and phone greeting systems.',
    },
    tags: ['t_soft', 't_narration'],
    sample: 'မင်္ဂလာပါ၊ ကျွန်မတို့ ဌာနမှ ကြိုဆိုပါတယ်။',
  },
];

const I18N = {
  mm: {
    nav_voices: 'အသံများ', nav_studio: 'Studio', nav_pricing: 'ဈေးနှုန်း', nav_try: 'စမ်းသုံးကြည့်ရန်',
    hero_kicker: 'မြန်မာ AI အသံဖန်တီးမှု စတူဒီယို',
    hero_h1a: 'စာသားကို', hero_h1b: 'ရွှေအသံ', hero_h1c: 'အဖြစ် ပြောင်းလိုက်ပါ',
    hero_lede: 'ကြော်ငြာ၊ ဇာတ်လမ်းပြောပြချက်နဲ့ ဗီဒီယိုတွေအတွက် သဘာဝကျပြီး ယုံကြည်စိတ်ချရတဲ့ မြန်မာ AI အသံများ။ Signature အသံ Roger အပါအဝင် အသံ ၅ မျိုးထဲက ရွေးပြီး စက္ကန့်ပိုင်းအတွင်း အသံထွက် ထုတ်လိုက်ပါ။',
    hero_cta1: 'Studio မှာ စမ်းကြည့်ရန်', hero_cta2: 'အသံတွေ နားထောင်ရန်',
    stat_voices: 'အသံ ၅ မျိုး', stat_native: 'မြန်မာ ဘာသာစကား အဓိက', stat_export: 'MP3 + SRT ထုတ်ယူနိုင်သည်',
    player_sub: 'နမူနာ · မြန်မာ ပြောပြချက်',
    lib_title: 'အသံ စာကြည့်တိုက်',
    lib_sub: 'တစ်ခုချင်းစီကို နမူနာ နားထောင်ပြီး သင့်ပရောဂျက်နဲ့ ကိုက်ညီတဲ့ အသံကို ရွေးပါ။ Roger က အခုမှ အသစ် ရောက်ရှိလာတဲ့ Signature အသံ ဖြစ်ပါတယ်။',
    st_title: 'Studio — အသံ ထုတ်လုပ်ရန်', st_sub: 'စာသား ရေးထည့်ပါ၊ အသံ ရွေးပါ၊ ခလုတ်တစ်ချက် နှိပ်လိုက်ရုံပါပဲ။',
    lbl_script: 'စာသား ရေးထည့်ပါ', results_title: 'ထုတ်လုပ်ပြီး အသံများ',
    empty_note: 'ပထမဆုံး အသံတစ်ခုကို ထုတ်လုပ်ကြည့်ပါ — ထုတ်ပြီးသား အသံတွေ ဒီနေရာမှာ ပေါ်လာပါမယ်။',
    lbl_voice: 'အသံ ရွေးချယ်ပါ', lbl_speed: 'အမြန်နှုန်း', lbl_stability: 'တည်ငြိမ်မှု',
    credit_left: 'လက်ကျန် Credit',
    credit_note: 'Starter အခမဲ့ Plan · Shwe Pro သို့ အဆင့်မြှင့်ရင် တစ်လ 50,000 credits ရပါမယ်။',
    how_title: 'အဆင့် ၃ ဆင့်တည်းနဲ့ ပြီးပါတယ်', how_sub: 'အသံသွင်း စတူဒီယို မလို၊ မိုက်ခရိုဖုန်း မလိုပါဘူး။',
    step1_t: 'စာသား ရေးပါ', step1_d: 'ပြောစေချင်တဲ့ စာသားကို Studio ထဲမှာ ရေးထည့်ပါ။ ဝါကျတိုတိုလေးတွေ ခွဲရေးရင် အသံထွက် ပိုသဘာဝကျပါတယ်။',
    step2_t: 'အသံ ရွေးပြီး ချိန်ညှိပါ', step2_d: 'Roger အပါအဝင် အသံ ၅ မျိုးထဲက ရွေးပြီး အမြန်နှုန်းနဲ့ တည်ငြိမ်မှုကို သင့်အလိုကျ ချိန်ညှိပါ။',
    step3_t: 'ထုတ်ယူ သုံးလိုက်ပါ', step3_d: 'အသံဖိုင်ကို ဒေါင်းလုဒ်ယူပြီး ဗီဒီယိုထဲ တန်းထည့်သုံးပါ။ SRT စာတန်းထိုးဖိုင်လည်း တစ်ပါတည်း ထုတ်ယူနိုင်ပါတယ်။',
    pr_title: 'ဈေးနှုန်း အစီအစဉ်များ', pr_sub: 'အခမဲ့ စမ်းသုံးရာကနေ စပြီး လုပ်ငန်းသုံး အတိုင်းအတာထိ ကြီးထွားလာနိုင်ပါတယ်။',
    per_month: '/ လ', per_month2: '/ လ',
    s_f1: 'အသံ ၅ မျိုး အားလုံး သုံးနိုင်သည်', s_f2: 'TTS + SRT ထုတ်ယူနိုင်သည်', s_f3: 'ကိုယ်ပိုင် ပရောဂျက်များအတွက်', s_f4: 'Community အကူအညီ',
    p_f1: 'Starter အစီအစဉ်ရဲ့ အားလုံး အပါအဝင်', p_f2: 'Dialogue mode အပြည့်အစုံ', p_f3: 'စီးပွားဖြစ် သုံးစွဲခွင့် လိုင်စင်', p_f4: 'ဦးစားပေး အကူအညီ',
    e_f1: 'Pro အစီအစဉ်ရဲ့ အားလုံး အပါအဝင်', e_f2: 'အဖွဲ့လိုက် အကောင့် စီမံခန့်ခွဲမှု', e_f3: 'ထုတ်လုပ်မှု ပမာဏ အများဆုံး', e_f4: 'သီးသန့် အကောင့် မန်နေဂျာ',
    plan_popular: 'အကျော်ကြားဆုံး', plan_start_free: 'အခမဲ့ စတင်ရန်', plan_go_pro: 'Pro စတင်ရန်', plan_contact: 'ဆက်သွယ်ရန်',
    cta_t: 'သင့်ရဲ့ ပထမဆုံး ရွှေအသံကို အခုပဲ ဖန်တီးလိုက်ပါ',
    cta_p: 'အကောင့် ဖွင့်စရာ မလိုသေးပါဘူး။ Studio ထဲမှာ စာသားတစ်ကြောင်း ရေးပြီး စမ်းထုတ်ကြည့်လိုက်ပါ။',
    cta_btn: 'Studio ဖွင့်ရန်', store_link: 'AI Tools By David — Digital Store',
    t_narration: 'ပြောပြချက်', t_ads: 'ကြော်ငြာ', t_trust: 'ယုံကြည်စိတ်ချရသော', t_audiobook: 'အသံစာအုပ်',
    t_docu: 'မှတ်တမ်းရုပ်ရှင်', t_story: 'ဇာတ်လမ်း', t_promo: 'ပရိုမို', t_sales: 'အရောင်းကြော်ငြာ', t_soft: 'နူးညံ့ ကြည်လင်',
    use_voice: 'ဒီအသံကို သုံးမယ်', badge_new: 'အသစ်',
    generating: 'ထုတ်လုပ်နေသည်…',
    toast_done: 'ပြီးပါပြီ — အသံ အဆင်သင့် ဖြစ်ပါပြီ။',
    toast_audio: 'အသံ ထုတ်မရပါ။ ထပ်ကြိုးစားပါ။',
    toast_srt_done: 'SRT ဖိုင်ကို ထုတ်ပြီး ဒေါင်းလုဒ် စတင်ပါပြီ။',
    toast_empty: 'အရင် စာသား ရေးထည့်ပါ။',
    toast_credit: 'Credit မလုံလောက်ပါ — Pro plan ကို စဉ်းစားကြည့်ပါ။',
    toast_copied: 'စာသားကို ကူးယူပြီးပါပြီ။',
    toast_selected: ' အသံကို ရွေးထားပါတယ်။',
    btn_listen: 'နားထောင်', btn_playing: 'ဖတ်နေသည်…', btn_srt: 'SRT', btn_copy: 'ကူးယူ', btn_download: 'ဒေါင်းလုဒ်',
    menu_open: 'မီနူး ဖွင့်ရန်', menu_close: 'မီနူး ပိတ်ရန်', speaker_a: 'ပြောသူ A', speaker_b: 'ပြောသူ B',
    est_suffix: 'ခန့်မှန်း', chars_word: 'စာလုံး', credits_word: 'credits',
  },
  en: {
    nav_voices: 'Voices', nav_studio: 'Studio', nav_pricing: 'Pricing', nav_try: 'Try it free',
    hero_kicker: 'Burmese AI Voice Studio',
    hero_h1a: 'Turn your words into a', hero_h1b: ' golden voice', hero_h1c: '',
    hero_lede: 'Natural, trustworthy Burmese AI voices for ads, narration and video. Pick from five voices — including Roger, the new Signature voice — and generate speech in seconds.',
    hero_cta1: 'Try the Studio', hero_cta2: 'Listen to the voices',
    stat_voices: '5 voices', stat_native: 'Burmese-first', stat_export: 'MP3 + SRT export',
    player_sub: 'Sample · Burmese narration',
    lib_title: 'Voice Library',
    lib_sub: 'Preview each voice and pick the one that fits your project. Roger is the newest arrival — our Signature voice.',
    st_title: 'Studio — Generate Audio', st_sub: 'Write your script, choose a voice, and press one button.',
    lbl_script: 'Write your script', results_title: 'Generated Audio',
    empty_note: 'Generate your first clip — finished audio will appear here.',
    lbl_voice: 'Choose a voice', lbl_speed: 'Speed', lbl_stability: 'Stability',
    credit_left: 'Credits remaining',
    credit_note: 'Starter free plan · Upgrade to Shwe Pro for 50,000 credits a month.',
    how_title: 'Done in three steps', how_sub: 'No recording studio. No microphone needed.',
    step1_t: 'Write the script', step1_d: 'Type the words you want spoken into the Studio. Short sentences sound the most natural.',
    step2_t: 'Pick and tune a voice', step2_d: 'Choose from five voices including Roger, then adjust speed and stability to taste.',
    step3_t: 'Export and use it', step3_d: 'Download the audio and drop it straight into your video. SRT subtitles export alongside it.',
    pr_title: 'Pricing plans', pr_sub: 'Start free and grow all the way to production scale.',
    per_month: '/ mo', per_month2: '/ mo',
    s_f1: 'All 5 voices included', s_f2: 'TTS + SRT export', s_f3: 'For personal projects', s_f4: 'Community support',
    p_f1: 'Everything in Starter', p_f2: 'Full Dialogue mode', p_f3: 'Commercial usage licence', p_f4: 'Priority support',
    e_f1: 'Everything in Pro', e_f2: 'Team account management', e_f3: 'Highest generation volume', e_f4: 'Dedicated account manager',
    plan_popular: 'Most popular', plan_start_free: 'Start free', plan_go_pro: 'Go Pro', plan_contact: 'Contact us',
    cta_t: 'Create your first golden voice today',
    cta_p: 'No account needed yet. Write one line in the Studio and generate it.',
    cta_btn: 'Open the Studio', store_link: 'AI Tools By David — Digital Store',
    t_narration: 'Narration', t_ads: 'Ads', t_trust: 'Trusted tone', t_audiobook: 'Audiobook',
    t_docu: 'Documentary', t_story: 'Storytelling', t_promo: 'Promo', t_sales: 'Sales', t_soft: 'Soft & clear',
    use_voice: 'Use this voice', badge_new: 'NEW',
    generating: 'Generating…',
    toast_done: 'Done — your audio is ready.',
    toast_audio: 'Audio could not be generated. Try again.',
    toast_srt_done: 'SRT file generated and downloading.',
    toast_empty: 'Please write some text first.',
    toast_credit: 'Not enough credits — consider the Pro plan.',
    toast_copied: 'Script copied.',
    toast_selected: ' selected.',
    btn_listen: 'Listen', btn_playing: 'Playing…', btn_srt: 'SRT', btn_copy: 'Copy', btn_download: 'Download',
    menu_open: 'Open menu', menu_close: 'Close menu', speaker_a: 'Speaker A', speaker_b: 'Speaker B',
    est_suffix: 'est.', chars_word: 'chars', credits_word: 'credits',
  },
} as const;

type CopyKey = keyof typeof I18N.en;

const MODES: Record<StudioTool, { sample: Record<Locale, string>; placeholder: Record<Locale, string>; hint: Record<Locale, string>; gen: Record<Locale, string> }> = {
  tts: {
    sample: {
      mm: 'မင်္ဂလာပါ။ Voice Gen By David မှ ကြိုဆိုပါတယ်။ မြန်မာ AI အသံ နည်းပညာဖြင့် သင့်ရဲ့ ဗီဒီယိုနဲ့ ကြော်ငြာတွေကို အဆင့်မြင့် အသံသရုပ်ဆောင်မှုနဲ့ ဖန်တီးလိုက်ပါ။',
      en: 'Hello and welcome to Voice Gen By David. Create premium Burmese voiceovers for your videos and ads in seconds.',
    },
    placeholder: { mm: 'ဒီမှာ အသံထွက်စေချင်တဲ့ စာသားကို ရေးထည့်ပါ…', en: 'Type the text you want spoken here…' },
    hint: {
      mm: 'စာလုံးတစ်လုံးချင်းစီကို credit တစ်ခု ကုန်ကျပါတယ်။ ဝါကျအလိုက် ခွဲရေးရင် အသံထွက် ပိုကောင်းပါတယ်။',
      en: 'Each character costs one credit. Splitting text into sentences gives the most natural result.',
    },
    gen: { mm: 'အသံ ထုတ်လုပ်မည်', en: 'Generate Audio' },
  },
  dialogue: {
    sample: {
      mm: 'A: မင်္ဂလာပါ၊ Voice Gen By David မှ ကြိုဆိုပါတယ်။\nB: မင်္ဂလာပါ။ ဒီနေ့ ဘယ်အကြောင်း ဆွေးနွေးကြမလဲ။\nA: မြန်မာ AI အသံတွေ အကြောင်း ပြောကြရအောင်။',
      en: 'A: Hello, welcome to Voice Gen By David.\nB: Hi there. What are we talking about today?\nA: Let\'s talk about Burmese AI voices.',
    },
    placeholder: { mm: 'A: …\nB: …', en: 'A: …\nB: …' },
    hint: {
      mm: 'တစ်ကြောင်းချင်းစီမှာ A: / B: ဖြင့် ပြောသူကို ခွဲရေးပါ။ အသံနှစ်သံ အပြန်အလှန် ပြောဆိုမှုကို ဖန်တီးပေးပါတယ်။',
      en: 'Start each line with A: or B: to mark the speaker. A two-voice conversation is generated.',
    },
    gen: { mm: 'Dialogue ထုတ်လုပ်မည်', en: 'Generate Dialogue' },
  },
  srt: {
    sample: {
      mm: 'မင်္ဂလာပါ။ Voice Gen By David မှ ကြိုဆိုပါတယ်။ မြန်မာ AI အသံ နည်းပညာဖြင့် သင့်ရဲ့ ဗီဒီယိုနဲ့ ကြော်ငြာတွေကို အဆင့်မြင့် အသံသရုပ်ဆောင်မှုနဲ့ ဖန်တီးလိုက်ပါ။',
      en: 'Hello and welcome to Voice Gen By David. Create premium Burmese voiceovers for your videos and ads in seconds.',
    },
    placeholder: { mm: 'စာတန်းထိုး ထုတ်ချင်တဲ့ စာသားကို ရေးထည့်ပါ…', en: 'Type the text you want turned into subtitles…' },
    hint: {
      mm: 'စာသားကို ဝါကျအလိုက် ခွဲပြီး အချိန်ကုဒ်ပါတဲ့ .srt ဖိုင်ကို တန်း၍ ထုတ်ပေးပါတယ်။',
      en: 'Your text is split into sentences and exported as a timed .srt subtitle file.',
    },
    gen: { mm: 'SRT ဖိုင် ထုတ်မည်', en: 'Generate SRT File' },
  },
};

const WAVE = [40, 70, 52, 88, 60, 95, 44, 76, 58, 84, 38, 66];
const CREDITS_TOTAL = 2500;

function chars(value: string) {
  return Array.from(value).length;
}

function fmt(n: number) {
  return n.toLocaleString('en-US');
}

function voiceById(id: VoiceId) {
  return DESIGN_VOICES.find(voice => voice.id === id) ?? DESIGN_VOICES[0];
}

function splitCues(text: string) {
  const lines = text.split(/\n+/).map(line => line.trim()).filter(Boolean);
  const cues: string[] = [];
  for (const line of lines) {
    const parts = line.match(/[^။.!?]+[။.!?]?/g) ?? [line];
    for (const part of parts) {
      const clean = part.replace(/^[AB]\s*[:：]\s*/, '').trim();
      if (clean) cues.push(clean);
    }
  }
  return cues.length ? cues : [text.trim()];
}

function srtTime(sec: number) {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  const ms = Math.round((sec - Math.floor(sec)) * 1000);
  const pad = (n: number, length: number) => String(n).padStart(length, '0');
  return `${pad(h, 2)}:${pad(m, 2)}:${pad(s, 2)},${pad(ms, 3)}`;
}

function buildSRT(text: string, speed: number) {
  const cues = splitCues(text);
  let at = 0;
  const out: string[] = [];
  cues.forEach((cue, index) => {
    const dur = Math.min(8, Math.max(1.4, chars(cue) * 0.16 / speed));
    out.push(String(index + 1), `${srtTime(at)} --> ${srtTime(at + dur)}`, cue, '');
    at += dur + 0.15;
  });
  return out.join('\n');
}

function downloadSRT(text: string, speed: number) {
  const blob = new Blob([buildSRT(text, speed)], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'voicegen-subtitles.srt';
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

function MicIcon() {
  return <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true"><rect x="9" y="2.5" width="6" height="11" rx="3" fill="currentColor" stroke="none" /><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M8.5 21h7" /></svg>;
}

function PlayIcon() {
  return <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true"><path d="M8 5.5v13l11-6.5z" /></svg>;
}

function PauseIcon() {
  return <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true"><rect x="6" y="5" width="4" height="14" rx="1" /><rect x="14" y="5" width="4" height="14" rx="1" /></svg>;
}

function Kanote() {
  return <div className="kanote" aria-hidden="true"><svg width="46" height="26" viewBox="0 0 46 26" fill="none" stroke="var(--gold)" strokeWidth="1.4"><path d="M23 2 L31 13 L23 24 L15 13 Z" /><circle cx="23" cy="13" r="2.6" /><path d="M4 13 h7 M35 13 h7" /><circle cx="4" cy="13" r="1.6" /><circle cx="42" cy="13" r="1.6" /></svg><span className="rule" /></div>;
}
const VOICE_IDS = ['roger', 'brian', 'daniel', 'adam', 'lily'] as const;
function isResult(value: unknown): value is Result {
  if (!value || typeof value !== 'object') return false;
  const item = value as Result;
  return typeof item.id === 'number' && typeof item.text === 'string' && typeof item.voice === 'string' && (item.mode === 'tts' || item.mode === 'dialogue' || item.mode === 'srt') && VOICE_IDS.includes(item.voiceId);
}
function dialogueLines(text: string, a: VoiceId, b: VoiceId) {
  return text.split(/\n+/).map(line => line.trim()).filter(Boolean).map(line => {
    const match = line.match(/^([AB])\s*[:：]\s*(.*)$/);
    if (!match) return { text: line, voice: a };
    return { text: match[2].trim(), voice: match[1] === 'A' ? a : b };
  }).filter(line => line.text);
}

export function GoldDesign({ locale, setLocale }: { locale: Locale; setLocale: (locale: Locale) => void }) {
  const copy = I18N[locale];
  const t = (key: CopyKey) => copy[key];
  const [voice, setVoice] = useState<VoiceId>('roger');
  const [mode, setMode] = useState<StudioTool>('tts');
  const [script, setScript] = useState(MODES.tts.sample.mm);
  const [userEdited, setUserEdited] = useState(false);
  const [credits, setCredits] = useState(CREDITS_TOTAL);
  const [speed, setSpeed] = useState(1);
  const [stability, setStability] = useState(50);
  const [generating, setGenerating] = useState(false);
  const [results, setResults] = useState<Result[]>(() => {
    try {
      const stored: unknown = JSON.parse(localStorage.getItem('voicegen.v2.results') ?? '[]');
      return Array.isArray(stored) ? stored.filter(isResult).slice(0, 20) : [];
    } catch { return []; }
  });
  const [menuOpen, setMenuOpen] = useState(false);
  const [speakerA, setSpeakerA] = useState<VoiceId>('roger');
  const [speakerB, setSpeakerB] = useState<VoiceId>('lily');
  const [playing, setPlaying] = useState<string | null>(null);
  const [toast, setToast] = useState('');
  const toastTimer = useRef<number | undefined>(undefined);
  const playTimer = useRef<number | undefined>(undefined);
  useEffect(() => {
    try { localStorage.setItem('voicegen.v2.results', JSON.stringify(results.map(({ audioUrl: _url, ...item }) => item))); } catch { /* storage blocked */ }
  }, [results]);
  const showToast = (message: string) => {
    setToast(message);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(''), 3200);
  };

  const stopPreview = () => {
    setPlaying(null);
    clearTimeout(playTimer.current);
    try { window.speechSynthesis?.cancel(); } catch { /* unsupported */ }
  };

  const speak = (id: string, text: string) => {
    if (playing === id) { stopPreview(); return; }
    stopPreview();
    setPlaying(id);
    const finish = () => setPlaying(current => current === id ? null : current);
    try {
      if ('speechSynthesis' in window && 'SpeechSynthesisUtterance' in window) {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = locale === 'mm' ? 'my-MM' : 'en-US';
        utterance.rate = speed;
        utterance.onend = finish;
        utterance.onerror = finish;
        window.speechSynthesis.speak(utterance);
      }
    } catch { /* preview is optional */ }
    clearTimeout(playTimer.current);
    playTimer.current = setTimeout(finish, Math.min(10000, Math.max(2800, text.length * 110)));
  };

  useEffect(() => {
    document.documentElement.lang = locale === 'mm' ? 'my' : 'en';
    return () => {
      clearTimeout(toastTimer.current);
      clearTimeout(playTimer.current);
      try { window.speechSynthesis?.cancel(); } catch { /* unsupported */ }
    };
  }, [locale]);

  const applyMode = (next: StudioTool, keepText: boolean) => {
    setMode(next);
    if (!keepText && !userEdited) setScript(MODES[next].sample[locale]);
  };

  const switchLang = (next: Locale) => {
    if (next === locale) return;
    stopPreview();
    if (!userEdited) setScript(MODES[mode].sample[next]);
    document.documentElement.lang = next === 'mm' ? 'my' : 'en';
    setLocale(next);
  };

  const go = (id: string) => { setMenuOpen(false); document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' }); };

  const generate = async () => {
    const text = script.trim();
    if (!text || generating) { if (!text) showToast(t('toast_empty')); return; }
    const cost = chars(text);
    if (cost > credits) { showToast(t('toast_credit')); return; }
    const lines = mode === 'dialogue' ? dialogueLines(text, speakerA, speakerB) : [{ text: text.replace(/^[AB]\s*[:：]\s*/gm, ''), voice }];
    if (!lines.length) { showToast(t('toast_empty')); return; }
    setGenerating(true);
    stopPreview();
    try {
      const response = await fetch(`${import.meta.env.BASE_URL}audio`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ lines, speed, voice }),
      });
      if (!response.ok) throw new Error('audio failed');
      const audioUrl = URL.createObjectURL(await response.blob());
      const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      const item: Result = { id: Date.now(), voice: mode === 'dialogue' ? `${voiceById(speakerA).name} / ${voiceById(speakerB).name}` : voiceById(voice).name, voiceId: voice, mode, text, cost, at: now, audioUrl, lines };
      setCredits(current => current - cost);
      setResults(items => [item, ...items].slice(0, 20));
      if (mode === 'srt') { downloadSRT(text, speed); showToast(t('toast_srt_done')); }
      else showToast(t('toast_done'));
    } catch {
      showToast(t('toast_audio'));
    } finally {
      setGenerating(false);
    }
  };

  const copyText = async (text: string) => {
    try { await navigator.clipboard.writeText(text); } catch { /* clipboard may be blocked */ }
    showToast(t('toast_copied'));
  };

  const count = chars(script);
  const duration = (text: string) => {
    const sec = Math.max(2, Math.round(chars(text) * 0.16 / speed));
    return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`;
  };

  return <div className="gold" lang={locale === 'mm' ? 'my' : 'en'}>
    <header className="nav glass">
      <a className="brand" href="#top" onClick={event => { event.preventDefault(); go('top'); }} aria-label="Voice Gen By David">
        <span className="brand-mark"><MicIcon /></span>
        <span><span className="brand-name">Voice Gen</span><span className="brand-sub">BY DAVID · V2</span></span>
      </a>
      <nav className="links" aria-label="Main">
        <a href="#voices" onClick={event => { event.preventDefault(); go('voices'); }}>{t('nav_voices')}</a>
        <a href="#studio" onClick={event => { event.preventDefault(); go('studio'); }}>{t('nav_studio')}</a>
        <a href="#pricing" onClick={event => { event.preventDefault(); go('pricing'); }}>{t('nav_pricing')}</a>
      </nav>
      <div className="nav-actions">
        <div className="lang-toggle" role="group" aria-label="Language">
          <button type="button" aria-pressed={locale === 'mm'} onClick={() => switchLang('mm')}>မြန်မာ</button>
          <button type="button" aria-pressed={locale === 'en'} onClick={() => switchLang('en')}>EN</button>
        </div>
        <button type="button" className="menu-btn" aria-label={menuOpen ? t('menu_close') : t('menu_open')} aria-expanded={menuOpen} aria-controls="mobile-nav" onClick={() => setMenuOpen(open => !open)}>{menuOpen ? '×' : '☰'}</button>
        <a className="btn btn-gold nav-try" href="#studio" onClick={event => { event.preventDefault(); go('studio'); }}>{t('nav_try')}</a>
      </div>
      <MobileNav open={menuOpen} items={[{ id: 'voices', label: t('nav_voices') }, { id: 'studio', label: t('nav_studio') }, { id: 'pricing', label: t('nav_pricing') }]} onNavigate={go} />
    </header>

    <main id="top" className="wrap">
      <div className="hero">
        <div>
          <span className="kicker">{t('hero_kicker')}</span>
          <h1><span>{t('hero_h1a')}</span> <span className="gold-text">{t('hero_h1b')}</span><span>{t('hero_h1c')}</span></h1>
          <p className="lede">{t('hero_lede')}</p>
          <div className="hero-ctas">
            <a className="btn btn-gold" href="#studio" onClick={event => { event.preventDefault(); go('studio'); }}>{t('hero_cta1')}</a>
            <a className="btn btn-ghost" href="#voices" onClick={event => { event.preventDefault(); go('voices'); }}>{t('hero_cta2')}</a>
          </div>
          <div className="stat-row">
            <span className="chip">{t('stat_voices')}</span>
            <span className="chip">{t('stat_native')}</span>
            <span className="chip">{t('stat_export')}</span>
          </div>
        </div>
        <div className="hero-visual">
          <div className="hero-frame glass">
            <img src={`${import.meta.env.BASE_URL}hero.webp`} alt="Gold studio microphone with a ribbon of sound" />
          </div>
          <div className={`hero-player glass ${playing === 'hero' ? 'playing' : ''}`} id="heroPlayer">
            <button className="play-btn" type="button" aria-label="Play Roger sample" onClick={() => speak('hero', DESIGN_VOICES[0].sample)}>{playing === 'hero' ? <PauseIcon /> : <PlayIcon />}</button>
            <div className="player-meta"><b>Roger — Signature Voice</b><span>{t('player_sub')}</span></div>
            <div className="wave" aria-hidden="true">{WAVE.map((height, index) => <i key={index} style={{ height: `${height}%` }} />)}</div>
          </div>
        </div>
      </div>

      <section id="voices">
        <div className="sec-head"><Kanote /><h2>{t('lib_title')}</h2><p>{t('lib_sub')}</p></div>
        <div className="voice-grid">
          {DESIGN_VOICES.map(item => <article key={item.id} className={`voice-card glass ${playing === item.id ? 'playing' : ''}`}>
            <div className="voice-top">
              <span className="avatar" aria-hidden="true">{item.initial}</span>
              <div><h3>{item.name}</h3><span className="role">{item.role[locale]}</span></div>
              {item.isNew && <span className="badge-new">{t('badge_new')}</span>}
            </div>
            <p>{item.desc[locale]}</p>
            <div className="tags">{item.tags.map(tag => <span className="chip" key={tag}>{t(tag as CopyKey)}</span>)}</div>
            <div className="voice-actions">
              <button type="button" className="btn btn-ghost sample-btn" aria-label={`Play ${item.name} sample`} onClick={() => speak(item.id, item.sample)}>{playing === item.id ? <PauseIcon /> : <PlayIcon />}</button>
              <button type="button" className="btn btn-gold" onClick={() => { setVoice(item.id); go('studio'); showToast(item.name + t('toast_selected')); }}>{t('use_voice')}</button>
            </div>
          </article>)}
        </div>
      </section>

      <section id="studio">
        <div className="sec-head"><Kanote /><h2>{t('st_title')}</h2><p>{t('st_sub')}</p></div>
        <div className="studio glass">
          <div className="tabs" role="tablist" aria-label="Mode">
            {(['tts', 'dialogue', 'srt'] as const).map(item => <button key={item} className="tab" role="tab" type="button" aria-selected={mode === item} onClick={() => applyMode(item, false)}>{item === 'tts' ? 'TTS' : item === 'dialogue' ? 'Dialogue' : 'SRT'}</button>)}
          </div>
          <div className="studio-grid">
            <div>
              <label className="f-label" htmlFor="script">{t('lbl_script')}</label>
              <textarea id="script" aria-label={t('lbl_script')} maxLength={5000} placeholder={MODES[mode].placeholder[locale]} value={script} onChange={event => { setUserEdited(true); setScript(event.target.value); }} />
              <div className="char-row">
                <span>{locale === 'mm' ? `စာလုံး ${fmt(count)} / 5,000` : `${fmt(count)} / 5,000 characters`}</span>
                <span>{locale === 'mm' ? `ကုန်ကျ credit ≈ ${fmt(count)}` : `Est. cost ≈ ${fmt(count)} credits`}</span>
              </div>
              <p className="mode-hint">{MODES[mode].hint[locale]}</p>
              <div className="results">
                <h3>{t('results_title')}</h3>
                <ResultList
                  items={results}
                  empty={t('empty_note')}
                  listenLabel={t('btn_listen')}
                  srtLabel={t('btn_srt')}
                  copyLabel={t('btn_copy')}
                  downloadLabel={t('btn_download')}
                  subtitle={item => `${duration(item.text)} ${t('est_suffix')} · ${fmt(chars(item.text))} ${t('chars_word')} · ${fmt(item.cost)} ${t('credits_word')} · ${item.at}`}
                  onListen={item => speak(`result-${item.id}`, item.text.replace(/^[AB]\s*[:：]\s*/gm, ''))}
                  onSrt={item => { downloadSRT(item.text, speed); showToast(t('toast_srt_done')); }}
                  onCopy={item => void copyText(item.text)}
                />
              </div>
            </div>
            <div>
              <span className="f-label">{t('lbl_voice')}</span>
              {mode === 'dialogue'
                ? <DialogueCast a={speakerA} b={speakerB} setA={setSpeakerA} setB={setSpeakerB} labelA={t('speaker_a')} labelB={t('speaker_b')} />
                : <div className="voice-chips">{DESIGN_VOICES.map(item => <button key={item.id} type="button" className="vchip" aria-pressed={voice === item.id} onClick={() => setVoice(item.id)}>{item.name}</button>)}</div>}
              <div className="slider-row">
                <div className="s-head"><label htmlFor="speed">{t('lbl_speed')}</label><output htmlFor="speed">{speed.toFixed(2)}×</output></div>
                <input type="range" id="speed" min="0.7" max="1.3" step="0.05" value={speed} onChange={event => setSpeed(Number(event.target.value))} />
              </div>
              <div className="slider-row">
                <div className="s-head"><label htmlFor="stability">{t('lbl_stability')}</label><output htmlFor="stability">{stability}%</output></div>
                <input type="range" id="stability" min="0" max="100" step="1" value={stability} onChange={event => setStability(Number(event.target.value))} />
              </div>
              <div className="credit-box glass">
                <div className="c-head"><span>{t('credit_left')}</span><span>{fmt(credits)} / {fmt(CREDITS_TOTAL)}</span></div>
                <div className="meter"><i style={{ width: `${Math.max(0, (credits / CREDITS_TOTAL) * 100)}%` }} /></div>
                <p>{t('credit_note')}</p>
              </div>
              <button className="btn btn-gold gen-btn" type="button" disabled={generating} onClick={generate}>
                <MicIcon /><span>{generating ? t('generating') : MODES[mode].gen[locale]}</span>
              </button>
              <div className={`progress ${generating ? 'on' : ''}`} aria-hidden="true"><i /></div>
            </div>
          </div>
        </div>
      </section>

      <section id="how">
        <div className="sec-head"><h2>{t('how_title')}</h2><p>{t('how_sub')}</p></div>
        <div className="steps">
          <div className="step glass"><span className="num">01</span><h3>{t('step1_t')}</h3><p>{t('step1_d')}</p></div>
          <div className="step glass"><span className="num">02</span><h3>{t('step2_t')}</h3><p>{t('step2_d')}</p></div>
          <div className="step glass"><span className="num">03</span><h3>{t('step3_t')}</h3><p>{t('step3_d')}</p></div>
        </div>
      </section>

      <section id="pricing">
        <div className="sec-head"><Kanote /><h2>{t('pr_title')}</h2><p>{t('pr_sub')}</p></div>
        <div className="price-grid">
          <div className="price-card glass">
            <span className="plan-name">Starter</span>
            <div className="price">Free <small>{t('per_month')}</small></div>
            <div className="credits-big">2,500 credits <span>{t('per_month2')}</span></div>
            <ul><li>{t('s_f1')}</li><li>{t('s_f2')}</li><li>{t('s_f3')}</li><li>{t('s_f4')}</li></ul>
            <a className="btn btn-ghost" href="#studio" onClick={event => { event.preventDefault(); go('studio'); }}>{t('plan_start_free')}</a>
          </div>
          <div className="price-card glass featured">
            <span className="plan-badge">{t('plan_popular')}</span>
            <span className="plan-name gold-text">Shwe Pro</span>
            <div className="price">39,000 <small>MMK <span>{t('per_month')}</span></small></div>
            <div className="credits-big">50,000 credits <span>{t('per_month2')}</span></div>
            <ul><li>{t('p_f1')}</li><li>{t('p_f2')}</li><li>{t('p_f3')}</li><li>{t('p_f4')}</li></ul>
            <a className="btn btn-gold" href="#studio" onClick={event => { event.preventDefault(); go('studio'); }}>{t('plan_go_pro')}</a>
          </div>
          <div className="price-card glass">
            <span className="plan-name">Enterprise</span>
            <div className="price">120,000 <small>MMK <span>{t('per_month')}</span></small></div>
            <div className="credits-big">250,000 credits <span>{t('per_month2')}</span></div>
            <ul><li>{t('e_f1')}</li><li>{t('e_f2')}</li><li>{t('e_f3')}</li><li>{t('e_f4')}</li></ul>
            <a className="btn btn-ghost" href="#studio" onClick={event => { event.preventDefault(); go('studio'); }}>{t('plan_contact')}</a>
          </div>
        </div>
      </section>

      <div className="cta-band glass">
        <h2>{t('cta_t')}</h2>
        <p>{t('cta_p')}</p>
        <a className="btn btn-gold" href="#studio" onClick={event => { event.preventDefault(); go('studio'); }}>{t('cta_btn')}</a>
      </div>

      <footer>
        <div className="f-row">
          <span>© 2026 Voice Gen By David</span>
          <span className="f-links">
            <a href="https://products.uiuiufs.site/" target="_blank" rel="noopener">{t('store_link')}</a>
            <a href="#voices" onClick={event => { event.preventDefault(); go('voices'); }}>{t('nav_voices')}</a>
            <a href="#pricing" onClick={event => { event.preventDefault(); go('pricing'); }}>{t('nav_pricing')}</a>
          </span>
        </div>
      </footer>
    </main>
    <div className={`toast ${toast ? 'show' : ''}`} role="status" aria-live="polite">{toast}</div>
  </div>;
}
