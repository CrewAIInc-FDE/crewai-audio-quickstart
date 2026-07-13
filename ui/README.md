# ui — browser client (Leptos / Rust → WASM)

All client-side: the page talks directly to (1) your CrewAI deployment and
(2) OpenAI's transcription API — from the browser, with keys you paste into
Settings (persisted only to your browser's localStorage).

## Run

```bash
rustup target add wasm32-unknown-unknown   # once
cargo install trunk                        # once
cd ui && trunk serve                       # http://127.0.0.1:8082
```

Fill in Settings:

| Field | Where it comes from |
|---|---|
| Deployment URL | your deployment's page in CrewAI AMP |
| Deployment bearer token | same page |
| OpenAI API key | only needed for the 🎤 mic button (transcription) |

Then type — or click **🎤 Talk**, speak, click **Stop**. The reply can be
spoken aloud (checkbox in Settings) via the browser's speech synthesis.

"New conversation" rotates the session UUID; keeping it means the assistant
remembers the conversation (that's what makes the form wizard work).

## Known constraint

The browser calls the deployment API cross-origin. If your browser console
shows CORS errors on `/kickoff`, the platform isn't sending CORS headers for
browser callers — use `client/ask.py` (identical loop, no browser rules) and
tell us; we're tracking whether the deployment API advertises CORS.
