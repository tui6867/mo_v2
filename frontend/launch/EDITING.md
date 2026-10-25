# Mass Outreach launch page: editing and deployment

## Start here

From `frontend/`:

```powershell
npm.cmd ci
npm.cmd run dev:launch
```

Open **http://127.0.0.1:5174**. Edits reload automatically. This is separate from
the existing HTTPS mail pilot at https://localhost:8443. Do not rebuild or restart
the pilot containers just to change the launch page.

## Where to edit

| What | File |
| --- | --- |
| Brand name, hero, CTA, sample people/files/messages, capability copy, roadmap, FAQ | `frontend/launch/content.ts` |
| Page sections, navigation, closing statement, section order | `frontend/launch/LaunchPage.tsx` |
| Colors, type, spacing, glass, breakpoints, motion | `frontend/launch/styles.css` (brand tokens at the top) |
| Workflow steps, permission model, editing, approval, simulated delivery | `frontend/launch/components/WorkflowDemo.tsx` |
| Waitlist drawer, fields, consent and submission experience | `frontend/launch/components/WaitlistDialog.tsx` |
| Preview-only waitlist adapter | `frontend/launch/services/waitlist.ts` |
| Future prototype vocabulary, deliberately not implemented | `frontend/launch/services/prototype-contract.ts` |
| Title, description, social metadata and indexing | `frontend/launch/index.html` |
| Security headers for Cloudflare Pages | `frontend/launch/public/_headers` |
| Favicon / social share art | `frontend/launch/public/` |

For the hero, edit `hero.headingLead` and `hero.headingAccent`. Keep HTML title,
description and social card text in sync manually. Example messages are prewritten
and should remain fictional (`.example` domains). Tone buttons replace only the
known closing sentence, preserving other edits. If a visitor manually removes that
sentence, the tone button intentionally does not overwrite their text.

All sample permission toggles are local state. The import control loads example
data, not a real file. No resume processing, AI call, contact discovery, email,
auth, analytics, browser storage, or waitlist persistence happens here.

## Design rules

- Graphite canvas, cool-blue signal, readable off-white text; self-hosted Manrope.
- Glass expresses the workspace layer, not every paragraph.
- One animated beam, only while the explicitly simulated sending sequence runs.
- Reduced-motion users see immediate simulated results after approval.
- Retain visible concept labels and the distinction between pilot and vision.
- No fabricated customer logos, user counts, results, pricing, or delivery claims.
- Native modal dialog handles focus containment and Escape. Never hide the preview notice.

## Test and build

```powershell
npm.cmd test
npm.cmd run test:launch:browser
npm.cmd run build:launch
npm.cmd run preview:launch
```

Production output: **`frontend/dist-launch`**. Preview: http://127.0.0.1:4174.
The original `npm.cmd run build` still builds the mail pilot into `frontend/dist`.
Neither app imports the other. Keep those output directories separate.

Browser tests use the existing Microsoft Edge installation on Windows. On other
platforms, install Playwright's Chromium browser for the test runner. They exercise
320, 390, 768 and 1440px layouts, dialog focus/Escape, the full sample workflow,
network isolation, and reduced motion. Screenshots are saved under ignored
`frontend/launch-artifacts/`. `720px` is also checked as a 200%-zoom-equivalent
layout; this is not a claim of testing every browser's native zoom implementation.

## Cloudflare Pages deployment

The template is deployable as a static Pages site. It does **not** require
Supabase keys, Python, Docker, or the pilot API. Supabase is not the frontend host.

In your Cloudflare account, create a **new** Pages project named
`mass-outreach-launch`—do not overwrite an existing site or change production DNS.
For a Git-connected build:

- Root directory: `frontend`
- Build command: `npm run build:launch`
- Build output: `dist-launch`
- Node: 22.12 or newer (a maintained Node 22/24 release)
- No Supabase or SMTP secrets and no `VITE_` secrets.

For a dashboard Direct Upload, build locally and upload **only** `dist-launch`.
`frontend/launch.wrangler.jsonc` is also provided for a separately authenticated
Wrangler workflow. Use `wrangler --help` / `wrangler pages deploy --help` for your
installed version before deploying.

No Cloudflare account token or authenticated CLI was available when this template
was created; a local build is not a public deployment. Publishing requires the
owner's Cloudflare login/authorization. An initial `pages.dev` preview is preferable
to changing the existing domain. Verify security headers after deployment; Vite's
local preview server does not apply Pages `_headers`.

The preview intentionally uses `noindex`. Before a public marketing launch, approve
the copy, replace the preview application with a real reviewed collection flow,
add privacy/contact information, set absolute social image/canonical URLs to the
actual public domain, and remove `noindex` if indexing is desired. Social platforms
need the publicly reachable domain to fetch the share card; localhost cannot do it.

## Connecting Supabase later (not done)

The intended architecture is:

```
Cloudflare Pages → WaitlistGateway → isolated Supabase Edge Function → private waitlist table

Interactive concept → in-memory sample state only
Existing prototype → separate authentication/API/sending boundary, untouched
```

See `ARCHITECTURE.md` for the required security/release gates. Do not paste secret
keys into frontend files or change the pilot's API permissions for this page.
