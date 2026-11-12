# Voice Gen V2 Voice Library + Studio — Validation Notes

## Automated checks
- `mise exec -- npm run build` passes with Vite 6.
- `mise exec -- npm run typecheck` passes with TypeScript strict mode.
- Portrait assets for Brian, Daniel, Lily and Adam are non-empty local PNGs (not temporary Figma URLs).
- The project has a root `index.html`, `src/main.tsx`, `src/styles.css`, and explicit Vite configuration.
- All four `.figma/make` lifecycle scripts are executable regular files and the source archive contains them at its root.
- No supplier API secrets, authentication secrets or payment credentials are included in the prototype.
- Noto Sans Myanmar is bundled with the app and does not depend on Google Fonts being reachable.

## Browser checks
- The Figma Make preview is supervised by `.figma/make/dev`.
- Headless Chromium at 1440px passed: four-persona rendering, EN/MM switching, search, category filters, favorite remove/restore, selection, Library-to-Studio navigation, Studio draft/mode/voice preservation, and Dialogue/SRT configuration-required states.
- Stubbed browser-speech interaction checks passed: one active preview globally, repeated-click stop behavior, two-voice comparison sequencing, and comparison stop behavior.
- Headless Chromium at 390px passed: mobile navigation, hidden desktop sidebar, and single-column voice cards.
- Chromium with `prefers-reduced-motion: reduce` confirmed avatar animation suppression.
- Browser Speech Synthesis output fidelity was not audibly evaluated; it remains device/browser dependent and is clearly labeled as a browser demo.

## Responsive alignment repair
- Chromium geometry checks passed in both English and Myanmar at 1440px, 1024px, 768px, and 390px.
- 1440px and 1024px use two voice-card columns; 768px and 390px use one column.
- Every tested viewport passed page-width, waveform containment, card-button containment, equal-row alignment, sidebar/drawer breakpoint, and comparison-control containment checks.
- Search, favorites, selected voice, category filters, language-state preservation, comparison start/stop, and avatar playback state remain functional.
- Review captures are stored in `qa-screenshots/`, including the 1440px before/after pair, tablet/mobile card layouts, and the focused 390px comparison layout.

## Global responsive text-flow audit
- English and Myanmar passed on both Library and Studio at 320px, 375px, 390px, 768px, 1024px, 1280px, 1440px, and 1920px.
- A single mounted session passed dynamic resizing through 1920 → 1280 → 768 → 320 → 1024 → 375 → 1440 → 390px.
- The 320px detail dialog and mobile drawer passed text-flow, button-visibility, and page-width checks.
- Injected long Myanmar descriptions, action labels, comparison text, Studio headings, tool labels, history text, and status copy passed without page overflow or sibling overlap.
- Library and Studio passed browser-zoom layout simulations at 125%, 150%, and 200%.
- Library and Studio passed direct text enlargement at 125%, 150%, and 200%.
- Checks covered page overflow, text-bearing button clipping, hidden text overflow, card row ordering, waveform containment, comparison-control overlap, topbar overlap, and Studio hero/mode overlap.
- Before/after captures for mobile, tablet, and desktop Library plus after captures for Studio are stored in `qa-screenshots/global-responsive/`.

## Audio fidelity notice
- Sample playback uses the user's browser/device Speech Synthesis. It does **not** represent the real Vibi or GenMax supplier voice associated with the pictured avatar. No user credits are spent.
