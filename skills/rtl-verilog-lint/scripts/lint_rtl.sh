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

# Resolve an interpreter rather than assuming python3: it is python on Windows
# and on some minimal images. A missing interpreter is its own error, not a
# failed check.
PYTHON="${PYTHON:-}"
if [[ -z "$PYTHON" ]]; then
  for candidate in python3 python py; do
    if command -v "$candidate" >/dev/null 2>&1; then PYTHON="$candidate"; break; fi
  done
fi
if [[ -z "$PYTHON" ]]; then
  echo "no Python interpreter found (tried python3, python, py)." >&2
  echo "Install Python 3.10+ or set PYTHON=/path/to/python and re-run." >&2
  exit 2
fi

# A path that starts with "-" would be read as an option by the tools below.
safe_path() { if [[ "$1" == -* ]]; then printf './%s' "$1"; else printf '%s' "$1"; fi; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --top)
      if [[ $# -lt 2 || -z "$2" ]]; then echo "--top needs a module name" >&2; exit 2; fi
      TOP="$2"; shift 2 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    --) shift; while [[ $# -gt 0 ]]; do TARGETS+=("$(safe_path "$1")"); shift; done ;;
    *) TARGETS+=("$(safe_path "$1")"); shift ;;
  esac
done

# The module name is interpolated into a Yosys script, so hold it to the
# Verilog identifier grammar.
if [[ -n "$TOP" && ! "$TOP" =~ ^[A-Za-z_][A-Za-z0-9_\$]*$ ]]; then
  echo "--top '$TOP' is not a plain Verilog module name" >&2
  exit 2
fi

if [[ ${#TARGETS[@]} -eq 0 ]]; then
  echo "usage: $0 [--top MODULE] FILE_OR_DIR..." >&2
  exit 2
fi

# Expand directories to source files for the tools that want explicit files.
FILES=()
for t in "${TARGETS[@]}"; do
  if [[ -d "$t" ]]; then
    while IFS= read -r -d '' f; do FILES+=("$f"); done       < <(find "$t" -type f \( -name '*.v' -o -name '*.sv' \) -print0)
  else
    FILES+=("$t")
  fi
done

echo "== synthesisability pre-check"
if ! "$PYTHON" "$SCRIPT_DIR/check_synthesizable.py" "${TARGETS[@]}" --fail-on error; then
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
  # Filenames go into a generated script rather than a `-p` string, quoted,
  # and anything that could end a Yosys command or start a comment is refused,
  # so a hostile filename cannot inject Yosys commands.
  YS="$(mktemp "${TMPDIR:-/tmp}/lint_rtl.XXXXXX.ys")"
  trap 'rm -f "$YS"' EXIT
  UNSAFE=0
  for f in "${FILES[@]}"; do
    if [[ "$f" == *[\;\#\"]* || "$f" =~ [[:cntrl:]] ]]; then
      echo "refusing to pass '$f' to yosys: name contains ; # \" or a control character" >&2
      UNSAFE=1
    else
      printf 'read_verilog -sv "%s"
' "$f" >> "$YS"
    fi
  done
  printf 'hierarchy -top %s -check
proc
check -assert
' "$TOP" >> "$YS"
  if [[ $UNSAFE -ne 0 ]] || ! yosys -q -s "$YS"; then
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
