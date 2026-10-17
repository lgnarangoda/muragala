# Muragala frontend (PWA)

Check a suspicious WhatsApp/SMS message before you pay. Works on any phone browser; on Android it also appears in the share sheet once installed.

## Run locally

```bash
npm install
cp .env.example .env      # leave VITE_API_URL empty for demo mode
npm run dev               # open the printed localhost URL
```

Demo mode returns sample answers so the UI can be built and recorded before the backend is ready. Put the Cloud Run URL in `.env` (`VITE_API_URL=https://...run.app`) to use the real ADK backend.

## Deploy to Firebase Hosting

```bash
npm install -g firebase-tools
firebase login
firebase use --add        # pick the same GCP project as the backend
npm run build
firebase deploy --only hosting
```

`firebase.json` is already set up (`dist` folder, single-page rewrites, service-worker headers).

## Pages

- `/` — Muragala check screen: sample buttons, paste/upload, risk result, guardian WhatsApp alert, "How Muragala decided" panel, Sinhala/English toggle.
- `/bank` — mock bank transfer that asks "is someone in a chat or call asking you to pay?" and shows the scam-context risk signal from `GET /v1/scam-context-signal/{check_id}`.

## Backend contract

`POST {VITE_API_URL}/check` (multipart: `text`, `files`) returns:
`check_id, risk_score, risk_level, scam_type, explanation_si, explanation_en, actions_si, actions_en, citations, guardian_message_si, analysis`.
