"""
Update checker utility for the Solar Monitoring Framework.

This module provides functionality to check for updates from GitHub
and compare versions using semantic versioning.
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
    try:
        url = GITHUB_API_URL.format(owner=repo_owner, repo=repo_name)
        logger.debug(f"Checking for updates from: {url}")
        
        with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                latest_version = data.get('tag_name', '').lstrip('v')  # Remove 'v' prefix if present
                logger.debug(f"Latest release version from GitHub: {latest_version}")
                return latest_version
            else:
                logger.warning(f"GitHub API returned status {response.status}")
                return None
                
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