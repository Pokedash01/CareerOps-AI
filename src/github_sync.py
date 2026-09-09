"""
GitHub sync utility for CareerOps bot.
Syncs local state and profile files to GitHub via the Contents API.
"""
import base64
import json
import os
from pathlib import Path
from typing import Optional

import requests


def _get_github_config():
    """Get GitHub configuration from environment."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN environment variable not set")

    repo = os.environ.get("GITHUB_REPOSITORY", "Pokedash01/CareerOps-AI")
    owner, repo_name = repo.split("/")

    return token, owner, repo_name


def _get_file_sha(token: str, owner: str, repo: str, path: str) -> Optional[str]:
    """Get the current SHA of a file in the GitHub repo, or None if it doesn't exist."""
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("sha")
        elif resp.status_code == 404:
            return None  # File doesn't exist yet
        else:
            print(f"[GitHub Sync] Error checking file {path}: {resp.status_code} {resp.text}")
            return None
    except Exception as e:
        print(f"[GitHub Sync] Exception checking file {path}: {e}")
        return None


def sync_file_to_github(local_path: Path, github_path: str, commit_message: str) -> bool:
    """
    Sync a local file to GitHub using the Contents API.

    Args:
        local_path: Path to the local file to sync
        github_path: Path in the GitHub repo (e.g., "data/state.json")
        commit_message: Commit message for the update

    Returns:
        True if sync successful, False otherwise
    """
    try:
        # Read local file
        if not local_path.exists():
            print(f"[GitHub Sync] Local file not found: {local_path}")
            return False

        content = local_path.read_bytes()
        b64_content = base64.b64encode(content).decode("utf-8")

        # Get GitHub config
        token, owner, repo = _get_github_config()

        # Check current file SHA (if exists)
        sha = _get_file_sha(token, owner, repo, github_path)

        # Prepare API request
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{github_path}"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }

        data = {
            "message": commit_message,
            "content": b64_content,
            "branch": "main",
        }

        if sha is not None:
            data["sha"] = sha

        # Push to GitHub
        resp = requests.put(url, headers=headers, json=data, timeout=15)

        if resp.status_code in (200, 201):
            print(f"[GitHub Sync] Successfully synced {github_path}")
            return True
        else:
            print(f"[GitHub Sync] Failed to sync {github_path}: {resp.status_code} {resp.text}")
            return False

    except Exception as e:
        print(f"[GitHub Sync] Exception syncing {local_path} to {github_path}: {e}")
        return False


def sync_state_to_github(state: dict) -> bool:
    """Sync the onboarding state to GitHub."""
    state_path = Path("data/state.json")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return sync_file_to_github(
        state_path,
        "data/state.json",
        "chore: update onboarding state via Telegram bot"
    )


def sync_profile_to_github(chat_id: str, profile: dict) -> bool:
    """Sync a user's profile to GitHub."""
    profile_path = Path(f"data/users/{chat_id}/profile.json")
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    return sync_file_to_github(
        profile_path,
        f"data/users/{chat_id}/profile.json",
        f"chore: update profile for user {chat_id} via Telegram bot"
    )