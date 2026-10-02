# utils/update_checker.py
"""
Update Checker Utility

Checks the public GitHub repository for newer Solar Monitoring releases and
compares versions using semantic versioning.

Features:
- GitHub API / release tag lookup for jcvsite/solar-monitoring
- Semantic version comparison via packaging.version
- Safe wrapper suitable for background startup checks
- Returns structured update-available metadata for UI/logging

GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""

import logging
import urllib.request
import urllib.error
import json
from typing import Optional, Dict, Any
from packaging import version

logger = logging.getLogger(__name__)

# GitHub API configuration
GITHUB_API_URL = "https://api.github.com/repos/{owner}/{repo}/releases/latest"
GITHUB_RAW_URL = "https://raw.githubusercontent.com/{owner}/{repo}/{branch}/main.py"

# Hardcoded repository configuration for jcvsite/solar-monitoring
REPO_OWNER = "jcvsite"
REPO_NAME = "solar-monitoring"
DEFAULT_BRANCH = "main"

# Request timeout in seconds
REQUEST_TIMEOUT = 10


def normalize_update_channel(value: str) -> str:
    """Return ``release`` or ``main``. Unknown values fall back to ``release``."""
    channel = (value or "").strip().lower()
    if channel in ("release", "main"):
        return channel
    if channel:
        logger.warning("Unknown UPDATE_CHANNEL %r. Using release.", value)
    return "release"


def _github_json(url: str) -> Optional[Dict[str, Any]]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "solar-monitoring",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        if response.status != 200:
            logger.warning(f"GitHub API returned status {response.status}")
            return None
        return json.loads(response.read().decode("utf-8"))


def get_latest_release(repo_owner: str = REPO_OWNER,
                       repo_name: str = REPO_NAME) -> Optional[Dict[str, str]]:
    """Return the latest release tag, semver, and zipball URL."""
    try:
        url = GITHUB_API_URL.format(owner=repo_owner, repo=repo_name)
        logger.debug(f"Checking for updates from: {url}")
        data = _github_json(url)
        if not data:
            return None
        tag = str(data.get("tag_name") or "").strip()
        zipball = str(data.get("zipball_url") or "").strip()
        if not tag or not zipball:
            logger.warning("GitHub release is missing tag_name or zipball_url")
            return None
        return {"tag": tag, "version": tag.lstrip("v"), "zipball_url": zipball}
    except urllib.error.HTTPError as e:
        if e.code == 404:
            logger.warning(f"Repository {repo_owner}/{repo_name} not found or no releases available")
        else:
            logger.warning(f"HTTP error checking for updates: {e.code} - {e.reason}")
        return None
    except urllib.error.URLError as e:
        logger.warning(f"Network error checking for updates: {e.reason}")
        return None
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse GitHub API response: {e}")
        return None
    except Exception as e:
        logger.warning(f"Unexpected error checking for updates: {e}")
        return None


def get_latest_version_from_github(repo_owner: str = REPO_OWNER,
                                 repo_name: str = REPO_NAME) -> Optional[str]:
    """
    Fetch the latest release version from GitHub API.

    Args:
        repo_owner: GitHub repository owner/username
        repo_name: GitHub repository name

    Returns:
        Latest version string if successful, None if failed
    """
    release = get_latest_release(repo_owner, repo_name)
    if not release:
        return None
    logger.debug(f"Latest release version from GitHub: {release['version']}")
    return release["version"]


def get_main_head(repo_owner: str = REPO_OWNER,
                  repo_name: str = REPO_NAME,
                  branch: str = DEFAULT_BRANCH) -> Optional[Dict[str, str]]:
    """Return the current commit SHA on ``branch`` and a zipball URL for that SHA."""
    try:
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/commits/{branch}"
        logger.debug(f"Checking {branch} head from: {url}")
        data = _github_json(url)
        if not data:
            return None
        sha = str(data.get("sha") or "").strip()
        if not sha:
            logger.warning("GitHub commit response is missing sha")
            return None
        zipball = f"https://api.github.com/repos/{repo_owner}/{repo_name}/zipball/{sha}"
        return {"sha": sha, "zipball_url": zipball}
    except urllib.error.HTTPError as e:
        logger.warning(f"HTTP error checking {branch}: {e.code} - {e.reason}")
        return None
    except urllib.error.URLError as e:
        logger.warning(f"Network error checking {branch}: {e.reason}")
        return None
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        logger.warning(f"Failed to parse GitHub commit response: {e}")
        return None
    except Exception as e:
        logger.warning(f"Unexpected error checking {branch}: {e}")
        return None


def lookup_update_target(channel: str,
                         repo_owner: str = REPO_OWNER,
                         repo_name: str = REPO_NAME) -> Optional[Dict[str, str]]:
    """
    Resolve the configured channel to a concrete install target.

    ``release`` uses the latest release tag. ``main`` uses the branch commit SHA,
    because unreleased commits often keep the same ``__version__``.
    """
    channel = normalize_update_channel(channel)
    if channel == "main":
        head = get_main_head(repo_owner, repo_name)
        if not head:
            return None
        return {
            "channel": "main",
            "ref": head["sha"],
            "zipball_url": head["zipball_url"],
            "label": head["sha"][:7],
        }
    release = get_latest_release(repo_owner, repo_name)
    if not release:
        return None
    return {
        "channel": "release",
        "ref": release["tag"],
        "version": release["version"],
        "zipball_url": release["zipball_url"],
        "label": release["tag"],
    }


def should_auto_install(target: Optional[Dict[str, str]],
                        current_version: str,
                        applied: Optional[Dict[str, Any]]) -> bool:
    """True when ``target`` should be downloaded and installed."""
    if not target or not target.get("ref") or not target.get("zipball_url"):
        return False
    if applied and applied.get("channel") == target.get("channel") and str(applied.get("ref")) == str(target.get("ref")):
        return False
    if target.get("channel") == "main":
        return True
    latest = target.get("version") or str(target.get("ref")).lstrip("v")
    return bool(compare_versions(current_version, latest).get("update_available"))


def get_version_from_main_py(repo_owner: str = REPO_OWNER,
                           repo_name: str = REPO_NAME,
                           branch: str = DEFAULT_BRANCH) -> Optional[str]:
    """
    Fetch the version directly from main.py in the repository.
    This is a fallback method if GitHub releases are not used.
    
    Args:
        repo_owner: GitHub repository owner/username
        repo_name: GitHub repository name
        branch: Git branch to check (default: main)
        
    Returns:
        Version string if found, None if failed
    """
    try:
        url = GITHUB_RAW_URL.format(owner=repo_owner, repo=repo_name, branch=branch)
        logger.debug(f"Fetching version from main.py: {url}")
        
        with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT) as response:
            if response.status == 200:
                content = response.read().decode('utf-8')
                
                # Look for __version__ = "x.x.x" pattern
                for line in content.split('\n'):
                    line = line.strip()
                    if line.startswith('__version__') and '=' in line:
                        # Extract version string between quotes
                        version_part = line.split('=', 1)[1].strip()
                        version_str = version_part.strip('\'"')
                        logger.debug(f"Found version in main.py: {version_str}")
                        return version_str
                        
                logger.warning("Could not find __version__ in main.py")
                return None
            else:
                logger.warning(f"Failed to fetch main.py, status: {response.status}")
                return None
                
    except Exception as e:
        logger.warning(f"Error fetching version from main.py: {e}")
        return None


def compare_versions(current_version: str, latest_version: str) -> Dict[str, Any]:
    """
    Compare two version strings using semantic versioning.
    
    Args:
        current_version: Current application version
        latest_version: Latest available version
        
    Returns:
        Dictionary with comparison results:
        - 'update_available': bool - True if update is available
        - 'current': str - Current version
        - 'latest': str - Latest version
        - 'comparison': str - Human readable comparison result
    """
    try:
        current_ver = version.parse(current_version)
        latest_ver = version.parse(latest_version)
        
        update_available = latest_ver > current_ver
        
        if update_available:
            comparison = f"Update available: {current_version} → {latest_version}"
        elif latest_ver < current_ver:
            comparison = f"Running newer version: {current_version} (latest: {latest_version})"
        else:
            comparison = f"Running latest version: {current_version}"
            
        return {
            'update_available': update_available,
            'current': current_version,
            'latest': latest_version,
            'comparison': comparison
        }
        
    except Exception as e:
        logger.warning(f"Error comparing versions: {e}")
        return {
            'update_available': False,
            'current': current_version,
            'latest': latest_version,
            'comparison': f"Version comparison failed: {e}"
        }


def check_for_updates(current_version: str, 
                     repo_owner: str = REPO_OWNER,
                     repo_name: str = REPO_NAME) -> Dict[str, Any]:
    """
    Check for updates from GitHub and compare with current version.
    
    This function tries multiple methods to get the latest version:
    1. GitHub Releases API (preferred)
    2. Direct parsing of main.py from repository (fallback)
    
    Args:
        current_version: Current application version
        repo_owner: GitHub repository owner/username
        repo_name: GitHub repository name
        
    Returns:
        Dictionary with update check results
    """
    logger.info("Checking for updates...")
    
    # Try GitHub Releases API first
    latest_version = get_latest_version_from_github(repo_owner, repo_name)
    
    # Fallback to parsing main.py if releases API fails
    if not latest_version:
        logger.debug("GitHub Releases API failed, trying main.py fallback")
        latest_version = get_version_from_main_py(repo_owner, repo_name)
    
    if not latest_version:
        logger.warning("Could not determine latest version from GitHub")
        return {
            'update_available': False,
            'current': current_version,
            'latest': 'unknown',
            'comparison': 'Update check failed - could not fetch latest version'
        }
    
    # Compare versions
    result = compare_versions(current_version, latest_version)
    
    # Log the result
    if result['update_available']:
        logger.info(f"🔄 {result['comparison']}")
        logger.info(f"Visit https://github.com/{repo_owner}/{repo_name}/releases for updates")
    else:
        logger.info(f"✅ {result['comparison']}")
    
    return result


def check_for_updates_safe(current_version: str,
                          repo_owner: str = REPO_OWNER,
                          repo_name: str = REPO_NAME) -> Optional[Dict[str, Any]]:
    """
    Safe wrapper for update checking that never raises exceptions.
    
    This function ensures that update checking failures never crash the application.
    
    Args:
        current_version: Current application version
        repo_owner: GitHub repository owner/username
        repo_name: GitHub repository name
        
    Returns:
        Update check results or None if check failed
    """
    try:
        return check_for_updates(current_version, repo_owner, repo_name)
    except Exception as e:
        logger.warning(f"Update check failed with unexpected error: {e}")
        return None