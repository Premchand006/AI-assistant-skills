# Deep Audit: `Premchand006/AI-assistant-skills`

**Audit scope:** main-branch source snapshot reviewed on 2026-10-16, including every Python and shell script, CI workflow, dependency file, plugin manifest, skill definition, evaluation suite, fixture, and contributor document. This repository is **not an OSINT, web-scraping, or intelligence-collection system**. It is a compact Claude Agent Skills plugin for RTL, CDC, OpenLane/Sky130, embedded firmware, ONNX/TFLite Micro, and skill evaluation. Agent skills are self-contained instruction/reference/script bundles loaded when relevant, which matches this repository’s actual architecture.[^1]

**Overall verdict:** the repository has unusually strong scope honesty, useful machine-readable checker output, a thoughtful evaluation design, and a clean extension pattern. Its present blockers are release-engineering and evidence-integrity defects: the current snapshot fails one checker test because an ignored fixture directory is absent, its ONNX smoke path fails in a fresh environment because `sympy` is undeclared, all model transcripts are absent, and replay still returns success with 152 missing transcript artifacts. It should not claim that CI currently proves “8/8 script checks” or end-to-end ONNX quantization until those defects are fixed and a clean tagged build reproduces the claims.

> **Remediation update (2026-10-16):** all four P0 items, the CI pinning item, and most quick wins have been fixed in the working tree. They are not committed yet. [Section 6](#remediation-status) maps each finding to its fix and lists what remains open. Sections 1–5 are kept as the original audit record.

## 1. 🔍 Scraping Efficiency & Pipeline Architecture

### Category fit

There is no HTTP crawler, browser automation, DOM parser, feed collector, search API, proxy layer, CAPTCHA handler, robots parser, URL frontier, or OSINT target model anywhere in the repository. Consequently, rate-limit resilience, CAPTCHA behavior, DOM-change tolerance, robots compliance, user-agent rotation, and collection throughput are **not applicable to the current codebase**. Adding user-agent rotation would be a category error rather than a quick win.

The only network-capable path is the optional model-evaluation runner in [`evals/eval_runner.py`](https://github.com/Premchand006/AI-assistant-skills/blob/main/evals/eval_runner.py):

- `ReplayRunner` reads committed Markdown transcripts.
- `CliRunner` invokes `claude -p` once per case using `subprocess.run(..., shell=False)`.
- `ApiRunner` sends prompts through the Anthropic Python SDK.
- The default is offline replay; live CLI/API execution is opt-in.

### Actual pipeline

The real pipeline is:

`SKILL.md + eval.yaml + fixture text → model runner → regex graders → in-memory report → results.json/Markdown table`

For static checkers it is:

`source/config files → recursive file discovery → whole-file regex/JSON parsing → finding objects → console or JSON output`

This is appropriate for a seven-skill repository, but it is not designed as a large-scale data pipeline:

- [`evals/eval_runner.py`](https://github.com/Premchand006/AI-assistant-skills/blob/main/evals/eval_runner.py) runs suites, cases, on/off modes, and discovery prompts sequentially. A full live run therefore launches many serial model requests with no repository-level concurrency, checkpoint scheduler, queue, or explicit 429/backoff policy.
- The API runner relies on SDK behavior and adds no explicit handling for 429, 5xx, timeout, connection reset, quota exhaustion, or partial completion. The CLI runner has a 900-second timeout but does not catch `TimeoutExpired` or retry failed calls.
- A CLI failure is converted to non-empty text beginning with `[runner error]`. Because availability is computed as `bool(text)`, the failed request is treated as an available response and sent through graders rather than recorded as an operational error.
- Static checkers read complete source files into memory and several recursively traverse directories with `rglob`. That is simple and fast for normal RTL/firmware trees, but there are no file-count, file-size, depth, symlink, timeout, or memory limits for hostile or very large inputs.
- Results are assembled entirely in memory and written as one indented JSON object. There is no streaming JSONL writer or resume index, so a late failure can lose an expensive live run unless individual transcripts were recorded.

### Reproducibility test

A clean-environment execution exposed two concrete pipeline failures:

1. `python tools/test_scripts.py` produced **7/8 passes**. The failing case was `openlane-sky130-flow / failed run`, because `evals/fixtures/openlane/runs` does not exist in the repository snapshot. The likely cause is the unanchored `runs/` rule in [`.gitignore`](https://github.com/Premchand006/AI-assistant-skills/blob/main/.gitignore), which also ignores the nested fixture path.
2. `python tools/smoke_imports.py` compiled all 13 scripts but failed the ONNX quantization smoke path. `onnxruntime.quantization.quant_pre_process()` attempted symbolic shape inference and raised an import error because `sympy` is not declared in [`requirements-dev.txt`](https://github.com/Premchand006/AI-assistant-skills/blob/main/requirements-dev.txt).

`python evals/eval_runner.py --runner replay` reported **152 missing transcript operations**, correctly displayed every result as “not run,” wrote `evals/out/results.json`, and exited with code 0. The honesty of the table is good; the success exit code is unsuitable for an evidence gate.

### Architectural assessment

| Dimension | Assessment | Evidence |
| --- | --- | --- |
| Collection resilience | Not applicable to websites; weak for live model calls | No crawler; no explicit retries/backoff/checkpoint resume |
| Local checker throughput | Good for small projects | Dependency-light scripts, recursive discovery, compact finding model |
| Large-run throughput | Limited | Serial requests and in-memory aggregation |
| Failure semantics | Needs correction | Runner errors can be graded as model output; missing replay artifacts do not fail by default |
| Reproducibility | Designed well, currently broken | Replay architecture is strong, but transcripts are absent and two clean-install checks fail |
| Storage scalability | Adequate only at present size | Markdown transcripts plus one nested JSON report; no indexed store |

## 2. 🛡️ Operational Security (OPSEC), Privacy, & Legal Compliance

### Network exposure and signatures

The repository performs no target-site requests and therefore does not leak a scraper user-agent, crawler fingerprint, browser profile, cookie jar, or proxy identity. When `--runner api` or `--runner cli` is selected, the user’s network path and normal client characteristics are necessarily visible to the model provider; the repository provides no Tor/proxy layer and should not imply anonymity.

More importantly, live evaluation sends the complete case prompt, embedded fixture contents, and—when skill mode is on—the complete `SKILL.md` to the external model. There is no preflight secret scan, PII classifier, path allowlist, redaction step, data-classification prompt, or confirmation gate. This is acceptable for the committed synthetic fixtures, but unsafe if contributors replace them with proprietary RTL, firmware, credentials, customer data, or unreleased architecture text.

### Credential handling

Credential handling is basically sound:

- `evals/eval_runner.py` checks `ANTHROPIC_API_KEY` in the environment and constructs `anthropic.Anthropic()` without embedding a key.
- No hard-coded credential pattern was found in the audited tree.
- Anthropic officially documents exporting `ANTHROPIC_API_KEY` as an environment variable, which the SDK reads automatically.[^2]

However, the repository should add `.env`, `.env.*`, local credential files, and common secret artifacts to `.gitignore`, while retaining a safe `.env.example`. It should also run a secret scanner in CI and document that debug-level SDK/CLI logging can expose request metadata or content.

### Transcript privacy

The largest OPSEC risk is the deliberate transcript workflow:

- `.gitignore` states that `evals/transcripts/` is committed on purpose.
- `CliRunner` and `ApiRunner` write raw model output directly to Markdown.
- There is no transcript schema, redaction pass, provenance header, retention rule, or review gate before commit.
- Prompt inputs are not stored alongside each response, so the record may leak output while still lacking complete forensic provenance.

Add a mandatory `transcript_sanitize.py` stage that rejects likely secrets, email addresses, private keys, cloud tokens, absolute home paths, and marked confidential strings. Commit only sanitized fixtures and outputs. Keep unsanitized captures outside the repository or encrypt them in an approved artifact store.

### Local execution risks

No direct shell injection was found in Python subprocess calls because argument arrays and `shell=False` are used. A static Bandit scan reported seven low-severity subprocess/import findings and no medium- or high-severity findings. Two narrower risks remain:

- [`skills/rtl-verilog-lint/scripts/lint_rtl.sh`](https://github.com/Premchand006/AI-assistant-skills/blob/main/skills/rtl-verilog-lint/scripts/lint_rtl.sh) concatenates discovered filenames into a Yosys command-language string passed with `yosys -p`. Shell quoting prevents shell injection, but an attacker-controlled filename containing Yosys metacharacters may alter the Yosys script. Generate a temporary `.ys` file with safely escaped/validated paths, reject control characters, or pass a controlled file list through a safer interface.
- `evals/eval_runner.py` constructs transcript paths from skill-directory names and YAML case IDs without verifying containment under the transcript root. A malicious case ID containing `../` can cause `--record` to write outside the intended directory. Resolve the destination and enforce `destination.is_relative_to(record_root.resolve())`; validate IDs against a conservative slug regex.

The shell wrappers should also use `--` before user-supplied file paths where supported and reject filenames beginning with `-` for tools that lack an end-of-options delimiter.

### CI supply chain

The workflow correctly sets `permissions: contents: read`, does not expose secrets, and separates Python and shell jobs. However, `actions/checkout@v7` and `actions/setup-python@v7` are mutable major tags. GitHub states that full-length commit-SHA pinning is the immutable way to consume actions, and its current guidance prefers workflow dependency lockfiles where available.[^3][^4]

Pin both actions to verified full commit SHAs and let Dependabot update those SHAs.[^9] Python dependencies are broad minimum-version ranges rather than a reproducible lock; the fresh-install `sympy` failure demonstrates the practical consequence. Add a lock/constraints file with hashes and retain a separate scheduled “latest compatible dependencies” job.

### Scraping and legal compliance

There is currently no scraping behavior, so robots.txt, terms-of-service, database rights, target authorization, and collection-rate controls do not apply. If an OSINT collector is later added, it must not be hidden inside these hardware skills. Build a separate package with per-target policy metadata, authorization records, robots handling, rate budgets, and data-retention rules. RFC 9309 defines `robots.txt` as the standardized mechanism by which service owners express crawler-access rules, while also clarifying that robots rules are not access authorization.[^5]

## 3. 📊 Data Quality & Normalization

### Strengths

The checker finding model is simple and analyst-friendly. Multiple tools can emit JSON records with a common conceptual shape:

```json
{
  "severity": "error",
  "rule": "multiple-drivers",
  "file": "rtl/example.sv",
  "line": 42,
  "message": "...",
  "hint": "..."
}
```

That is considerably better than prose-only diagnostics. Rule identifiers are stable enough for CI filtering, severity is explicit, locations are included, and scripts distinguish “skipped” from “passed.” The repository also keeps model usefulness, positive discovery, and adversarial discovery conceptually separate; this is a strong evaluation design.

### Normalization gaps

The tools do not yet share a formal schema or version. Similar findings are implemented independently, so downstream consumers cannot rely on a guaranteed contract. Add a versioned JSON Schema such as `schemas/finding-v1.schema.json` and require these common fields:

- `schema_version`
- `tool`, `tool_version`, `rule_id`, `severity`
- `path`, `start_line`, `start_column`, optional end location
- `message`, `recommendation`
- `confidence` and `limitations`
- `fingerprint` derived from normalized path/rule/location/content
- `run_id`, `repository_commit`, and timestamp

Support SARIF 2.1.0 as an additional output format so findings can appear as GitHub code-scanning annotations.[^8] Keep existing JSON output for lightweight consumers.

### Deduplication and corruption handling

There is no general deduplication. A recursive scan can report repeated or overlapping findings, and merged outputs from several tools have no stable fingerprint. Introduce deterministic fingerprints and a merge command that preserves the highest severity while recording all contributing tools.

Input handling is readable but permissive:

- Missing target files can collapse into “no files matched” rather than listing each missing path.
- Large and binary-like files have no size/encoding guard.
- Symlink behavior and duplicate paths are not normalized explicitly.
- JSON config validation checks domain properties but is not backed by a published JSON Schema.
- Regex-based checkers intentionally miss macros, preprocessing, elaboration, and cross-file semantics; these limitations are documented well and should remain prominent.

### Evaluation integrity

Several result-model details need correction:

- `available = bool(text)` conflates empty valid output with missing output.
- `[runner error] ...` is non-empty and therefore counted as available.
- Discovery summary denominators use all prompts while numerators use only available prompts. Conservative reporting is defensible, but the table should separately show `passed / graded / total` to avoid ambiguity.
- Replay with all transcripts missing exits 0 unless `--fail-under` is explicitly supplied.
- Reports do not capture repository commit, skill content hash, eval-suite hash, Python/package versions, OS, model provider request ID, latency, token usage, or cost.
- The regex graders can reward keyword inclusion without establishing semantic correctness. The methodology acknowledges this, but results should be described as deterministic proxy checks rather than comprehensive correctness.

Add explicit statuses—`passed`, `failed`, `missing`, `runner_error`, `timeout`, `invalid_output`, and `skipped`—and make summary aggregation status-aware. Record immutable hashes of every input and a machine-readable environment manifest. Claims about measurable improvement should remain withheld until recorded on/off transcripts exist and independent replay succeeds; reproducible claims should expose methodology, inputs, and source evidence rather than only headline numbers.[^6]

### Storage design

For the current scale, Git-tracked Markdown plus JSON is inspectable and easy to review. For repeated model/version matrices, move the canonical result store to append-only JSONL or SQLite, then generate Markdown from it. A practical normalized schema would use:

- `runs(run_id, commit_sha, model, runner, started_at, environment_hash)`
- `cases(case_id, skill, family, prompt_hash, suite_hash)`
- `responses(run_id, case_id, mode, status, latency_ms, tokens, transcript_path, response_hash)`
- `grader_results(run_id, case_id, mode, grader_id, passed, detail)`

This enables resumption, deduplication, trend analysis, and reliable comparison without requiring a heavyweight external database.

## 4. 📖 Documentation, Tool Setup, & Extensibility

### Documentation quality

Documentation is one of the repository’s strongest areas. The README clearly states scope, names the seven skills, gives plugin-install commands, provides standalone examples, labels model results “not run,” explains evaluation families, identifies heuristic limitations, and avoids claiming unmeasured model improvement. `docs/eval-methodology.md`, `docs/authoring-skills.md`, contribution templates, and false-result issue forms create a credible maintainer workflow.

The setup surface is also compact:

- Python checkers use standard-library parsing where possible.
- `Makefile` exposes `check`, `validate`, `scripts`, `smoke`, `evals`, and `record` targets.
- CI covers Python 3.10, 3.12, and 3.13.
- Shell wrappers degrade explicitly when external EDA/static-analysis tools are missing.
- Plugin manifests are concise and valid in structure.

### Setup defects

The present documentation overstates what a clean checkout proves:

- The README says `tools/test_scripts.py` produces 8/8 passes, but the audited snapshot produces 7/8 because an expected OpenLane run fixture is absent.
- The README says the ONNX quantization path runs end to end, but a fresh environment from `requirements-dev.txt` fails because symbolic shape inference requires undeclared `sympy`.
- The README says Python 3.8+ for checkers, while CI only exercises 3.10, 3.12, and 3.13. Either test 3.8/3.9 or raise the documented minimum.
- `ai-edge-litert` is intentionally omitted, leaving the actual TFLite report path untested. That limitation is documented, but a scheduled optional-dependency job should exercise it.

Add `pyproject.toml` with supported Python metadata, dependency groups, console entry points, formatter/linter configuration, and package versioning. Add a reproducible bootstrap command and a CI job that creates a brand-new environment from the locked dependencies.

### Extensibility

For adding a new **skill**, the repository is well designed:

- `skills/<name>/SKILL.md`
- `evals/eval.yaml`
- optional `scripts/` and `references/`
- `new_skill.py` scaffolding
- strict structural validation
- usefulness/discovery/adversarial cases
- contributor requirements and honest-limits policy

For adding a new **OSINT module, spider, or target**, there is no architecture—and that is correct for the current scope. Do not graft spiders into `skills/`. If OSINT becomes a real objective, create a separate repository or top-level Python package with explicit interfaces such as `Collector`, `Policy`, `Normalizer`, `Sink`, and `EvidenceRecord`. A skill in this repository could then teach agents how to use that separate collector, but should not silently perform collection.

### Maintainer readiness

Before a public release, add:

- `SECURITY.md` with vulnerability reporting and supported versions.
- `CODEOWNERS` for domain-sensitive skills.
- Tagged releases and immutable changelog entries.
- A provenance/SBOM workflow and release checksums.
- Branch protection requiring all test jobs.
- A compatibility matrix for Claude Code/plugin format versions.
- Machine-readable schemas for findings and eval results.
- A release gate that proves README claims from the exact release commit.

GitHub Actions is intended to automate repository workflows such as validation and testing, so these release checks belong in CI rather than in manual maintainer memory.[^7]

## 5. 🚀 Actionable Improvements (Prioritized Matrix)

### Priority matrix

| Priority | Improvement | Impact | Effort | Primary files | Status (2026-10-16) |
| --- | --- | ---: | ---: | --- | --- |
| P0 | Restore missing OpenLane fixture and fix `.gitignore` rule | High | Low | `.gitignore`, `evals/fixtures/openlane/`, `tools/test_scripts.py` | ✅ Done |
| P0 | Declare `sympy` or disable symbolic shape inference deliberately | High | Low | `requirements-dev.txt`, `quantize_onnx.py`, `tools/smoke_imports.py` | ✅ Done |
| P0 | Distinguish runner errors/missing data and fail evidence CI appropriately | High | Medium | `evals/eval_runner.py`, workflow, methodology docs | ✅ Done |
| P0 | Prevent transcript path traversal and sanitize committed transcripts | High | Medium | `evals/eval_runner.py`, `evals/transcripts/`, validator | ✅ Done |
| P1 | Lock Python dependencies and pin Actions immutably | High | Medium | lock/constraints file, `.github/workflows/test.yml`, Dependabot | ◐ Actions pinned; no hash lock |
| P1 | Record real on/off transcripts and publish reproducible evidence | High | Medium | `evals/transcripts/`, README eval block | ⏳ Open (needs a live model run) |
| P1 | Add schemas and SARIF output | High | High | new `schemas/`, checker scripts, CI | ⏳ Open |
| P1 | Harden live model execution with retries, checkpointing, and metadata | High | High | `evals/eval_runner.py` | ◐ Retries + metadata; no checkpoint/resume |
| P2 | Package tools with `pyproject.toml` and entry points | Medium | Medium | new `pyproject.toml`, script imports | ⏳ Open |
| P2 | Add size/symlink/path guards for untrusted trees | Medium | Medium | all recursive checkers | ⏳ Open (documented in `SECURITY.md`) |
| P3 | Optimize repeated regex compilation and line lookup | Low | Low | checker scripts | ⏳ Open |

### Quick Wins — Low Effort / High Impact

- **Fix the ignored fixture immediately.** Change the broad `.gitignore` entry `runs/` to `/runs/` if only root output is intended, or add `!evals/fixtures/openlane/runs/**`. Commit a minimal failed-run fixture matching the expectations in `tools/test_scripts.py`.
- **Repair the ONNX clean install.** Add a compatible `sympy` dependency because `quant_pre_process(..., skip_symbolic_shape=False)` requires it, or explicitly set `skip_symbolic_shape=True` only after proving that accuracy and shape handling remain valid. Add a test asserting the selected behavior.
- **Stop treating operational failures as model answers.** In `CliRunner.generate`, return a structured result with status, stdout, stderr, return code, and latency; catch timeout and missing-executable exceptions. Never pass runner-error text into semantic graders.
- **Add `--fail-on-missing`.** Make replay fail when expected transcripts are absent in release/evidence CI. Keep a separate non-blocking command for contributor previews.
- **Validate transcript keys.** Restrict skill names and case IDs to `^[a-z0-9][a-z0-9._-]*$`, resolve output paths, and reject writes outside the configured transcript root.
- **Add transcript secret scanning.** Run Gitleaks or an equivalent scanner on commits and add a repository-specific sanitizer before `--record` output is accepted.
- **Expand `.gitignore`.** Add `.env`, `.env.*`, `!.env.example`, `.python-version` if local-only, coverage artifacts, and temporary model/provider logs.
- **Pin Actions.** Replace `actions/checkout@v7` and `actions/setup-python@v7` with verified 40-character SHAs and retain Dependabot updates; GitHub recommends immutable SHA pinning when a dependency lockfile is not used.[^4]
- **Correct README evidence claims.** Until the release workflow is green from a clean checkout, replace “8/8” and “runs end to end” with the current verified status. Generate the claims table from CI artifacts rather than editing it manually.
- **Align Python support.** Test 3.8 and 3.9 or change documentation and package metadata to 3.10+.
- **Add `SECURITY.md`.** Include private reporting instructions, supported versions, transcript privacy warnings, and a statement that these heuristic tools must not replace authoritative EDA/compiler analysis.

### Major Projects — High Effort / High Impact

- **Refactor the evaluator around typed run records.** Introduce a `GenerationResult` model containing `status`, `text`, `error`, `latency_ms`, `provider_request_id`, token usage, and cost. Make every runner implement the same contract and make every grader reject non-success statuses.
- **Build resumable, bounded-concurrency evaluation.** Use a checkpoint database or append-only JSONL; add configurable concurrency, exponential backoff with jitter, retry classification, rate budgets, and resume-by-content-hash. Preserve strict on/off comparability by recording identical model parameters and immutable input hashes.
- **Create a provenance-complete result schema.** Capture commit SHA, dirty-tree state, skill hash, suite hash, fixture hashes, Python and package versions, OS/architecture, runner/model identifiers, generation parameters, timestamps, and grader versions. Generate README tables only from signed or checksum-verified run artifacts.
- **Standardize checker output and add SARIF.** Define `finding-v1` JSON Schema, migrate every checker to a shared library, produce deterministic fingerprints, and support SARIF uploads to GitHub code scanning.
- **Harden untrusted-input execution.** Apply file-size/count/depth limits, avoid following external symlinks, normalize paths, reject control characters, isolate EDA tools in a container, enforce CPU/memory/time limits, and replace interpolated Yosys command strings with safely generated scripts.
- **Establish reproducible dependency management.** Add `pyproject.toml`, a hash-locked environment, optional groups for ONNX/TFLite and live evaluation, an SBOM, and two CI lanes: locked/reproducible and latest-compatible. The latter catches ecosystem drift without breaking release reproducibility.
- **Produce real model evidence.** Run all 35 usefulness cases in both modes plus discovery/adversarial prompts, commit sanitized transcripts, replay them independently, and publish per-case details—not only aggregate pass counts. Repeat across more than one model/version before making cross-model claims.
- **Add regression corpora from real defects.** Expand beyond planted single-file examples to multi-file RTL, preprocessor macros, parameterized modules, real OpenLane reports, compile databases, and genuine TFLite artifacts with licenses/provenance recorded.
- **Keep OSINT separate if pursued.** Create a dedicated repository with collectors, policy enforcement, normalization, evidence lineage, and sinks. Do not add stealth scraping, CAPTCHA bypass, or proxy rotation as incidental features of this hardware-skill plugin.

### Micro-optimizations — Low Effort / Low Impact

- Precompile module-level regular expressions reused across files instead of compiling inside checking loops.
- Replace repeated `text.count("\n", 0, pos)` calls with a precomputed newline-offset index for very large files.
- Deduplicate normalized paths returned from mixed file/directory arguments before scanning.
- Add deterministic sorting keys that include rule ID after severity, file, and line.
- Write large JSON reports incrementally or compactly; keep pretty-printing as an optional presentation step.
- Add `--quiet`, `--format text|json|sarif`, and `--output FILE` consistently across all checkers.
- Print tool and schema versions in `--version` and JSON metadata.
- Add column numbers where regex match positions are already known.
- Validate `--compile-db` has a following argument in `run_static.sh`; current `shift 2` handling can terminate unclearly on malformed input.
- Use `find ... -print0`/null-delimited reads in shell wrappers to handle filenames containing newlines safely.
- Add `--` before positional file arguments for external tools where supported.
- Cache skill frontmatter parsing during evaluation rather than importing validator logic dynamically for each process invocation.
- Separate generated timestamp from evidence timestamp so replaying old transcripts does not visually imply that model calls occurred at replay time.
- Add unit tests for malformed YAML, duplicate case IDs, invalid regex graders, empty responses, timeout responses, runner failures, partial transcript sets, and path traversal attempts.

<a id="remediation-status"></a>

## 6. ✅ Remediation Status

Applied to the working tree on 2026-10-16 and not committed yet. Each row names the finding from sections 1–5, what changed, and the evidence.

### Fixed

| Finding | Fix | Evidence |
| --- | --- | --- |
| OpenLane failed-run fixture ignored by unanchored `runs/` (7/8 on a fresh clone) | `.gitignore` keeps `runs/` for real OpenLane output but re-includes `!evals/fixtures/openlane/runs/`; the synthetic fixture (two `metrics.json` and one `error.log`) is now tracked | `git check-ignore` no longer matches the fixture; `tools/test_scripts.py` passes 8/8 |
| `sympy` undeclared; ONNX smoke fails in a fresh environment | `sympy>=1.12` added to `requirements-dev.txt` with the reason; `quantize_onnx.py` checks for it up front and prints how to install it instead of failing mid-run | `tools/smoke_imports.py` passes in a brand-new venv built only from `requirements-dev.txt` |
| `[runner error]` text graded as a model answer; `available = bool(text)` | New `Generation` record with statuses `ok`, `missing`, `empty`, `runner_error`, `timeout`. Only `ok` is graded. Failures are never recorded as transcripts. `TimeoutExpired`, `OSError`, a non-zero exit and a missing `claude` binary are all handled. Legacy `[runner error]` transcripts are classified as errors on replay. | `tools/test_eval_runner.py` (`test_runner_error_is_not_graded`, `test_replay_missing_and_legacy_error`) |
| A failed discovery call counted as "correctly stayed quiet" | Discovery `passed` now requires `ok`; columns read `passed/graded (of N)` | `test_discovery_error_never_passes_negative`, `test_summary_counts_errors_and_ratios` |
| Replay with 152 missing transcripts exits 0 | `--fail-on-missing` flag; a `release evidence` CI job runs it on `v*` tags; `make evidence`. Default replay stays a non-blocking preview. The runner always exits 1 on a runner error or timeout. | `ExitCodes` tests: exit 0 by default, exit 1 with the flag |
| Transcript path traversal via case IDs | Skill names and case IDs must match `^[a-z0-9][a-z0-9._-]*$`; duplicate IDs are rejected; every transcript path is resolved and checked to stay under its root, for replay as well as recording | `TranscriptPaths`, `SuiteLoading` tests |
| No transcript sanitiser | `tools/check_transcripts.py` scans for Anthropic/OpenAI/AWS/GitHub/Google/Slack tokens, private keys, JWTs, quoted secrets, non-example e-mail addresses, home-directory paths and confidentiality markers. The recorder writes matching responses to `evals/out/quarantine/` instead of `evals/transcripts/`. CI scans the committed directory. Matches are truncated in output, so a secret is never echoed to a log. | `TranscriptScan` tests; CI step `transcript scan` |
| Yosys command injection through filenames in `lint_rtl.sh` | Commands go into a generated `.ys` file with quoted paths. Names containing `;`, `#`, `"` or control characters are refused. `--top` must be a Verilog identifier. | Stub-`yosys` test: `my counter.sv` is passed quoted and `evil;tee x.sv` is refused |
| `--compile-db` / `--top` with no argument terminate unclearly; newline-unsafe `find`; option-like filenames | Both wrappers exit 2 with a message. Scans use `find -print0` with `read -d ''`. Paths beginning with `-` are rewritten to `./-…`, and `--` ends option parsing. | Manual runs; `shellcheck -S style` clean |
| Mutable `@v7` action tags | `actions/checkout@3d3c42e…` (v7.0.1) and `actions/setup-python@5fda3b9…` (v7.0.0), both resolved with `git ls-remote`; Dependabot comment updated | `.github/workflows/test.yml` |
| Reports lack provenance | `results.json` records the commit SHA, dirty-tree flag, Python version, platform and per-skill `SKILL.md`+`eval.yaml` SHA-256. Each response records prompt and response hashes, latency, and (API runner) token counts, request ID and stop reason. | `evals/eval_runner.py` |
| API runner has no retry policy | SDK retries raised to 5 (exponential backoff on 429/5xx/connection errors). `APITimeoutError` and `APIError` become statuses instead of aborting the run. | `evals/eval_runner.py` |
| No `.env` ignores, no `SECURITY.md` | `.env`, `.env.*`, `*.pem`, `*.key` and coverage output ignored; `.env.example` added; `SECURITY.md` covers private reporting, supported versions, the heuristic-tool disclaimer, untrusted-input limits and live-run privacy | new files |
| README says Python 3.8+ while CI tests 3.10/3.12/3.13 | Documentation (README, wrapper error text) raised to 3.10+ | README |
| README "13 scripts compile" | Updated to 15, since two tools were added; README and the methodology claims table list the new checks | README, `docs/eval-methodology.md` |

Docs updated alongside: `CHANGELOG.md` (Unreleased), `CONTRIBUTING.md` (case-ID slug rule, transcript scan, synthetic-fixture rule), `docs/eval-methodology.md` (status table, exit codes, privacy of live runs), `evals/transcripts/README.md` (quarantine flow), and `Makefile` (`unit`, `transcripts`, `evidence` targets).

### Verification run (2026-10-16, Windows 11, Python 3.10.0)

| Command | Result |
| --- | --- |
| `python tools/validate_skills.py --strict` | 7/7 skills pass |
| `python tools/test_scripts.py` | 8/8 pass |
| `python tools/test_eval_runner.py` | 17 tests, all pass |
| `python tools/check_transcripts.py` | 1 file scanned, 0 findings |
| `python tools/smoke_imports.py` | 15 scripts compile; ONNX quantisation PASS |
| Fresh venv: `pip install -r requirements-dev.txt` then `smoke_imports.py` | `sympy` 1.14.0 installed; 15 scripts compile; ONNX quantisation PASS; harness unit tests pass |
| `python evals/eval_runner.py --runner replay` | exit 0, every case "not run" (no transcripts yet) |
| `python evals/eval_runner.py --runner replay --fail-on-missing` | exit 1, as intended |
| `shellcheck -S style skills/*/scripts/*.sh` | clean |

Not exercised locally: the CI workflow itself (it runs on the next push), and real Yosys, Verilator, cppcheck and clang-tidy runs, since none of these tools is installed here.

### Still open

- **Real model evidence (P1).** Run `make record` (all 35 usefulness cases in both modes, plus the discovery and adversarial prompts), review the transcripts, commit them, then tag a release so the `release evidence` job proves the README table. This requires a live model run and cannot be done offline.
- **Hash-locked dependencies (P1).** Add a `requirements-lock.txt` generated with `pip-compile --generate-hashes` for each Python version in CI. Keep `requirements-dev.txt` as the loose "latest compatible" lane.
- **Checkpoint/resume and bounded concurrency for live runs (P1).** Statuses and metadata exist now; append-only JSONL with resume-by-hash does not.
- **`finding-v1` JSON Schema and SARIF output (P1).** Includes a shared checker library and deterministic fingerprints.
- **`pyproject.toml` and entry points (P2).**
- **Size, count, depth and symlink limits in recursive checkers (P2).** Currently documented in `SECURITY.md` as a known limit.
- **Optional-dependency CI lane for `tflite_report.py` with `ai-edge-litert` (P2).**
- **Maintainer items:** `CODEOWNERS`, branch protection requiring all jobs, an SBOM/provenance workflow, and a Claude Code plugin-format compatibility matrix.
- **Micro-optimisations (P3)** listed in section 5.

---

## References

[^1]: Anthropic, [Agent Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview). Skills are folders of instructions, scripts and resources loaded when relevant.
[^2]: Anthropic, [Get started with Claude](https://platform.claude.com/docs/en/get-started). Export your API key as an environment variable; the SDK reads `ANTHROPIC_API_KEY` automatically.
[^3]: GitHub, [Secure use reference (Enterprise Server 3.17)](https://docs.github.com/en/enterprise-server@3.17/actions/reference/security/secure-use). Pinning an action to a full-length commit SHA is currently the only way to use an action as an immutable release.
[^4]: GitHub, [Secure use reference](https://docs.github.com/en/actions/reference/security/secure-use). SHA pinning mitigates a bad actor adding a backdoor to an action's repository.
[^5]: IETF, [RFC 9309: Robots Exclusion Protocol](https://www.rfc-editor.org/rfc/rfc9309.html). Specifies `robots.txt`; it states the rules are not a form of access authorization.
[^6]: SSW Rules, [Do you replace vague claims with measurable facts?](https://www.ssw.com.au/rules/back-claims-with-data) Publish the methodology and how to reproduce your own statistics.
[^7]: GitHub, [GitHub Actions documentation](https://docs.github.com/en/actions).
[^8]: GitHub, [SARIF support for code scanning](https://docs.github.com/en/code-security/code-scanning/integrating-with-code-scanning/sarif-support-for-code-scanning). The format behind the SARIF recommendation in sections 3 and 5.
[^9]: GitHub, [Keeping your actions up to date with Dependabot](https://docs.github.com/en/code-security/dependabot/working-with-dependabot/keeping-your-actions-up-to-date-with-dependabot). Dependabot updates SHA-pinned actions.
