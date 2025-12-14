"""
AutoDoc Metadata Schema

This module defines the unified data structures for representing extracted
project metadata. All extractors produce data conforming to these schemas,
enabling consistent processing regardless of the source project type.

Design Principles:
    1. Every extractable field has an associated confidence score (0.0-1.0)
    2. Source tracking: know where each piece of information came from
    3. Explicit placeholders for missing/uncertain information
    4. Human-readable when serialized

Confidence Score Guidelines:
    1.0  - Explicitly stated (e.g., name in package.json)
    0.8  - Strongly inferred (e.g., license from LICENSE file content)
    0.6  - Reasonably inferred (e.g., entry point from common patterns)
    0.4  - Weakly inferred (e.g., description from directory name)
    0.2  - Guessed (e.g., author from git config)
    0.0  - Unknown/placeholder
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Confidence(Enum):
    """
    Semantic confidence levels for extracted metadata.

    Using an enum provides consistent, documented confidence levels
    rather than arbitrary float values throughout the codebase.
    """
    EXPLICIT = 1.0      # Directly stated in a file (e.g., "name" in package.json)
    STRONG = 0.8        # Strongly inferred (e.g., MIT from LICENSE file text)
    REASONABLE = 0.6    # Reasonably inferred (e.g., main.py as entry point)
    WEAK = 0.4          # Weakly inferred (e.g., project name from folder)
    GUESS = 0.2         # Educated guess (e.g., author from git config)
    UNKNOWN = 0.0       # No information available; placeholder needed

    def __float__(self) -> float:
        return self.value

    def __str__(self) -> str:
        return self.name.lower()


@dataclass
class MetadataField:
    """
    A single piece of extracted metadata with provenance tracking.

    Attributes:
        value: The extracted value (None if not found)
        confidence: How confident we are in this value
        source: File path or method that produced this value
        note: Optional explanation (especially for low confidence or placeholders)

    Example:
        >>> license_field = MetadataField(
        ...     value="MIT",
        ...     confidence=Confidence.STRONG,
        ...     source="LICENSE",
        ...     note="Detected 'MIT License' text in file header"
        ... )
    """
    value: Optional[str]
    confidence: Confidence
    source: Optional[str] = None
    note: Optional[str] = None

    def is_placeholder(self) -> bool:
        """Returns True if this field needs human input."""
        return self.value is None or self.confidence == Confidence.UNKNOWN

    def needs_review(self) -> bool:
        """Returns True if confidence is low enough to warrant review."""
        return self.confidence.value < Confidence.REASONABLE.value


@dataclass
class Dependency:
    """
    A single project dependency.

    Attributes:
        name: Package/library name
        version_constraint: Version specifier (e.g., ">=1.0.0", "^2.3.4")
        is_dev: Whether this is a development-only dependency
        source: File where this dependency was found
    """
    name: str
    version_constraint: Optional[str] = None
    is_dev: bool = False
    source: Optional[str] = None


@dataclass
class Author:
    """
    Author or maintainer information.

    Attributes:
        name: Author's name
        email: Author's email (optional)
        role: Role description (e.g., "maintainer", "contributor")
        source: Where this information was extracted from
    """
    name: str
    email: Optional[str] = None
    role: Optional[str] = None
    source: Optional[str] = None


@dataclass
class EntryPoint:
    """
    A detected entry point for the project.

    Attributes:
        path: File path relative to project root
        entry_type: Type of entry point (e.g., "cli", "module", "script")
        command: CLI command if applicable (e.g., "autodoc")
        confidence: How confident we are this is a real entry point
        note: Explanation of why this was detected
    """
    path: str
    entry_type: str  # "cli", "module", "script", "main"
    command: Optional[str] = None
    confidence: Confidence = Confidence.REASONABLE
    note: Optional[str] = None


@dataclass
class ProjectMetadata:
    """
    Complete metadata for a project, unified across all source types.

    This is the central schema that all extractors populate and the
    renderer consumes. Fields are grouped by category for clarity.

    All MetadataField attributes support confidence tracking and
    source provenance. List attributes contain their own source info.
    """

    # === Project Identification ===
    name: MetadataField = field(
        default_factory=lambda: MetadataField(
            value=None,
            confidence=Confidence.UNKNOWN,
            note="Project name could not be detected"
        )
    )
    description: MetadataField = field(
        default_factory=lambda: MetadataField(
            value=None,
            confidence=Confidence.UNKNOWN,
            note="No project description found"
        )
    )
    version: MetadataField = field(
        default_factory=lambda: MetadataField(
            value=None,
            confidence=Confidence.UNKNOWN,
            note="Version not specified"
        )
    )

    # === Authors & Maintainers ===
    authors: list[Author] = field(default_factory=list)

    # === License ===
    license: MetadataField = field(
        default_factory=lambda: MetadataField(
            value=None,
            confidence=Confidence.UNKNOWN,
            note="No license file or declaration found"
        )
    )

    # === Dependencies ===
    dependencies: list[Dependency] = field(default_factory=list)
    dev_dependencies: list[Dependency] = field(default_factory=list)
    python_version: MetadataField = field(
        default_factory=lambda: MetadataField(
            value=None,
            confidence=Confidence.UNKNOWN,
            note="Python version requirement not specified"
        )
    )

    # === Entry Points ===
    entry_points: list[EntryPoint] = field(default_factory=list)

    # === Repository Info ===
    repository_url: MetadataField = field(
        default_factory=lambda: MetadataField(
            value=None,
            confidence=Confidence.UNKNOWN,
            note="Repository URL not found"
        )
    )
    homepage_url: MetadataField = field(
        default_factory=lambda: MetadataField(
            value=None,
            confidence=Confidence.UNKNOWN,
            note="Homepage URL not found"
        )
    )

    # === Documentation Hints ===
    # These help the renderer know what sections to include
    has_tests: bool = False
    has_docs_folder: bool = False
    has_examples: bool = False
    has_ci_config: bool = False

    # === Analysis Metadata ===
    # Information about the extraction process itself
    file_count: int = 0
    primary_language: MetadataField = field(
        default_factory=lambda: MetadataField(
            value=None,
            confidence=Confidence.UNKNOWN,
            note="Primary language not determined"
        )
    )
    extraction_warnings: list[str] = field(default_factory=list)

    # === LLM-Generated Content ===
    # These fields are populated by LLM enhancement
    key_features: list[str] = field(default_factory=list)
    architecture_summary: Optional[str] = None
    config_files: list[str] = field(default_factory=list)  # Detected config file paths

    def get_placeholder_fields(self) -> list[str]:
        """
        Returns names of fields that need human input.

        Useful for generating TODO comments in the README.
        """
        placeholders = []
        for field_name in ['name', 'description', 'version', 'license',
                           'python_version', 'repository_url', 'homepage_url',
                           'primary_language']:
            field_value = getattr(self, field_name)
            if isinstance(field_value, MetadataField) and field_value.is_placeholder():
                placeholders.append(field_name)
        return placeholders

    def get_low_confidence_fields(self) -> list[tuple[str, Confidence]]:
        """
        Returns fields with low confidence that should be reviewed.

        Returns:
            List of (field_name, confidence) tuples for fields needing review.
        """
        review_needed = []
        for field_name in ['name', 'description', 'version', 'license',
                           'python_version', 'repository_url', 'homepage_url',
                           'primary_language']:
            field_value = getattr(self, field_name)
            if isinstance(field_value, MetadataField) and field_value.needs_review():
                review_needed.append((field_name, field_value.confidence))
        return review_needed

    def merge_from(self, other: 'ProjectMetadata') -> None:
        """
        Merge another ProjectMetadata into this one.

        Higher confidence values take precedence. This allows multiple
        extractors to contribute to the same metadata object.

        Args:
            other: Another ProjectMetadata to merge from
        """
        # Merge MetadataFields (higher confidence wins)
        for field_name in ['name', 'description', 'version', 'license',
                           'python_version', 'repository_url', 'homepage_url',
                           'primary_language']:
            self_field = getattr(self, field_name)
            other_field = getattr(other, field_name)
            if other_field.confidence.value > self_field.confidence.value:
                setattr(self, field_name, other_field)

        # Merge lists (avoid duplicates by name)
        existing_author_names = {a.name for a in self.authors}
        for author in other.authors:
            if author.name not in existing_author_names:
                self.authors.append(author)
                existing_author_names.add(author.name)

        existing_dep_names = {d.name for d in self.dependencies}
        for dep in other.dependencies:
            if dep.name not in existing_dep_names:
                self.dependencies.append(dep)
                existing_dep_names.add(dep.name)

        existing_dev_dep_names = {d.name for d in self.dev_dependencies}
        for dep in other.dev_dependencies:
            if dep.name not in existing_dev_dep_names:
                self.dev_dependencies.append(dep)
                existing_dev_dep_names.add(dep.name)

        existing_entry_paths = {e.path for e in self.entry_points}
        for entry in other.entry_points:
            if entry.path not in existing_entry_paths:
                self.entry_points.append(entry)
                existing_entry_paths.add(entry.path)

        # Merge boolean flags (True wins)
        self.has_tests = self.has_tests or other.has_tests
        self.has_docs_folder = self.has_docs_folder or other.has_docs_folder
        self.has_examples = self.has_examples or other.has_examples
        self.has_ci_config = self.has_ci_config or other.has_ci_config

        # Take max file count
        self.file_count = max(self.file_count, other.file_count)

        # Merge warnings
        self.extraction_warnings.extend(other.extraction_warnings)
