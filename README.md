# Nexus Language & Nexus Number System

**A work of the Nexus Group — 넥서스 그룹의 작품입니다.**

> **v0.2.0 (2026-11-07):** Definitions rewritten from the essence up.
> The v0.1.x text described what the system *does*; this edition states
> what it *is*. Registered data (dictionaries, measured figures) is
> unchanged — meanings never change; documents grow by addition.

---

## The essence — a name is not the thing

A building stands in New York. People call it the Empire State
Building. A snake looking at the same building does not call it that;
a visitor from another world would give it a name in their own tongue.
The thing exists; the name is only a label that some community agreed
on for its own convenience. No name is the eternal name, and no name
is the "correct" name — had the first person to name corn chosen a
different word, corn would carry that word today.

**Nexus Language is built on that fact.** Every word used to write
programs and machine state is cut down to word-sized units, and each
unit is defined as **one symbol**. A ten-letter word becomes one
symbol; when that word appears ten times in a brain, it is written as
one symbol ten times — a tenth of the bulk. The vocabulary of machine
language is finite, so every word can be defined; when a symbol is
missing, we mint one and agree on it. The dictionary's rule — *a
registered meaning never changes; growth is by new registration
only* — is the lock that keeps those agreements fixed.

Machine-to-machine conversation is where this system is *used*. The
definition system itself is what it *is*.

## What this is

Out of µTAG (2025), a tag-capsule protocol for passing direction and
context between AIs, Nexus Language adds what a protocol needs to
become a language: a fixed grammar, an immutable dictionary, a
deterministic code-layer interpreter, and a book of laws with
three-valued verdicts (pass / hold / reject).

**The Nexus Number System** is its sibling, built on the same
principle. A Nexus number carries three things in one body:

- **Value** — the number itself; arithmetic stays ordinary
  mathematics, with the operator symbols everyone shares
  (+ − × ÷ √ …).
- **Intensity** (세기 — depth/brightness) — how many times the same
  number runs in a row, folded into the number itself instead of
  being written out repeatedly. The number of gradations is an
  *agreement*, not a physical limit: between any two steps the scale
  divides fractally, and we fix the steps by convention — a
  hundredth, a millionth, whatever the system declares.
- **Size as weight** (중량) — a number's size carries weight; the
  deeper, the heavier, up to a maximum weight fixed by agreement.
  Nothing in the system is heavier than that.

The *pattern layer* sits on top: the grain (결) formed by values,
intensities, and weights across a set of numbers is registered in a
dictionary under one symbol, so the symbol **means** the pattern
instead of replacing the numbers.

Two companion methods complete the package:

- **Akashic Search** — don't store the world; know how to find it.
- **Tag-born Records** — records generated in tag form at the moment
  they are created, never translated afterwards from prose.

## Measured results

All figures come from tests run against a live system, documented in
`language/패턴언어_해석효율시험_2026-11-05.md`.

| Test | Result |
| --- | --- |
| Status reports, 20 items — tokens, pattern language vs prose | **194 vs 612 (−68.3%)** |
| Status reports, 20 items — tokens, pattern language vs JSON | **194 vs 972 (−80.0%)** |
| Read-back accuracy — pattern language (code parse) | **100% (20/20)** |
| Read-back accuracy — prose (model re-read, 10-item sample) | 48.8% of fields |
| Interpretation — code interpreter | **100%** (roundtrip 16/16, collision check 0) |
| Interpretation — local AI models, 12 tasks, full marks | 7/12 (4B waiter) · 5/12 (8B kitchen) |
| Class-consistency check | 398/398 valid claims pass · 796/796 false claims caught |
| Tag-born records, ledger-shared form | −16.2% tokens vs prose (measured average) |

The honest reading: **the language lives at the code layer.**
Computers parse it perfectly; AI models read it only partially, so
wherever a model is involved, the code layer expands the symbols and
hands over plain text.

**What shrinks, and what does not** (simulation, 2026-11-07, on the
Qwen3-4B pattern dictionary): describing a brain's 398 tensors by
listing values takes ≈48 GB of text; describing the same brain in
Nexus patterns takes ≈16 KB — the *description, direction, and
oversight layer* collapses by over 99.99%. The weight values
themselves do **not** shrink: patterns mean values, they never
replace them, and run-folding inside the weight body yields only an
estimated 0.5–2%. The operating layer (records, status, direction)
is measured at −16% to −80%.

## Brain-frame conversion — repeated A/B measurement (2026-11-07)

The same local model (Qwen3-14B class) was run under two operating
frames — the previous frame, close to the bare model, and a frame
rebuilt on the Nexus systems with a code layer enforcing hard
boundaries — and measured on 18 fixed questions × 3 rounds × both
sides (108 runs, 0 errors). Full method, tables, raw data, and
limitations: [`brain-comparison/`](brain-comparison/).

| Measure | Result |
| --- | --- |
| Mean response time | 26.4 s → 25.3 s (**−4.2% — inside ±40% round drift; no speed claim is made**) |
| Payment-execution request | Code-gate stop in 0.0 s, 3/3 rounds, both frames (gate contribution, labelled as such) |
| Unknown-person question | No fabrication either side; new frame answered with the **same short formal refusal 3/3** (mean 26.7 s → 10.7 s) |
| Arithmetic (300,000 KRW × 36) | Old 2/3 (one 10× error) → new **3/3** (this sample only, n=3) |
| Code-layer overhead of the new frame | ≈ 0 (per-layer timing) |

An earlier single-pass figure (−37%) did **not** replicate under
repetition and is withdrawn as an effect figure. Disclosure: the
new frame also runs a non-public operations layer whose
contribution is included in these numbers; separable contributions
are labelled "gate contribution," and the results must not be read
as the effect of the language and number systems alone.

## Layout

```
language/          Essence, grammar canon, dictionaries, interpreters, test report
numbers/           Number-system principles (incl. the weight principle, v0.2.0) + pattern dictionary
akashic-search/    The find-don't-store search method and procedure
tag-records/       Grammar of tag-born records (capsule format)
brain-comparison/  Brain-frame A/B measurement: method, results, raw data (2026-11-07)
```

Canonical documents are in Korean; this README is the English
overview.

## Principles

- **A name is an agreement.** Meanings are fixed by registration,
  never by nature — and once registered, never changed.
- **No guessing.** Unknown tokens, broken order, and claims that
  contradict measured facts are rejected, never improvised around.
- **The surface stays human.** Nexus Language serves the machine
  layer underneath — internal signals, state reports, records,
  ledgers.
- **Security is not secrecy.** Safety rests on encryption, keys, and
  access control — which is why publishing this costs nothing in
  security.
- **Measure, then claim.** Every figure published here was measured
  on a running system first.

## License

- Code (`*.py`, including the interpreters and their tests):
  **Apache License 2.0** — see `LICENSE`.
- Documents, grammars, dictionaries, and **all data files**
  (including the pattern dictionary JSON): **CC BY 4.0** — see
  `LICENSE-CC-BY.txt`.

Use freely, with attribution to the Nexus Group.

- Attribution and name-use terms: see `NOTICE`.

Finalized after the Nexus Group's legal review on 2026-11-05.

---

*A work of the Nexus Group. Forged 2025–2026 from µTAG, through the
Nexus Language canon, to the pattern language and Nexus Numbers.*
