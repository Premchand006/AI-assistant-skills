# Convenience targets. Every one of these also runs in CI.
PYTHON ?= python3

.PHONY: help check validate scripts unit transcripts smoke evals evidence record clean

help:
	@echo "make check     - everything CI runs (validate, scripts, unit, transcripts, smoke, replay)"
	@echo "make validate  - frontmatter, size budgets, house style, eval files"
	@echo "make scripts   - bundled checkers against the fixtures"
	@echo "make unit      - eval harness unit tests (statuses, paths, exit codes)"
	@echo "make transcripts - scan committed transcripts for secrets and personal data"
	@echo "make smoke     - compile every script; run the ONNX quantisation path"
	@echo "make evals     - re-grade the committed transcripts (no API key)"
	@echo "make evidence  - as evals, but fail if any transcript is missing (release gate)"
	@echo "make record    - run the evals against a live model and save transcripts"
	@echo "make clean     - remove generated files"

check: validate scripts unit transcripts smoke evals

validate:
	$(PYTHON) tools/validate_skills.py --strict

scripts:
	$(PYTHON) tools/test_scripts.py

unit:
	$(PYTHON) tools/test_eval_runner.py

transcripts:
	$(PYTHON) tools/check_transcripts.py

smoke:
	$(PYTHON) tools/smoke_imports.py

evals:
	$(PYTHON) evals/eval_runner.py --runner replay

evidence:
	$(PYTHON) evals/eval_runner.py --runner replay --fail-on-missing

# Calls a real model once per case per mode. Costs tokens and takes a while.
record:
	$(PYTHON) evals/eval_runner.py --runner cli --record --update-readme

clean:
	rm -rf evals/out
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	find . -name '*.pyc' -delete
