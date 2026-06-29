---
name: augmented-summary
description: >
  Generate an "Augmented Summary" of a book or textbook chapter: an order-faithful
  summary with typed associations (backward/forward/lateral/external), domain-expert
  expansions of concepts the chapter only mentions, learning scaffolding (prerequisites,
  difficulty, hands-on exercises), an annotated bibliography, and an interactive concept
  graph. Use when the user says "augmented summary", "augment this chapter", "deep-dive
  summary with references", or asks to summarize a chapter AND expand its external/out-of-scope
  references. Works best with a chapter PDF and a reference cache folder.
argument-hint: "[chapter PDF + page range] [--depth direct|deep] [--refs all|papers] [--visual]"
---

# Augmented Summary

Produce an Augmented Summary for a chapter by following the pipeline in `PROCESS-SPEC.md`. Read that spec first; this file is the operational checklist.

## When to use
- User wants more than a plain summary: order-faithful narrative + concept links + expansions of referenced/out-of-scope material + optional interactive visual.

## Required clarifications (ask once, up front)
1. Which chapter (PDF + page range) and output folder?
2. Recursion depth for references — direct citations only (default) vs. deeper?
3. Which references to include — all, or substantive papers only?
4. Output format(s) — Markdown is default; add interactive HTML graph? Add-ons (prereq tags, exercises, cross-chapter graph, verification pass)?

## Procedure
1. **Parse structure** (Stage 1): extract section order + headings + page numbers, all footnotes/citations, and "for a comprehensive review, see…" pointers. For PDFs, use `pypdf` (`pip install pypdf --break-system-packages`).
2. **Ordered summary + associations** (Stage 2): summarize in the author's introduction order; tag each concept with ◀ backward / ▶ forward / ↔ lateral / ⧉ external associations naming their targets.
3. **Resolve & classify** (Stage 3): for each reference and thin concept, mark in-scope vs out-of-scope; resolve external links to arXiv/DOI; cache PDFs if a folder is configured.
4. **Expand** (Stage 4): dispatch each out-of-scope concept to the `ml-concept-expander` sub-agent (`agents/ml-concept-expander.md`). One batch per call.
5. **Verify** (Stage 5): dispatch expansions to the `expansion-verifier` sub-agent (independent invocation). Correct or flag `⚠` failures.
6. **Enrich** (Stage 6): add prerequisites + difficulty per concept; add a hands-on exercise per major concept; merge `concepts.json` into the book-level graph.
7. **Visualize** (Stage 7): render `ChapterN-Concept-Graph.html` — interactive concept graph with clickable links to sections, papers, tools, and exercises. Base it on `templates/concept-graph.template.html`.
8. **Assemble & QA** (Stage 8): build `ChapterN-Augmented-Summary.md` from `templates/augmented-summary-template.md`, embed `concepts.json`, and run the definition-of-done checks.

## Outputs
`ChapterN-Augmented-Summary.md`, `ChapterN-Concept-Graph.html`, `ChapterN-concepts.json`, `ChapterN-references.md`.

## Definition of done
See PROCESS-SPEC.md "Quality bar". Key checks: order fidelity; every concept has ≥1 association; every out-of-scope concept verified-or-flagged; every external link resolved-or-flagged; graph opens standalone with working links.

## Notes
- For non-ML domains, clone `ml-concept-expander` and reframe the domain (e.g., `bio-concept-expander`).
- The verifier MUST be a separate sub-agent invocation from the expander to preserve independence.
