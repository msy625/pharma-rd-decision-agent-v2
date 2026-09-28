# Compatibility tests

The current website uses normalized template APIs and institution-oriented evidence APIs. A small compatibility surface remains registered for older clients; its tests are marked with `compatibility` so it can be run or audited independently.

Run the current default suite:

```bash
./.venv/bin/python -m pytest -q -m "not compatibility"
```

Run retained legacy-route checks:

```bash
./.venv/bin/python -m pytest -q -m compatibility
```

Compatibility-marked modules cover old company profile/comparison routes, the old company timeline and decision-brief routes, and legacy frontend degradation behavior. These routes are retained; marking them does not disable them or exclude them from an unfiltered full test run.
