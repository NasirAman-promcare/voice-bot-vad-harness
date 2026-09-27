# Text normalisation

## Purpose
Every transcript the lab scores, reference and hypothesis alike, goes through the same normaliser before words are compared. This removes differences that are not recognition errors, such as casing, punctuation, `twenty-five` against `25`, or `colour` against `color`. The normaliser is the Whisper English text normaliser at a pinned version, with three lab rules on top. It is built in `aqis_lab/scoring/normalise.py` (WP-0.3, FR-0.3-01 to FR-0.3-03) and used by the scorer (`docs/contracts/SCORE_TABLE.md`).

## Normalisers
| Variant | Name | Version | Fillers |
| --- | --- | --- | --- |
| `main` | `aqis-whisper-english` | `1+whisper-normalizer-0.1.1` | removed (the main score) |
| `disfluency_aware` | `aqis-whisper-english-keep-disfluencies` | `1+whisper-normalizer-0.1.1` | kept |

- **Version.** The part before `+` is the version of the lab's own rules (below). The part after it is the pinned package, `whisper-normalizer` 0.1.1, whose `EnglishTextNormalizer` is OpenAI Whisper's English normaliser unchanged: its code matches `openai-whisper` 20250625 apart from how it finds its word list, and its `english.json` word list is byte-identical. The slow test `test_FR_0_3_01_matches_openai_whisper_original` compares the two on 20,000 generated inputs.
- **Pinned.** The package is hash-pinned in `requirements/aqis_lab/phase0.txt`. On first use the normaliser checks the installed version and stops with `NormaliserVersionError` if it is missing or different. Later releases (0.1.2 and newer) add rules that are not Whisper's, such as `cause → because`.
- **Run cards.** A run card's `normaliser` field holds the main normaliser's name and version (`normaliser_identity()`).

## What a normaliser does
One **step** is:
1. **Fold typographic apostrophes** (lab rule, approved in `docs/approvals/WP-0.3.md`, plan question 4): `’` (U+2019), `‘` (U+2018) and `ʼ` (U+02BC) become `'`. Without this, Whisper does not expand `don’t` (it gives `don t`), so a hand-typed reference would disagree with a system that writes `don't`.
2. **Whisper's English normaliser**, in its own order:
   1. lower-case the text;
   2. remove text between `[ ]` or `< >`, and between `( )`;
   3. remove the fillers listed below (main variant only);
   4. expand contractions and common abbreviations (`won't` → `will not`, `Mr.` → `mister`, `gonna` → `going to`, and `'s` → ` is`);
   5. remove commas between digits and full stops not followed by a digit;
   6. remove symbols, punctuation and diacritics, keeping `.`, `%`, `$`, `¢`, `€` and `£` for the next step;
   7. write numbers, ordinals, currency and percentages in digits (`twenty-five dollars` → `$25`, `first` → `1st`, `ten percent` → `10%`), and write the digit `1` as `one`;
   8. change British spellings to American ones (`colour` → `color`) with Whisper's word list;
   9. remove the remaining symbols that are not part of a number, and collapse runs of whitespace to one space.
3. **Trim** leading and trailing whitespace (lab rule).

The normaliser repeats the step until the text no longer changes (lab rule, approved plan question 1) and returns that text. This makes normalisation idempotent: normalising a normalised text changes nothing. Whisper on its own is not idempotent; for example, `minus five` becomes `-5` after one pass and `5` after two. If the text is still changing after 10 steps, the normaliser stops with `NormalisationError` rather than return a text that is not settled. In testing, no input needed more than 3 changing steps.

Where one Whisper pass is already settled, the result is exactly Whisper's output with its ends trimmed.

The result is lower case, with single spaces between words and no space at either end. It can be empty.

## Filler list
The main score removes Whisper's own filler list, and the disfluency-aware score keeps it (FR-0.3-03). Fillers are matched as whole words in any case, so `Um,` is removed and `umbrella` is not. Whisper's spelling list writes `mhm` and `mmm` as `hmm`, so in the disfluency-aware score those two are kept in that spelling.

| Filler | Disfluency-aware output |
| --- | --- |
| `hmm` | `hmm` |
| `mm` | `mm` |
| `mhm` | `hmm` |
| `mmm` | `hmm` |
| `uh` | `uh` |
| `um` | `um` |

Other hesitation words, such as `er`, `erm` and `ah`, are not on the list and stay in both scores. Word repetitions (`I I I mean`) stay too.

## Variants
The two normalisers use the same pinned code, the same lab rules and the same word lists. The only difference is that the disfluency-aware normaliser has Whisper's filler pattern switched off. Every clip is scored under both, and each score row names its variant and normaliser (`docs/contracts/SCORE_TABLE.md`).

An **empty reference** is judged after normalisation, per variant. `um` is an empty reference in the main score but not in the disfluency-aware one.

## Surprising behaviours
These come from Whisper and are kept, because they apply to references and hypotheses in the same way. They can still produce errors where the two texts are written differently.
- **The letter O is read as zero.** `B-O-B` → `b 0 b`, `I O U` → `i 0 u`, `Mr. O'Brien` → `mister 0 brien`, `at 9 o'clock` → `at 90 clock`.
- **The digit 1 is written as a word.** `1` → `one`, `$1` → `one`, `1/4` → `one 4`.
- **Times split or merge differently.** `7:30` → `7 30` (two words), but `seven thirty` → `730` (one word).
- **Dates keep their parts.** `3/3/2024` → `3 3 2024`, `2024-03-03` → `2024 3 3`.
- **Possessive `'s` becomes `is`.** `McDonald's` → `mcdonald is`.
- **Currency moves the symbol.** `fifty cents` → `¢50`, `five pounds` → `£5`.
- **Some filler pairs vanish.** `mm-hmm` → an empty text in the main score, and `uh-huh` → `huh`.
- **`ain't`** → `aint`; **`a hundred`** → `a 100`.

## Examples
Every row is a test (`test_FR_0_3_02_documented_example`). The test checks both outputs, and checks that each output is settled, that is, normalising it again changes nothing. Inputs and outputs are code spans; `(empty)` is the empty text. The expected outputs were written from the rules above and confirmed against OpenAI's original `openai-whisper` 20250625 code with the lab rules applied (`docs/progress/WP-0.3/EVIDENCE.md`, FR-0.3-02).

| ID | Category | Input | Main | Disfluency-aware |
| --- | --- | --- | --- | --- |
| N01 | numbers | `one hundred and twenty three` | `123` | `123` |
| N02 | numbers | `1,234,567` | `1234567` | `1234567` |
| N03 | numbers | `three point one four` | `3.14` | `3.14` |
| N04 | numbers | `two and a half` | `2.5` | `2.5` |
| N05 | numbers | `nineteen eighty four` | `1984` | `1984` |
| N06 | numbers | `a hundred` | `a 100` | `a 100` |
| N07 | numbers | `zero` | `0` | `0` |
| N08 | numbers | `1.5 million` | `1500000` | `1500000` |
| N09 | numbers | `1` | `one` | `one` |
| C01 | currency | `five pounds` | `£5` | `£5` |
| C02 | currency | `£5` | `£5` | `£5` |
| C03 | currency | `three dollars and twenty cents` | `$3.20` | `$3.20` |
| C04 | currency | `$3.20` | `$3.20` | `$3.20` |
| C05 | currency | `fifty cents` | `¢50` | `¢50` |
| C06 | currency | `ten euros` | `€10` | `€10` |
| C07 | currency | `two million dollars` | `$2000000` | `$2000000` |
| D01 | dates | `March 3rd, 2024` | `march 3rd 2024` | `march 3rd 2024` |
| D02 | dates | `the third of March` | `the 3rd of march` | `the 3rd of march` |
| D03 | dates | `3/3/2024` | `3 3 2024` | `3 3 2024` |
| D04 | dates | `2024-03-03` | `2024 3 3` | `2024 3 3` |
| D05 | dates | `in the nineties` | `in the 90s` | `in the 90s` |
| D06 | dates | `twenty twenty four` | `2024` | `2024` |
| T01 | times | `3:30 pm` | `3 30 pm` | `3 30 pm` |
| T02 | times | `7:30` | `7 30` | `7 30` |
| T03 | times | `seven thirty` | `730` | `730` |
| T04 | times | `half past three` | `half past 3` | `half past 3` |
| T05 | times | `at 9 o'clock` | `at 90 clock` | `at 90 clock` |
| T06 | times | `10.30am` | `10.30 am` | `10.30 am` |
| O01 | ordinals | `first` | `1st` | `1st` |
| O02 | ordinals | `twenty-first` | `21st` | `21st` |
| O03 | ordinals | `one hundredth` | `100th` | `100th` |
| O04 | ordinals | `the 2nd time` | `the 2nd time` | `the 2nd time` |
| K01 | contractions | `I'm` | `i am` | `i am` |
| K02 | contractions | `won't` | `will not` | `will not` |
| K03 | contractions | `can't` | `can not` | `can not` |
| K04 | contractions | `they'd've` | `they would have` | `they would have` |
| K05 | contractions | `gonna` | `going to` | `going to` |
| K06 | contractions | `McDonald's` | `mcdonald is` | `mcdonald is` |
| K07 | contractions | `don’t` | `do not` | `do not` |
| K08 | contractions | `ain't` | `aint` | `aint` |
| H01 | hyphens | `well-known` | `well known` | `well known` |
| H02 | hyphens | `twenty-five` | `25` | `25` |
| H03 | hyphens | `mother-in-law` | `mother in law` | `mother in law` |
| H04 | hyphens | `e-mail` | `e mail` | `e mail` |
| F01 | disfluencies | `um I think` | `i think` | `um i think` |
| F02 | disfluencies | `Uh, well` | `well` | `uh well` |
| F03 | disfluencies | `mhm yes` | `yes` | `hmm yes` |
| F04 | disfluencies | `mm-hmm` | (empty) | `mm hmm` |
| F05 | disfluencies | `uh-huh` | `huh` | `uh huh` |
| F06 | disfluencies | `er, erm, ah` | `er erm ah` | `er erm ah` |
| F07 | disfluencies | `I I I mean` | `i i i mean` | `i i i mean` |
| A01 | casing | `HELLO World` | `hello world` | `hello world` |
| A02 | casing | `iPhone` | `iphone` | `iphone` |
| A03 | casing | `NASA` | `nasa` | `nasa` |
| P01 | punctuation | `Hello, world!` | `hello world` | `hello world` |
| P02 | punctuation | `Wait... what?` | `wait what` | `wait what` |
| P03 | punctuation | `[noise] hello (inaudible)` | `hello` | `hello` |
| P04 | punctuation | `it's 5% off` | `it is 5% off` | `it is 5% off` |
| P05 | punctuation | `semi;colon: dash — em` | `semi colon dash em` | `semi colon dash em` |
| L01 | spelled-out letters | `A B C` | `a b c` | `a b c` |
| L02 | spelled-out letters | `A.B.C.` | `a b c` | `a b c` |
| L03 | spelled-out letters | `the U.S.` | `the u s` | `the u s` |
| L04 | spelled-out letters | `B-O-B` | `b 0 b` | `b 0 b` |
| L05 | spelled-out letters | `I O U` | `i 0 u` | `i 0 u` |
| L06 | spelled-out letters | `Mr. O'Brien` | `mister 0 brien` | `mister 0 brien` |
| S01 | British spelling | `colour` | `color` | `color` |
| S02 | British spelling | `organise` | `organize` | `organize` |
| X01 | fixed point | `minus five` | `5` | `5` |
| X02 | fixed point | `oh one` | `one` | `one` |
| X03 | fixed point | `double oh seven` | `7` | `7` |
| X04 | fixed point | `$1.50` | `one.50` | `one.50` |
| X05 | fixed point | `$1` | `one` | `one` |

## Using it
```python
from aqis_lab.scoring.normalise import normalise, normalise_keep_disfluencies, normaliser_identity, VARIANTS

normalise("Um, I have twenty-five dollars.")                    # 'i have $25'
normalise_keep_disfluencies("Um, I have twenty-five dollars.")  # 'um i have $25'
VARIANTS["main"].name, VARIANTS["main"].version                 # ('aqis-whisper-english', '1+whisper-normalizer-0.1.1')
normaliser_identity()                                           # the run card's normaliser object
```
Only `str` is accepted; anything else raises `TypeError`.

## Versioning and change policy
- Any change that can alter an output changes the version: a new `whisper-normalizer` version changes the part after `+`, and a change to the lab rules (apostrophes, trimming, the fixed point, the filler list) increases the number before it.
- Scores made with different normaliser versions are not compared with each other. Every score row records the version, so this can always be checked.
- The document, the examples, the code and the tests change in the same commit. The example tests keep this document true.
