"""Thin wrapper around the GitHub Contents API for reading/writing a single
file in a repo. Uses only `requests`, no external GitHub SDK required."""

import base64
import requests

API_ROOT = "https://api.github.com"


class GitHubError(Exception):
    pass


def _headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_file(owner, repo, path, token, branch="main"):
    """Fetch a file's raw bytes from a GitHub repo.

    Returns (content_bytes, sha). Raises GitHubError if not found / failed.
    """
    url = f"{API_ROOT}/repos/{owner}/{repo}/contents/{path}"
    resp = requests.get(url, headers=_headers(token), params={"ref": branch}, timeout=30)
    if resp.status_code == 404:
        raise GitHubError(f"File not found: {path} (branch {branch})")
    if not resp.ok:
        raise GitHubError(f"GitHub API error {resp.status_code}: {resp.text}")

    data = resp.json()
    if isinstance(data, list):
        raise GitHubError(f"'{path}' is a directory, not a file")

    content_b64 = data["content"]
    content_bytes = base64.b64decode(content_b64)
    return content_bytes, data["sha"]


def put_file(owner, repo, path, content_bytes, message, token, branch="main", sha=None):
    """Create or update a file in a GitHub repo.

    If `sha` is None, this will look up the current sha automatically (needed
    to update an existing file); pass sha explicitly to skip that lookup.
    """
    url = f"{API_ROOT}/repos/{owner}/{repo}/contents/{path}"

    if sha is None:
        existing = requests.get(url, headers=_headers(token), params={"ref": branch}, timeout=30)
        if existing.ok:
            sha = existing.json().get("sha")
        elif existing.status_code != 404:
            raise GitHubError(f"GitHub API error {existing.status_code}: {existing.text}")

    payload = {
        "message": message,
        "content": base64.b64encode(content_bytes).decode("ascii"),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha

    resp = requests.put(url, headers=_headers(token), json=payload, timeout=60)
    if not resp.ok:
        raise GitHubError(f"GitHub API error {resp.status_code}: {resp.text}")
    return resp.json()


def list_repo_files(owner, repo, token, branch="main", path=""):
    """List files/dirs at a given path (non-recursive)."""
    url = f"{API_ROOT}/repos/{owner}/{repo}/contents/{path}"
    resp = requests.get(url, headers=_headers(token), params={"ref": branch}, timeout=30)
    if not resp.ok:
        raise GitHubError(f"GitHub API error {resp.status_code}: {resp.text}")
    return resp.json()
