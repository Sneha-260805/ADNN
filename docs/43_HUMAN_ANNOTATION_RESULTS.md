# Human annotation results: 100 minimal pairs (REQ-LBL-05)

- **Status:** independent agreement computed on 2026-11-05 by Member 1. **No adjudication has
  been performed.** Every number in §2 to §4 comes from the two independently returned
  workbooks, unchanged.
- **Requirement:** REQ-LBL-05 (two humans label the same random sample of 100 pairs without
  seeing the automatic label; report κ human–human and human–automatic, with CIs).
- **Not changed:** both returned workbooks, the frozen sampling manifest, the blank sheets,
  the annotation instructions, and frozen dataset v2.0 (records and labels). No example was
  relabelled.
- **Reproduce:**

  ```text
  .venv/Scripts/python.exe scripts/annotation/human_100.py agreement \
      --a1 ADNN_Annotator_1.xlsx --a2 ADNN_Annotator_2_filled.xlsx --accept-uncertain-no
  ```

  Reruns give byte-identical CSV/JSON outputs; `summary.json` differs only in `computed_utc`.

## 1. Inputs and validation

| Input | SHA-256 |
|---|---|
| `ADNN_Annotator_1.xlsx` (Annotator 1, returned) | `6ac7b3507b13b0badc61b4bd3b7e1384cf9bdaf872b2bee9ca60561247c615ad` |
| `ADNN_Annotator_2_filled.xlsx` (Annotator 2, corrected return) | `e146d1c0564592b739fd52f55c70b759e8b585ff6de686ba7f1fe902283209b5` |
| `data/annotation/human_100_pairs/sampling_manifest.json` (frozen) | `49a0bc6b4f595291492f3337db43b7e717de5c967226e3e91acfce3cc8914bf8` |
| `data/production/v2.0/records.jsonl` (frozen gold, label at h = 3) | `d03cd8f38ad4b36ce540409e7b3062e0eb4b457d6916483a3334ebde0acdab73` |

The earlier, incorrect Annotator 2 workbook was not used. Only the corrected file above was
read.

**Checks that passed** (both workbooks):

- each is the issued workbook for its annotator (sheet title), with the issued header row;
- all **200** annotation ids present, no unknown or duplicate ids;
- `pair` and `example` columns match every id (pair assignment and A/B order unchanged);
- task, state, action and tool text unchanged for all 200 rows (content hash per row against
  the manifest);
- every label is one of R, P, I, U (no U was used by either annotator);
- the frozen manifest re-derives from frozen v2.0: the eligible minimal-pair set hash matches,
  the 100 pairs and their A/B order are reproduced from seed 20261105, every pair is a strict
  minimal pair (same action, different gold label), and the blank sheets are unchanged;
- the two workbooks are different files and do not have identical labels and notes.

**Validation failure (strict mode), and how it was handled.** In
`ADNN_Annotator_2_filled.xlsx`, **all 200** `uncertain` cells contain `no`. The instructions
and the workbook dropdown allow only empty or `yes`, so the strict validator rejects the
sheet and computes no statistic:

```text
annotator_2: 200 invalid 'uncertain' values (leave empty or write yes): ["H001-A='no'", ...]
```

`no` has only one reading ("not uncertain"), so the run above uses the explicit opt-in
`--accept-uncertain-no`. Member 1 approved it on 2026-11-05 for the corrected Annotator 2
workbook. Without this flag no statistic can be computed at all, because the strict validator
rejects the whole sheet. The flag reads the `uncertain` value `no` as "not uncertain". It
uses the same normalization the validator already applies to `yes` (surrounding spaces
trimmed, case-folded), and no other value is accepted (`maybe` is still an error). It never
reads or changes a label. **Strict validation remains the default**: without the flag the same
command fails, as shown above. The strict error is kept in `summary.json` (`validation.strict_ok = false`,
`validation.strict_errors`). The flag affects only the secondary analysis that drops
uncertain examples. The primary analysis does not use the `uncertain` column at all.
Annotator 1 flagged 2 examples as uncertain (H082-A, H089-A, both P, about revoked share-link
records). Annotator 2 flagged none.

## 2. Agreement (independent, primary analysis)

200 examples (100 pairs). No example was excluded, because nobody used U. The CIs are 95%
percentile bootstrap intervals over 1,000 resamples of **pairs** (seed 20261105).

| Comparison | Cohen's κ | κ 95% CI | Raw agreement | Raw 95% CI |
|---|---|---|---|---|
| Annotator 1 vs Annotator 2 | **0.6206** | [0.5059, 0.7288] | 0.735 (147/200) | [0.645, 0.815] |
| Annotator 1 vs automatic gold | **0.8169** | [0.7432, 0.8798] | 0.880 (176/200) | [0.835, 0.920] |
| Annotator 2 vs automatic gold | **0.7339** | [0.6428, 0.8214] | 0.820 (164/200) | [0.755, 0.880] |

**Secondary analysis** (also drops the 2 examples Annotator 1 flagged uncertain; n = 198):
human–human κ = 0.6172 [0.5035, 0.7275], raw agreement 0.7323; A1–gold κ = 0.8145
[0.7416, 0.8796]; A2–gold κ = 0.7316 [0.6423, 0.8196].

**Label distributions**

| | R | P | I |
|---|---|---|---|
| Annotator 1 | 98 | 41 | 61 |
| Annotator 2 | 47 | 94 | 59 |
| Automatic gold | 74 | 58 | 68 |

**Confusion matrices** (rows = first-named, columns = second-named)

Annotator 1 (rows) × Annotator 2 (cols):

| | R | P | I |
|---|---|---|---|
| **R** | 47 | 51 | 0 |
| **P** | 0 | 41 | 0 |
| **I** | 0 | 2 | 59 |

Annotator 1 (rows) × automatic (cols):

| | R | P | I |
|---|---|---|---|
| **R** | 74 | 17 | 7 |
| **P** | 0 | 41 | 0 |
| **I** | 0 | 0 | 61 |

Annotator 2 (rows) × automatic (cols):

| | R | P | I |
|---|---|---|---|
| **R** | 47 | 0 | 0 |
| **P** | 27 | 58 | 9 |
| **I** | 0 | 0 | 59 |

Both annotators deviate from gold in one direction only. Annotator 1 is more lenient (R where
gold says P or I) and Annotator 2 is more conservative (P where gold says R or I). No annotator
ever said I where gold was not I. Neither ever said R where the other said I.

## 3. Human–human disagreements (unresolved)

**53** of 200 examples (in 29 of the 100 pairs) have different labels. All 53 are exported in
`results/human_annotation/human_disagreements_detailed.csv`. Each row has the anonymous
annotation id (no dataset record id), the action, the shown state, the task and tools, both
labels, both uncertainty flags, both notes, and the automatic label. It also has post-hoc
diagnostic columns (`diag_*`: action verb, pivot, scenario family, oracle depths), which were
never shown to the annotators. All rows have `status = unresolved`.

| Split | n | Direction | Automatic label | Matches automatic |
|---|---|---|---|---|
| **R/P** | **51** | A1 = R, A2 = P in all 51 | R 27, P 17, I 7 | A1 27, A2 17, neither 7 |
| **P/I** | **2** | A1 = I, A2 = P | I 2 | A1 2 |
| **R/I** | **0** | — | — | — |

**R/P (51) by sub-case.** Every one of these is a file revision/backup scenario:

| Family (action) | Pivot: backup | Gold | n | Ids |
|---|---|---|---|---|
| second edit, backup (`edit_file`) | fresh | R | 10 | H031-A H033-B H036-A H041-B H047-A H052-A H055-B H068-B H072-A H083-A |
| second edit, backup (`edit_file`) | stale | P | 10 | H031-B H033-A H036-B H041-A H047-B H052-B H055-A H068-A H072-B H083-B |
| edit, backup (`edit_file`) | fresh | R | 7 | H030-B H032-B H045-B H054-A H069-B H073-B H098-B |
| edit, backup (`edit_file`) | stale | P | 7 | H030-A H032-A H045-A H054-B H069-A H073-A H098-A |
| restore from backup (`restore_backup`) | fresh (no-op) | R | 9 | H014-B H023-A H027-A H028-A H029-A H059-A H075-B H085-A H086-B |
| restore from backup (`restore_backup`) | stale | I | 7 | H014-A H023-B H027-B H028-B H029-B H075-A H086-A |
| delete, backup present (`delete_file`) | fresh, no bin | R | 1 | H077-B |

**P/I (2):** H024-B, H035-A. Both are `transfer_money` of 90 where refunds cost a fee of 90.
Annotator 1 wrote "refund fee 90 is ≥ amount 90, so a refund returns nothing" (I). Annotator 2
wrote "refund possible, fee lost, record remains, not exact" (P).

**Where disagreement is concentrated.** The four backup/revision families make up 27 sampled
pairs (54 examples), and 51 of those 54 examples are disagreements. In the other 73 pairs
(146 examples), the two annotators disagree on 2 examples. This is a descriptive count. No κ
was recomputed on a subset, and the primary κ above is the only reported human–human
statistic.

**Pair members were not distinguished.** In the 24 pairs where both members are disagreements,
each annotator gave **the same label to both members** in all 24 (A1: R/R, A2: P/P). The only
difference between those two members is whether the stored backup is at the file's current
revision ("fresh") or at an older one ("stale").

## 4. Do the disagreements point to ambiguous instructions?

**Yes, at the R/P boundary for file recovery.** This is an inference from the label pattern
and the annotators' own notes. It is not a confirmed cause.

1. **What a file recovery does to the revision number is never stated.** The instructions list
   "a file has its old content again, but its revision number or version history differs" as an
   example of P. They do not say whether `revert_file` or `restore_backup` keep or advance the
   revision number. The two annotators filled this gap in opposite ways, and each did so
   consistently:
   - Annotator 1 treated `revert_file` as an exact restore ("Versioning on; revert_file restores
     the previous content", 34 rows). In the sandbox a revert is a new write: the content comes
     back, but the revision advances. So by the instructions' own P example, this route is only
     approximate.
   - Annotator 2 treated every file recovery as inexact, including a recovery from a backup at
     the same revision ("the recreated file metadata/revision may differ", H077-B) and actions
     that change nothing (a `restore_backup` whose backup equals the current revision; gold R at
     depth 0, 9 rows).
2. **The exact route through a backup at the current revision is not spelled out.** For edits,
   gold R hinges on "Backups: plan.txt (revision 3)" matching "plan.txt (revision 3)": restoring
   that backup is exact. Neither annotator's notes mention this route for the edit families. As
   a result, both labelled the fresh and stale members identically (§3), even though the
   instructions say pair members may differ. So "exact within 3 actions" versus "partial"
   depended on whether the annotator matched revision numbers between the file and backup
   lists. The instructions never ask for that comparison or give an example of it.
3. **Whether `restore_backup` creates a previous version is undefined.** In the 7 stale
   `restore_backup` examples (gold I), both annotators assumed versioning lets them revert the
   overwrite (A1 R, A2 P). In the sandbox, `restore_backup` does not record a previous version,
   so nothing can bring the overwritten text back. The instructions say "every edit keeps the
   previous version", but they do not say whether restoring a backup counts as an edit. This is
   a shared deviation from gold, not a human–human split. Its R/P disagreement comes from
   point 1.
4. **A fee that equals the amount** (P/I, 2 rows). "Money comes back only minus a fee" (P) and
   "balances once fees are counted must match" (otherwise not approximate) conflict when the fee
   consumes the whole refund. The instructions do not cover this edge case.

The other mechanisms (recycle bin, payment policies, email undo windows, share links) show
almost no human–human disagreement (2 of 146 examples).

**Observation on the notes.** Both annotators' notes are highly formulaic: there are 27
distinct note texts across Annotator 1's 200 rows and 20 across Annotator 2's. The sheets
alone cannot establish or rule out independence. The automated check (identical labels and
notes) did not fire.

## 5. Independent agreement vs adjudication

- §2 to §4 report **independent** agreement only. These are the numbers for REQ-LBL-05 and
  for any paper or data card. They must not be replaced by post-adjudication figures.
- **No adjudication has taken place.** All 53 disagreements are unresolved. If one is held
  later, its outcome must go in a separate file (for example
  `results/human_annotation/adjudication.csv`). Any adjudicated agreement must be reported
  next to the independent κ = 0.6206 and clearly labelled as adjudicated.
- Disagreement with gold is not evidence that gold is wrong, and no gold label was changed.
  The 7 examples where both humans disagree with gold I (stale `restore_backup`) and the 17
  where Annotator 1 said R against gold P are candidates for a gold audit. Any change to gold
  would be a new dataset version, not an edit to v2.0.
- An instruction revision (points 1 to 4) would apply only to a **new** annotation round with
  fresh, independent labels. It must not be used to reinterpret the labels reported here.

## 6. Generated files

All files are under `results/human_annotation/`. That folder is git-ignored (`results/*`), so
the files are identified by checksum.

| File | Content | SHA-256 |
|---|---|---|
| `summary.json` | inputs and hashes, validation (strict errors, opt-in, manifest check), label counts, κ, raw agreement with bootstrap CIs, confusion matrices (primary and secondary) | `a65a23e741b11c98642dfc4ce6b3abd26199609bcd8c7394b5541a8751668c4c` (final run; changes with `computed_utc`) |
| `human_disagreements.csv` | 53 disagreements: labels, uncertainty flags, notes (original format) | `8addb8b8d1a5edb5fc700cafaa187a617c34e00e98ad36d3ec802ad5f1b32855` |
| `human_disagreements_detailed.csv` | 53 disagreements with action, state, task, tools, automatic label, split, diagnostics | `0d69af3b0d7afa9a9cfde1a53c598d669c54de94ef67d5ff0b68c9edf5a1decd` |
| `disagreement_groups.json` | counts by R/P, P/I, R/I; direction, gold label, action, pivot, family, ids; pair-level consistency | `933ae20cd4a969ce88b3e36ba80c925bd2834e026dd4fbc198cada4ac4c5b772` |
| `human_vs_automatic.csv` | every example where either human differs from gold (includes record ids; internal use) | `2b2a9e2094c04f7b3e74418bcf3522cbb535d54e3d0299f86b04432635bb0ce8` |

Apart from `summary.json`, these files reproduce byte for byte. After the run, the inputs in
§1, the blank sheets (`annotator_{1,2}.csv`, `3522866d…7cc83`), the blank workbooks and
`ANNOTATION_INSTRUCTIONS.md` (`68df56e2…56e`) still match their checksums from before the run.

**Code changes made for this run** (no change to sampling or statistics definitions):
`check_sheet(..., accept_uncertain_no=False)` and `split_pattern` in
`src/adnn/dataset/annotation.py`. In `scripts/annotation/human_100.py`: the
`--accept-uncertain-no` flag, the recorded strict validation, the re-derivation of the frozen
manifest before any statistic, the bootstrap CI for raw agreement (same resampling as κ), and
the two new disagreement exports. Also new: `scripts/annotation/archive_human_100.py` (§7).
Tests: two new tests and an extended end-to-end test in `tests/test_human_annotation.py`, plus
a redaction test in `tests/test_annotation_xlsx.py`. That makes 28 annotation tests, all
passing.

## 7. Reproducibility archive

The git-ignored inputs and outputs are archived in
`ADNN_REQ-LBL-05_Human_Agreement_Archive.zip` at the repository root (not committed). Build it
with:

```text
.venv/Scripts/python.exe scripts/annotation/archive_human_100.py \
    --a1 ADNN_Annotator_1.xlsx --a2 ADNN_Annotator_2_filled.xlsx
```

- **Layout.** Files sit at their repository paths:
  - the study folder: instructions, READMEs, blank CSV sheets, blank workbooks, and the
    sampling and Excel manifests;
  - the two returned workbooks, under `data/annotation/human_100_pairs/completed/` with their
    original names;
  - frozen `data/production/v2.0/` (7 files);
  - the five result files.

  `ARCHIVE_MANIFEST.json` lists every file with its SHA-256 and size. It also records the code
  commit, the reproduction command, the validation note and "no adjudication".
- **Privacy.** No annotator names are archived. The Annotator 1 workbook's document properties
  contained a personal name (`lastModifiedBy`). In the archived copy, `creator` and
  `lastModifiedBy` are set to `ADNN project`. No cell is touched, so validation and every
  statistic are unchanged. The manifest records both the original SHA-256 (`6ac7b350…`) and
  the archived one. The Annotator 2 workbook has no document properties and is archived byte
  for byte. The e-mail addresses in the state texts are synthetic `example.org`/`example.com`
  dataset content.
- **Originals.** The original returned workbooks stay unchanged at the repository root.
