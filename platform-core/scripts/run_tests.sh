#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3.12}"
DEPS_MARKER="${VENV_DIR}/.deps-installed"
START_TS="$(date +%s)"

print_section() {
  printf '\n== %s ==\n' "$1"
}

print_kv() {
  printf '  %-14s %s\n' "$1" "$2"
}

finish() {
  local exit_code=$?
  local end_ts elapsed
  end_ts="$(date +%s)"
  elapsed="$((end_ts - START_TS))"

  if [[ $exit_code -eq 0 ]]; then
    print_section "Done"
    print_kv "status" "passed"
    print_kv "duration" "${elapsed}s"
  else
    print_section "Done"
    print_kv "status" "failed"
    print_kv "duration" "${elapsed}s"
    print_kv "hint" "inspect the pytest output above"
  fi

  exit "$exit_code"
}

trap finish EXIT

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "error: ${PYTHON_BIN} is not installed or not on PATH" >&2
  exit 1
fi

print_section "Preflight"
print_kv "project" "${PROJECT_ROOT}"
print_kv "python" "${PYTHON_BIN}"
print_kv "venv" "${VENV_DIR}"
print_kv "targets" "full test suite"

if [[ ! -d "${VENV_DIR}" ]]; then
  print_section "Environment"
  echo "Creating virtual environment"
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

if [[ ! -x "${VENV_DIR}/bin/pytest" || ! -f "${DEPS_MARKER}" || "${PROJECT_ROOT}/pyproject.toml" -nt "${DEPS_MARKER}" ]]; then
  print_section "Dependencies"
  echo "Installing project and test dependencies"
  pip install -e '.[dev]'
  touch "${DEPS_MARKER}"
fi

cd "${PROJECT_ROOT}"

print_section "Versions"
print_kv "python" "$(python --version 2>&1)"
print_kv "pytest" "$(pytest --version)"

print_section "Run"
pytest tests
