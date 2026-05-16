# Test Suite

Run from `backend`:

```powershell
$env:PYTHONPATH='.'
pytest -q
```

The suite validates prompt rules, evidence parsing, dedupe behavior, URL refresh fail-closed behavior, valuation, and end-to-end Wix CSV export.
