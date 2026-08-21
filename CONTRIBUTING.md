# Contributing

1. Open an issue describing the evidence, formula, source and safety impact.
2. Do not add simulated values to production paths.
3. Preserve explicit live/cache/baseline/model/fixture states.
4. Add deterministic tests and, where appropriate, independent oracle checks.
5. Run:

```bash
python -m pip install -r requirements.txt
PYTHONPATH=src python -m compileall -q src apps audit
PYTHONPATH=src pytest -q
```

6. Live tests are opt-in:

```bash
PYTHONPATH=src pytest -m live -o addopts='' -q -vv
```

Never include secrets, farmer PII, raw evidence or operational mission traces without authorization.
