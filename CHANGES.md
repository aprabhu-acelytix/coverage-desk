# Revision 2 — changes from the previous starter

Implementation status now lives in README.md and BUILD_NOTES.md. The package-validation section below is historical and is not the current application status. The active goal supersedes prior requests to wait for live-call approval.

Prepared 27 September 2026.

- Replaced the ordinary OpenAI SDK/Responses API design with the official Codex Python SDK and local App Server, using Codex-managed ChatGPT sign-in.
- Removed API-key/model setup from the environment template. Added a dedicated runtime home, optional runtime executable/model settings, owner Slack member ID, and bounded job controls.
- Preserved news/web discovery, optional YouTube, manual contributions, message evidence, Explore / Team board / Briefings, and collaborative review.
- Restricted live AI and publishing to the configured owner while keeping authorized shared-artifact collaboration available to teammates.
- Removed API-specific retention assumptions. Added ChatGPT data controls, no-secret-inheritance requirements, fresh job contexts, explicit usage-limit states, and no scheduled AI.
- Updated setup, migration guidance, live-check authorization, acceptance checks, and the /goal command. Added CODEX_RUNTIME.md and AGENTS.md.
- Retained the original Slack app manifest without widening permissions.

## Package validation

Checked locally when preparing this package: archive integrity; YAML parsing and intended scopes/settings; complete expected file inventory; /goal under 4,000 characters; no API-key assignments in the environment template; no actual secrets, credential files, runtime data, or old archive bundled.

These are starter-file checks only. No application code is implemented here, no dependencies are installed, and no account login, live Codex inference, Slack installation, or data-provider call has been performed. Codex must implement and validate the application on the owner's machine.
