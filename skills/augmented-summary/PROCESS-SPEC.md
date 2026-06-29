# Augmented Summary — Process Specification

A standardized, repeatable pipeline that turns a single book/textbook chapter into an **Augmented Summary**: an order-faithful summary, deeply linked to internal and external concepts, with domain-expert expansions of everything the chapter mentions but doesn't fully explain, plus learning scaffolding and an interactive concept graph.

Version 1.0. Designed for technical non-fiction (initially *Designing Machine Learning Systems*, Chip Huyen) but domain-agnostic.

---

## Inputs

| Input | Required | Notes |
|---|---|---|
| Chapter source (PDF page range, or extracted text) | Yes | The chapter to summarize. |
| Book context | Recommended | Full TOC + chapter list, to resolve forward/backward associations. |
| Prior chapters' concept records | Optional | Enables the cross-chapter graph (add-on C). |
| Reference cache folder | Optional | Folder where resolved external PDFs/links are stored and reused. |

## Outputs

1. `ChapterN-Augmented-Summary.md` — the narrative summary with inline associations, expansions, exercises, and difficulty tags.
2. `ChapterN-Concept-Graph.html` — interactive concept graph (nodes = concepts/references; edges = associations; clickable links).
3. `ChapterN-concepts.json` — machine-readable concept records (feeds the cross-chapter graph and future runs).
4. `ChapterN-references.md` — annotated bibliography of every cited source (this is the artifact already produced for Ch 4).

---

## Pipeline stages

### Stage 0 — Intake
Confirm chapter page range, output folder, and which add-ons are enabled. Locate the reference cache.

### Stage 1 — Structural parse
Extract, in reading order: section/subsection headings and their page numbers; every footnote/endnote and inline citation; figures/tables; and the author's "for a comprehensive review, see…" pointers. Produce an ordered list of **concept anchors** (heading or first mention) and a **reference list** (full citation + any link).

### Stage 2 — Ordered narrative summary with associations
Summarize the chapter **in the exact order the author introduces each concept**. As each concept appears, attach typed associations:

| Association | Symbol | Meaning |
|---|---|---|
| Backward | ◀ | Builds on a concept introduced earlier in this chapter or an earlier chapter ("as covered in §X / Ch N"). |
| Forward | ▶ | Will be expanded later in this chapter or a future chapter ("revisited in Ch N"). |
| Jump / lateral | ↔ | Related concept elsewhere in the book or a sibling idea, not on the main through-line. |
| External | ⧉ | Points to an external reference, tool, dataset, or paper. |

Each association names its target and (where known) the section/chapter/URL so it can become a graph edge.

### Stage 3 — Reference resolution & out-of-scope detection
For every reference and every named-but-thin concept, classify as **in-scope** (chapter explains it sufficiently) or **out-of-scope** (mentioned, deferred, or "see external review"). Resolve external references to stable URLs (arXiv/DOI) and, when a reference cache is configured, download the PDF for offline grounding. Out-of-scope items become the work queue for Stage 4.

### Stage 4 — Domain expansion (sub-agent)
Dispatch each out-of-scope item to the **`ml-concept-expander`** sub-agent (see `/agents`). It returns, per concept: a 200–350 word practitioner-level expansion with the actual mechanism/math; verified key reference(s); hands-on resources; prerequisites; and a difficulty rating. The expander grounds claims in cached survey PDFs where available and must not fabricate URLs.

### Stage 5 — Verification (sub-agent)
Dispatch all Stage-4 output to the **`expansion-verifier`** sub-agent. It independently checks formulas, claims, citation accuracy, and URL validity, and flags anything unsupported. Items failing verification are corrected or marked `⚠ unverified` rather than silently shipped.

### Stage 6 — Enrichment add-ons
- **(A) Prerequisite & difficulty tags** — every concept record carries `prerequisites[]` and `difficulty ∈ {Intro, Intermediate, Advanced}`, enabling an ordered learning path.
- **(B) Hands-on exercises & projects** — for each major concept, a concrete exercise, library/function, dataset, or mini-project.
- **(C) Cross-chapter concept graph** — merge this chapter's `concepts.json` into a running book-level graph so concepts link across chapters (backward/forward associations resolve to real nodes).
- **(D) Verification pass** — Stage 5; required when expansions will be relied upon.

### Stage 7 — Visual generation
Render `ChapterN-Concept-Graph.html`: an interactive force/cluster graph. Nodes are color-coded by section and sized by importance; difficulty shown via badge. Clicking a node opens a panel with the summary blurb and live links: jump to the chapter section, open the referenced paper (in-folder PDF or URL), open external tools/tutorials, and the hands-on exercise. Edges render the association type. Cross-chapter edges (add-on C) are dashed.

### Stage 8 — Assembly & QA
Stitch Stages 2–6 into the Markdown deliverable, embed the concept JSON, and run a final consistency check (every association has a target; every out-of-scope concept has an expansion or an explicit `⚠`; every external link resolved or flagged).

---

## Concept record schema (`concepts.json`)

```json
{
  "id": "weak-supervision-label-model",
  "label": "Weak supervision label model (Snorkel)",
  "chapter": 4,
  "section": "Labeling > Handling the Lack of Labels > Weak Supervision",
  "order": 11,
  "scope": "out-of-scope",
  "summary": "Combine noisy labeling functions into denoised probabilistic labels via a generative label model.",
  "difficulty": "Advanced",
  "prerequisites": ["probabilistic graphical models", "maximum likelihood / EM"],
  "associations": [
    {"type": "backward", "target": "hand-labeling", "ref": "Ch4 §Labeling"},
    {"type": "external", "target": "Ratner et al. 2016, Data Programming", "url": "https://arxiv.org/abs/1605.07723"}
  ],
  "expansion": "…200–350 words…",
  "hands_on": ["snorkel LabelModel spam tutorial"],
  "references": [{"citation": "Ratner et al., Snorkel, VLDB 2018", "url": "https://arxiv.org/abs/1711.10160"}],
  "verified": true
}
```

---

## Roles (sub-agents)

| Agent | File | Responsibility |
|---|---|---|
| `ml-concept-expander` | `/agents/ml-concept-expander.md` | Stage 4 — deep, cited expansions of out-of-scope concepts. |
| `expansion-verifier` | `/agents/expansion-verifier.md` | Stage 5 — independent fact/citation/URL verification. |

Both are dispatched via the Agent tool. For non-ML books, clone `ml-concept-expander` and swap the domain framing (e.g., `bio-concept-expander`).

---

## Quality bar (definition of done)

- Summary order matches the chapter's actual introduction order.
- Every concept carries ≥1 typed association; the through-line (backward/forward) is unbroken.
- Every out-of-scope concept has a verified expansion or an explicit `⚠ unverified` flag.
- Every external link resolves to a stable URL (arXiv/DOI preferred) or is flagged.
- The interactive graph opens standalone (no server) and every node link works.
- `concepts.json` validates against the schema and merges cleanly into the book graph.
