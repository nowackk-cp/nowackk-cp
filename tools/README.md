# GitHub Profile Audit

A small GitHub REST API integration that reports public merged pull requests
and stars on public, non-fork repositories owned by a user. It provides evidence
for checking profile achievement milestones; it does not claim to award badges.

Requires Python 3.10 or newer. No packages, login, token, or account permissions
are required. The script only sends GET requests to `api.github.com`.

```sh
python tools/github_profile_audit.py nowackk-cp
```

The output is JSON, including a UTC timestamp and explicit limitations. Private
activity and accepted discussion answers are excluded. GitHub's public API
does not provide a complete list of earned achievements. Unauthenticated API
rate limits apply; API errors cause a nonzero exit code instead of a misleading
report. The script paginates repository results and rejects incomplete PR search
results.

Support: [aemryld@gmail.com](mailto:aemryld@gmail.com).

API documentation:
- [List repositories for a user](https://docs.github.com/en/rest/repos/repos#list-repositories-for-a-user)
- [Search issues and pull requests](https://docs.github.com/en/rest/search/search#search-issues-and-pull-requests)

Milestone reference:
[Community achievement catalog](https://github.com/Schweinepriester/github-profile-achievements).

Developed with AI assistance (Codex).
