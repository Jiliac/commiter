"""commiter — generate a commit message from your staged diff with a Fireworks-hosted model."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile

from dotenv import find_dotenv, load_dotenv

DEFAULT_MODEL = "accounts/fireworks/models/deepseek-v4-flash"
FIREWORKS_BASE_URL = "https://api.fireworks.ai/inference/v1"
DIFF_CHAR_CAP = 12_000

SYSTEM_PROMPT = """You are an expert software engineer writing a git commit message.

Given a staged diff, write a single commit message that follows the Conventional \
Commits specification:
- A subject line of the form `type(optional-scope): summary`, where type is one of \
feat, fix, docs, style, refactor, perf, test, build, ci, chore.
- The summary must be in the imperative mood and at most 72 characters.
- Optionally, after a blank line, a body that explains the what and why, wrapped at \
about 72 characters. Omit the body for trivial changes.

Return ONLY the commit message text. Do not wrap it in markdown, backticks, or quotes, \
and do not add any commentary."""


def _err(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)


def run_git(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    # Git output can contain non-UTF-8 bytes (e.g. a binary file the diff
    # heuristic misclassifies as text), so decode tolerantly instead of
    # crashing with UnicodeDecodeError.
    kwargs.setdefault("errors", "replace")
    return subprocess.run(["git", *args], text=True, capture_output=True, **kwargs)


def ensure_git_repo() -> None:
    result = run_git(["rev-parse", "--is-inside-work-tree"])
    if result.returncode != 0 or result.stdout.strip() != "true":
        _err("not inside a git work tree.")
        sys.exit(1)


def stage_all() -> None:
    result = run_git(["add", "-A"])
    if result.returncode != 0:
        _err(f"`git add -A` failed:\n{result.stderr.strip()}")
        sys.exit(1)


def staged_diff() -> str:
    result = run_git(["diff", "--cached"])
    if result.returncode != 0:
        _err(f"`git diff --cached` failed:\n{result.stderr.strip()}")
        sys.exit(1)
    return result.stdout


def truncate_diff(diff: str) -> str:
    if len(diff) <= DIFF_CHAR_CAP:
        return diff
    return diff[:DIFF_CHAR_CAP] + "\n\n[diff truncated]"


def generate_message(diff: str, api_key: str, model: str) -> str:
    from openai import OpenAI

    client = OpenAI(base_url=FIREWORKS_BASE_URL, api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Here is the staged diff:\n\n{diff}"},
        ],
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


def edit_message(message: str) -> str:
    editor = os.environ.get("EDITOR")
    if not editor:
        print("No $EDITOR set. Type the message, end with an empty line:")
        lines: list[str] = []
        while True:
            try:
                line = input()
            except EOFError:
                break
            if line == "":
                break
            lines.append(line)
        edited = "\n".join(lines).strip()
        return edited or message

    with tempfile.NamedTemporaryFile(
        mode="w+", suffix=".gitcommit", delete=False
    ) as tf:
        tf.write(message)
        path = tf.name
    try:
        subprocess.run([*editor.split(), path], check=False)
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    finally:
        os.unlink(path)


def commit(message: str) -> None:
    result = run_git(["commit", "-F", "-"], input=message)
    if result.returncode != 0:
        _err(f"`git commit` failed:\n{result.stderr.strip()}")
        sys.exit(1)
    print(result.stdout.strip())


def review_loop(diff: str, api_key: str, model: str, auto_yes: bool) -> None:
    message = generate_message(diff, api_key, model)

    while True:
        print("\n" + "─" * 60)
        print(message)
        print("─" * 60)

        if auto_yes:
            commit(message)
            return

        choice = input("\n[a]ccept / [e]dit / [r]egenerate / [q]uit: ").strip().lower()
        if choice in ("a", "accept", ""):
            commit(message)
            return
        if choice in ("e", "edit"):
            message = edit_message(message)
        elif choice in ("r", "regenerate"):
            print("Regenerating…")
            message = generate_message(diff, api_key, model)
        elif choice in ("q", "quit"):
            print("Aborted. Your changes remain staged.")
            return
        else:
            print("Please choose a, e, r, or q.")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="commiter",
        description="Stage all changes and generate a commit message with a "
        "Fireworks-hosted model.",
    )
    parser.add_argument(
        "-y", "--yes", action="store_true", help="skip the prompt and commit immediately"
    )
    parser.add_argument("--model", help="override the model ID for this run")
    args = parser.parse_args()

    # Look for a .env in the current directory tree (not next to the installed
    # package), so a globally installed `commiter` still picks up a repo-local .env.
    load_dotenv(find_dotenv(usecwd=True))

    api_key = os.environ.get("FIREWORKS_API_KEY")
    if not api_key:
        _err(
            "FIREWORKS_API_KEY is not set. Add it to a .env file or export it. "
            "See .env.example."
        )
        sys.exit(1)

    model = args.model or os.environ.get("FIREWORKS_MODEL") or DEFAULT_MODEL

    ensure_git_repo()
    stage_all()

    diff = staged_diff()
    if not diff.strip():
        print("nothing to commit.")
        sys.exit(0)

    review_loop(truncate_diff(diff), api_key, model, args.yes)


if __name__ == "__main__":
    main()
