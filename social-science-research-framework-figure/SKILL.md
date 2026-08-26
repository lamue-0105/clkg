---
name: social-science-research-framework-figure
description: Create publication-ready, editable SVG research framework diagrams for history and social science papers, grant proposals, literature reviews, theoretical models, methodological architectures, multi-scale historical studies, and network/GIS research. Use when the user asks to turn a paper, proposal, PDF, notes, image, or outline into a clear academic figure rather than a decorative infographic.
---

# Social Science Research Framework Figure

Use this skill to convert historical and social-science arguments into auditable academic diagrams. Prefer code-native SVG with editable text, explicit arrows, restrained color, and a layout that expresses scholarly relations rather than a generic workflow.

## Core Principle

Preserve the source argument before improving its appearance. Do not invent theories, cases, evidence, causal relations, dates, or contributions. If a relation is inferred, label it as an inference or ask for confirmation. Treat every arrow as a claim that must be supported by the source material.

## Workflow

Run the following stages in order. For a small request, combine adjacent text-only stages, but do not skip the semantic audit or final visual QA.

### Bootstrap — Set the Contract

Identify or reasonably infer:

- target: paper article, grant proposal, dissertation, review article, presentation, or exhibition;
- figure type: literature-review map, research framework, theory model, method architecture, historical multi-scale model, network/GIS schema, or contribution map;
- audience and reading direction: top-to-bottom, left-to-right, macro-to-micro, or center-outward;
- language, page ratio, expected final size, and whether the output must remain editable;
- required deliverables: SVG first; optionally PDF and high-resolution PNG.

If the user gives no preference, choose a white-background academic schematic, 16:9 working canvas, editable SVG, and Chinese labels when the source is Chinese.

### S0 — Build the Argument Foundation

Read the supplied source material and extract a compact evidence table:

| Element | Extract |
|---|---|
| Research object | people, institutions, documents, places, events, practices, or processes |
| Core question | one central question, not a list of topics |
| Scope | period, region, scale, and comparison boundary |
| Literature strands | established research paths and their relation |
| Theory/concepts | only concepts explicitly used or clearly required |
| Materials/evidence | archives, interviews, statistics, databases, maps, cases |
| Methods | textual, archival, spatial, network, comparative, ethnographic, or mixed |
| Mechanisms | how one condition, relation, or practice produces an outcome |
| Contributions | theoretical, empirical, methodological, policy, or heritage contribution |

Mark unsupported items as `待核实` instead of filling them from general knowledge. Keep source citations or section anchors in the working notes when available.

### S1 — Compile the Semantic Graph

Represent the figure as nodes and typed edges before drawing it.

Use these node classes where relevant:

- `context`: historical background, policy setting, regional environment;
- `problem`: empirical tension, research gap, or unresolved question;
- `literature`: research strand, debate, or limitation;
- `theory`: conceptual lens, analytical framework, or key construct;
- `material`: archive, corpus, interview, statistics, map, or case;
- `method`: method, operation, model, or analytical procedure;
- `mechanism`: process linking conditions, relations, and outcomes;
- `case`: village, city, institution, person, event, or comparison unit;
- `finding`: historical pattern, empirical result, or interpreted relation;
- `contribution`: theoretical, empirical, methodological, or practical value;
- `output`: article, database, map, exhibition, policy brief, or educational product.

Use typed edges instead of anonymous connectors:

- `背景约束`: context → problem or context → question;
- `问题提出`: problem → core question;
- `理论解释`: theory → mechanism or theory → analysis;
- `材料支撑`: material → analysis or material → finding;
- `方法处理`: method → material/analysis;
- `机制作用`: mechanism → finding/outcome;
- `尺度转换`: macro ↔ meso ↔ micro;
- `比较关系`: case ↔ case or region ↔ region;
- `综合提升`: finding → contribution;
- `成果转化`: contribution → output.

For every edge record source support, direction, and whether it is causal, chronological, comparative, or merely organizational. Do not use a causal arrow where the source only establishes association or sequence.

### S2 — Select the Scholarly Layout

Choose the simplest layout that preserves the argument:

1. **Literature review map**: four or fewer research strands → shared core question → three-layer research gaps → current study entry point.
2. **Research framework**: context → question → theory → material/data → method → analysis/mechanism → findings → contribution/output.
3. **Historical multi-scale model**: macro structure → regional or institutional network → village/family/person case → synthesis and historical meaning.
4. **Theory model**: conditions/constructs → mediating mechanisms → boundary conditions → outcomes; use dashed borders for propositions or tentative links.
5. **Network/GIS schema**: entities and sources → structured data → spatial/organizational networks → indicators and route verification → historical interpretation.
6. **Mixed framework**: use two aligned bands only when the source genuinely combines a conceptual model with an empirical workflow.

Avoid dashboard layouts, decorative cards, excessive section numbering, and arrows that only indicate visual alignment. Prefer hierarchy, whitespace, and short labels.

### S3 — Produce a Diagram Specification

Before writing SVG, define:

- canvas size and safe margins;
- reading order and primary spine;
- node inventory with exact visible text;
- edge inventory with arrow direction and line style;
- grouping boundaries and labels;
- color role for each semantic class;
- items moved to caption or正文 because they are too long for the figure.

Keep visible text concise: normally one title, one short subtitle, 3–6 words per node heading, and no more than 2–3 short lines per node. Put detailed explanations in the caption or accompanying prose.

### S4 — Draw the Editable SVG

Create the final figure directly as SVG whenever exact labels, arrows, Chinese text, or editability matter. Do not use raster image generation for the main scholarly diagram. Use image generation only for optional non-semantic decorative imagery, never for text-bearing nodes or evidence-bearing arrows.

SVG requirements:

- keep all labels as selectable `<text>` elements;
- use explicit `marker-end` arrowheads and unique IDs;
- define colors and typography in a top-level `<style>` block;
- use rounded rectangles or light grouping bands sparingly;
- preserve a consistent coordinate grid and aligned baselines;
- avoid embedded screenshots, gradients, 3D effects, clip-art, and unverified icons;
- include `role="img"` and a concise `<title>` where practical;
- write output to the user’s project folder with a descriptive Chinese filename.

### S5 — Audit and Package

Check the diagram in this order:

1. **Semantic completeness**: every essential node and relation from the specification appears.
2. **Arrow integrity**: no duplicate, dangling, reversed, hidden, or ambiguous arrows.
3. **Text integrity**: no clipped, overlapping, misspelled, or unreadable labels; preserve Chinese punctuation.
4. **Hierarchy**: the primary reading path is obvious at thumbnail size.
5. **Evidence discipline**: no claim exceeds the supplied source; uncertain relations are visually differentiated.
6. **Publication readiness**: white background, vector output, consistent typography, sufficient contrast, and no decorative elements that compete with the argument.

If rendering tools are available, validate the SVG XML, render a PNG preview, inspect the preview, and revise once if needed. Deliver the SVG first and optionally provide PDF/PNG derivatives. Also provide a one-paragraph framework summary and a suggested figure caption.

## Visual Standards

Use the detailed palette, typography, and layout rules in [references/visual-standards.md](references/visual-standards.md). Default to:

- white or near-white background;
- dark navy for primary structure and headings;
- muted blue, teal, sage, amber, or lavender as semantic accents;
- no more than five accent colors;
- no gradients, glow, heavy shadows, or poster-like decoration;
- strong contrast and redundant encoding through line style or shape, not color alone;
- consistent font family, with a CJK-capable sans-serif fallback.

## Interaction Rules

When the user provides a long paper or proposal, first return the extracted argument foundation and semantic graph in concise form before generating the final diagram, unless the user explicitly asks for direct generation. If the user supplies an existing figure, preserve its valid content but repair missing or surplus arrows only after reconstructing the intended graph.

When the user asks for “SCI风格” in a history or social-science context, interpret it as a clean, publication-ready academic schematic, not a biomedical illustration or computer-science architecture diagram. For Chinese humanities and social-science outputs, prioritize logical hierarchy, evidence traceability, and legible text over visual novelty.

