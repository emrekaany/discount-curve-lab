# Public trust contract

This repository contains only synthetic fixtures, portable source, documentation, tests, and
original marketing visuals.

## Every release gate

Before publishing a change:

1. Run tests with branch coverage, formatting, linting, type checks, a real dry-run, package smoke
   tests, dependency checks, and full-history secret scanning.
2. Verify the tracked tree contains no workstation paths, credentials, connection strings,
   recipients, internal identifiers, or real market data.
3. Clone the repository anonymously and repeat the install plus dry-run.
4. Require protected-branch checks before accepting changes.

The public runtime intentionally excludes database, email, HTTP, cloud, scheduler, and live
market-data adapters. Those capabilities require a separately authorized architecture and are not
added to this trust boundary by a GitHub issue or pull request.

Do not post credentials, proprietary data, connection details, internal screenshots, or real
operational output on public GitHub.
