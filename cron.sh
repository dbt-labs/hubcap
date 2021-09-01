#!/bin/bash

# ==
# == Setup
# ==

export RUN_DIR="$(pwd)"
export GIT_TMP="$RUN_DIR/git-tmp"

exit_routine() {
  local -r exit_status="${1}"

    if [ -d "${GIT_TMP}" ]; then
        rm -rf "${GIT_TMP}"
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
    email='drew@fishtownanalytics.com'
    user_name='dbt-hubcap'
else
    email='test@notarealuser.com'
    user_name='dbt-hubcap-staging'
fi

git config --global user.email "${email}"
git config --global user.name "${user_name}"

if ! [ -d "${GIT_TMP}" ]; then
    mkdir "${GIT_TMP}"
else
    >&2 printf "Error: ${GIT_TMP} already exists. Deleting and exiting."
    exit 1
fi

python3 hubcap/hubcap.py
