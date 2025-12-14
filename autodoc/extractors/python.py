"""
Python Metadata Extractor

This module extracts metadata from Python projects by parsing:
    - pyproject.toml (PEP 518/621 project metadata)
    - setup.py (legacy setuptools configuration)
    - setup.cfg (declarative setuptools configuration)
    - requirements.txt and requirements-dev.txt

Supported Metadata:
    - Project name, version, description
    - Authors and maintainers
    - License information
    - Dependencies (runtime and development)
    - Python version requirements
    - Entry points (console scripts)
    - Repository and homepage URLs

Heuristics and Limitations:
    - setup.py parsing uses regex, not AST; may miss dynamic configurations
    - pyproject.toml is preferred over setup.py when both exist
    - License detection from classifiers uses common patterns
    - Version requirements parsing is simplified (does not handle all PEP 440)

Confidence Scoring Approach:
    - EXPLICIT (1.0): Directly specified in pyproject.toml or setup.cfg
    - STRONG (0.8): Clearly stated in setup.py or inferred from classifiers
    - REASONABLE (0.6): Parsed from requirements.txt or similar
    - WEAK (0.4): Inferred from file patterns or partial matches
"""

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


# Try to import tomllib (Python 3.11+) or fall back to tomli
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        tomllib = None  # type: ignore


class PythonExtractor(BaseExtractor):
    """
    Extracts metadata from Python projects.

    This extractor handles the common Python project configurations:
    pyproject.toml, setup.py, setup.cfg, and requirements files.

    Priority order (highest confidence first):
        1. pyproject.toml [project] section (PEP 621)
        2. pyproject.toml [tool.poetry] section
        3. setup.cfg [metadata] section
        4. setup.py (regex-based parsing)
        5. requirements.txt files

    Usage:
        extractor = PythonExtractor()
        if extractor.can_handle(discovery_result):
            metadata = extractor.extract(discovery_result, root_path)
    """

    name = "Python"

    # Common license classifiers and their SPDX identifiers
    LICENSE_CLASSIFIERS: dict[str, str] = {
        "License :: OSI Approved :: MIT License": "MIT",
        "License :: OSI Approved :: Apache Software License": "Apache-2.0",
        "License :: OSI Approved :: BSD License": "BSD",
        "License :: OSI Approved :: GNU General Public License v3": "GPL-3.0",
        "License :: OSI Approved :: GNU General Public License v2": "GPL-2.0",
        "License :: OSI Approved :: GNU Lesser General Public License v3": "LGPL-3.0",
        "License :: OSI Approved :: Mozilla Public License 2.0": "MPL-2.0",
        "License :: OSI Approved :: ISC License": "ISC",
        "License :: OSI Approved :: GNU Affero General Public License v3": "AGPL-3.0",
    }

    def can_handle(self, discovery_result: DiscoveryResult) -> bool:
        """
        Check if this is a Python project.

        Returns True if any Python-related package files are found:
        - pyproject.toml
        - setup.py
        - setup.cfg
        - requirements.txt

        Args:
            discovery_result: The result of file discovery

        Returns:
            True if Python project files are detected
        """
        # Check for Python package manifests
        for f in discovery_result.files:
            if f.relative_path.name in {
                "pyproject.toml",
                "setup.py",
                "setup.cfg",
            }:
                return True

        # Check for requirements files
        if discovery_result.has_category(FileCategory.REQUIREMENTS):
            return True

        # Check if there are Python source files (indicates a Python project)
        python_files = [
            f for f in discovery_result.files
            if f.path.suffix == ".py"
        ]
        return len(python_files) > 0

    def extract(
        self,
        discovery_result: DiscoveryResult,
        root_path: Path,
    ) -> ProjectMetadata:
        """
        Extract metadata from Python project files.

        Processes files in priority order and merges results.

        Args:
            discovery_result: The result of file discovery
            root_path: The repository root path

        Returns:
            ProjectMetadata populated with Python project information
        """
        self.root_path = root_path
        metadata = ProjectMetadata()

        # Mark that this is a Python project
        metadata.primary_language = MetadataField(
            value="Python",
            confidence=Confidence.STRONG,
            source="File extension analysis",
            note="Python source files detected",
        )

        # Try to extract from pyproject.toml first (highest priority)
        pyproject_path = root_path / "pyproject.toml"
        if pyproject_path.exists():
            pyproject_metadata = self._extract_from_pyproject(pyproject_path)
            metadata.merge_from(pyproject_metadata)

        # Try setup.cfg
        setup_cfg_path = root_path / "setup.cfg"
        if setup_cfg_path.exists():
            setup_cfg_metadata = self._extract_from_setup_cfg(setup_cfg_path)
            metadata.merge_from(setup_cfg_metadata)

        # Try setup.py (lower priority due to regex-based parsing)
        setup_py_path = root_path / "setup.py"
        if setup_py_path.exists():
            setup_py_metadata = self._extract_from_setup_py(setup_py_path)
            metadata.merge_from(setup_py_metadata)

        # Extract dependencies from requirements files
        requirements_metadata = self._extract_from_requirements(discovery_result, root_path)
        metadata.merge_from(requirements_metadata)

        # Extract dependencies from setup.sh (conda/pip install commands)
        setup_sh_path = root_path / "setup.sh"
        if setup_sh_path.exists():
            setup_sh_metadata = self._extract_from_setup_sh(setup_sh_path)
            metadata.merge_from(setup_sh_metadata)

        # Detect entry points from common file patterns
        entry_point_metadata = self._detect_entry_points(discovery_result, root_path)
        metadata.merge_from(entry_point_metadata)

        # Check for test files
        if discovery_result.has_category(FileCategory.TEST_FILE):
            metadata.has_tests = True

        # Check for CI configuration
        if discovery_result.has_category(FileCategory.CI_CONFIG):
            metadata.has_ci_config = True

        return metadata

    def _extract_from_pyproject(self, path: Path) -> ProjectMetadata:
        """
        Extract metadata from pyproject.toml.

        Supports both PEP 621 [project] section and Poetry's [tool.poetry].

        Args:
            path: Path to pyproject.toml

        Returns:
            ProjectMetadata with extracted information
        """
        metadata = ProjectMetadata()

        if tomllib is None:
            self.add_warning(
                "Cannot parse pyproject.toml: tomllib/tomli not available. "
                "Install tomli for Python <3.11 support."
            )
            return metadata

        content = self.read_file_safe(path)
        if content is None:
            return metadata

        try:
            data = tomllib.loads(content)
        except Exception as e:
            self.add_warning(f"Failed to parse pyproject.toml: {e}")
            return metadata

        source = "pyproject.toml"

        # Try PEP 621 [project] section first
        if "project" in data:
            self._extract_pep621(data["project"], metadata, source)

        # Try Poetry [tool.poetry] section
        elif "tool" in data and "poetry" in data["tool"]:
            self._extract_poetry(data["tool"]["poetry"], metadata, source)

        # Check for build system info
        if "build-system" in data:
            build_requires = data["build-system"].get("requires", [])
            for req in build_requires:
                # These are build dependencies, not runtime
                dep = self._parse_requirement(req)
                if dep:
                    dep.is_dev = True
                    dep.source = f"{source} [build-system]"
                    metadata.dev_dependencies.append(dep)

        return metadata

    def _extract_pep621(
        self,
        project: dict[str, Any],
        metadata: ProjectMetadata,
        source: str,
    ) -> None:
        """
        Extract metadata from PEP 621 [project] section.

        Args:
            project: The [project] table from pyproject.toml
            metadata: ProjectMetadata to populate
            source: Source file name for attribution
        """
        # Name
        if "name" in project:
            metadata.name = MetadataField(
                value=project["name"],
                confidence=Confidence.EXPLICIT,
                source=f"{source} [project.name]",
            )

        # Version
        if "version" in project:
            metadata.version = MetadataField(
                value=project["version"],
                confidence=Confidence.EXPLICIT,
                source=f"{source} [project.version]",
            )

        # Description
        if "description" in project:
            metadata.description = MetadataField(
                value=project["description"],
                confidence=Confidence.EXPLICIT,
                source=f"{source} [project.description]",
            )

        # Authors
        if "authors" in project:
            for author_data in project["authors"]:
                if isinstance(author_data, dict):
                    author = Author(
                        name=author_data.get("name", "Unknown"),
                        email=author_data.get("email"),
                        source=f"{source} [project.authors]",
                    )
                    metadata.authors.append(author)

        # Maintainers (also treated as authors with different role)
        if "maintainers" in project:
            for maint_data in project["maintainers"]:
                if isinstance(maint_data, dict):
                    author = Author(
                        name=maint_data.get("name", "Unknown"),
                        email=maint_data.get("email"),
                        role="maintainer",
                        source=f"{source} [project.maintainers]",
                    )
                    metadata.authors.append(author)

        # License
        if "license" in project:
            license_info = project["license"]
            if isinstance(license_info, dict):
                license_text = license_info.get("text") or license_info.get("file", "")
            else:
                license_text = str(license_info)
            metadata.license = MetadataField(
                value=license_text,
                confidence=Confidence.EXPLICIT,
                source=f"{source} [project.license]",
            )

        # Python version requirement
        if "requires-python" in project:
            metadata.python_version = MetadataField(
                value=project["requires-python"],
                confidence=Confidence.EXPLICIT,
                source=f"{source} [project.requires-python]",
            )

        # Dependencies
        if "dependencies" in project:
            for dep_str in project["dependencies"]:
                dep = self._parse_requirement(dep_str)
                if dep:
                    dep.source = f"{source} [project.dependencies]"
                    metadata.dependencies.append(dep)

        # Optional/dev dependencies
        if "optional-dependencies" in project:
            for group_name, deps in project["optional-dependencies"].items():
                is_dev = group_name.lower() in {"dev", "development", "test", "testing"}
                for dep_str in deps:
                    dep = self._parse_requirement(dep_str)
                    if dep:
                        dep.source = f"{source} [project.optional-dependencies.{group_name}]"
                        dep.is_dev = is_dev
                        if is_dev:
                            metadata.dev_dependencies.append(dep)
                        else:
                            metadata.dependencies.append(dep)

        # Entry points (console scripts)
        if "scripts" in project:
            for cmd_name, cmd_path in project["scripts"].items():
                entry = EntryPoint(
                    path=cmd_path,
                    entry_type="cli",
                    command=cmd_name,
                    confidence=Confidence.EXPLICIT,
                    note=f"Console script: {cmd_name}",
                )
                metadata.entry_points.append(entry)

        # URLs
        if "urls" in project:
            urls = project["urls"]
            if "Homepage" in urls or "homepage" in urls:
                homepage = urls.get("Homepage") or urls.get("homepage")
                metadata.homepage_url = MetadataField(
                    value=homepage,
                    confidence=Confidence.EXPLICIT,
                    source=f"{source} [project.urls]",
                )
            if "Repository" in urls or "repository" in urls:
                repo = urls.get("Repository") or urls.get("repository")
                metadata.repository_url = MetadataField(
                    value=repo,
                    confidence=Confidence.EXPLICIT,
                    source=f"{source} [project.urls]",
                )

        # License from classifiers
        if "classifiers" in project and metadata.license.value is None:
            for classifier in project["classifiers"]:
                if classifier in self.LICENSE_CLASSIFIERS:
                    metadata.license = MetadataField(
                        value=self.LICENSE_CLASSIFIERS[classifier],
                        confidence=Confidence.STRONG,
                        source=f"{source} [project.classifiers]",
                        note=f"Inferred from classifier: {classifier}",
                    )
                    break

    def _extract_poetry(
        self,
        poetry: dict[str, Any],
        metadata: ProjectMetadata,
        source: str,
    ) -> None:
        """
        Extract metadata from Poetry's [tool.poetry] section.

        Args:
            poetry: The [tool.poetry] table from pyproject.toml
            metadata: ProjectMetadata to populate
            source: Source file name for attribution
        """
        poetry_source = f"{source} [tool.poetry]"

        # Name
        if "name" in poetry:
            metadata.name = MetadataField(
                value=poetry["name"],
                confidence=Confidence.EXPLICIT,
                source=f"{poetry_source}.name",
            )

        # Version
        if "version" in poetry:
            metadata.version = MetadataField(
                value=poetry["version"],
                confidence=Confidence.EXPLICIT,
                source=f"{poetry_source}.version",
            )

        # Description
        if "description" in poetry:
            metadata.description = MetadataField(
                value=poetry["description"],
                confidence=Confidence.EXPLICIT,
                source=f"{poetry_source}.description",
            )

        # Authors (Poetry format: "Name <email>")
        if "authors" in poetry:
            for author_str in poetry["authors"]:
                author = self._parse_author_string(author_str)
                if author:
                    author.source = f"{poetry_source}.authors"
                    metadata.authors.append(author)

        # License
        if "license" in poetry:
            metadata.license = MetadataField(
                value=poetry["license"],
                confidence=Confidence.EXPLICIT,
                source=f"{poetry_source}.license",
            )

        # Python version
        if "python" in poetry:
            # Poetry uses caret/tilde syntax: ^3.8, ~3.9
            metadata.python_version = MetadataField(
                value=poetry["python"],
                confidence=Confidence.EXPLICIT,
                source=f"{poetry_source}.python",
            )

        # Dependencies
        if "dependencies" in poetry:
            for name, version in poetry["dependencies"].items():
                if name.lower() == "python":
                    continue  # Skip Python itself
                dep = Dependency(
                    name=name,
                    version_constraint=self._poetry_version_to_str(version),
                    source=f"{poetry_source}.dependencies",
                )
                metadata.dependencies.append(dep)

        # Dev dependencies
        if "dev-dependencies" in poetry:
            for name, version in poetry["dev-dependencies"].items():
                dep = Dependency(
                    name=name,
                    version_constraint=self._poetry_version_to_str(version),
                    is_dev=True,
                    source=f"{poetry_source}.dev-dependencies",
                )
                metadata.dev_dependencies.append(dep)

        # Also check group.dev.dependencies (Poetry 1.2+)
        if "group" in poetry:
            for group_name, group_data in poetry["group"].items():
                if "dependencies" in group_data:
                    is_dev = group_name.lower() in {"dev", "development", "test"}
                    for name, version in group_data["dependencies"].items():
                        dep = Dependency(
                            name=name,
                            version_constraint=self._poetry_version_to_str(version),
                            is_dev=is_dev,
                            source=f"{poetry_source}.group.{group_name}.dependencies",
                        )
                        if is_dev:
                            metadata.dev_dependencies.append(dep)
                        else:
                            metadata.dependencies.append(dep)

        # Scripts
        if "scripts" in poetry:
            for cmd_name, cmd_path in poetry["scripts"].items():
                entry = EntryPoint(
                    path=cmd_path,
                    entry_type="cli",
                    command=cmd_name,
                    confidence=Confidence.EXPLICIT,
                    note=f"Poetry script: {cmd_name}",
                )
                metadata.entry_points.append(entry)

        # URLs
        if "homepage" in poetry:
            metadata.homepage_url = MetadataField(
                value=poetry["homepage"],
                confidence=Confidence.EXPLICIT,
                source=f"{poetry_source}.homepage",
            )
        if "repository" in poetry:
            metadata.repository_url = MetadataField(
                value=poetry["repository"],
                confidence=Confidence.EXPLICIT,
                source=f"{poetry_source}.repository",
            )

    def _extract_from_setup_cfg(self, path: Path) -> ProjectMetadata:
        """
        Extract metadata from setup.cfg.

        Uses configparser to read the [metadata] section.

        Args:
            path: Path to setup.cfg

        Returns:
            ProjectMetadata with extracted information
        """
        import configparser

        metadata = ProjectMetadata()
        content = self.read_file_safe(path)
        if content is None:
            return metadata

        config = configparser.ConfigParser()
        try:
            config.read_string(content)
        except configparser.Error as e:
            self.add_warning(f"Failed to parse setup.cfg: {e}")
            return metadata

        source = "setup.cfg"

        if "metadata" in config:
            meta = config["metadata"]

            if "name" in meta:
                metadata.name = MetadataField(
                    value=meta["name"],
                    confidence=Confidence.EXPLICIT,
                    source=f"{source} [metadata.name]",
                )

            if "version" in meta:
                metadata.version = MetadataField(
                    value=meta["version"],
                    confidence=Confidence.EXPLICIT,
                    source=f"{source} [metadata.version]",
                )

            if "description" in meta:
                metadata.description = MetadataField(
                    value=meta["description"],
                    confidence=Confidence.EXPLICIT,
                    source=f"{source} [metadata.description]",
                )

            if "author" in meta:
                author = Author(
                    name=meta["author"],
                    email=meta.get("author_email"),
                    source=f"{source} [metadata]",
                )
                metadata.authors.append(author)

            if "license" in meta:
                metadata.license = MetadataField(
                    value=meta["license"],
                    confidence=Confidence.EXPLICIT,
                    source=f"{source} [metadata.license]",
                )

            if "url" in meta:
                metadata.homepage_url = MetadataField(
                    value=meta["url"],
                    confidence=Confidence.EXPLICIT,
                    source=f"{source} [metadata.url]",
                )

        # Check options for python_requires
        if "options" in config:
            options = config["options"]
            if "python_requires" in options:
                metadata.python_version = MetadataField(
                    value=options["python_requires"],
                    confidence=Confidence.EXPLICIT,
                    source=f"{source} [options.python_requires]",
                )

            # install_requires (may be multiline)
            if "install_requires" in options:
                deps_str = options["install_requires"]
                for line in deps_str.strip().split("\n"):
                    line = line.strip()
                    if line:
                        dep = self._parse_requirement(line)
                        if dep:
                            dep.source = f"{source} [options.install_requires]"
                            metadata.dependencies.append(dep)

        return metadata

    def _extract_from_setup_py(self, path: Path) -> ProjectMetadata:
        """
        Extract metadata from setup.py using regex patterns.

        This is a heuristic approach that works for most simple setup.py files
        but may miss complex or dynamic configurations.

        Args:
            path: Path to setup.py

        Returns:
            ProjectMetadata with extracted information

        Limitations:
            - Cannot evaluate Python code (only regex matching)
            - May miss values from variables or function calls
            - Works best with literal string values
        """
        metadata = ProjectMetadata()
        content = self.read_file_safe(path)
        if content is None:
            return metadata

        source = "setup.py"

        # Pattern to match keyword arguments in setup() call
        # Handles: name="value", name='value'
        def extract_string_kwarg(key: str) -> Optional[str]:
            # Match: key="value" or key='value'
            pattern = rf'{key}\s*=\s*["\']([^"\']+)["\']'
            match = re.search(pattern, content)
            if match:
                return match.group(1)
            return None

        # Extract common fields
        name = extract_string_kwarg("name")
        if name:
            metadata.name = MetadataField(
                value=name,
                confidence=Confidence.STRONG,
                source=source,
                note="Extracted via regex from setup() call",
            )

        version = extract_string_kwarg("version")
        if version:
            metadata.version = MetadataField(
                value=version,
                confidence=Confidence.STRONG,
                source=source,
                note="Extracted via regex from setup() call",
            )

        description = extract_string_kwarg("description")
        if description:
            metadata.description = MetadataField(
                value=description,
                confidence=Confidence.STRONG,
                source=source,
                note="Extracted via regex from setup() call",
            )

        author = extract_string_kwarg("author")
        author_email = extract_string_kwarg("author_email")
        if author:
            metadata.authors.append(Author(
                name=author,
                email=author_email,
                source=source,
            ))

        license_val = extract_string_kwarg("license")
        if license_val:
            metadata.license = MetadataField(
                value=license_val,
                confidence=Confidence.STRONG,
                source=source,
            )

        url = extract_string_kwarg("url")
        if url:
            metadata.homepage_url = MetadataField(
                value=url,
                confidence=Confidence.STRONG,
                source=source,
            )

        python_requires = extract_string_kwarg("python_requires")
        if python_requires:
            metadata.python_version = MetadataField(
                value=python_requires,
                confidence=Confidence.STRONG,
                source=source,
            )

        # Try to extract install_requires list
        # Pattern: install_requires=["pkg1", "pkg2"] or install_requires=['pkg1', 'pkg2']
        install_requires_match = re.search(
            r'install_requires\s*=\s*\[(.*?)\]',
            content,
            re.DOTALL,
        )
        if install_requires_match:
            requires_content = install_requires_match.group(1)
            # Extract individual requirements
            req_pattern = r'["\']([^"\']+)["\']'
            for match in re.finditer(req_pattern, requires_content):
                dep = self._parse_requirement(match.group(1))
                if dep:
                    dep.source = f"{source} install_requires"
                    metadata.dependencies.append(dep)

        return metadata

    def _extract_from_setup_sh(self, path: Path) -> ProjectMetadata:
        """
        Extract dependencies from setup.sh shell scripts.

        Parses pip install and conda install commands commonly found in
        setup scripts for ML/data science projects.

        Args:
            path: Path to setup.sh

        Returns:
            ProjectMetadata with dependencies and Python version

        Limitations:
            - Only parses simple pip/conda install commands
            - May miss complex shell variable substitutions
            - Does not evaluate shell conditionals
        """
        metadata = ProjectMetadata()
        content = self.read_file_safe(path)
        if content is None:
            return metadata

        source = "setup.sh"

        # Extract Python version from conda create command
        # Pattern: conda create ... python=3.8 or python==3.8
        python_version_match = re.search(
            r'conda\s+create\s+.*python[=]+([0-9.]+)',
            content,
        )
        if python_version_match:
            metadata.python_version = MetadataField(
                value=f">={python_version_match.group(1)}",
                confidence=Confidence.REASONABLE,
                source=f"{source} (conda create)",
                note="Extracted from conda create command",
            )

        # Extract pip install packages
        # Patterns:
        #   pip install package==1.0.0
        #   pip install package>=1.0.0
        #   pip install package
        pip_install_pattern = re.compile(
            r'pip\s+install\s+([a-zA-Z0-9_-]+(?:[=<>!]+[0-9.]+)?)',
        )
        for match in pip_install_pattern.finditer(content):
            pkg_spec = match.group(1)
            dep = self._parse_requirement(pkg_spec)
            if dep:
                dep.source = f"{source} (pip install)"
                metadata.dependencies.append(dep)

        # Extract conda install packages
        # Pattern: conda install package==1.0.0 or package=1.0.0
        conda_install_pattern = re.compile(
            r'conda\s+install\s+(?:.*?\s+)?([a-zA-Z0-9_-]+(?:[=]+[0-9.]+)?)',
        )
        for match in conda_install_pattern.finditer(content):
            pkg_spec = match.group(1)
            # Skip conda flags and channels
            if pkg_spec.startswith('-') or pkg_spec in {'pytorch', 'torchvision', 'torchaudio'}:
                # Handle PyTorch separately as it's often installed via conda
                if pkg_spec in {'pytorch', 'torchvision', 'torchaudio'}:
                    dep = Dependency(
                        name=pkg_spec,
                        source=f"{source} (conda install)",
                    )
                    metadata.dependencies.append(dep)
                continue
            dep = self._parse_requirement(pkg_spec.replace('=', '=='))
            if dep:
                dep.source = f"{source} (conda install)"
                metadata.dependencies.append(dep)

        # Also check for pytorch in the full line
        if 'pytorch' in content.lower():
            pytorch_match = re.search(
                r'conda\s+install\s+.*pytorch==?([0-9.]+)?',
                content,
            )
            if pytorch_match:
                version = pytorch_match.group(1)
                dep = Dependency(
                    name="pytorch",
                    version_constraint=f"=={version}" if version else None,
                    source=f"{source} (conda install)",
                )
                # Avoid duplicates
                if not any(d.name == "pytorch" for d in metadata.dependencies):
                    metadata.dependencies.append(dep)

        return metadata

    def _extract_from_requirements(
        self,
        discovery_result: DiscoveryResult,
        root_path: Path,
    ) -> ProjectMetadata:
        """
        Extract dependencies from requirements.txt files.

        Handles:
            - requirements.txt (runtime dependencies)
            - requirements-dev.txt, requirements-test.txt (dev dependencies)
            - requirements/*.txt pattern

        Args:
            discovery_result: The discovery result
            root_path: Repository root path

        Returns:
            ProjectMetadata with dependencies populated
        """
        metadata = ProjectMetadata()

        requirements_files = discovery_result.get_files_by_category(FileCategory.REQUIREMENTS)

        for req_file in requirements_files:
            content = self.read_file_safe(req_file.path)
            if content is None:
                continue

            # Determine if this is a dev requirements file
            name_lower = req_file.relative_path.name.lower()
            is_dev = any(kw in name_lower for kw in ["dev", "test", "development"])

            for line in content.split("\n"):
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue

                # Skip -r includes and other flags
                if line.startswith("-"):
                    continue

                # Skip editable installs
                if line.startswith("git+") or line.startswith("https://"):
                    continue

                dep = self._parse_requirement(line)
                if dep:
                    dep.source = str(req_file.relative_path)
                    dep.is_dev = is_dev
                    if is_dev:
                        metadata.dev_dependencies.append(dep)
                    else:
                        metadata.dependencies.append(dep)

        return metadata

    def _detect_entry_points(
        self,
        discovery_result: DiscoveryResult,
        root_path: Path,
    ) -> ProjectMetadata:
        """
        Detect likely entry points from file patterns.

        Checks for common entry point file names and __main__.py modules.

        Args:
            discovery_result: The discovery result
            root_path: Repository root path

        Returns:
            ProjectMetadata with entry_points populated
        """
        metadata = ProjectMetadata()

        entry_point_files = discovery_result.get_files_by_category(FileCategory.ENTRY_POINT)

        for ep_file in entry_point_files:
            # Only consider Python files
            if ep_file.path.suffix != ".py":
                continue

            entry_type = "script"
            note = f"Detected from filename: {ep_file.relative_path.name}"

            if ep_file.relative_path.name == "__main__.py":
                entry_type = "module"
                # Get the package name from the parent directory
                package_name = ep_file.relative_path.parent.name
                note = f"Package entry point: python -m {package_name}"
            elif ep_file.relative_path.name == "cli.py":
                entry_type = "cli"
                note = "Likely CLI entry point"
            elif ep_file.relative_path.name == "main.py":
                entry_type = "main"
                note = "Main application entry point"

            entry = EntryPoint(
                path=str(ep_file.relative_path),
                entry_type=entry_type,
                confidence=Confidence.REASONABLE,
                note=note,
            )
            metadata.entry_points.append(entry)

        return metadata

    def _parse_requirement(self, req_str: str) -> Optional[Dependency]:
        """
        Parse a requirement string into a Dependency object.

        Handles common formats:
            - package
            - package==1.0.0
            - package>=1.0.0
            - package>=1.0.0,<2.0.0
            - package[extra]>=1.0.0

        Args:
            req_str: The requirement string to parse

        Returns:
            Dependency object, or None if parsing failed
        """
        req_str = req_str.strip()
        if not req_str:
            return None

        # Remove inline comments
        if "#" in req_str:
            req_str = req_str.split("#")[0].strip()

        # Remove extras: package[extra] -> package
        name = req_str
        version_constraint = None

        # Match package name (possibly with extras) and version
        # Pattern: name[extras]>=version,<version or name[extras] or name>=version
        match = re.match(
            r'^([a-zA-Z0-9_-]+)(?:\[[^\]]+\])?\s*(.*)?$',
            req_str,
        )

        if match:
            name = match.group(1)
            version_part = match.group(2)
            if version_part:
                version_constraint = version_part.strip()

        if not name:
            return None

        return Dependency(
            name=name,
            version_constraint=version_constraint if version_constraint else None,
        )

    def _parse_author_string(self, author_str: str) -> Optional[Author]:
        """
        Parse an author string in "Name <email>" format.

        Args:
            author_str: String like "John Doe <john@example.com>"

        Returns:
            Author object, or None if parsing failed
        """
        # Pattern: Name <email> or just Name
        match = re.match(r'^([^<]+?)(?:\s*<([^>]+)>)?$', author_str.strip())
        if match:
            name = match.group(1).strip()
            email = match.group(2)
            if name:
                return Author(name=name, email=email)
        return None

    def _poetry_version_to_str(self, version: Any) -> Optional[str]:
        """
        Convert a Poetry version specification to a string.

        Poetry allows both string versions ("^3.8") and table versions
        ({version = "^3.8", optional = true}).

        Args:
            version: Version value from pyproject.toml

        Returns:
            Version string, or None if not extractable
        """
        if isinstance(version, str):
            return version
        elif isinstance(version, dict):
            return version.get("version")
        return None
