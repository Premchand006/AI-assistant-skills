# Convenience targets. Every one of these also runs in CI.
PYTHON ?= python3

.PHONY: help check validate scripts smoke evals record clean

help:
	@echo "make check     - everything CI runs (validate + scripts + smoke + replay)"
	@echo "make validate  - frontmatter, size budgets, house style, eval files"
	@echo "make scripts   - bundled checkers against the fixtures"
	@echo "make smoke     - compile every script; run the ONNX quantisation path"
	@echo "make evals     - re-grade the committed transcripts (no API key)"
	@echo "make record    - run the evals against a live model and save transcripts"
	@echo "make clean     - remove generated files"

check: validate scripts smoke evals

validate:
	$(PYTHON) tools/validate_skills.py --strict

scripts:
	$(PYTHON) tools/test_scripts.py

smoke:
	$(PYTHON) tools/smoke_imports.py

evals:
	$(PYTHON) evals/eval_runner.py --runner replay

# Calls a real model once per case per mode. Costs tokens and takes a while.
record:
	$(PYTHON) evals/eval_runner.py --runner cli --record --update-readme

clean:
	rm -rf evals/out
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	find . -name '*.pyc' -delete
