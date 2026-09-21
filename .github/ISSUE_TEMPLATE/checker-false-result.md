---
name: A checker reported the wrong thing
about: A bundled script flagged correct code, or stayed quiet on a real defect
title: '[checker] '
labels: ['checker']
---

**Which script**

<!-- e.g. skills/timing-closure-cdc/scripts/cdc_scan.py -->

**False positive or false negative**

<!-- Flagged something correct / missed something broken. -->

**Smallest input that shows it**

```systemverilog
// Paste the smallest file that reproduces it. If it becomes a fixture under
// evals/fixtures/ with a case in tools/test_scripts.py, the fix stays fixed.
```

**What the script printed**

```text

```

**What it should have printed**

<!-- Note: every checker here is a single-file heuristic. It does not
     preprocess, elaborate, or follow references across files, and each
     SKILL.md says so under "Honest limits". A miss inside a macro or across
     a module boundary may be a documented limit rather than a bug — but say
     so anyway, because the limit may be worth narrowing. -->
