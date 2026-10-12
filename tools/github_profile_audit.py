"""Read public GitHub activity; never modify accounts or repositories."""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def github_get(path: str) -> object:
    request = Request(
        f"https://api.github.com/{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "github-profile-audit",
            "X-GitHub-Api-Version": "2026-03-10",
        },
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def audit(username: str) -> dict:
    repositories = []
    page = 1
    while True:
        batch = github_get(
            f"users/{username}/repos?"
            + urlencode({"type": "owner", "per_page": 100, "page": page})
        )
        repositories.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    search = github_get(
        "search/issues?"
        + urlencode({"q": f"is:pr is:merged author:{username}", "per_page": 1})
    )
    if search.get("incomplete_results"):
        raise ValueError("GitHub returned incomplete PR search results; retry later.")
    owned_sources = [
        repo for repo in repositories
        if not repo["fork"] and repo["owner"]["login"].lower() == username.lower()
    ]
    return {
        "username": username,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "public activity only; unauthenticated read-only GitHub REST API",
        "merged_public_pull_requests": search["total_count"],
        "owned_public_source_repositories": [
            {
                "name": repo["full_name"],
                "url": repo["html_url"],
                "stars": repo["stargazers_count"],
                "stars_to_16": max(0, 16 - repo["stargazers_count"]),
            }
            for repo in sorted(owned_sources, key=lambda repo: -repo["stargazers_count"])
        ],
        "limitations": [
            "GitHub REST API does not expose a complete earned-achievements list.",
            "Metrics are evidence, not confirmation that GitHub awarded a badge.",
            "Private contributions and accepted discussion answers are not counted.",
            "The 16-star milestone is community-reported, not an API eligibility rule.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username", help="GitHub username, for example nowackk-cp")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", args.username):
        parser.error("Provide a GitHub username, not a URL or search expression.")
    try:
        result = audit(args.username)
    except HTTPError as error:
        print(f"GitHub API HTTP {error.code}; check the username or API rate limit.", file=sys.stderr)
        return 1
    except (URLError, TimeoutError, ValueError) as error:
        print(f"Audit failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
