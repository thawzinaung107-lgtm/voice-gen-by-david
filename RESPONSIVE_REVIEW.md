# Responsive source review — 10 November 2026

## Changes
- Removed global horizontal-overflow hiding so layout errors cannot be concealed.
- Myanmar headings use the bundled Noto Sans Myanmar font, normal letter spacing and 1.75 line height. No font sizes were reduced.
- Reserved desktop hero space for the microphone decoration; mobile hero text uses the full width.
- Comparison controls use available-width grid tracks with a separate full-width action row. Cards retain content-driven heights and aligned actions.
- Filter labels wrap; wave bars can shrink within their visual track without clipping text labels.
- Selected-voice actions retain their icon and readable size on mobile.
- Sidebar navigation and footer remain scrollable on short screens. The mobile navigation uses the full viewport height, rather than assuming a fixed header height; it is suppressed at desktop widths. The menu button exposes its expanded state and controlled navigation ID.
- Existing avatar PNGs, translations, four voice personas, speech-preview logic and project configuration are preserved.

## Verification
- TypeScript `npm run typecheck`: PASS.
- Production `npm run build`: PASS.
- Local headless Chromium: 390, 768, 1024 and 1440 CSS pixels, English and Myanmar, 900px viewport height.
- Library, Studio, details dialog and applicable mobile menu: no measured page overflow, tested control/container overflow, waveform escape or sibling overlap.
- Search, favorite toggling and voice selection tested at every width/language combination.
- Six-times-length voice description tested for content-driven card growth.
- Mobile and desktop Myanmar Library screenshots visually inspected.
- Actual synthesized audio quality was not evaluated. Audio logic was not changed.

## Repeat checks
Run `npm ci`, install Playwright in your test environment, and install its Chromium browser. With Vite port 5173 free, run `node tests/responsive.cjs`. Optionally set CHROMIUM_EXECUTABLE_PATH to an installed Chromium. Set QA_SCREENSHOTS=1 to capture screenshots. Results are written to responsive-results.json.

## Delivery boundary
These changes were applied and verified in the uploaded source, not in the live Figma Make editor. The existing Make editor was inaccessible because its browser reported unsupported WebGL, and the GitHub connector could not access the supplied repository. No new Figma project was created, no remote files were changed and nothing was published. Apply the changed src/styles.css and src/main.tsx to the existing project and review its Make preview before publishing.

Earlier QA.md and screenshots shipped with the upload are historical records; this report and responsive-results.json describe this run.
