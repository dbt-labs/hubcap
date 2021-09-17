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

  if [ "${CLEANUP:-yes}" = 'yes' ]; then
    if [ -d "${GIT_TMP}" ]; then
        rm -rf "${GIT_TMP}"
    fi
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

# specified in Heroku's config variables
export ENV="${ENV-development}"
if [ "$ENV" = 'prod' ] || [ "$ENV" = 'test' ]; then
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
