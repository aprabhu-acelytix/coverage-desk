# Start here — ChatGPT subscription edition

**The local Slack application is now implemented. Start with [README.md](README.md), [BUILD_NOTES.md](BUILD_NOTES.md), and [DEMO.md](DEMO.md).** The instructions below describe the original starter and are retained for background only. The current owner goal authorizes configured Slack/source/runtime validation with persistent caps of 30 source requests and 10 AI jobs. APP_MODE is live. Do not wait for another live-call approval. Managed runtime sign-in and exact owner UI confirmation for channel publishing are still required.

The AI path is **Slack → local app → official Codex SDK/App Server → your ChatGPT-authenticated Codex session → validated results**. Source retrieval and Slack publishing remain ordinary application code. Your machine runs the backend; model inference is not offline.

## 1. Start the build

Extract this folder into a dedicated local project directory. Open a local Codex session there and paste `GOAL_PROMPT.txt`. Codex should read `BUILD_SPEC.md` and `CODEX_RUNTIME.md`, then implement and test using fixtures before requesting live access.

Already started the previous version? Back up or commit your existing code, then bring over these revised instruction files. Merge `.env.example` changes into your **local** `.env` without replacing working Slack/source credentials. Do not overwrite `.env`, delete code, or reset Git history. The new starter requires no OpenAI API-key or `OPENAI_MODEL` setting; any stale values must not be used by the runtime.

## 2. Configure the environment file

Copy the template only when `.env` does not already exist.

PowerShell:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Bash:

```bash
[ -f .env ] || cp .env.example .env
```

Edit the file locally. Do not paste secrets into a chat or ask Codex to print the file. All settings in this package are implementation requirements; they do nothing until Codex wires them into the app.

## 3. Slack — still required for the live interface

Use your own development workspace. At `https://api.slack.com/apps`, create an app **From a manifest** using `slack-app-manifest.yaml` (or compare it with your existing app). Review it before installation. [S1]

- Install the app; put its Bot User OAuth Token (`xoxb-...`) in `SLACK_BOT_TOKEN`.
- Generate an App-Level Token (`xapp-...`) with `connections:write`; put it in `SLACK_APP_TOKEN`. Confirm Socket Mode is enabled. [S2]
- Set `SLACK_OWNER_USER_ID` to your own Slack member ID. The completed app should provide a safe identity/status command that reports the authenticated acting member ID; do not use a display name as authorization.
- Invite the bot to a public development channel and set `SLACK_DEMO_CHANNEL_ID` to its channel ID. `SLACK_WORKSPACE_ID` is optional; the backend must otherwise bind to the installed workspace returned by `auth.test`.

The manifest is unchanged from the previous starter. It has been parsed and locally checked, not imported into a live workspace. It requests `commands`, `chat:write`, and `channels:read`, not channel history.

## 4. AI — sign in with ChatGPT, no API key

Do **not** create an OpenAI Platform key or configure API billing for this design. The official Codex SDK/App Server supports managed ChatGPT authentication; the app must verify the runtime's auth mode and use no API fallback. [C1, C2, C3]

Codex should provide a local sign-in/status helper using the same executable and `COVERAGE_CODEX_HOME` as the application. Run that helper when implementation is ready. The dedicated runtime home defaults to `~/.coverage-desk-codex` and is deliberately separate from the development session, so you may need to sign in once there even when Codex is already signed in elsewhere.

For a standalone installed Codex CLI, these commands illustrate checking/signing in to that dedicated home. Use them in the **same OS environment** as the backend. They affect only the command's process environment, not your persistent system settings. Use the actual configured path when it differs from the default.

PowerShell:

```powershell
$previousCodexHome = $env:CODEX_HOME
try {
    $env:CODEX_HOME = Join-Path $HOME '.coverage-desk-codex'
    New-Item -ItemType Directory -Force $env:CODEX_HOME | Out-Null
    codex login status
    # Only when sign-in is needed, uncomment and complete Sign in with ChatGPT:
    # codex login
} finally {
    if ($null -eq $previousCodexHome) {
        Remove-Item Env:CODEX_HOME -ErrorAction SilentlyContinue
    } else {
        $env:CODEX_HOME = $previousCodexHome
    }
}
```

Bash:

```bash
mkdir -p "$HOME/.coverage-desk-codex"
CODEX_HOME="$HOME/.coverage-desk-codex" codex login status
# Only when sign-in is needed, uncomment and complete Sign in with ChatGPT:
# CODEX_HOME="$HOME/.coverage-desk-codex" codex login
```

The SDK may bundle its own runtime. Its generated helper is the authoritative login/status route for this app; the CLI example is not proof that a different SDK runtime is connected. Never copy an auth file, access token, refresh token, or browser cookie into `.env`. The app should select a supported subscription model and document `CODEX_MODEL`. [C1, C2]

Review ChatGPT data controls before live use. Personal Plus/Pro Codex content may be used to improve models unless training is disabled. This demo should use public/synthetic material only. Subscription limits still apply. [C4]

**Collaboration remains:** authorized teammates may browse shared findings, contribute perspectives, review results, and edit shared drafts. They may not run your personal AI worker. A hosted or multi-user AI service is not part of this prototype and needs a separately verified access arrangement. [C5]

## 5. Search — unchanged

Create or reuse a Brave key at `https://api-dashboard.search.brave.com` for News/Web Search and set `BRAVE_API_KEY`. Confirm your plan's storage rights before setting `BRAVE_STORAGE_ALLOWED=true`. Otherwise the connector remains blocked for retained results; manual contributions and offline fixtures still work. [S3]

`YOUTUBE_API_KEY` remains optional. To add it, enable YouTube Data API v3 in Google Cloud and restrict the key to that API. Codex must check applicable data-use policies before implementing retention or AI analysis. Public metadata discovery does not establish access to video contents. [S4]

## 6. Bounded live check, then the walkthrough

Historical authorization example only: the current goal has already granted broader bounded live authorization. Keep automated tests offline and scheduling disabled. No need to resend the following:

```text
The local environment is configured and I have completed the runtime's managed ChatGPT sign-in. I authorize the bounded live check described in BUILD_SPEC.md: Slack authentication, Codex auth/config checks, one tiny synthetic AI analysis, and one Brave News plus one Brave Web query only if storage permission is confirmed. Skip optional YouTube. No retries, posts, scheduled jobs, credit purchases, or deployment. Report actual outcomes and then guide me through the Slack walkthrough. Ask before enabling continuing live operation.
```

The current goal has authorized `APP_MODE=live` plus the existing `ALLOW_LIVE_CALLS=true`. Publishing still requires an exact preview and explicit owner action in Slack. Scheduling stays disabled. The persistent validation ledger must not be reset across restarts.

The backend must remain running for Slack interactions. Socket Mode avoids a public webhook URL; it does not host the code for you. [S2]

## Documentation

- [C1] Codex SDK: `https://developers.openai.com/codex/sdk/`
- [C2] Codex auth/login/storage: `https://developers.openai.com/codex/auth/`
- [C3] Codex App Server: `https://developers.openai.com/codex/app-server/`
- [C4] Plan usage/data controls: `https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan`
- [C5] Personal-plan restrictions: `https://help.openai.com/en/articles/9793128-what-is-chatgpt-pro`
- [S1] Slack app manifest: `https://docs.slack.dev/reference/app-manifest/`
- [S2] Slack Socket Mode: `https://docs.slack.dev/apis/events-api/using-socket-mode/`
- [S3] Brave plans/storage FAQ: `https://brave.com/search/api/`
- [S4] YouTube setup/policies: `https://developers.google.com/youtube/v3/getting-started` and `https://developers.google.com/youtube/terms/developer-policies`
