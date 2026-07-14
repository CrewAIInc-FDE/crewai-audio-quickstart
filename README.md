# crewai-audio-quickstart

**A voice-ready, conversational field assistant on CrewAI AMP — the full reference
pattern:** audio → transcription → a deployed Flow with intent routing, tool-using
agents, and session memory that survives across kickoffs → answer (text you can
speak back).

The flow mirrors an architecture running in real field deployments, with every
customer-specific piece swapped for a generic, self-contained stand-in (the data
layer is a seeded SQLite file — no external services, no credentials).

## Architecture

```
audio file / mic ──► OpenAI transcription (client-side; the only OpenAI-key use)
                          │  text
                          ▼
             POST {deployment}/kickoff  {"inputs": {"id": "<uuid>", "message": "..."}}
                          │
                          ▼
        AssistantFlow  (one kickoff = one conversational turn)
        ├─ deterministic-first router: quit / cancel / form-continuation
        │  are handled with ZERO LLM calls; everything else gets one small
        │  classification call (asset_data | start_form:<type> | unknown)
        ├─ Asset-data agent — 3 tools over the SQLite readings table:
        │    get_latest_reading · get_period_stats · list_assets
        │    (fuzzy name matching → canonical names; "latest" skips the
        │    in-progress day and says so when it can't)
        ├─ Form agent — voice-guided wizard (maintenance / incident report):
        │    one field per turn, typed validation, read-back, explicit
        │    "confirm" before a (mock) submission
        └─ @persist state keyed on `id`: history + form progress survive
           across kickoff executions (on AMP SaaS, state lands on the
           persistent volume by default)
```

**Session contract:** `{"id": "<uuid>", "message": "<user text>"}` → reply string.
Reuse the same `id` to continue the conversation (the form wizard depends on this);
new UUID = new conversation. `id` must be a full, valid UUID.

## Deploy (CrewAI AMP)

1. Connect this repo (Deploy From Code → Git Repository), branch `main`.
   The repo auto-deploys on new commits once connected.
2. The deployment needs an LLM: an **OpenAI LLM connection** in your org, or an
   `OPENAI_API_KEY` environment variable on the deployment (the agents and the
   intent classifier use `openai/gpt-4o`).
3. No other configuration. No database env vars (SQLite is seeded on first use),
   and no storage env vars (AMP persists flow state by default).

## Ask it something (audio in, answer out)

```bash
cp .env.example .env         # fill in the two deployment values
python3 client/ask.py samples/question.wav
```

`client/ask.py` is stdlib-only and does the whole loop: transcribe → discover the
deployment's input contract (`GET /inputs` — never assume key names) → kickoff →
poll → print. It keeps a `.session` file so consecutive questions continue ONE
conversation — which is what makes the form wizard work by voice:

```bash
python3 client/ask.py clips/file-a-report.wav      # "I'd like to file a maintenance report"
python3 client/ask.py clips/asset-id.wav           # "Pump A1"
python3 client/ask.py clips/work-done.wav          # ... one field per clip ...
python3 client/ask.py --new-session clips/next.wav # fresh conversation
```

Things to try:
- "What assets do you have?"
- "What was the latest output on pump A1?"
- "Average energy use on compressor B1 this week?"
- "I'd like to file an incident report." → then answer its questions → "confirm"

Record clips with `scripts/make_sample_audio.sh`, your phone, or anything that
produces wav/mp3/m4a.

## Browser client (`ui/`)

A fully client-side web UI (Rust/Leptos → WASM): paste your deployment URL,
bearer token, and OpenAI key (stored in your browser's localStorage, sent nowhere
else), then talk — mic capture → transcription → kickoff → spoken reply via the
browser's speech synthesis. See [`ui/README.md`](ui/README.md) for build/run.

> Browser calls go directly to the deployment API; if your browser blocks them
> (CORS), use `client/ask.py` — same loop, no browser restrictions.

## Local development

```bash
uv sync
OPENAI_API_KEY=sk-... uv run kickoff     # scripted 3-turn smoke session
```

The data layer (`src/audio_quickstart/data.py`) seeds deterministic synthetic
readings for five assets × 45 days. Swap `connect()`/the tool internals for your
warehouse or API to make this real — the agents, router, and session machinery
don't change.

## Layout

```
src/audio_quickstart/
├── flow.py      # AssistantFlow: router + handlers + @persist session state
├── agents.py    # data agent + form agent (one LLM instance per agent)
├── tools.py     # 3 data tools (SQLite) + 3 form tools; caching disabled
├── forms.py     # form schemas, typed validation, session state machine
├── data.py      # synthetic SQLite readings (the stubbed "warehouse")
└── main.py      # local smoke entry point
client/ask.py    # stdlib audio client (transcribe → kickoff → poll)
ui/              # Leptos (Rust/WASM) browser client
```

## Releasing the browser UI (GitHub Pages)

The UI is published at https://crewaiinc-fde.github.io/crewai-audio-quickstart/ —
built locally, no CI:

```
./scripts/release-ui.sh
```

The script trunk-builds `ui/` with the Pages subpath baked in and force-pushes
the snapshot to the `gh-pages` branch, which Pages serves (Settings → Pages →
Deploy from a branch → `gh-pages` / root). Everything runs client-side: users
paste their own deployment URL, bearer token, and (for the mic) OpenAI key,
stored only in the browser's localStorage.
