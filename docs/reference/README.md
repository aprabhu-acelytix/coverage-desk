# Pinned upstream implementation evidence

Downloaded from the official `openai/codex` repository at tag `rust-v0.157.1`:

- `codex-rs/core/config.schema.json` → `codex-config.schema.json`
- `codex-rs/models-manager/models.json` → `codex-models.json`
- `codex-rs/core/src/tools/spec_plan.rs` → `codex-spec-plan.rs`
- `codex-rs/tools/src/tool_config.rs` → `codex-tool-config.rs`
- `codex-rs/core/src/tools/handlers/apply_patch_spec.rs` → `codex-apply-patch.rs`

These are public upstream files, not account configuration or histories. See `LICENSE-codex.txt` for upstream licensing. Runtime generation uses the schema to reject unknown controls and copies the catalog with shell/apply-patch/alternate execution capability metadata disabled. It still verifies the selected model against the actual managed account's model list first. Tool registration in `spec_plan.rs` shows why disabling the apply-patch feature flag alone is insufficient: registration also depends on model capability metadata.
