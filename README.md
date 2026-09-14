# Obsidian-2PC: Deterministic Two-Phase Knowledge Ingestion for AI Agents

> **Stop AI from polluting your Obsidian vault.**  
> Zero-friction capture during fast conversations, strict deterministic validation before writing to your core Wiki.

---

## 💡 The Core Problem (痛点)

When using AI CLI agents (like Claude Code, Codex, or OpenClaw) with Obsidian:
1. **Unchecked Writes Pollute the Vault**: Letting an LLM freely edit Markdown files leads to hallucinated wikilinks (ghost links), broken frontmatter, and wiped history.
2. **Manual Ingestion Leads to Burnout**: Having to manually review and link every single daily scratchpad leads to unmaintainable note hoarding. As Andrej Karpathy pointed out: *"Maintenance cost is the primary killer of personal knowledge bases."*
3. **Background Pipelines Fail**: Fully automated background cron jobs lack contextual judgment, producing generic summaries and cluttering your vault.

---

## 🛡️ The Two-Phase Commit (2PC) Pattern

Instead of choosing between complete automation and painful manual curation, **Obsidian-2PC splits knowledge lifecycle into two decoupled phases**:

```text
[ Daily Scratchpad / Quick Notes ]
               │
               ▼
   Phase 1: Zero-Friction Staging
   (Fast, silent append to notes/ or daily note; ZERO approval popups)
               │
               │ (Triggered on project milestones or explicit "synthesize" command)
               ▼
   Phase 2: Transaction Bundle (Dry-Run)
   (AI generates a concise ≤10-line proposal: Facts, Decisions, and Planned Diffs)
               │
               ▼
   Deterministic Gate (`tx_bundle.py validate`)
   (Physical disk scan: blocks hallucinated [[ghost-links]] and broken paths)
               │
               ▼ (Human reviews in 5 seconds -> "LGTM")
   Atomic Commit (`tx_bundle.py commit`)
   (All-or-nothing disk write + audit ledger for 1-click rollback)
```

---

## 🚀 Quick Start

### 1. Requirements
- Python 3.9+ (Standard library only, zero external dependencies).
- Obsidian Vault.

### 2. Basic Usage

Set your vault path (or pass `--vault /path/to/vault`):
```bash
export OBSIDIAN_VAULT="/path/to/your/Obsidian Vault"
```

#### Step 1: Validate a Transaction (Deterministic Gate)
Before applying any change, scan the physical disk to ensure all target files and `[[wikilinks]]` actually exist:
```bash
python3 tx_bundle.py validate transaction.json
```
If the AI hallucinated a link `[[non-existent-note]]`, `tx_bundle.py` exits with code `1` and prints the exact broken references.

#### Step 2: Atomic Commit
Once validated and approved by human:
```bash
python3 tx_bundle.py commit transaction.json
```
- Applies all append/create operations simultaneously.
- Appends an audit trail to `.tx_ledger.jsonl` in your vault root for instant rollbacks.

---

## 📋 Transaction Bundle Schema

Transactions are defined in lightweight JSON:

```json
{
  "id": "TX-20260914-001",
  "source_file": "00-OS/notes/2026-09-14-quick-note.md",
  "summary": "Link scratchpad into Architecture MOC",
  "actions": [
    {
      "type": "append",
      "target_file": "wiki/architecture.md",
      "append_content": "\n- Synthesis: [[2026-09-14-quick-note|Two-Phase Commit in Obsidian]].\n"
    }
  ]
}
```

---

## 🤝 Prompt Template for Your Agent (`CLAUDE.md`)

Add this prompt rule to your agent's system prompt (e.g. `CLAUDE.md`):

```markdown
### Knowledge Ingestion Rule
1. **Daily Capture**: When user says "save/note this down", silently write to staging/inbox without confirmation. Never touch core wiki pages directly.
2. **Synthesis / Ingestion**: When user asks to "synthesize/ingest into wiki":
   - Generate a concise (<= 10 lines) Transaction Proposal covering: Source, Fact/Decision, and Target files.
   - Run `python3 /path/to/tx_bundle.py validate <tx.json>` to verify zero ghost links.
   - Only execute `commit` after explicit user confirmation.
```

---

## License

MIT License. Feel free to adapt into your agent tools or personal workflows.
