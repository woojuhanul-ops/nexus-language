# Release Notes

## v0.3.0 — Brain-frame A/B measurement published (2026-11-07)

- Added `brain-comparison/`: the repeated A/B measurement of two
  operating frames around the same local model (Qwen3-14B class) —
  method, full result tables, gate/accuracy results, limitations,
  the 18 test questions, and the complete raw records (108 runs,
  JSON + CSV).
- Headline, stated honestly: mean response time moved −4.2%,
  inside ±40% round-to-round drift — **no speed improvement is
  claimed**. Confirmed instead: exact reproducibility of the
  code-gate payment stop (0.0 s, 3/3, both frames), consistent
  formal refusals on the unknown-person question in the new frame
  (3/3 identical, mean 26.7 s → 10.7 s), code-layer overhead ≈ 0,
  and arithmetic 2/3 → 3/3 in this sample (n=3, not generalized).
- The earlier single-pass figure (−37%) is explicitly withdrawn
  as an effect figure; the document explains why.
- Disclosure: the new frame also runs a non-public operations
  layer; its contribution is included in the numbers, separable
  contributions are labelled "gate contribution," and the results
  must not be read as the effect of the language and number
  systems alone. The non-public layer's internals are not
  published.
- No registered dictionary values or previously published figures
  were changed.

## v0.2.0 — Definitions rewritten from the essence (2026-11-07)

- README.md / README.ko.md rewritten: the essence now leads — a
  name is an agreement, not the thing; every machine word is defined
  as one symbol; a Nexus number carries value, intensity (세기),
  and weight (중량).
- Added `language/넥서스언어_본질_2026-11-07.md`: the essence of
  Nexus Language stated as canon.
- Added `numbers/수체계_원리_중량보충_2026-11-07.md`: Principle 3 —
  a number's size carries weight, capped by an agreed maximum; the
  canonical terms are 세기 (intensity) and 중량 (weight).
- Added the honest shrink accounting to the README: the
  description/direction/oversight layer of a brain collapses by
  over 99.99% (simulation, 2026-11-07); weight values themselves do
  not shrink (patterns mean, never replace).
- No registered dictionary values or measured figures were changed.

## v0.1.1 — Number system principles supplement (2026-11-05)

- Added `numbers/수체계_원칙_보충_2026-11-05.md`: two principles of the
  Nexus Number System stated as spec — (1) intensity gradations between
  values are fixed by agreement (declared in the spec), not by a
  physical limit; (2) anything that appears two or more times can be
  compressed, subject to the dictionary-plus-index accounting rule —
  plus the run-folding encoding rule (repetition count carried by a
  symbol's intensity) and the measured evidence for it.
- No registered dictionary values were changed; extension is by new
  documents only, as before.

## First public release

- **First publication date: 2026-11-05**
- Release tag: v0.1.0

### Publication record procedure

1. On the day this package is first published, replace the placeholder
   above with the actual calendar date of first publication, and keep
   this file in the release tag. The first-publication date is the
   fact that fixes the public record — record it exactly, on the day.
2. Licensing in effect from first publication: code under the Apache
   License 2.0 (`LICENSE`); documents, grammars, dictionaries, and
   data files under CC BY 4.0 (`LICENSE-CC-BY.txt`); attribution and
   name-use terms in `NOTICE`.
3. Legal review: Nexus Group legal review completed 2026-11-05
   (conditional pass; all required pre-publication measures applied).
4. No patent application has been filed for this work, and no patent
   is claimed. This release is a defensive publication: the methods
   are published so that they remain free for everyone to use.
