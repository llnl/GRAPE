#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../../../.." && pwd)"
token_file="${GRAPE_GITLAB_TOKEN_FILE:-${HOME}/.gitlab_agent_authentication/gitlab_token}"

args=("$@")
has_user=0

for arg in "${args[@]}"; do
  case "${arg}" in
    --user|--user=*)
      has_user=1
      break
      ;;
  esac
done

if [[ "${has_user}" -eq 0 ]]; then
  default_user="${GRAPE_REVIEW_USER:-${USER:-}}"
  if [[ -n "${default_user}" ]]; then
    args+=("--user=${default_user}")
  fi
fi

cmd=("${repo_root}/grape" review --printUnresolvedComments "${args[@]}")

if [[ -r "${token_file}" ]]; then
  token="$(tr -d '\r\n' < "${token_file}")"
  if [[ -n "${token}" ]]; then
    GRAPE_GITLAB_ACCESS_TOKEN="${token}" "${cmd[@]}"
    exit $?
  fi
fi

"${cmd[@]}"
