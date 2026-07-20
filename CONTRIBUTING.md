# Contributing

## Development Workflow

1. Create a focused branch from the current default branch.
2. Use only synthetic or deliberately public sample data.
3. Keep valuation logic, provider integrations, frontend changes, and deployment changes modular.
4. Run the repository test command and review the staged diff.

```powershell
.\RUN_TESTS_WINDOWS.ps1
git diff --check
```

## Public-Release Rules

- Never commit real customer media, storage-unit locations, personal contact details, sales history, credentials, `.env` files, databases, uploads, exports, or logs.
- Do not put provider secrets in frontend code.
- Preserve the app's verified, inferred, and unknown confidence labels.
- Do not invent product facts or prices when evidence is missing.
- Add reusable documentation rather than internal operational notes.

Pull requests must describe the change, validation performed, risk, rollback, and any remaining work.
