#!/bin/bash -ex

git config --global user.email "drew@fishtownanalytics.com"
git config --global user.name "Hubcap"

rm -rf git-tmp/ROOT
which python
python3 hubcap/hubcap.py

