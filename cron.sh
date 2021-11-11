#!/bin/bash

# ==
# == Parse args
# ==

POSITIONAL=()
while [ "$#" != '0' ]; do
  case "$1" in
    # useful for wanting to save git-tmp and observe commits/build artifacts
    -n|--no-cleanup)
      CLEANUP='no'
      shift
      ;;
    *)
      POSITIONAL+=("$1")
      shift
      ;;
  esac
done
set -- "${POSITIONAL[@]}"

# ==
# == Setup
# ==

# export to expose to python script later on
export RUN_DIR="$(pwd)"
export GIT_TMP="$RUN_DIR/git-tmp"

exit_routine() {
  local -r exit_status="${1}"

  # Remove temp files to avoid future conflicts
  if [ "${CLEANUP:-yes}" = 'yes' ]; then
    if [ -d "${GIT_TMP}" ]; then
        rm -rf "${GIT_TMP}"
    fi
  fi

  # Reset local email and name git settings to wrote-author commits
  if [ "$ENV" = 'prod' ] || [ "$ENV" = 'test' ]; then
    function reset_git_params() {
      # reset machine's git config state to pre-script invocation
      if [ -z "${2}" ]; then
          git config --global --unset user."${1}"
      else
          git config --global user."${1}" "${2}"
      fi
    }
    reset_git_params 'email' "$PRIOR_GIT_EMAIL"
    reset_git_params 'name' "$PRIOR_GIT_NAME"
  fi

  exit "${exit_status}"
}

trap 'exit_routine $?' EXIT

set -o errexit
set -o errtrace
set -o nounset
set -o pipefail

# ==
# == Main
# ==

# specify ENV in Heroku's config variables or override on CLI
export ENV="${ENV:-development}"

if [ "$ENV" = 'prod' ] || [ "$ENV" = 'test' ]; then
    # User's prior state saved to avoid corrupting local git config params
    PRIOR_GIT_EMAIL="$(git config --global user.email)"
    PRIOR_GIT_NAME="$(git config --global user.name)"

    # Setup git repo for automated commits during execution
    git config --global user.email 'drew@fishtownanalytics.com'  # TODO: make this a dedicated CI user
    git config --global user.name 'dbt-hubcap'
fi

# hubcap expects a fresh git-tmp, so deletion of git-tmp is forced before script is allowed to run in full
if ! [ -d "${GIT_TMP}" ]; then
    mkdir "${GIT_TMP}"
else
    >&2 printf "Error: ${GIT_TMP} already exists. Deleting and exiting.\n"
    unset CLEANUP
    exit 1
fi

python3 hubcap/hubcap.py
