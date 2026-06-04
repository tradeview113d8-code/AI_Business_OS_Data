#!/usr/bin/env python3
"""
export_memory.py

Architecture-centric Repo Memory Generator
Principles:
- FACT > INFERENCE > UNKNOWN
- Never mark YES without evidence
- Separate verified facts from assumptions
- Environment-driven configuration
"""

import os
from pathlib import Path
from datetime import datetime
import requests

ROOT_DIR = Path(__file__).resolve().parent.parent

GIST_ID = os.getenv("GIST_ID")
GIST_FILENAME = os.getenv("GIST_FILENAME", "repo_memory.txt")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

IGNORE_DIRS = {
    ".git",
    "__pycache__",
    "venv",
    ".idea",
    "node_modules",
    "dist",
    "build",
}


def validate_env():
    if not GIST_ID:
        raise RuntimeError("Missing GIST_ID environment variable")

    if os.getenv("REPO_MEMORY_UPLOAD_ONLY") == "1" and not GITHUB_TOKEN:
        raise RuntimeError("Missing GITHUB_TOKEN environment variable")


def iter_files():
    for path in ROOT_DIR.rglob("*"):
        if not path.is_file():
            continue

        if any(part in IGNORE_DIRS for part in path.parts):
            continue

        yield path


def generate_memory():
    lines = []

    lines.append("# REPO MEMORY")
    lines.append(f"Generated: {datetime.utcnow().isoformat()} UTC")
    lines.append("")

    py_files = list(ROOT_DIR.rglob("*.py"))

    lines.append("## VERIFIED FACTS")
    lines.append(f"- Python files detected: {len(py_files)}")
    lines.append("")

    lines.append("## UNKNOWN AREAS")
    lines.append("- Manual architectural review recommended")
    lines.append("")

    lines.append("## FILE INVENTORY")
    for f in sorted(py_files)[:200]:
        try:
            rel = f.relative_to(ROOT_DIR)
        except Exception:
            rel = f
        lines.append(f"- {rel}")

    return "\n".join(lines)


def write_memory_file():
    content = generate_memory()
    output = ROOT_DIR / "repo_memory.txt"
    output.write_text(content, encoding="utf-8")
    print(f"Generated: {output}")
    return output


def upload_gist(content: str):
    url = f"https://api.github.com/gists/{GIST_ID}"

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }

    payload = {
        "files": {
            GIST_FILENAME: {
                "content": content
            }
        }
    }

    response = requests.patch(url, headers=headers, json=payload, timeout=60)

    if response.status_code != 200:
        raise RuntimeError(
            f"Gist upload failed: {response.status_code} {response.text}"
        )

    print("Gist updated successfully")


def main():
    validate_env()

    if os.getenv("REPO_MEMORY_ONLY") == "1":
        write_memory_file()
        return

    if os.getenv("REPO_MEMORY_UPLOAD_ONLY") == "1":
        path = ROOT_DIR / "repo_memory.txt"

        if not path.exists():
            raise FileNotFoundError("repo_memory.txt not found")

        upload_gist(path.read_text(encoding="utf-8"))
        return

    path = write_memory_file()
    upload_gist(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
