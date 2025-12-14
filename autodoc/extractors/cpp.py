"""
C/C++ Metadata Extractor

This module extracts metadata from C and C++ projects by parsing:
    - CMakeLists.txt (CMake build configuration)
    - Makefile (Make build configuration)
    - configure.ac / configure.in (Autoconf)
    - meson.build (Meson build system)
    - conanfile.txt / conanfile.py (Conan package manager)

Supported Metadata:
    - Project name, version, description
    - C/C++ standard requirements
    - Dependencies (find_package, pkg_check_modules)
    - License information
    - Entry points (executables)

Heuristics and Limitations:
    - Uses regex for parsing (not full CMake/Make parser)
    - Only parses root-level build files
    - Variable substitution is not fully resolved
    - Complex CMake logic may not be correctly interpreted
"""

import re
from pathlib import Path
from typing import Optional

from autodoc.discovery import DiscoveryResult, FileCategory
from autodoc.extractors.base import BaseExtractor
from autodoc.schema import (
    Confidence,
    Dependency,
    EntryPoint,
    MetadataField,
    ProjectMetadata,
)


class CppExtractor(BaseExtractor):
    """
    Extracts metadata from C/C++ projects.

    This extractor handles CMake, Make, and other C/C++ build systems.

    Priority order:
        1. CMakeLists.txt (CMake) - Regex parsing
        2. meson.build (Meson) - Regex parsing
        3. Makefile - Regex parsing
        4. configure.ac (Autoconf) - Regex parsing

    Usage:
        extractor = CppExtractor()
        if extractor.can_handle(discovery_result):
            metadata = extractor.extract(discovery_result, root_path)
    """

    name = "C/C++"

    def can_handle(self, discovery_result: DiscoveryResult) -> bool:
        """
        Check if this is a C/C++ project.

        Returns True if CMake, Makefile, or C/C++ source files are found.

        Args:
            discovery_result: The result of file discovery

        Returns:
            True if C/C++ project files are detected
        """
        build_files = {"CMakeLists.txt", "Makefile", "makefile", "configure.ac", "meson.build"}
        for f in discovery_result.files:
            if f.relative_path.name in build_files:
                return True

        # Check for C/C++ source files
        c_extensions = {".c", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".hxx"}
        c_files = [f for f in discovery_result.files if f.path.suffix in c_extensions]
        return len(c_files) > 0

    def extract(
        self,
        discovery_result: DiscoveryResult,
        root_path: Path,
    ) -> ProjectMetadata:
        """
        Extract metadata from C/C++ project files.

        Args:
            discovery_result: The result of file discovery
            root_path: The repository root path

        Returns:
            ProjectMetadata populated with C/C++ project information
        """
        self.root_path = root_path
        metadata = ProjectMetadata()

        # Detect primary language (C vs C++)
        cpp_files = [f for f in discovery_result.files
                     if f.path.suffix in {".cpp", ".cc", ".cxx", ".hpp", ".hxx"}]
        c_files = [f for f in discovery_result.files
                   if f.path.suffix in {".c", ".h"}]

        if len(cpp_files) > len(c_files):
            metadata.primary_language = MetadataField(
                value="C++",
                confidence=Confidence.STRONG,
                source="File extension analysis",
            )
        else:
            metadata.primary_language = MetadataField(
                value="C",
                confidence=Confidence.STRONG,
                source="File extension analysis",
            )

        # Try CMakeLists.txt first
        cmake_path = root_path / "CMakeLists.txt"
        if cmake_path.exists():
            cmake_metadata = self._extract_from_cmake(cmake_path)
            metadata.merge_from(cmake_metadata)

        # Try meson.build
        meson_path = root_path / "meson.build"
        if meson_path.exists():
            meson_metadata = self._extract_from_meson(meson_path)
            metadata.merge_from(meson_metadata)

        # Try Makefile
        makefile_path = root_path / "Makefile"
        if not makefile_path.exists():
            makefile_path = root_path / "makefile"
        if makefile_path.exists():
            make_metadata = self._extract_from_makefile(makefile_path)
            metadata.merge_from(make_metadata)

        # Try configure.ac
        configure_path = root_path / "configure.ac"
        if not configure_path.exists():
            configure_path = root_path / "configure.in"
        if configure_path.exists():
            autoconf_metadata = self._extract_from_autoconf(configure_path)
            metadata.merge_from(autoconf_metadata)

        # Try conanfile.txt
        conan_path = root_path / "conanfile.txt"
        if conan_path.exists():
            conan_metadata = self._extract_from_conanfile(conan_path)
            metadata.merge_from(conan_metadata)

        # Check for test files
        if discovery_result.has_category(FileCategory.TEST_FILE):
            metadata.has_tests = True

        # Check for CI config
        if discovery_result.has_category(FileCategory.CI_CONFIG):
            metadata.has_ci_config = True

        return metadata

    def _extract_from_cmake(self, path: Path) -> ProjectMetadata:
        """
        Extract metadata from CMakeLists.txt.

        Args:
            path: Path to CMakeLists.txt

        Returns:
            ProjectMetadata with extracted information
        """
        metadata = ProjectMetadata()
        content = self.read_file_safe(path)
        if content is None:
            return metadata

        source = "CMakeLists.txt"

        # Project name and version
        # project(name VERSION 1.0.0 LANGUAGES CXX)
        project_match = re.search(
            r'project\s*\(\s*([^\s)]+)(?:\s+VERSION\s+([^\s)]+))?',
            content,
            re.IGNORECASE,
        )
        if project_match:
            metadata.name = MetadataField(
                value=project_match.group(1),
                confidence=Confidence.EXPLICIT,
                source=source,
            )
            if project_match.group(2):
                metadata.version = MetadataField(
                    value=project_match.group(2),
                    confidence=Confidence.EXPLICIT,
                    source=source,
                )

        # Description (from PROJECT_DESCRIPTION or set command)
        desc_match = re.search(
            r'(?:DESCRIPTION\s+"([^"]+)"|set\s*\(\s*PROJECT_DESCRIPTION\s+"([^"]+)")',
            content,
        )
        if desc_match:
            description = desc_match.group(1) or desc_match.group(2)
            metadata.description = MetadataField(
                value=description,
                confidence=Confidence.EXPLICIT,
                source=source,
            )

        # C++ standard
        cxx_std_match = re.search(
            r'(?:CMAKE_CXX_STANDARD|CXX_STANDARD)\s+(\d+)',
            content,
        )
        if cxx_std_match:
            metadata.python_version = MetadataField(  # Reusing for C++ standard
                value=f"C++{cxx_std_match.group(1)}",
                confidence=Confidence.EXPLICIT,
                source=source,
            )
        else:
            # Check for -std=c++XX flag
            std_flag_match = re.search(r'-std=c\+\+(\d+)', content)
            if std_flag_match:
                metadata.python_version = MetadataField(
                    value=f"C++{std_flag_match.group(1)}",
                    confidence=Confidence.EXPLICIT,
                    source=source,
                )

        # Dependencies from find_package
        find_package_pattern = re.compile(
            r'find_package\s*\(\s*(\w+)(?:\s+(\d+(?:\.\d+)*))?\s*(?:REQUIRED|COMPONENTS)?',
            re.IGNORECASE,
        )
        for match in find_package_pattern.finditer(content):
            dep_name = match.group(1)
            dep_version = match.group(2)
            dependency = Dependency(
                name=dep_name,
                version_constraint=dep_version,
                source=f"{source} [find_package]",
            )
            metadata.dependencies.append(dependency)

        # Dependencies from pkg_check_modules
        pkg_check_pattern = re.compile(
            r'pkg_check_modules\s*\(\s*\w+\s+(?:REQUIRED\s+)?(\w+)',
            re.IGNORECASE,
        )
        for match in pkg_check_pattern.finditer(content):
            dependency = Dependency(
                name=match.group(1),
                source=f"{source} [pkg_check_modules]",
            )
            metadata.dependencies.append(dependency)

        # Entry points from add_executable
        exec_pattern = re.compile(
            r'add_executable\s*\(\s*(\w+)',
            re.IGNORECASE,
        )
        for match in exec_pattern.finditer(content):
            entry = EntryPoint(
                path=match.group(1),
                entry_type="executable",
                confidence=Confidence.EXPLICIT,
                note="CMake executable target",
            )
            metadata.entry_points.append(entry)

        return metadata

    def _extract_from_meson(self, path: Path) -> ProjectMetadata:
        """
        Extract metadata from meson.build.

        Args:
            path: Path to meson.build

        Returns:
            ProjectMetadata with extracted information
        """
        metadata = ProjectMetadata()
        content = self.read_file_safe(path)
        if content is None:
            return metadata

        source = "meson.build"

        # Project name and version
        # project('name', 'cpp', version: '1.0.0')
        project_match = re.search(
            r"project\s*\(\s*['\"]([^'\"]+)['\"].*?(?:version\s*:\s*['\"]([^'\"]+)['\"])?",
            content,
            re.DOTALL,
        )
        if project_match:
            metadata.name = MetadataField(
                value=project_match.group(1),
                confidence=Confidence.EXPLICIT,
                source=source,
            )
            if project_match.group(2):
                metadata.version = MetadataField(
                    value=project_match.group(2),
                    confidence=Confidence.EXPLICIT,
                    source=source,
                )

        # Dependencies from dependency()
        dep_pattern = re.compile(
            r"dependency\s*\(\s*['\"]([^'\"]+)['\"](?:.*?version\s*:\s*['\"]([^'\"]+)['\"])?",
        )
        for match in dep_pattern.finditer(content):
            dependency = Dependency(
                name=match.group(1),
                version_constraint=match.group(2),
                source=f"{source} [dependency]",
            )
            metadata.dependencies.append(dependency)

        # Entry points from executable()
        exec_pattern = re.compile(
            r"executable\s*\(\s*['\"]([^'\"]+)['\"]",
        )
        for match in exec_pattern.finditer(content):
            entry = EntryPoint(
                path=match.group(1),
                entry_type="executable",
                confidence=Confidence.EXPLICIT,
                note="Meson executable",
            )
            metadata.entry_points.append(entry)

        return metadata

    def _extract_from_makefile(self, path: Path) -> ProjectMetadata:
        """
        Extract metadata from Makefile.

        Args:
            path: Path to Makefile

        Returns:
            ProjectMetadata with extracted information
        """
        metadata = ProjectMetadata()
        content = self.read_file_safe(path)
        if content is None:
            return metadata

        source = "Makefile"

        # Project name from various common patterns
        name_patterns = [
            r'^PROJECT\s*[?:]?=\s*(\S+)',
            r'^NAME\s*[?:]?=\s*(\S+)',
            r'^TARGET\s*[?:]?=\s*(\S+)',
            r'^PROGRAM\s*[?:]?=\s*(\S+)',
        ]
        for pattern in name_patterns:
            match = re.search(pattern, content, re.MULTILINE)
            if match:
                metadata.name = MetadataField(
                    value=match.group(1),
                    confidence=Confidence.STRONG,
                    source=source,
                )
                break

        # Version from common patterns
        version_match = re.search(
            r'^VERSION\s*[?:]?=\s*(\S+)',
            content,
            re.MULTILINE,
        )
        if version_match:
            metadata.version = MetadataField(
                value=version_match.group(1),
                confidence=Confidence.STRONG,
                source=source,
            )

        # C++ standard from CXXFLAGS
        std_match = re.search(r'-std=c\+\+(\d+)', content)
        if std_match:
            metadata.python_version = MetadataField(
                value=f"C++{std_match.group(1)}",
                confidence=Confidence.STRONG,
                source=source,
            )
        else:
            # Check for C standard
            c_std_match = re.search(r'-std=c(\d+)', content)
            if c_std_match:
                metadata.python_version = MetadataField(
                    value=f"C{c_std_match.group(1)}",
                    confidence=Confidence.STRONG,
                    source=source,
                )

        # Dependencies from pkg-config or -l flags
        pkg_config_match = re.findall(r'\$\(shell\s+pkg-config\s+--\w+\s+([^\)]+)\)', content)
        for pkg in pkg_config_match:
            for dep_name in pkg.split():
                dependency = Dependency(
                    name=dep_name.strip(),
                    source=f"{source} [pkg-config]",
                )
                metadata.dependencies.append(dependency)

        # Libraries from -l flags
        libs_match = re.findall(r'-l(\w+)', content)
        for lib in libs_match:
            # Skip common system libraries
            if lib not in {"m", "c", "pthread", "dl", "rt"}:
                dependency = Dependency(
                    name=lib,
                    source=f"{source} [-l flag]",
                )
                metadata.dependencies.append(dependency)

        return metadata

    def _extract_from_autoconf(self, path: Path) -> ProjectMetadata:
        """
        Extract metadata from configure.ac or configure.in.

        Args:
            path: Path to configure.ac/configure.in

        Returns:
            ProjectMetadata with extracted information
        """
        metadata = ProjectMetadata()
        content = self.read_file_safe(path)
        if content is None:
            return metadata

        source = path.name

        # AC_INIT(name, version, email, ...)
        init_match = re.search(
            r'AC_INIT\s*\(\s*\[?([^\],\)]+)\]?\s*,\s*\[?([^\],\)]+)\]?',
            content,
        )
        if init_match:
            metadata.name = MetadataField(
                value=init_match.group(1).strip(),
                confidence=Confidence.EXPLICIT,
                source=source,
            )
            metadata.version = MetadataField(
                value=init_match.group(2).strip(),
                confidence=Confidence.EXPLICIT,
                source=source,
            )

        # PKG_CHECK_MODULES
        pkg_check_pattern = re.compile(
            r'PKG_CHECK_MODULES\s*\(\s*\w+\s*,\s*\[?([^\],\)]+)',
        )
        for match in pkg_check_pattern.finditer(content):
            dep_str = match.group(1).strip()
            # Parse "dep >= version" format
            for dep in dep_str.split():
                if dep and not dep.startswith('>') and not dep.startswith('<') and not dep[0].isdigit():
                    dependency = Dependency(
                        name=dep,
                        source=f"{source} [PKG_CHECK_MODULES]",
                    )
                    metadata.dependencies.append(dependency)

        return metadata

    def _extract_from_conanfile(self, path: Path) -> ProjectMetadata:
        """
        Extract metadata from conanfile.txt.

        Args:
            path: Path to conanfile.txt

        Returns:
            ProjectMetadata with extracted information
        """
        metadata = ProjectMetadata()
        content = self.read_file_safe(path)
        if content is None:
            return metadata

        source = "conanfile.txt"
        in_requires_section = False

        for line in content.splitlines():
            line = line.strip()

            if line.startswith("["):
                in_requires_section = line.lower() == "[requires]"
                continue

            if in_requires_section and line and not line.startswith("#"):
                # Format: package/version
                parts = line.split("/")
                if parts:
                    dep_name = parts[0]
                    dep_version = parts[1] if len(parts) > 1 else None
                    dependency = Dependency(
                        name=dep_name,
                        version_constraint=dep_version,
                        source=f"{source} [requires]",
                    )
                    metadata.dependencies.append(dependency)

        return metadata
