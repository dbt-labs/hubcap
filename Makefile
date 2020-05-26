
install:
	rm -rf env
	python3 -m venv env
	env/bin/pip install -r requirements.txt

run:
	rm -rf git-tmp/ROOT
	env/bin/python hubcap.py

