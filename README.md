# kb-skills

Claude skills for knowledge-base driven development. Query and review code/designs against your personal knowledge base built from books and validated principles — not improvised answers.

## Skills

### `ask-kb`
Query your KB with a question. Claude reads `kb-registry.yaml`, selects only the relevant sources, and answers with citations. If the answer isn't in the KB, it says so.

### `consult-kb`
Review code, RFCs, ADRs, or design docs against your KB. Produces structured feedback — violations 🔴, tensions 🟡, aligned patterns 🟢, suggestions 💡 — every finding backed by a source citation.

### `add-pdf-to-kb` ⭐ NEW
Automated workflow for adding PDFs/EPUBs to your KB. Wraps `ebook_to_kb.py` to extract content, create structured markdown files, and update `kb-registry.yaml` automatically. Just say "add book.pdf to my KB" and it handles everything.

### `kb-indexer`
Manual workflow for ingesting PDFs, EPUBs, and documents. Use `add-pdf-to-kb` for automated processing, or this skill for custom extraction with specific guidance.

## Setup

1. **Install the skills**: Copy skill directories to `~/.claude/skills/`
   ```bash
   cp -r ask-kb consult-kb add-pdf-to-kb kb-indexer ~/.claude/skills/
   ```

2. **Install Python dependencies**:
   ```bash
   pip install pdfplumber pypdf ebooklib beautifulsoup4 pyyaml
   ```

3. **Add your first book**:
   ```
   Claude: add ~/Downloads/your-book.pdf to my KB
   ```

4. **Query your KB**:
   ```
   Claude: ask-kb "how should I handle distributed transactions?"
   ```

## KB Structure

```
~/kb/
├── kb-registry.yaml          # Index — Claude reads this first
├── architecture/
│   ├── building-microservices.md
│   └── my-principles.md
├── engineering/
│   └── clean-code.md
└── strategy/
    └── playing-to-win.md
```

## The idea

Vibe coding with guardrails. You keep prompting freely, but architectural decisions stay consistent because Claude consults the same principles every session — the ones you've already validated.

```
Without KB: "build an ingestion service"
→ Claude invents something different every time

With KB: "build an ingestion service"  
→ Claude checks your KB, sees you use saga + event sourcing
→ Follows the patterns you've already decided on
```
