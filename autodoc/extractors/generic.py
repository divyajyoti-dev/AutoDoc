"""
Generic Metadata Extractor

This module extracts metadata that is language-agnostic, including:
    - Project name from directory name
    - License from LICENSE file content
    - Repository URL from git config
    - README detection and analysis

This extractor runs for all projects and provides fallback values
when language-specific extractors cannot find information.

Confidence Levels:
    - License from file content: STRONG (0.8)
    - Project name from directory: WEAK (0.4)
    - Repository URL from git: STRONG (0.8)
"""

import re
import subprocess
from pathlib import Path
from typing import Optional

from autodoc.discovery import DiscoveryResult, FileCategory
from autodoc.extractors.base import BaseExtractor
from autodoc.schema import (
    Confidence,
    MetadataField,
    ProjectMetadata,
)


# Common license patterns and their SPDX identifiers
# These patterns match the beginning of license files
LICENSE_PATTERNS: list[tuple[str, str]] = [
    # MIT variants
    (r"MIT License", "MIT"),
    (r"The MIT License", "MIT"),
    (r"Permission is hereby granted, free of charge", "MIT"),

    # Apache
    (r"Apache License\s*\n\s*Version 2\.0", "Apache-2.0"),
    (r"Licensed under the Apache License, Version 2\.0", "Apache-2.0"),

    # GPL variants
    (r"GNU GENERAL PUBLIC LICENSE\s*\n\s*Version 3", "GPL-3.0"),
    (r"GNU GENERAL PUBLIC LICENSE\s*\n\s*Version 2", "GPL-2.0"),
    (r"GNU LESSER GENERAL PUBLIC LICENSE\s*\n\s*Version 3", "LGPL-3.0"),
    (r"GNU AFFERO GENERAL PUBLIC LICENSE\s*\n\s*Version 3", "AGPL-3.0"),

    # BSD variants
    (r"BSD 3-Clause License", "BSD-3-Clause"),
    (r"BSD 2-Clause License", "BSD-2-Clause"),
    (r"Redistribution and use in source and binary forms", "BSD"),

    # ISC
    (r"ISC License", "ISC"),
    (r"Permission to use, copy, modify, and/or distribute", "ISC"),

    # Mozilla
    (r"Mozilla Public License Version 2\.0", "MPL-2.0"),
    (r"Mozilla Public License, version 2\.0", "MPL-2.0"),

    # Unlicense
    (r"This is free and unencumbered software", "Unlicense"),

    # Creative Commons
    (r"Creative Commons Legal Code\s*\n\s*CC0", "CC0-1.0"),

    # WTFPL
    (r"DO WHAT THE FUCK YOU WANT TO PUBLIC LICENSE", "WTFPL"),
]


class GenericExtractor(BaseExtractor):
    """
    Extracts language-agnostic metadata from repositories.

    This extractor provides fallback values for:
        - Project name (from directory name)
        - License (from LICENSE file content)
        - Repository URL (from git remote)
        - Documentation hints (presence of docs/, examples/, etc.)

    It runs for all projects and has lower confidence than
    language-specific extractors, so its values are only used
    when better sources are not available.

    Usage:
        extractor = GenericExtractor()
        if extractor.can_handle(discovery_result):
            metadata = extractor.extract(discovery_result, root_path)
    """

    name = "Generic"

    def can_handle(self, discovery_result: DiscoveryResult) -> bool:
        """
        Generic extractor can handle any repository.

        Returns:
            Always returns True
        """
        return True

    def extract(
        self,
        discovery_result: DiscoveryResult,
        root_path: Path,
    ) -> ProjectMetadata:
        """
        Extract generic metadata from the repository.

        Args:
            discovery_result: The result of file discovery
            root_path: The repository root path

        Returns:
            ProjectMetadata with generic information
        """
        self.root_path = root_path
        metadata = ProjectMetadata()

        # Extract project name from directory name (low confidence fallback)
        metadata.name = MetadataField(
            value=root_path.name,
            confidence=Confidence.WEAK,
            source="Directory name",
            note="Inferred from repository directory name",
        )

        # Try to extract license from LICENSE file
        license_metadata = self._extract_license(discovery_result, root_path)
        if license_metadata.license.value:
            metadata.license = license_metadata.license

        # Try to get repository URL from git
        repo_url = self._get_git_remote_url(root_path)
        if repo_url:
            metadata.repository_url = MetadataField(
                value=repo_url,
                confidence=Confidence.STRONG,
                source="git remote",
                note="Extracted from git remote origin",
            )

        # Detect documentation hints
        self._detect_documentation_hints(discovery_result, metadata)

        # Detect primary language from file extensions
        self._detect_primary_language(discovery_result, metadata)

        return metadata

    def _extract_license(
        self,
        discovery_result: DiscoveryResult,
        root_path: Path,
    ) -> ProjectMetadata:
        """
        Extract license information from LICENSE file content.

        Reads the LICENSE file and matches against known patterns
        to determine the license type.

        Args:
            discovery_result: The discovery result
            root_path: Repository root path

        Returns:
            ProjectMetadata with license field populated
        """
        metadata = ProjectMetadata()

        license_files = discovery_result.get_files_by_category(FileCategory.LICENSE)

        if not license_files:
            return metadata

        # Try the first license file found
        license_file = license_files[0]
        content = self.read_file_safe(license_file.path)

        if content is None:
            return metadata

        # Try to match against known patterns
        for pattern, spdx_id in LICENSE_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                metadata.license = MetadataField(
                    value=spdx_id,
                    confidence=Confidence.STRONG,
                    source=str(license_file.relative_path),
                    note=f"Detected from LICENSE file content (pattern: {pattern[:30]}...)",
                )
                return metadata

        # Could not determine license type
        metadata.license = MetadataField(
            value="Custom",
            confidence=Confidence.WEAK,
            source=str(license_file.relative_path),
            note="LICENSE file exists but license type could not be determined",
        )

        return metadata

    def _get_git_remote_url(self, root_path: Path) -> Optional[str]:
        """
        Get the git remote origin URL.

        Args:
            root_path: Repository root path

        Returns:
            Remote URL or None if not available
        """
        try:
            result = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=root_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                # Convert SSH URLs to HTTPS for display
                if url.startswith("git@"):
                    # git@github.com:user/repo.git -> https://github.com/user/repo
                    url = url.replace(":", "/").replace("git@", "https://")
                # Remove .git suffix if present
                if url.endswith(".git"):
                    url = url[:-4]
                return url
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            # Git not available or not a git repo
            pass
        return None

    def _detect_documentation_hints(
        self,
        discovery_result: DiscoveryResult,
        metadata: ProjectMetadata,
    ) -> None:
        """
        Detect presence of documentation-related directories and files.

        Args:
            discovery_result: The discovery result
            metadata: ProjectMetadata to update
        """
        # Check for docs folder
        for f in discovery_result.files:
            path_str = str(f.relative_path).lower()

            if path_str.startswith("docs/") or path_str.startswith("doc/"):
                metadata.has_docs_folder = True

            if path_str.startswith("examples/") or path_str.startswith("example/"):
                metadata.has_examples = True

        # Check for tests
        if discovery_result.has_category(FileCategory.TEST_FILE):
            metadata.has_tests = True

        # Check for CI config
        if discovery_result.has_category(FileCategory.CI_CONFIG):
            metadata.has_ci_config = True

    def _detect_primary_language(
        self,
        discovery_result: DiscoveryResult,
        metadata: ProjectMetadata,
    ) -> None:
        """
        Detect the primary programming language based on file extensions.

        Args:
            discovery_result: The discovery result
            metadata: ProjectMetadata to update
        """
        extension_counts: dict[str, int] = {}

        for f in discovery_result.files:
            if f.category == FileCategory.SOURCE_CODE:
                ext = f.path.suffix.lower()
                extension_counts[ext] = extension_counts.get(ext, 0) + 1

        if not extension_counts:
            return

        # Map extensions to language names
        ext_to_lang = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".jsx": "JavaScript",
            ".tsx": "TypeScript",
            ".go": "Go",
            ".rs": "Rust",
            ".java": "Java",
            ".c": "C",
            ".cpp": "C++",
            ".h": "C/C++",
            ".rb": "Ruby",
            ".php": "PHP",
            ".swift": "Swift",
            ".kt": "Kotlin",
            ".scala": "Scala",
            ".cs": "C#",
            ".sh": "Shell",
        }

        # Find the most common extension
        most_common_ext = max(extension_counts, key=extension_counts.get)  # type: ignore
        language = ext_to_lang.get(most_common_ext, most_common_ext)

        metadata.primary_language = MetadataField(
            value=language,
            confidence=Confidence.REASONABLE,
            source="File extension analysis",
            note=f"Based on {extension_counts[most_common_ext]} {most_common_ext} files",
        )
