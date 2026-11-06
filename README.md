# Nexus Language & Nexus Number System

**A work of the Nexus Group — 넥서스 그룹의 작품입니다.**

A language and number system designed for machines to speak to machines —
and for the records they leave behind to be born already structured.

> **Status: pre-release.** The Nexus Group's legal review is complete
> (2026-11-05, conditional pass — all required measures applied). The
> licensing terms below are final and take effect on first publication,
> whose date will be recorded in `RELEASE_NOTES.md`.

---

## What this is

Human languages serve human speakers. **Nexus Language** serves the other
conversation: AI systems, programs, and computers exchanging state,
instructions, and records with each other. It grows out of µTAG (2025), a
tag-capsule protocol for passing direction and context between AIs, and adds
what a protocol needs to become a language: a fixed grammar, an immutable
dictionary, a deterministic code-layer interpreter, and a book of laws with
three-valued verdicts (pass / hold / reject).

**The Nexus Number System (Nexus Numbers)** is its sibling. Numbers keep doing arithmetic, with the
ordinary operator symbols everyone already shares (+ − × ÷ √ …). On top of
the values sits a *pattern layer*: every measured distribution ("the grain"
of a set of numbers) is registered in a dictionary under one symbol, so the
symbol **means** the pattern instead of replacing the numbers.

Two companion methods complete the package:

- **Akashic Search** — don't store the world; know how to find it. A
  question is decomposed, routed to verified shortcuts and field gateways,
  retrieved in full, judged against sources and dates, and the successful
  path is recorded so the system gets faster the more it is used.
- **Tag-born Records** — records are generated in tag form at the moment
  they are created (never translated afterwards from prose), in a
  ledger-shared capsule format that code can parse deterministically.

## Measured results

All figures below come from tests run against a live system and are
documented in `language/패턴언어_해석효율시험_2026-11-05.md`
(interpretation & efficiency test report).

| Test | Result |
|---|---|
| Status reports, 20 items — tokens, pattern language vs prose | **194 vs 612 (−68.3%)** |
| Status reports, 20 items — tokens, pattern language vs JSON | **194 vs 972 (−80.0%)** |
| Read-back accuracy — pattern language (code parse) | **100% (20/20)** |
| Read-back accuracy — prose (model re-read, 10-item sample) | 48.8% of fields |
| Interpretation — code interpreter | **100%** (roundtrip 16/16, collision check 0) |
| Interpretation — local AI models, 12 tasks, full marks | 7/12 (4B waiter) · 5/12 (8B kitchen) |
| Class-consistency check (refinement №1) | 398/398 valid claims pass · 796/796 false claims caught |
| Tag-born records, ledger-shared form | −16.2% tokens vs prose (measured average) |

The honest reading of these numbers: **the language lives at the code
layer.** Computers parse it perfectly; AI models read it only partially,
so wherever a model is involved, the code layer expands the symbols and
hands over plain text. The pattern dictionary of Qwen3-4B (398 tensors —
361 concentrated, 37 uniform, 0 mixed) is included under `numbers/` as a
worked example of the method.

## Layout

```
language/        Grammar canon, dictionaries, interpreters, test report
numbers/         Pattern dictionary of Qwen3-4B (JSON + human-readable)
akashic-search/  The find-don't-store search method and procedure
tag-records/     Grammar of tag-born records (capsule format)
```

Canonical documents are in Korean; this README is the English overview.
An English edition of the core documents is planned before publication.

## Principles

- **The dictionary never changes meaning.** A registered symbol keeps its
  meaning forever; growth happens only by registering new symbols.
- **No guessing.** Unknown tokens, broken order, and claims that contradict
  measured facts are rejected, never improvised around.
- **The surface stays human.** Screens people see, and conversation with
  people, remain in human language. Nexus Language is for the machine
  layer underneath — internal signals, state reports, records, ledgers.
- **Security is not secrecy.** Safety rests on encryption, keys, and access
  control. The language adds at most a thin layer of "not casually
  readable" — which is why publishing it costs nothing in security.
- **Measure, then claim.** Every figure published here was measured on a
  running system first, against a recorded baseline.

## License

- Code (`*.py`, including the interpreters and their tests):
  **Apache License 2.0** — see `LICENSE`.
- Documents, grammars, dictionaries, and **all data files** (including
  the pattern dictionary JSON): **CC BY 4.0** — see `LICENSE-CC-BY.txt`.
  Use freely, with attribution to the Nexus Group.
- Attribution and name-use terms: see `NOTICE`.

Finalized after the Nexus Group's legal review on 2026-11-05. These
licenses take effect on first publication.

---

*A work of the Nexus Group. Forged 2025–2026 from µTAG, through the Nexus
Language canon, to the pattern language and Nexus Numbers.*
