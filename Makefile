.PHONY: test smoke quick

test:
	PYTHONPATH=src python -m unittest discover -s tests -v

smoke:
	PYTHONPATH=src python -m cubesec_sim run --profile smoke --output artifacts/smoke --save-iq none

quick:
	PYTHONPATH=src python -m cubesec_sim run --profile quick --output artifacts/quick --save-iq none

