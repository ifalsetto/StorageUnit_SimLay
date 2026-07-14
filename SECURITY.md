# Security Policy

## Supported Version

Security updates apply to the current default branch.

## Report a Vulnerability

Use GitHub's private vulnerability reporting feature when it is available. Otherwise, contact the repository owner privately through their GitHub profile. Do not publish a customer record, credential, storage-unit location, uploaded image, sales record, or exploit in a public issue.

## Data Boundary

- Keep real inventory media, customer information, sales history, addresses, and unit locations outside Git.
- Store provider keys only in a local ignored environment file or the deployment platform's secret store.
- Treat uploaded media, generated exports, databases, and application logs as private runtime data.
- Use mock/sample inputs for demonstrations and automated tests.
- Review every generated CSV and JSON file before sharing it.

If a credential is committed, revoke or rotate it first. Deleting it from the latest file does not remove it from Git history.
