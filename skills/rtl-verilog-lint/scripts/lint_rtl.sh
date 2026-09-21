#!/usr/bin/env bash
# Run every RTL check that is installed on this machine, in increasing order of
# cost, and say plainly which ones were skipped. A clean run here means "the
# installed tools found nothing", which is not the same as "the RTL is correct".
#
# Usage: ./lint_rtl.sh [--top MODULE] FILE_OR_DIR...
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOP=""
TARGETS=()
SKIPPED=()
FAILED=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --top) TOP="$2"; shift 2 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    *) TARGETS+=("$1"); shift ;;
  esac
done

if [[ ${#TARGETS[@]} -eq 0 ]]; then
  echo "usage: $0 [--top MODULE] FILE_OR_DIR..." >&2
  exit 2
fi

# Expand directories to source files for the tools that want explicit files.
FILES=()
for t in "${TARGETS[@]}"; do
  if [[ -d "$t" ]]; then
    while IFS= read -r f; do FILES+=("$f"); done < <(find "$t" -type f \( -name '*.v' -o -name '*.sv' \))
  else
    FILES+=("$t")
  fi
done

echo "== synthesisability pre-check"
if ! python3 "$SCRIPT_DIR/check_synthesizable.py" "${TARGETS[@]}" --fail-on error; then
  FAILED=1
fi

echo
echo "== verilator --lint-only"
if command -v verilator >/dev/null 2>&1; then
  VFLAGS=(--lint-only -Wall -Wno-fatal)
  [[ -n "$TOP" ]] && VFLAGS+=(--top-module "$TOP")
  if ! verilator "${VFLAGS[@]}" "${FILES[@]}"; then
    FAILED=1
  fi
else
  SKIPPED+=("verilator (install: apt install verilator | brew install verilator)")
  echo "not installed - skipped"
fi

echo
echo "== verible style lint"
if command -v verible-verilog-lint >/dev/null 2>&1; then
  if ! verible-verilog-lint --rules=-line-length "${FILES[@]}"; then
    FAILED=1
  fi
else
  SKIPPED+=("verible-verilog-lint (github.com/chipsalliance/verible/releases)")
  echo "not installed - skipped"
fi

echo
echo "== yosys elaboration"
if command -v yosys >/dev/null 2>&1 && [[ -n "$TOP" ]]; then
  READ_CMDS=""
  for f in "${FILES[@]}"; do READ_CMDS+="read_verilog -sv $f; "; done
  if ! yosys -q -p "${READ_CMDS} hierarchy -top $TOP -check; proc; check -assert"; then
    FAILED=1
  else
    echo "elaborated cleanly"
  fi
elif ! command -v yosys >/dev/null 2>&1; then
  SKIPPED+=("yosys (install: apt install yosys | brew install yosys)")
  echo "not installed - skipped"
else
  echo "no --top given - skipped"
fi

echo
if [[ ${#SKIPPED[@]} -gt 0 ]]; then
  echo "checks skipped because the tool is missing:"
  for s in "${SKIPPED[@]}"; do echo "  - $s"; done
fi

if [[ $FAILED -ne 0 ]]; then
  echo "RESULT: at least one check reported a problem"
  exit 1
fi
echo "RESULT: every installed check passed (${#SKIPPED[@]} skipped)"
