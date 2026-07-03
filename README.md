# commiter

A small CLI that stages your working-tree changes, generates a
[Conventional Commits](https://www.conventionalcommits.org/) message with a
Fireworks-hosted DeepSeek model, lets you review it, and creates the commit.

## Setup

1. **Create `.env`** with your Fireworks API key (pulled from 1Password):

   ```bash
   printf 'FIREWORKS_API_KEY=%s\n' \
     "$(op read 'op://Engineering/FIREWORKS_API_KEY/password')" > .env
   ```

   See [`.env.example`](.env.example) for all supported variables. `.env` is
   git-ignored.

2. **Install dependencies for local dev:**

   ```bash
   uv sync
   ```

## Usage

Run from inside any git repository:

```bash
uv run commiter          # local dev
commiter                 # after a global install (see below)
```

`commiter`:

1. Stages everything with `git add -A`.
2. Reads the staged diff (exits with "nothing to commit" if empty).
3. Generates a commit message and shows a preview.
4. Prompts: **[a]ccept / [e]dit / [r]egenerate / [q]uit**.
   - **edit** opens `$EDITOR` (falls back to a typed line).
   - **regenerate** asks the model again.
   - **quit** leaves your changes staged, uncommitted.

### Flags

- `-y` / `--yes` — skip the prompt and commit immediately.
- `--model <id>` — override the model for this run.

### Configuration

| Variable            | Default                                       | Purpose              |
| ------------------- | --------------------------------------------- | -------------------- |
| `FIREWORKS_API_KEY` | _(required)_                                  | Fireworks API key    |
| `FIREWORKS_MODEL`   | `accounts/fireworks/models/deepseek-v4-flash` | Model ID (swappable) |

## Install globally

```bash
uv tool install .        # puts `commiter` on your PATH (~/.local/bin)
```

Re-run after code changes:

```bash
uv tool install --reinstall .
```
