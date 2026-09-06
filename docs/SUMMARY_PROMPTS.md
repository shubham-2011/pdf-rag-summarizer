# SUMMARY_PROMPTS.md

Prompts for the Summary & Roadmap path (`summarizer_service.py`). Map-reduce: one map call per chunk group, one reduce call to combine.

Plain language is a constraint on *wording*, never on accuracy. A simpler summary that drops a qualifier is worse than a denser one that keeps it — and with no validation stage downstream, nothing catches the loss.

## Plain-language rules

These go in every prompt below. Stated as rules the model can check, not as "be clear".

| Rule | Why |
|---|---|
| Sentences average under 20 words | The single biggest readability lever |
| Define a technical term the first time, then reuse it | Dropping the term entirely loses precision; explaining it every time is padding |
| Active voice, named actor | "The model scored 87%" beats "an accuracy of 87% was achieved" |
| Concrete numbers over vague quantifiers | "6 of 9 features" beats "several features" |
| No filler openers | "This document discusses…", "It is important to note…" |
| One idea per sentence | Splitting a clause is almost always the fix |

**Never simplify away:** numbers, units, conditions ("only when…"), limitations, negations, or uncertainty the source expressed. If a fact cannot be said simply, say it plainly and add a short explanation — do not drop it.

---

## Prompt 1 — Map (per chunk group)

### System

```text
You extract the key points from one section of a document. You write in plain, direct
language for a reader who is not a specialist. You output JSON and nothing else.
```

### User

```text
Document section {i} of {n}:
{chunk_text}

Extract the points a reader would need to understand this section.

Return JSON only:
{
  "section_topic": "<what this section is about, under 10 words>",
  "points": [
    {
      "point": "<one plain sentence, under 25 words>",
      "kind": "finding|method|definition|limitation|number|recommendation",
      "locator": "<page, section heading, or table reference from the metadata>",
      "terms_used": ["<technical term that will need defining, if any>"]
    }
  ],
  "tables": [
    {"what_it_shows": "<one sentence>", "key_values": "<the 2-3 numbers that matter>",
     "locator": "<where>"}
  ],
  "has_substance": true
}

Rules:
1. Only what this section states. Do not infer, and do not fill gaps from general knowledge.
2. Keep every number, unit, and condition exactly as written. Do not round, and do not turn
   "up to 87%" into "87%".
3. Tables are content, not decoration. If a table is present, extract what it shows and its
   key values. A summary that ignores tables misses where the results usually live.
4. Set has_substance to false for boilerplate, page furniture, or headers with no content,
   and return empty points. This keeps filler out of the reduce step.
5. Plain wording: short sentences, active voice, no filler openers.
6. Do not write a summary here. Extract points; the reduce step writes prose.
```

## Prompt 2 — Reduce (combine into the summary)

### System

```text
You write short, plain-language document summaries from extracted points. You write for a
capable adult who does not know this field. You never add information that is not in the
points you were given.
```

### User

```text
Document: {title}
Sections: {n}
Type: {domain}

Extracted points, in document order:
{mapped_points}

Write a summary the reader can understand in one pass.

Structure:
1. **What this is** — one or two sentences. What kind of document, what it covers.
2. **The main points** — 3 to 6 bullets, most important first. Each starts with the point
   itself, not a lead-in.
3. **Key numbers** — results, metrics, table values that matter. Keep units and conditions.
   Omit this section if the document has none; do not invent one.
4. **Limits** — what the document says it does not cover, or where it is uncertain. Omit if
   the document states none.

Plain language rules:
- Sentences average under 20 words.
- Define each technical term the first time in a short clause, then use the term normally.
  "The model uses a random forest — many decision trees voting together — to classify..."
- Active voice with a named actor.
- Concrete numbers, never "several" or "various" where a count exists.
- No filler openers: "This document discusses", "It is worth noting", "In conclusion".
- One idea per sentence.

Accuracy rules, which outrank the wording rules:
1. Use only the points supplied. Do not add context, background, or interpretation from
   general knowledge, however obviously true.
2. Keep every number, unit, and condition exactly. Never round, never drop a qualifier to
   shorten a sentence. "Accurate only on balanced data" must not become "accurate".
3. Cite the locator after each factual claim, like [p. 4] or [Table 2].
4. Cover the whole document. Points come in order — if your bullets all draw from the first
   third, you have dropped the rest. Check the last few sections are represented.
5. Never claim a conclusion the document did not state.
6. If the points are too thin to summarise, say so plainly instead of padding.

Length: 150-300 words. Shorter is better if the document is thin.
```

## Prompt 3 — Roadmap (the learning-path view)

### System

```text
You turn a document into a learning path: what to understand first, and what it unlocks.
You write in plain language. You output JSON and nothing else.
```

### User

```text
Document: {title}
Extracted points, in document order:
{mapped_points}

Build a learning roadmap: the order a newcomer should tackle this in.

Return JSON only:
{
  "prerequisites": ["<what the reader should already know, or [] if none needed>"],
  "stages": [
    {
      "stage": 1,
      "title": "<short, plain>",
      "learn": "<what to understand here, 1-2 plain sentences>",
      "why_first": "<what later stages depend on this, one clause>",
      "covers": "<locators, e.g. pp. 1-4>",
      "effort": "quick|moderate|deep"
    }
  ],
  "not_covered": ["<what a reader might expect here but the document does not address>"]
}

Rules:
1. Order by dependency, not by page order. If section 7 explains a term section 2 uses,
   section 7 comes first.
2. 3 to 6 stages. More than that is a table of contents, not a roadmap.
3. Every stage maps to real content with a locator. Do not invent a stage to round out the
   structure.
4. not_covered is derived from the document's own stated scope and gaps — not from your
   opinion of what it should have included. Return [] if unclear.
5. Plain language throughout. Stage titles are descriptive, not clever.
```

---

## Register toggle

If you expose a "simple language" control, vary only the wording block. **Never vary the accuracy rules** — a simpler register must not be a less accurate one.

**Standard** (default): the rules above.

**Plain** (simpler): append to the reduce prompt:

```text
Additional wording constraints:
- Sentences average under 15 words.
- Prefer everyday words: "use" over "utilise", "before" over "prior to", "about" over
  "approximately", "shows" over "demonstrates".
- Explain every technical term in the sentence where it first appears, even common ones.
- Avoid nested clauses. Split into two sentences instead.
- Aim for a reading level around grade 8-9.

These change wording only. Every number, unit, condition and limitation stays exactly as
it is. If a fact resists simple phrasing, state it plainly and add one short explanatory
sentence — never drop it.
```

---

## Verification

Plain-language output is easy to check mechanically. Add these to `test_d3_*`:

```python
def test_summary_readability(summary):
    sentences = [s for s in re.split(r'[.!?]+', summary) if s.strip()]
    avg = mean(len(s.split()) for s in sentences)
    assert avg < 20, f"average sentence {avg:.1f} words"

    longest = max(sentences, key=lambda s: len(s.split()))
    assert len(longest.split()) < 40, f"a {len(longest.split())}-word sentence"

    for filler in ("this document discusses", "it is worth noting",
                   "it is important to note", "in conclusion", "delve into"):
        assert filler not in summary.lower()

def test_numbers_survive_simplification(summary, source_numbers):
    """Plain language must not round or drop values."""
    missing = [n for n in source_numbers if n not in summary]
    assert not missing, f"numbers lost: {missing}"

def test_qualifiers_survive(summary):
    """The dangerous failure: 'accurate only on balanced data' -> 'accurate'."""
    ...  # check each source qualifier near its claim
```

That second test is the one that matters. Readability catches bad writing; the qualifier check catches simplification that silently changes meaning — and with no validation stage, nothing downstream will.

## Coverage

Map-reduce drops tail sections on long documents. The reduce prompt says to check the last sections; verify it actually happened:

```python
def test_summary_covers_tail(summary, locators):
    """Fails when every citation points at the opening third."""
    pages = [int(p) for p in re.findall(r'p\.\s*(\d+)', summary)]
    assert max(pages) > total_pages * 0.6, "summary only covers the opening sections"
```

Test with a short and a long document and compare. If coverage degrades with length, the reduce step is compressing the tail away — a prompt change will not fix that, the map output needs chunking into multiple reduce passes.

## Notes for this system

- Locators are format-dependent. PDF gets `[p. 4]`; native DOCX gets `[Section 2]` or `[Table 3]` since it has no pages. See `docs/FORMAT_UNITS.md`.
- Tables carry the results in most technical documents. The map prompt extracts them separately so the reduce step cannot skip them — a summary of an ML report with no metrics in it has missed the point.
- No validation stage. These prompts are the only thing keeping the summary grounded, so treat edits to the accuracy rules as higher-risk than edits to the wording rules.
