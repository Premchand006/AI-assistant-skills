#!/usr/bin/env bash
# Run the static analysis that is installed, in increasing order of cost, and
# say which checks were skipped. Skipped is not the same as passed.
#
# Usage: ./run_static.sh [--misra] [--compile-db build/compile_commands.json] SRC...
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MISRA=0
COMPILE_DB=""
TARGETS=()
SKIPPED=()
FAILED=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --misra) MISRA=1; shift ;;
    --compile-db) COMPILE_DB="$2"; shift 2 ;;
    -h|--help) sed -n '2,6p' "$0"; exit 0 ;;
    *) TARGETS+=("$1"); shift ;;
  esac
done

if [[ ${#TARGETS[@]} -eq 0 ]]; then
  echo "usage: $0 [--misra] [--compile-db FILE] SRC..." >&2
  exit 2
fi

echo "== ISR and shared-state check"
if ! python3 "$SCRIPT_DIR/check_isr_safety.py" "${TARGETS[@]}" --fail-on error; then
  FAILED=1
fi

echo
echo "== cppcheck"
if command -v cppcheck >/dev/null 2>&1; then
  CPPFLAGS=(--enable=warning,style,performance,portability
            --inline-suppr --error-exitcode=1 --quiet
            --suppress=missingIncludeSystem)
  [[ -n "$COMPILE_DB" ]] && CPPFLAGS+=(--project="$COMPILE_DB")

  if [[ $MISRA -eq 1 ]]; then
    # The MISRA addon needs a local copy of the rule texts; cppcheck ships the
    # addon but not the rules, which are licensed separately.
    if [[ -f "misra_rules.txt" ]]; then
      CPPFLAGS+=(--addon="{\"script\":\"misra\",\"args\":[\"--rule-texts=misra_rules.txt\"]}")
    else
      CPPFLAGS+=(--addon=misra)
      echo "note: no misra_rules.txt found; findings will show rule numbers without text"
    fi
  fi

  if ! cppcheck "${CPPFLAGS[@]}" "${TARGETS[@]}"; then
    FAILED=1
  else
    echo "clean"
  fi
else
  SKIPPED+=("cppcheck (apt install cppcheck | brew install cppcheck)")
  echo "not installed - skipped"
fi

echo
echo "== clang-tidy"
if command -v clang-tidy >/dev/null 2>&1; then
  TIDY_CHECKS='clang-analyzer-*,bugprone-*,cert-*,-clang-analyzer-osx*'
  TIDY_ARGS=(-quiet "--checks=$TIDY_CHECKS")
  [[ -n "$COMPILE_DB" ]] && TIDY_ARGS+=(-p "$(dirname "$COMPILE_DB")")
  SOURCES=()
  for t in "${TARGETS[@]}"; do
    if [[ -d "$t" ]]; then
      while IFS= read -r f; do SOURCES+=("$f"); done < <(find "$t" -name '*.c')
    else
      SOURCES+=("$t")
    fi
  done
  if ! clang-tidy "${TIDY_ARGS[@]}" "${SOURCES[@]}" -- -I. 2>/dev/null; then
    FAILED=1
  else
    echo "clean"
  fi
else
  SKIPPED+=("clang-tidy (part of LLVM)")
  echo "not installed - skipped"
fi

echo
echo "== compiler warnings"
if command -v arm-none-eabi-gcc >/dev/null 2>&1; then
  echo "arm-none-eabi-gcc found. Build with at least:"
  echo "  -Wall -Wextra -Wshadow -Wconversion -Wdouble-promotion"
  echo "  -Wformat=2 -Wundef -fno-common -Werror"
else
  SKIPPED+=("arm-none-eabi-gcc")
  echo "not installed - skipped"
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
