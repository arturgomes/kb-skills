# kb-skills

Claude skills for knowledge-base driven development. Query and review code/designs against your personal knowledge base built from books and validated principles — not improvised answers.

## Skills

### `ask-kb`
Query your KB with a question. Claude reads `kb-registry.yaml`, selects only the relevant sources, and answers with citations. If the answer isn't in the KB, it says so.

### `consult-kb`
Review code, RFCs, ADRs, or design docs against your KB. Produces structured feedback — violations 🔴, tensions 🟡, aligned patterns 🟢, suggestions 💡 — every finding backed by a source citation.

### `kb-indexer`
Ingest PDFs, EPUBs, and documents into structured KB files. Extracts principles, decision frameworks, and patterns. Updates `kb-registry.yaml` automatically.

## Setup

1. Install the `.skill` files in Claude
2. Create `~/kb/kb-registry.yaml` (see `ask-kb/references/kb-registry-example.yaml`)
3. Run `kb-indexer` on your first book
4. Ask away with `ask-kb`

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
