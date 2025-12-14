"""
Java Metadata Extractor

This module extracts metadata from Java projects by parsing:
    - pom.xml (Maven project descriptor)
    - build.gradle / build.gradle.kts (Gradle build files)
    - gradle.properties (Gradle properties)

Supported Metadata:
    - Project name, version, description
    - Group ID and artifact ID
    - License information
    - Dependencies
    - Java version requirements
    - Repository and homepage URLs

Heuristics and Limitations:
    - Uses regex for Gradle files (not a full Groovy/Kotlin parser)
    - Only parses root pom.xml (not multi-module)
    - Dynamic versions in Gradle may not be fully resolved
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

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


class JavaExtractor(BaseExtractor):
    """
    Extracts metadata from Java projects.

    This extractor handles Maven (pom.xml) and Gradle build configurations.

    Priority order:
        1. pom.xml (Maven) - XML parsing
        2. build.gradle / build.gradle.kts (Gradle) - Regex parsing

    Usage:
        extractor = JavaExtractor()
        if extractor.can_handle(discovery_result):
            metadata = extractor.extract(discovery_result, root_path)
    """

    name = "Java"

    # Maven namespace
    POM_NS = {"m": "http://maven.apache.org/POM/4.0.0"}

    def can_handle(self, discovery_result: DiscoveryResult) -> bool:
        """
        Check if this is a Java project.

        Returns True if Maven or Gradle files are found.

        Args:
            discovery_result: The result of file discovery

        Returns:
            True if Java project files are detected
        """
        java_build_files = {"pom.xml", "build.gradle", "build.gradle.kts"}
        for f in discovery_result.files:
            if f.relative_path.name in java_build_files:
                return True

        # Check for Java source files
        java_files = [f for f in discovery_result.files if f.path.suffix == ".java"]
        return len(java_files) > 0

    def extract(
        self,
        discovery_result: DiscoveryResult,
        root_path: Path,
    ) -> ProjectMetadata:
        """
        Extract metadata from Java project files.

        Args:
            discovery_result: The result of file discovery
            root_path: The repository root path

        Returns:
            ProjectMetadata populated with Java project information
        """
        self.root_path = root_path
        metadata = ProjectMetadata()

        # Mark as Java project
        metadata.primary_language = MetadataField(
            value="Java",
            confidence=Confidence.STRONG,
            source="Build file analysis",
        )

        # Try Maven first
        pom_path = root_path / "pom.xml"
        if pom_path.exists():
            pom_metadata = self._extract_from_pom(pom_path)
            metadata.merge_from(pom_metadata)

        # Try Gradle
        gradle_path = root_path / "build.gradle"
        gradle_kts_path = root_path / "build.gradle.kts"
        if gradle_path.exists():
            gradle_metadata = self._extract_from_gradle(gradle_path)
            metadata.merge_from(gradle_metadata)
        elif gradle_kts_path.exists():
            gradle_metadata = self._extract_from_gradle(gradle_kts_path)
            metadata.merge_from(gradle_metadata)

        # Check for test files
        if discovery_result.has_category(FileCategory.TEST_FILE):
            metadata.has_tests = True

        # Check for CI config
        if discovery_result.has_category(FileCategory.CI_CONFIG):
            metadata.has_ci_config = True

        return metadata

    def _extract_from_pom(self, path: Path) -> ProjectMetadata:
        """
        Extract metadata from pom.xml.

        Args:
            path: Path to pom.xml

        Returns:
            ProjectMetadata with extracted information
        """
        metadata = ProjectMetadata()
        content = self.read_file_safe(path)
        if content is None:
            return metadata

        try:
            # Try parsing with namespace
            root = ET.fromstring(content)
        except ET.ParseError as e:
            self.add_warning(f"Failed to parse pom.xml: {e}")
            return metadata

        source = "pom.xml"

        # Determine namespace
        ns = self.POM_NS if root.tag.startswith("{") else {}

        def find_text(parent, tag: str) -> Optional[str]:
            """Find text content of a tag, handling namespaces."""
            if ns:
                elem = parent.find(f"m:{tag}", ns)
            else:
                elem = parent.find(tag)
            return elem.text.strip() if elem is not None and elem.text else None

        # Group ID
        group_id = find_text(root, "groupId")

        # Artifact ID (used as name)
        artifact_id = find_text(root, "artifactId")
        if artifact_id:
            # Combine with group ID for full name if available
            full_name = f"{group_id}:{artifact_id}" if group_id else artifact_id
            metadata.name = MetadataField(
                value=artifact_id,  # Use artifact ID as the simple name
                confidence=Confidence.EXPLICIT,
                source=source,
                note=f"Full coordinates: {full_name}" if group_id else None,
            )

        # Version
        version = find_text(root, "version")
        if version:
            metadata.version = MetadataField(
                value=version,
                confidence=Confidence.EXPLICIT,
                source=source,
            )

        # Name (display name)
        name = find_text(root, "name")
        if name and name != artifact_id:
            metadata.name = MetadataField(
                value=name,
                confidence=Confidence.EXPLICIT,
                source=source,
            )

        # Description
        description = find_text(root, "description")
        if description:
            metadata.description = MetadataField(
                value=description,
                confidence=Confidence.EXPLICIT,
                source=source,
            )

        # URL
        url = find_text(root, "url")
        if url:
            metadata.homepage_url = MetadataField(
                value=url,
                confidence=Confidence.EXPLICIT,
                source=source,
            )

        # SCM URL
        scm = root.find("m:scm", ns) if ns else root.find("scm")
        if scm is not None:
            scm_url = find_text(scm, "url")
            if scm_url:
                metadata.repository_url = MetadataField(
                    value=scm_url,
                    confidence=Confidence.EXPLICIT,
                    source=f"{source} [scm]",
                )

        # Licenses
        licenses = root.find("m:licenses", ns) if ns else root.find("licenses")
        if licenses is not None:
            license_elem = licenses.find("m:license", ns) if ns else licenses.find("license")
            if license_elem is not None:
                license_name = find_text(license_elem, "name")
                if license_name:
                    metadata.license = MetadataField(
                        value=license_name,
                        confidence=Confidence.EXPLICIT,
                        source=source,
                    )

        # Developers
        developers = root.find("m:developers", ns) if ns else root.find("developers")
        if developers is not None:
            for dev in developers.findall("m:developer", ns) if ns else developers.findall("developer"):
                dev_name = find_text(dev, "name")
                dev_email = find_text(dev, "email")
                if dev_name:
                    author = Author(
                        name=dev_name,
                        email=dev_email,
                        role="developer",
                        source=source,
                    )
                    metadata.authors.append(author)

        # Properties (for Java version)
        properties = root.find("m:properties", ns) if ns else root.find("properties")
        if properties is not None:
            # Try various Java version properties
            java_version = None
            for prop_name in ["java.version", "maven.compiler.source", "maven.compiler.target"]:
                prop_elem = properties.find(f"m:{prop_name}", ns) if ns else properties.find(prop_name)
                if prop_elem is not None and prop_elem.text:
                    java_version = prop_elem.text.strip()
                    break

            if java_version:
                metadata.python_version = MetadataField(  # Reusing for Java version
                    value=f"Java {java_version}",
                    confidence=Confidence.EXPLICIT,
                    source=f"{source} [properties]",
                )

        # Dependencies
        deps = root.find("m:dependencies", ns) if ns else root.find("dependencies")
        if deps is not None:
            for dep in deps.findall("m:dependency", ns) if ns else deps.findall("dependency"):
                dep_group = find_text(dep, "groupId")
                dep_artifact = find_text(dep, "artifactId")
                dep_version = find_text(dep, "version")
                dep_scope = find_text(dep, "scope")

                if dep_artifact:
                    is_dev = dep_scope in {"test", "provided"}
                    dependency = Dependency(
                        name=f"{dep_group}:{dep_artifact}" if dep_group else dep_artifact,
                        version_constraint=dep_version,
                        is_dev=is_dev,
                        source=source,
                    )
                    if is_dev:
                        metadata.dev_dependencies.append(dependency)
                    else:
                        metadata.dependencies.append(dependency)

        return metadata

    def _extract_from_gradle(self, path: Path) -> ProjectMetadata:
        """
        Extract metadata from build.gradle or build.gradle.kts.

        Uses regex patterns - not a full Groovy/Kotlin parser.

        Args:
            path: Path to Gradle build file

        Returns:
            ProjectMetadata with extracted information
        """
        metadata = ProjectMetadata()
        content = self.read_file_safe(path)
        if content is None:
            return metadata

        source = path.name
        is_kts = path.suffix == ".kts"

        # Extract common fields using regex
        # Group
        group_match = re.search(
            r'group\s*[=:]\s*["\']([^"\']+)["\']',
            content,
        )

        # Version
        version_match = re.search(
            r'version\s*[=:]\s*["\']([^"\']+)["\']',
            content,
        )
        if version_match:
            metadata.version = MetadataField(
                value=version_match.group(1),
                confidence=Confidence.EXPLICIT,
                source=source,
            )

        # Name might be in settings.gradle
        settings_path = path.parent / ("settings.gradle.kts" if is_kts else "settings.gradle")
        if settings_path.exists():
            settings_content = self.read_file_safe(settings_path)
            if settings_content:
                name_match = re.search(
                    r'rootProject\.name\s*[=:]\s*["\']([^"\']+)["\']',
                    settings_content,
                )
                if name_match:
                    metadata.name = MetadataField(
                        value=name_match.group(1),
                        confidence=Confidence.EXPLICIT,
                        source="settings.gradle",
                    )

        # Use group as name fallback
        if metadata.name.is_placeholder() and group_match:
            metadata.name = MetadataField(
                value=group_match.group(1),
                confidence=Confidence.STRONG,
                source=source,
                note="Using group as name",
            )

        # Java version from sourceCompatibility/targetCompatibility
        java_version_match = re.search(
            r'(?:sourceCompatibility|targetCompatibility|jvmTarget)\s*[=:]\s*["\']?([0-9.]+|JavaVersion\.[A-Z_0-9]+)["\']?',
            content,
        )
        if java_version_match:
            version_str = java_version_match.group(1)
            # Clean up JavaVersion enum
            if "JavaVersion" in version_str:
                version_str = version_str.replace("JavaVersion.", "").replace("_", ".")
            metadata.python_version = MetadataField(
                value=f"Java {version_str}",
                confidence=Confidence.EXPLICIT,
                source=source,
            )

        # Dependencies - match various Gradle dependency syntaxes
        # implementation "group:artifact:version"
        # implementation("group:artifact:version")
        # testImplementation ...
        dep_pattern = re.compile(
            r'(implementation|api|compile|testImplementation|testCompile|compileOnly)\s*[\("]([^")\n]+)["\)]',
        )
        for match in dep_pattern.finditer(content):
            config = match.group(1)
            dep_str = match.group(2)

            # Parse dependency string (group:artifact:version)
            parts = dep_str.split(":")
            if len(parts) >= 2:
                name = f"{parts[0]}:{parts[1]}"
                version = parts[2] if len(parts) > 2 else None
                is_dev = config in {"testImplementation", "testCompile"}

                dependency = Dependency(
                    name=name,
                    version_constraint=version,
                    is_dev=is_dev,
                    source=source,
                )
                if is_dev:
                    metadata.dev_dependencies.append(dependency)
                else:
                    metadata.dependencies.append(dependency)

        return metadata
