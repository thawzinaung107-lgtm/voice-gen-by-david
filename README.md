# Voice Gen By David V2 – Voice Library + Studio Foundation

A standalone React + TypeScript/Vite prototype based on the Figma V2 designs. This is **not a production application** and does not connect to Base44, Vibi, GenMax, a wallet, authentication, storage, or other supplier APIs.

## Features

- Responsive dark cyberpunk interface; mobile-first layout and English/မြန်မာ toggle
- Four original illustrated voice-persona avatars with Idle/Playing/Selected states
- Searches, category filters, favorites, selection, and two-voice comparison
- One speech sample at a time using **browser Speech Synthesis** (device/browser voice, NOT actual Brian/Daniel/Lily/Adam supplier voices)
- Reduced-motion support, keyboard navigation, focus states, and fallback portraits
- Locale switch retains filters, selected voice, Studio mode, tool choice, and current script draft
- Noto Sans Myanmar is bundled locally so Myanmar Unicode does not depend on an external font request
- Voice Studio foundation with Guided/Advanced modes, TTS editor, voice casting, character count, credit-estimate placeholder, and generation-history entry points
- Dialogue, SRT, advanced supplier controls, credit estimate, and generation are visibly configuration-gated

## To run locally

`npm install && npm run dev`

In Figma Make, the supervised preview starts through `.figma/make/dev`; do not start a second development server.

Figma Make lifecycle scripts: `.figma/make/{install,dev,deploy-preview,deploy}`.

## Design source

https://www.figma.com/design/nfBcPAGo1Nco3qoYw1AAyh?node-id=42-3
