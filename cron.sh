#!/bin/bash

git config --global user.email "drew@fishtownanalytics.com"
git config --global user.name "Hubcap"

curl https://raw.githubusercontent.com/fishtown-analytics/hubcap/master/hub.json > hub.current.json
echo ${CONFIG} > config.json
rm -rf git-tmp/ROOT
python hubcap.py

