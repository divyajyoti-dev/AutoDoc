"""
GitHub Integration for AutoDoc.

This module provides GitHub API integration to fetch additional metadata
that cannot be extracted from local files:
    - Repository contributors as authors
    - Repository description
    - Topics/tags
    - Language statistics
    - Star count and other metrics

Environment Variables:
    - GITHUB_TOKEN: Personal access token for higher rate limits (optional)

Note: Works without authentication but has lower rate limits (60 req/hour).
With a token, rate limit is 5000 req/hour.
"""

import os
import re
import urllib.request
import urllib.error
import json
from typing import Any, Optional
from dataclasses import dataclass

from autodoc.schema import Author, Confidence, MetadataField, ProjectMetadata


@dataclass
class GitHubRepo:
    """Parsed GitHub repository information."""
    owner: str
    repo: str

    @property
    def api_url(self) -> str:
        """Get the API URL for this repo."""
        return f"https://api.github.com/repos/{self.owner}/{self.repo}"

    @property
    def contributors_url(self) -> str:
        """Get the contributors API URL."""
        return f"{self.api_url}/contributors"

    @property
    def languages_url(self) -> str:
        """Get the languages API URL."""
        return f"{self.api_url}/languages"


def parse_github_url(url: str) -> Optional[GitHubRepo]:
    """
    Parse a GitHub URL to extract owner and repo.

    Supports formats:
        - https://github.com/owner/repo
        - https://github.com/owner/repo.git
        - git@github.com:owner/repo.git
        - github.com/owner/repo

    Args:
        url: GitHub repository URL

    Returns:
        GitHubRepo with owner and repo, or None if not a valid GitHub URL
    """
    # HTTPS format
    https_match = re.match(
        r'https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$',
        url,
    )
    if https_match:
        return GitHubRepo(owner=https_match.group(1), repo=https_match.group(2))

    # SSH format
    ssh_match = re.match(
        r'git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$',
        url,
    )
    if ssh_match:
        return GitHubRepo(owner=ssh_match.group(1), repo=ssh_match.group(2))

    # Simple format (github.com/owner/repo)
    simple_match = re.match(
        r'github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$',
        url,
    )
    if simple_match:
        return GitHubRepo(owner=simple_match.group(1), repo=simple_match.group(2))

    return None


class GitHubClient:
    """
    Client for GitHub API interactions.

    Uses urllib to avoid external dependencies. Supports optional
    authentication via GITHUB_TOKEN environment variable.
    """

    def __init__(self, token: Optional[str] = None):
        """
        Initialize GitHub client.

        Args:
            token: GitHub personal access token (or uses GITHUB_TOKEN env var)
        """
        self.token = token or os.environ.get("GITHUB_TOKEN")

    def _make_request(self, url: str) -> Optional[dict[str, Any]]:
        """
        Make an authenticated request to the GitHub API.

        Args:
            url: API endpoint URL

        Returns:
            JSON response as dict, or None on error
        """
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "AutoDoc/0.1.0",
        }

        if self.token:
            headers["Authorization"] = f"token {self.token}"

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 403:
                print("GitHub API rate limit exceeded. Set GITHUB_TOKEN for higher limits.")
            elif e.code == 404:
                pass  # Repo not found, silent fail
            else:
                print(f"GitHub API error: {e.code} {e.reason}")
            return None
        except Exception as e:
            print(f"GitHub request failed: {e}")
            return None

    def get_repo_info(self, repo: GitHubRepo) -> Optional[dict[str, Any]]:
        """
        Get repository information.

        Args:
            repo: GitHubRepo to fetch info for

        Returns:
            Repository data dict, or None on error
        """
        return self._make_request(repo.api_url)

    def get_contributors(
        self,
        repo: GitHubRepo,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Get repository contributors.

        Args:
            repo: GitHubRepo to fetch contributors for
            limit: Maximum number of contributors to return

        Returns:
            List of contributor data dicts
        """
        url = f"{repo.contributors_url}?per_page={limit}"
        result = self._make_request(url)
        return result if isinstance(result, list) else []

    def get_languages(self, repo: GitHubRepo) -> dict[str, int]:
        """
        Get repository language statistics.

        Args:
            repo: GitHubRepo to fetch languages for

        Returns:
            Dict of language -> bytes of code
        """
        result = self._make_request(repo.languages_url)
        return result if isinstance(result, dict) else {}


class GitHubEnhancer:
    """
    Enhances ProjectMetadata with GitHub repository information.

    This fetches additional metadata from GitHub that cannot be
    extracted from local files:
        - Contributors as authors
        - Repository description
        - Language statistics
        - Topics
    """

    def __init__(self, token: Optional[str] = None):
        """Initialize with optional GitHub token."""
        self.client = GitHubClient(token)

    def enhance(
        self,
        metadata: ProjectMetadata,
        github_url: Optional[str] = None,
    ) -> ProjectMetadata:
        """
        Enhance metadata with GitHub information.

        Args:
            metadata: ProjectMetadata to enhance
            github_url: GitHub URL (uses metadata.repository_url if not provided)

        Returns:
            Enhanced ProjectMetadata (modified in place)
        """
        # Get GitHub URL
        url = github_url or (metadata.repository_url.value if metadata.repository_url.value else None)
        if not url:
            return metadata

        # Parse the URL
        repo = parse_github_url(url)
        if not repo:
            return metadata

        # Fetch repo info
        repo_info = self.client.get_repo_info(repo)
        if repo_info:
            self._enhance_from_repo_info(metadata, repo_info)

        # Fetch contributors
        contributors = self.client.get_contributors(repo, limit=5)
        if contributors:
            self._add_contributors(metadata, contributors)

        # Fetch languages
        languages = self.client.get_languages(repo)
        if languages:
            self._add_languages(metadata, languages)

        return metadata

    def _enhance_from_repo_info(
        self,
        metadata: ProjectMetadata,
        repo_info: dict[str, Any],
    ) -> None:
        """Enhance metadata from repo info response."""
        # Description (only if missing)
        if metadata.description.is_placeholder() and repo_info.get("description"):
            metadata.description = MetadataField(
                value=repo_info["description"],
                confidence=Confidence.STRONG,
                source="GitHub repository description",
            )

        # Name (only if weak confidence)
        if metadata.name.confidence.value < Confidence.STRONG.value and repo_info.get("name"):
            metadata.name = MetadataField(
                value=repo_info["name"],
                confidence=Confidence.STRONG,
                source="GitHub repository name",
            )

        # Homepage URL
        if metadata.homepage_url.is_placeholder() and repo_info.get("homepage"):
            metadata.homepage_url = MetadataField(
                value=repo_info["homepage"],
                confidence=Confidence.EXPLICIT,
                source="GitHub repository homepage",
            )

        # License from GitHub
        if metadata.license.is_placeholder() and repo_info.get("license"):
            license_info = repo_info["license"]
            if license_info.get("spdx_id") and license_info["spdx_id"] != "NOASSERTION":
                metadata.license = MetadataField(
                    value=license_info["spdx_id"],
                    confidence=Confidence.EXPLICIT,
                    source="GitHub repository license",
                )

    def _add_contributors(
        self,
        metadata: ProjectMetadata,
        contributors: list[dict[str, Any]],
    ) -> None:
        """Add GitHub contributors as authors."""
        existing_names = {a.name.lower() for a in metadata.authors}

        for contrib in contributors:
            login = contrib.get("login", "")
            # Skip bots
            if "[bot]" in login or login.endswith("-bot"):
                continue

            # Use login as name (real name requires additional API call)
            name = login
            if name.lower() not in existing_names:
                author = Author(
                    name=name,
                    role="contributor",
                    source="GitHub contributors",
                )
                metadata.authors.append(author)
                existing_names.add(name.lower())

    def _add_languages(
        self,
        metadata: ProjectMetadata,
        languages: dict[str, int],
    ) -> None:
        """Add language statistics to metadata."""
        if not languages:
            return

        # Sort by bytes of code
        sorted_langs = sorted(languages.items(), key=lambda x: x[1], reverse=True)

        # Set primary language if not already set with high confidence
        if sorted_langs and metadata.primary_language.confidence.value < Confidence.STRONG.value:
            primary = sorted_langs[0][0]
            metadata.primary_language = MetadataField(
                value=primary,
                confidence=Confidence.STRONG,
                source="GitHub language statistics",
            )

        # Store all languages in extraction_warnings for now
        # (Schema doesn't have a dedicated field for this)
        total_bytes = sum(languages.values())
        lang_summary = []
        for lang, bytes_count in sorted_langs[:5]:
            percentage = (bytes_count / total_bytes) * 100
            lang_summary.append(f"{lang}: {percentage:.1f}%")

        if lang_summary:
            metadata.extraction_warnings.append(
                f"Languages detected: {', '.join(lang_summary)}"
            )


def get_github_enhancer(token: Optional[str] = None) -> GitHubEnhancer:
    """
    Get a configured GitHub enhancer.

    Args:
        token: Optional GitHub token

    Returns:
        GitHubEnhancer instance
    """
    return GitHubEnhancer(token)
