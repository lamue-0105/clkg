---
name: clkg-researcher-needs
description: Design, pilot, analyse, or revise researcher-needs studies for CLKG, including cross-type cultural heritage interviews, questionnaires, workflow maps, card-sorting exercises, and evidence-based requirement synthesis. Use when work concerns cultural heritage researchers' data-organisation practices, research workflows, data provenance, uncertainty, ethics, or translating findings into CLKG design decisions; do not use for software implementation alone.
---

# CLKG Researcher Needs

Use this skill to discover and validate the needs of cultural heritage researchers before proposing CLKG features or implementation.

## Principles

- Treat the unit of inquiry as one recent, concrete research task, not a respondent's imagined ideal system.
- Organise discovery around the workflow `materials → organisation → evidence and interpretation → research output`, not a single heritage category or data format.
- Treat UNESCO World Heritage, documentary heritage, movable cultural property, and intangible cultural heritage as overlapping governance vocabularies. Permit multiple selections; do not present them as one exclusive hierarchy.
- Separate facts, expert judgments, and future wishes in notes and analysis. A stated need is a hypothesis until triangulated with an example, artefact, or additional respondent.
- Preserve human responsibility for historical interpretation, community consent, access decisions, and publication-level claims.
- Do not claim that survey results validate an ontology or a system. Report what they support, what they challenge, and what remains untested.

## Choose the study mode

| Need | Use |
| --- | --- |
| Discover unknown workflows, exceptions, and field vocabulary | Semi-structured contextual interviews. Ask the participant to reconstruct a recent task with real materials. |
| Compare recurring needs across roles, heritage types, or data modalities | The questionnaire in `references/questionnaire-blueprint.md`. |
| Test whether proposed labels or groupings make sense to researchers | Open or hybrid card sorting, followed by short probing questions. |
| Test a draft form for ambiguity, burden, and missing options | Cognitive pilot: ask participants to think aloud while answering. |
| Translate findings into CLKG research/design claims | The interpretation rules in `references/clkg-evidence-map.md`. |

Begin with interviews when terms, roles, workflows, or answer options are uncertain. Do not substitute an AI-simulated persona for real participants.

## Discovery workflow

1. Define the decision the study must inform, such as validating the cross-type core model, prioritising a pilot workflow, or identifying data-governance requirements.
2. Build a purposive sample across heritage scope, research role, data modality, and research stage. Include cross-category projects rather than forcing a single primary type.
3. Run 6–8 contextual interviews or cognitive pilots before distributing a formal questionnaire. Record consent and remove direct identifiers from working notes.
4. For each interview, capture: trigger, inputs and their locations, actual steps and workarounds, decisions and exceptions, outputs, verification criteria, ownership, and sensitive-data constraints.
5. Use the core questionnaire unchanged for comparability. Add a conditional GIS, oral-history/community, or documentary-heritage module only when the participant selected the relevant material type.
6. Keep closed questions for comparison, scales for intensity, and no more than two or three high-value open questions for missing language and concrete cases.
7. Pilot the form for understanding, not agreement. Revise ambiguous terms, overlapping answer options, excessive matrices, and missing `not applicable` choices.
8. Analyse results by both common workflow needs and subgroup differences. Do not infer that a difference is statistically meaningful if subgroup sizes are too small.
9. Produce an evidence ledger that links each finding to participants, task contexts, evidence strength, affected CLKG concept, and an explicit next validation step.

## Interview guide

Ask in this order; follow the participant's actual case rather than reading questions mechanically.

1. What research question and output did this task serve?
2. Please walk through the most recent real case from first material to final map, dataset, argument, or publication.
3. Which step required the most rework or depended on personal expertise?
4. Which sources are authoritative, who updates them, and how are contradictory or uncertain materials handled?
5. What information must remain linked to the final research claim for it to be credible?
6. Which actions require researcher, institution, community, or domain-expert approval?
7. What may not be disclosed, retained, or redistributed?
8. What would have to change for this workflow to be meaningfully better?

## Card sorting protocol

Use card sorting only after participants have described real work.

- Prepare cards for `ResearchCollection`, heritage-object types, `DataAsset`, `Evidence`, `AnalysisSnapshot`, source, version, authority, and rights/access concepts.
- Ask participants to group by how they would find, describe, or reuse materials; do not ask them to reproduce the proposed database schema.
- Ask why a card belongs in a group and whether it can belong in more than one group.
- Record labels, disagreements, unplaced cards, and terms participants introduce.
- Interpret clusters as usability evidence for vocabulary and navigation, not as proof of ontological truth.

## Ethics and data handling

- State purpose, voluntary participation, estimated time, storage arrangement, contact method, and withdrawal route before collecting answers.
- Keep contact details separate from survey responses.
- Never request original sensitive materials, exact vulnerable-site coordinates, personal data, or community-restricted knowledge merely to illustrate a workflow.
- For oral history and community knowledge, ask about consent, access scope, attribution, and the right to revise or withdraw; do not assume a recording is freely reusable.

## Output requirements

Deliver findings in five parts:

1. A one-sentence problem statement tied to a real research workflow.
2. A workflow map with inputs, transformations, decisions, exceptions, outputs, and owners.
3. A ranked list of shared needs and subgroup-specific needs, with counts and qualitative examples kept distinct.
4. An evidence-to-CLKG map using `references/clkg-evidence-map.md`.
5. An uncertainty register listing missing samples, ambiguous answers, ethical constraints, and the next validation action.

Read `references/questionnaire-blueprint.md` when drafting, reviewing, translating, or piloting the questionnaire. Read `references/clkg-evidence-map.md` when coding responses or making research/design claims.
