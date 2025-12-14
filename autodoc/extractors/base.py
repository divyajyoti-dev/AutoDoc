"""
Base Extractor Interface

This module defines the abstract base class that all metadata extractors
must implement. It establishes a consistent contract for how extractors
receive discovered files and produce ProjectMetadata.

Design Principles:
    1. Single Responsibility: Each extractor handles one type of file or ecosystem
    2. Graceful Degradation: Extractors must handle missing/malformed files gracefully
    3. Confidence Tracking: All extracted data must include confidence scores
    4. Source Attribution: Every piece of data should record where it came from

Usage Pattern:
    1. Discovery phase produces a DiscoveryResult with categorized files
    2. Each extractor's `can_handle()` method checks if it has relevant files
    3. Extractors that can handle files run `extract()` to produce metadata
    4. Multiple extractor results are merged using ProjectMetadata.merge_from()
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from autodoc.discovery import DiscoveryResult
from autodoc.schema import ProjectMetadata


class BaseExtractor(ABC):
    """
    Abstract base class for all metadata extractors.

    Each extractor is responsible for:
        - Determining if it can extract data from the discovered files
        - Reading and parsing relevant files
        - Producing a ProjectMetadata object with extracted information
        - Handling errors gracefully (log warnings, don't crash)

    Subclasses must implement:
        - name: Human-readable name for the extractor
        - can_handle(): Check if this extractor is relevant
        - extract(): Perform the actual extraction

    Example implementation:
        class PythonExtractor(BaseExtractor):
            name = "Python"

            def can_handle(self, discovery_result: DiscoveryResult) -> bool:
                # Check if any Python package files exist
                return discovery_result.has_category(FileCategory.PACKAGE_MANIFEST)

            def extract(self, discovery_result: DiscoveryResult) -> ProjectMetadata:
                metadata = ProjectMetadata()
                # ... parse setup.py, pyproject.toml, etc.
                return metadata

    Attributes:
        name: Human-readable identifier for this extractor
        root_path: The repository root path (set during extraction)
    """

    # Human-readable name for this extractor (e.g., "Python", "JavaScript")
    # Subclasses should override this
    name: str = "Base"

    def __init__(self):
        """Initialize the extractor."""
        self.root_path: Optional[Path] = None
        self._warnings: list[str] = []

    def add_warning(self, message: str) -> None:
        """
        Record a warning encountered during extraction.

        Warnings are non-fatal issues that should be reported but don't
        prevent extraction from continuing.

        Args:
            message: The warning message to record
        """
        self._warnings.append(f"[{self.name}] {message}")

    def get_warnings(self) -> list[str]:
        """
        Get all warnings recorded during extraction.

        Returns:
            List of warning messages
        """
        return self._warnings.copy()

    def clear_warnings(self) -> None:
        """Clear all recorded warnings."""
        self._warnings = []

    def read_file_safe(self, path: Path, encoding: str = "utf-8") -> Optional[str]:
        """
        Safely read a file's contents, returning None on error.

        This helper method handles common file reading errors gracefully,
        recording warnings instead of raising exceptions.

        Args:
            path: Path to the file to read
            encoding: File encoding (default: utf-8)

        Returns:
            File contents as a string, or None if reading failed
        """
        try:
            with open(path, "r", encoding=encoding) as f:
                return f.read()
        except FileNotFoundError:
            self.add_warning(f"File not found: {path}")
            return None
        except PermissionError:
            self.add_warning(f"Permission denied: {path}")
            return None
        except UnicodeDecodeError:
            self.add_warning(f"Could not decode file (not {encoding}): {path}")
            return None
        except IOError as e:
            self.add_warning(f"Could not read file {path}: {e}")
            return None

    @abstractmethod
    def can_handle(self, discovery_result: DiscoveryResult) -> bool:
        """
        Determine if this extractor can extract data from the discovered files.

        This method should be fast and lightweight. It typically checks
        if certain file categories or specific files are present.

        Args:
            discovery_result: The result of file discovery

        Returns:
            True if this extractor has relevant files to process
        """
        pass

    @abstractmethod
    def extract(
        self,
        discovery_result: DiscoveryResult,
        root_path: Path,
    ) -> ProjectMetadata:
        """
        Extract metadata from the discovered files.

        This is the main extraction logic. It should:
            1. Identify relevant files from discovery_result
            2. Read and parse each file
            3. Populate a ProjectMetadata object with extracted data
            4. Handle errors gracefully (use add_warning())
            5. Assign appropriate confidence scores

        Args:
            discovery_result: The result of file discovery
            root_path: The repository root path

        Returns:
            ProjectMetadata object populated with extracted information.
            Fields that could not be extracted should use default
            (UNKNOWN confidence) values.
        """
        pass


class ExtractorRegistry:
    """
    Registry for managing available extractors.

    This class maintains a list of all available extractors and provides
    methods to run them against a discovery result.

    Usage:
        registry = ExtractorRegistry()
        registry.register(PythonExtractor())
        registry.register(JavaScriptExtractor())

        # Run all applicable extractors
        metadata = registry.extract_all(discovery_result, root_path)
    """

    def __init__(self):
        """Initialize an empty registry."""
        self._extractors: list[BaseExtractor] = []

    def register(self, extractor: BaseExtractor) -> None:
        """
        Register an extractor with the registry.

        Args:
            extractor: The extractor instance to register
        """
        self._extractors.append(extractor)

    def get_extractors(self) -> list[BaseExtractor]:
        """
        Get all registered extractors.

        Returns:
            List of registered extractor instances
        """
        return self._extractors.copy()

    def get_applicable_extractors(
        self,
        discovery_result: DiscoveryResult,
    ) -> list[BaseExtractor]:
        """
        Get extractors that can handle the discovered files.

        Args:
            discovery_result: The result of file discovery

        Returns:
            List of extractors whose can_handle() returns True
        """
        return [
            ext for ext in self._extractors
            if ext.can_handle(discovery_result)
        ]

    def extract_all(
        self,
        discovery_result: DiscoveryResult,
        root_path: Path,
    ) -> ProjectMetadata:
        """
        Run all applicable extractors and merge their results.

        This is the main entry point for extraction. It:
            1. Finds all extractors that can handle the files
            2. Runs each extractor
            3. Merges results (higher confidence wins)
            4. Collects all warnings

        Args:
            discovery_result: The result of file discovery
            root_path: The repository root path

        Returns:
            Merged ProjectMetadata from all applicable extractors
        """
        merged = ProjectMetadata()
        merged.file_count = discovery_result.total_file_count

        applicable = self.get_applicable_extractors(discovery_result)

        for extractor in applicable:
            extractor.clear_warnings()
            result = extractor.extract(discovery_result, root_path)

            # Merge this extractor's results into the combined metadata
            merged.merge_from(result)

            # Collect warnings from this extractor
            merged.extraction_warnings.extend(extractor.get_warnings())

        # Also include discovery warnings
        merged.extraction_warnings.extend(discovery_result.warnings)

        return merged
