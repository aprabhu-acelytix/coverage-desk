# Project instructions

Read BUILD_SPEC.md and CODEX_RUNTIME.md before implementing Coverage Desk.

This is the ChatGPT-subscription revision. Never restore an OpenAI API-key requirement, a paid API fallback, token extraction, or a shared subscription inference service. Use official Codex-managed authentication for a local owner-operated analytical worker.

Preserve the core product: Explore, Team board, Briefings, inspectable sources, evidence-backed message tracking, explicit sharing, and professional Slack-native UX. Collaboration must work without letting other users invoke the owner's AI session.

Implement and test offline first. The owner has authorized loading .env without exposing secrets, preserving existing values and setting APP_MODE=live. Never print .env, inspect Codex auth files, personal Codex histories, or unrelated private configuration. Do not mutate the development user's global Codex configuration. The runtime has its own isolated configuration/home.

The active goal explicitly authorizes project-local dependencies, configured Slack connection and owner Home updates, live sources, owner-supplied permitted storage, and owner-operated Codex validation. Do not ask for this authorization again. Persist total validation limits of 30 source requests and 10 runtime AI jobs, including retries across restarts; do not reset the ledger. No deployment, purchases, paid fallback, automatic channel posts, or scheduled AI. Channel publishing still requires the owner's exact preview/confirmation UI action. Preserve existing user code and local secrets. Report tested facts, distinguish fixtures from live evidence, and keep within the assignment scope.
