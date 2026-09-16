"""One-shot backfill of GitHub issues, PRs, commits, and workflow runs into raw bucket."""

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

GITHUB_API = "https://api.github.com"


def _s3() -> object:
    return boto3.client("s3")


def _secrets() -> object:
    return boto3.client("secretsmanager")


def handler(event: dict, _context: object) -> dict:
    """
    Pull recent GitHub data for repos listed in the event payload.

    :param event: dict with optional repos list. Example: {"repos": ["mimir"]}
    :return: summary dict. Example: {"written": 12, "repos": ["mimir"]}
    """
    token = _github_token()
    repos = event.get("repos") or json.loads(os.environ.get("REPOS_JSON", "[]"))
    org = os.environ["GITHUB_ORG"]
    bucket = os.environ["RAW_BUCKET"]
    written = 0
    for repo in repos:
        written += _backfill_repo(org, repo, token, bucket)
    logger.info("GithubBackfillFn written=%s repos=%s", written, repos)
    return {"written": written, "repos": repos}


def _github_token() -> str:
    arn = os.environ["GITHUB_TOKEN_SECRET_ARN"]
    return _secrets().get_secret_value(SecretId=arn)["SecretString"]


def _backfill_repo(org: str, repo: str, token: str, bucket: str) -> int:
    count = 0
    for path, kind in (
        (f"repos/{org}/{repo}/issues", "issues"),
        (f"repos/{org}/{repo}/pulls", "pulls"),
        (f"repos/{org}/{repo}/commits", "commits"),
    ):
        count += _fetch_pages(path, token, bucket, repo, kind)
    runs_path = f"repos/{org}/{repo}/actions/runs"
    count += _fetch_pages(runs_path, token, bucket, repo, "workflow_runs")
    return count


def _list_url(path: str, kind: str) -> str:
    """
    Build the first-page GitHub API URL for a backfill resource.

    Issues and pulls default to open-only on GitHub; cycle-time analytics
    require closed/merged history, so those use state=all.

    :param path: API path without host. Example: "repos/o/r/issues"
    :param kind: backfill kind. Example: "issues"
    :return: full URL. Example: "https://api.github.com/repos/o/r/issues?per_page=100&state=all"
    """
    params = "per_page=100"
    if kind in ("issues", "pulls"):
        params += "&state=all"
    return f"{GITHUB_API}/{path}?{params}"


def _fetch_pages(path: str, token: str, bucket: str, repo: str, kind: str) -> int:
    written = 0
    url = _list_url(path, kind)
    logger.info("GithubBackfillFn fetch kind=%s repo=%s url=%s", kind, repo, url)
    while url:
        data, url = _get(url, token)
        items = data if isinstance(data, list) else data.get("workflow_runs", [])
        for item in items:
            event_id = str(item.get("id", item.get("sha", item.get("number", "unknown"))))
            now = datetime.now(timezone.utc)
            key = f"github/{now:%Y}/{now:%m}/{now:%d}/backfill-{repo}-{kind}-{event_id}.json"
            body = json.dumps({"backfill": True, "kind": kind, "repo": repo, "payload": item})
            _s3().put_object(Bucket=bucket, Key=key, Body=body.encode("utf-8"))
            written += 1
        if isinstance(data, dict):
            break
    return written


def _get(url: str, token: str) -> tuple[object, str | None]:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        logger.warning("GitHub API error url=%s code=%s", url, exc.code)
        return {}, None
    next_url = None
    link = response.headers.get("Link", "")
    for part in link.split(","):
        if 'rel="next"' in part:
            next_url = part.split(";")[0].strip(" <>")
    return payload, next_url
