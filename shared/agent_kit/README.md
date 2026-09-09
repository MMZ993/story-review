# agent-kit — shared agent support (Phase 5)

Fail-loud helpers shared by the four agent packages:

- `agent_kit.prompts.load_prompt(slug, prompts_dir=None)` — implements the
  `PROMPTS_DIR` contract from `docs/operations/repository-layout.md`:
  resolves the directory (explicit arg → `PROMPTS_DIR` env → `/app/prompts`),
  reads `<slug>.md` as UTF-8, aborts loudly on a missing/invalid file, and
  returns an immutable `LoadedPrompt(slug, text, sha256)` with the SHA-256
  over the file bytes (the `prompt_sha256` audit value).
- `agent_kit.config.load_agent_config(path)` — strictly validates an
  agent's immutable `config.yaml` (model, location, temperature,
  max_output_tokens; unknown keys rejected) into a frozen `AgentConfig`.

Tests: `make agent-kit-test` from the repository root.
