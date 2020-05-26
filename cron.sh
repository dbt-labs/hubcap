#!/bin/bash

echo ${CONFIG} > config.json
rm -rf git-tmp/ROOT
python hubcap.py

