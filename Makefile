
run:
	rm -rf git-tmp/ROOT
	python hubcap.py

setup_creds:
	echo ${CONFIG} > config.json

