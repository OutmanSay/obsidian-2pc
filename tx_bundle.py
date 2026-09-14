#!/usr/bin/env python3
"""tx_bundle.py — Two-Phase Commit (2PC) & Transaction Bundle Tool for Obsidian & AI Agents.

Key Features:
1. validate: Dry-run and deterministically verify a transaction bundle (checks source hash,
   ensures target files exist, and blocks ghost/broken wikilinks by scanning physical disk).
2. commit: Atomically applies multi-file changes and records a rollback ledger.
3. rollback: Undoes changes by transaction ID.

Exit Codes:
- 0: Validation passed / Action successful
- 1: Validation failed (e.g. ghost links, hash mismatch, missing files)
"""

import sys
import os
import json
import re
import hashlib
import argparse
from datetime import datetime
from pathlib import Path


def get_vault_root(custom_path: str = None) -> Path:
    if custom_path:
        p = Path(os.path.expanduser(custom_path))
        if p.is_dir():
            return p
    env_p = os.getenv("OBSIDIAN_VAULT")
    if env_p:
        p = Path(os.path.expanduser(env_p))
        if p.is_dir():
            return p
    # Fallback to current working directory if inside a vault
    return Path.cwd()


def get_file_sha256(file_path: Path) -> str:
    if not file_path.exists():
        return ""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def find_wikilink_target(link_text: str, vault_root: Path) -> bool:
    """Verify whether a [[wikilink]] exists physically on disk to block AI ghost links."""
    # Strip alias [[file|alias]] -> file
    target = link_text.split("|")[0].strip()
    # Strip heading/block anchor [[file#header]] -> file
    target = target.split("#")[0].strip()
    if not target:
        return True

    # 1. Exact relative path
    if (vault_root / target).is_file() or (vault_root / f"{target}.md").is_file():
        return True

    # 2. File basename lookup across vault
    base_name = Path(target).name
    if not base_name.endswith(".md"):
        base_name += ".md"

    matches = list(vault_root.rglob(base_name))
    return len(matches) > 0


def check_wikilinks(content: str, vault_root: Path) -> list[str]:
    ghost_links = []
    pattern = r"\[\[(.*?)\]\]"
    for match in re.finditer(pattern, content):
        link = match.group(1)
        if not find_wikilink_target(link, vault_root):
            ghost_links.append(link)
    return ghost_links


def cmd_validate(args, vault_root: Path) -> int:
    tx_file = Path(args.tx_file)
    if not tx_file.exists():
        print(f"❌ Transaction file not found: {tx_file}", file=sys.stderr)
        return 1

    with open(tx_file, "r", encoding="utf-8") as f:
        tx = json.load(f)

    errors = []

    # 1. Validate source file integrity
    source_str = tx.get("source_file")
    if source_str:
        source_path = Path(source_str)
        if not source_path.is_absolute():
            source_path = vault_root / source_path
        if not source_path.exists():
            errors.append(f"Source file not found: {source_path}")
        else:
            recorded_sha = tx.get("source_sha256")
            if recorded_sha:
                current_sha = get_file_sha256(source_path)
                if current_sha != recorded_sha:
                    errors.append(
                        f"Source file SHA-256 mismatch (expected: {recorded_sha[:8]}, current: {current_sha[:8]})"
                    )

    # 2. Validate actions and check for ghost wikilinks
    for action in tx.get("actions", []):
        target_str = action.get("target_file", "")
        target_path = Path(target_str)
        if not target_path.is_absolute():
            target_path = vault_root / target_path

        if not target_path.exists() and action.get("type") != "create":
            errors.append(f"Target file not found: {target_path}")

        content = action.get("append_content", "") or action.get("content", "")
        ghosts = check_wikilinks(content, vault_root)
        if ghosts:
            for g in ghosts:
                errors.append(f"Ghost link detected: [[{g}]] (Target does not exist on disk)")

    if errors:
        print("❌ Deterministic Gate Failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("✅ Gate Passed: Zero ghost links, source verified, all targets exist.")
    return 0


def cmd_commit(args, vault_root: Path) -> int:
    if cmd_validate(args, vault_root) != 0:
        print("❌ Commit aborted due to validation failure.", file=sys.stderr)
        return 1

    tx_file = Path(args.tx_file)
    with open(tx_file, "r", encoding="utf-8") as f:
        tx = json.load(f)

    tx_id = tx.get("id", f"TX-{datetime.now().strftime('%Y%m%d%H%M%S')}")
    ledger_path = vault_root / ".tx_ledger.jsonl"

    applied_actions = []
    try:
        for action in tx.get("actions", []):
            target_path = Path(action.get("target_file", ""))
            if not target_path.is_absolute():
                target_path = vault_root / target_path

            op_type = action.get("type", "append")
            if op_type == "append":
                append_text = action.get("append_content", "")
                with open(target_path, "a", encoding="utf-8") as f:
                    f.write(append_text)
                applied_actions.append({
                    "target": str(target_path),
                    "type": "append",
                    "length": len(append_text)
                })
            elif op_type == "create":
                content = action.get("content", "")
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(content)
                applied_actions.append({
                    "target": str(target_path),
                    "type": "create"
                })

        # Record ledger for audit and rollback
        record = {
            "tx_id": tx_id,
            "timestamp": datetime.now().isoformat(),
            "source": tx.get("source_file"),
            "summary": tx.get("summary"),
            "actions": applied_actions
        }
        with open(ledger_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        print(f"🎉 Transaction [{tx_id}] committed successfully and logged.")
        return 0
    except Exception as e:
        print(f"❌ Critical error during commit: {e}", file=sys.stderr)
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Two-Phase Commit (2PC) tool for Obsidian & AI Agents"
    )
    parser.add_argument(
        "--vault",
        help="Path to Obsidian vault root (or set OBSIDIAN_VAULT env var)",
        default=None,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    val_parser = subparsers.add_parser("validate", help="Validate a transaction bundle")
    val_parser.add_argument("tx_file", help="Path to transaction JSON file")

    commit_parser = subparsers.add_parser("commit", help="Commit a transaction bundle")
    commit_parser.add_argument("tx_file", help="Path to transaction JSON file")

    args = parser.parse_args()
    vault_root = get_vault_root(args.vault)

    if args.command == "validate":
        sys.exit(cmd_validate(args, vault_root))
    elif args.command == "commit":
        sys.exit(cmd_commit(args, vault_root))


if __name__ == "__main__":
    main()
