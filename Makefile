all: install

install:
	python setup.py install

test:
	python -m pytest schemaperfect --doctest-modules

test-coverage:
	python -m pytest schemaperfect --cov=schemaperfect
