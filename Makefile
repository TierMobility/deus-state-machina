all:
	nosetests -s

LATEST := $(shell bash -c "find dist | sort -V -r | head -n 1")

release:
	python ./setup.py sdist
	twine upload -r pypi $(LATEST)