"""
JavaScript/Node.js Metadata Extractor

This module extracts metadata from JavaScript and Node.js projects by parsing:
    - package.json (npm package manifest)
    - package-lock.json (dependency versions)
    - yarn.lock (Yarn dependency versions)

Supported Metadata:
    - Project name, version, description
    - Authors and maintainers
    - License information
    - Dependencies (runtime, dev, peer)
    - Node.js version requirements
    - Entry points (main, bin, scripts)
    - Repository and homepage URLs

Heuristics and Limitations:
    - Only parses package.json; does not analyze JS/TS code
    - Peer dependencies are treated as runtime dependencies
    - Workspace/monorepo configurations are not fully supported
"""

import json
import re
from pathlib import Path
from typing import Any, Optional

from autodoc.discovery import DiscoveryResult, FileCategory
from autodoc.extractors.base import BaseExtractor
from autodoc.schema import (
    Author,
    Confidence,
    Dependency,
    EntryPoint,
    MetadataField,
    ProjectMetadata,
)


class JavaScriptExtractor(BaseExtractor):
    """
    Extracts metadata from JavaScript/Node.js projects.

    This extractor handles npm/yarn project configurations,
    primarily through package.json parsing.

    Usage:
        extractor = JavaScriptExtractor()
        if extractor.can_handle(discovery_result):
            metadata = extractor.extract(discovery_result, root_path)
    """

    name = "JavaScript"

    def can_handle(self, discovery_result: DiscoveryResult) -> bool:
        """
        Check if this is a JavaScript/Node.js project.

        Returns True if package.json is found or if there are JS/TS files.

        Args:
            discovery_result: The result of file discovery

        Returns:
            True if JavaScript project files are detected
        """
        for f in discovery_result.files:
            if f.relative_path.name == "package.json":
                return True

        # Check for JS/TS source files
        js_extensions = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
        js_files = [
            f for f in discovery_result.files
            if f.path.suffix in js_extensions
        ]
        return len(js_files) > 0

    def extract(
        self,
        discovery_result: DiscoveryResult,
        root_path: Path,
    ) -> ProjectMetadata:
        """
        Extract metadata from JavaScript project files.

        Args:
            discovery_result: The result of file discovery
            root_path: The repository root path

        Returns:
            ProjectMetadata populated with JavaScript project information
        """
        self.root_path = root_path
        metadata = ProjectMetadata()

        # Mark as JavaScript project
        metadata.primary_language = MetadataField(
            value="JavaScript",
            confidence=Confidence.STRONG,
            source="File extension analysis",
        )

        # Parse package.json
        package_json_path = root_path / "package.json"
        if package_json_path.exists():
            pkg_metadata = self._extract_from_package_json(package_json_path)
            metadata.merge_from(pkg_metadata)

        # Detect entry points from common patterns
        entry_metadata = self._detect_entry_points(discovery_result, root_path)
        metadata.merge_from(entry_metadata)

        # Check for TypeScript
        ts_files = [f for f in discovery_result.files if f.path.suffix in {".ts", ".tsx"}]
        if ts_files:
            # Update primary language to TypeScript
            metadata.primary_language = MetadataField(
                value="TypeScript",
                confidence=Confidence.STRONG,
                source="TypeScript files detected",
            )

        # Check for test files
        if discovery_result.has_category(FileCategory.TEST_FILE):
            metadata.has_tests = True

        # Check for CI config
        if discovery_result.has_category(FileCategory.CI_CONFIG):
            metadata.has_ci_config = True

        return metadata

    def _extract_from_package_json(self, path: Path) -> ProjectMetadata:
        """
        Extract metadata from package.json.

        Args:
            path: Path to package.json

        Returns:
            ProjectMetadata with extracted information
        """
        metadata = ProjectMetadata()
        content = self.read_file_safe(path)
        if content is None:
            return metadata

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            self.add_warning(f"Failed to parse package.json: {e}")
            return metadata

        source = "package.json"

        # Name
        if "name" in data:
            metadata.name = MetadataField(
                value=data["name"],
                confidence=Confidence.EXPLICIT,
                source=source,
            )

        # Version
        if "version" in data:
            metadata.version = MetadataField(
                value=data["version"],
                confidence=Confidence.EXPLICIT,
                source=source,
            )

        # Description
        if "description" in data:
            metadata.description = MetadataField(
                value=data["description"],
                confidence=Confidence.EXPLICIT,
                source=source,
            )

        # Author (can be string or object)
        if "author" in data:
            author = self._parse_author(data["author"], source)
            if author:
                metadata.authors.append(author)

        # Contributors
        if "contributors" in data:
            for contrib in data["contributors"]:
                author = self._parse_author(contrib, source)
                if author:
                    author.role = "contributor"
                    metadata.authors.append(author)

        # Maintainers
        if "maintainers" in data:
            for maint in data["maintainers"]:
                author = self._parse_author(maint, source)
                if author:
                    author.role = "maintainer"
                    metadata.authors.append(author)

        # License
        if "license" in data:
            license_val = data["license"]
            if isinstance(license_val, dict):
                license_val = license_val.get("type", str(license_val))
            metadata.license = MetadataField(
                value=str(license_val),
                confidence=Confidence.EXPLICIT,
                source=source,
            )

        # Node.js version (engines.node)
        if "engines" in data and "node" in data["engines"]:
            metadata.python_version = MetadataField(  # Reusing python_version for node
                value=f"Node.js {data['engines']['node']}",
                confidence=Confidence.EXPLICIT,
                source=f"{source} [engines.node]",
            )

        # Dependencies
        if "dependencies" in data:
            for name, version in data["dependencies"].items():
                dep = Dependency(
                    name=name,
                    version_constraint=version,
                    source=f"{source} [dependencies]",
                )
                metadata.dependencies.append(dep)

        # Dev dependencies
        if "devDependencies" in data:
            for name, version in data["devDependencies"].items():
                dep = Dependency(
                    name=name,
                    version_constraint=version,
                    is_dev=True,
                    source=f"{source} [devDependencies]",
                )
                metadata.dev_dependencies.append(dep)

        # Peer dependencies (treat as runtime)
        if "peerDependencies" in data:
            for name, version in data["peerDependencies"].items():
                dep = Dependency(
                    name=name,
                    version_constraint=version,
                    source=f"{source} [peerDependencies]",
                )
                metadata.dependencies.append(dep)

        # Entry points from main/bin
        if "main" in data:
            entry = EntryPoint(
                path=data["main"],
                entry_type="module",
                confidence=Confidence.EXPLICIT,
                note="Main entry point",
            )
            metadata.entry_points.append(entry)

        if "bin" in data:
            bin_data = data["bin"]
            if isinstance(bin_data, str):
                # Single binary with package name
                entry = EntryPoint(
                    path=bin_data,
                    entry_type="cli",
                    command=data.get("name", ""),
                    confidence=Confidence.EXPLICIT,
                )
                metadata.entry_points.append(entry)
            elif isinstance(bin_data, dict):
                # Multiple binaries
                for cmd_name, cmd_path in bin_data.items():
                    entry = EntryPoint(
                        path=cmd_path,
                        entry_type="cli",
                        command=cmd_name,
                        confidence=Confidence.EXPLICIT,
                    )
                    metadata.entry_points.append(entry)

        # Scripts (common ones)
        if "scripts" in data:
            scripts = data["scripts"]
            # Note important scripts
            important_scripts = ["start", "build", "test", "dev"]
            for script_name in important_scripts:
                if script_name in scripts:
                    entry = EntryPoint(
                        path=f"npm run {script_name}",
                        entry_type="script",
                        command=script_name,
                        confidence=Confidence.EXPLICIT,
                        note=f"npm script: {scripts[script_name][:50]}...",
                    )
                    metadata.entry_points.append(entry)

        # URLs
        if "homepage" in data:
            metadata.homepage_url = MetadataField(
                value=data["homepage"],
                confidence=Confidence.EXPLICIT,
                source=source,
            )

        if "repository" in data:
            repo = data["repository"]
            if isinstance(repo, str):
                repo_url = repo
            elif isinstance(repo, dict):
                repo_url = repo.get("url", "")
            else:
                repo_url = ""

            # Clean up git URLs
            if repo_url:
                repo_url = repo_url.replace("git+", "").replace(".git", "")
                if repo_url.startswith("git://"):
                    repo_url = repo_url.replace("git://", "https://")

                metadata.repository_url = MetadataField(
                    value=repo_url,
                    confidence=Confidence.EXPLICIT,
                    source=source,
                )

        return metadata

    def _parse_author(
        self,
        author_data: Any,
        source: str,
    ) -> Optional[Author]:
        """
        Parse author data from package.json.

        Handles formats:
            - "Name <email> (url)"
            - {"name": "Name", "email": "email", "url": "url"}

        Args:
            author_data: Author data from package.json
            source: Source file for attribution

        Returns:
            Author object, or None if parsing failed
        """
        if isinstance(author_data, str):
            # Parse "Name <email> (url)" format
            match = re.match(
                r'^([^<(]+?)(?:\s*<([^>]+)>)?(?:\s*\(([^)]+)\))?$',
                author_data.strip(),
            )
            if match:
                name = match.group(1).strip()
                email = match.group(2)
                # url = match.group(3)  # Not stored in Author
                if name:
                    return Author(name=name, email=email, source=source)
        elif isinstance(author_data, dict):
            name = author_data.get("name")
            if name:
                return Author(
                    name=name,
                    email=author_data.get("email"),
                    source=source,
                )

        return None

    def _detect_entry_points(
        self,
        discovery_result: DiscoveryResult,
        root_path: Path,
    ) -> ProjectMetadata:
        """
        Detect entry points from common file patterns.

        Args:
            discovery_result: The discovery result
            root_path: Repository root path

        Returns:
            ProjectMetadata with entry_points populated
        """
        metadata = ProjectMetadata()

        # Common entry point patterns for JS
        entry_patterns = {
            "index.js": ("module", "Main module entry"),
            "index.ts": ("module", "Main TypeScript entry"),
            "main.js": ("main", "Main application entry"),
            "main.ts": ("main", "Main TypeScript entry"),
            "app.js": ("main", "Application entry"),
            "app.ts": ("main", "TypeScript application entry"),
            "server.js": ("server", "Server entry point"),
            "server.ts": ("server", "TypeScript server entry"),
            "cli.js": ("cli", "CLI entry point"),
            "cli.ts": ("cli", "TypeScript CLI entry"),
        }

        for f in discovery_result.files:
            filename = f.relative_path.name
            if filename in entry_patterns:
                entry_type, note = entry_patterns[filename]
                entry = EntryPoint(
                    path=str(f.relative_path),
                    entry_type=entry_type,
                    confidence=Confidence.REASONABLE,
                    note=note,
                )
                metadata.entry_points.append(entry)

        return metadata
