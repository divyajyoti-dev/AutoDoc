"""
AutoDoc File Discovery Module

This module handles recursive traversal of a repository's file system,
identifying files relevant for metadata extraction while respecting
ignore patterns and scope constraints.

Key Responsibilities:
    1. Walk the directory tree starting from a root path
    2. Parse and respect .gitignore patterns
    3. Skip common non-relevant directories (node_modules, __pycache__, etc.)
    4. Categorize discovered files by type/purpose
    5. Enforce repository size limits and warn when exceeded

Design Notes:
    - We use pathlib for cross-platform path handling
    - .gitignore parsing uses fnmatch-style patterns (simplified, not full git spec)
    - File categorization is heuristic-based and documented in RELEVANT_PATTERNS

Limitations:
    - Does not support nested .gitignore files (only root-level)
    - Pattern matching is simplified compared to full git behavior
    - Symlinks are not followed to avoid cycles
"""

import fnmatch
import os
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional


class FileCategory(Enum):
    """
    Categories for discovered files based on their purpose.

    These categories help extractors know which files to examine
    for specific types of metadata.
    """
    # Package/dependency management files
    PACKAGE_MANIFEST = auto()       # package.json, Cargo.toml, setup.py, etc.
    DEPENDENCY_LOCK = auto()        # package-lock.json, Cargo.lock, etc.
    REQUIREMENTS = auto()           # requirements.txt, requirements-dev.txt

    # Documentation files
    README = auto()                 # README.md, README.rst, etc.
    LICENSE = auto()                # LICENSE, COPYING, etc.
    DOCS = auto()                   # Files in docs/ folder

    # Configuration files
    CONFIG = auto()                 # .eslintrc, pyproject.toml, tsconfig.json
    CI_CONFIG = auto()              # .github/workflows, .gitlab-ci.yml, etc.
    ENV_CONFIG = auto()             # .env.example, environment files

    # Source code files
    SOURCE_CODE = auto()            # .py, .js, .ts, .rs, .go, etc.
    TEST_FILE = auto()              # test_*.py, *.test.js, etc.

    # Entry point candidates
    ENTRY_POINT = auto()            # main.py, index.js, cli.py, etc.

    # Other
    OTHER = auto()                  # Files that don't fit other categories


# Patterns for categorizing files.
# Each tuple contains: (glob_pattern, category, description)
# Order matters: first match wins.
CATEGORIZATION_PATTERNS: list[tuple[str, FileCategory, str]] = [
    # Package manifests (high priority, check first)
    ("package.json", FileCategory.PACKAGE_MANIFEST, "Node.js package manifest"),
    ("Cargo.toml", FileCategory.PACKAGE_MANIFEST, "Rust package manifest"),
    ("setup.py", FileCategory.PACKAGE_MANIFEST, "Python setuptools config"),
    ("setup.cfg", FileCategory.PACKAGE_MANIFEST, "Python setup config"),
    ("pyproject.toml", FileCategory.PACKAGE_MANIFEST, "Python project config (PEP 518)"),
    ("go.mod", FileCategory.PACKAGE_MANIFEST, "Go module definition"),
    ("Gemfile", FileCategory.PACKAGE_MANIFEST, "Ruby gem dependencies"),
    ("composer.json", FileCategory.PACKAGE_MANIFEST, "PHP Composer manifest"),
    ("pom.xml", FileCategory.PACKAGE_MANIFEST, "Maven project file"),
    ("build.gradle", FileCategory.PACKAGE_MANIFEST, "Gradle build file"),

    # Lock files
    ("package-lock.json", FileCategory.DEPENDENCY_LOCK, "npm lock file"),
    ("yarn.lock", FileCategory.DEPENDENCY_LOCK, "Yarn lock file"),
    ("pnpm-lock.yaml", FileCategory.DEPENDENCY_LOCK, "pnpm lock file"),
    ("Cargo.lock", FileCategory.DEPENDENCY_LOCK, "Cargo lock file"),
    ("Gemfile.lock", FileCategory.DEPENDENCY_LOCK, "Bundler lock file"),
    ("poetry.lock", FileCategory.DEPENDENCY_LOCK, "Poetry lock file"),
    ("composer.lock", FileCategory.DEPENDENCY_LOCK, "Composer lock file"),

    # Requirements files
    ("requirements*.txt", FileCategory.REQUIREMENTS, "Python requirements file"),
    ("constraints*.txt", FileCategory.REQUIREMENTS, "Python constraints file"),

    # README files
    ("README*", FileCategory.README, "Project README"),
    ("readme*", FileCategory.README, "Project README (lowercase)"),

    # License files
    ("LICENSE*", FileCategory.LICENSE, "License file"),
    ("LICENCE*", FileCategory.LICENSE, "License file (British spelling)"),
    ("COPYING*", FileCategory.LICENSE, "License/copying file"),

    # CI/CD configuration
    (".github/workflows/*", FileCategory.CI_CONFIG, "GitHub Actions workflow"),
    (".gitlab-ci.yml", FileCategory.CI_CONFIG, "GitLab CI config"),
    (".travis.yml", FileCategory.CI_CONFIG, "Travis CI config"),
    ("Jenkinsfile", FileCategory.CI_CONFIG, "Jenkins pipeline"),
    (".circleci/*", FileCategory.CI_CONFIG, "CircleCI config"),
    ("azure-pipelines.yml", FileCategory.CI_CONFIG, "Azure Pipelines config"),

    # Environment configuration
    (".env.example", FileCategory.ENV_CONFIG, "Environment template"),
    (".env.sample", FileCategory.ENV_CONFIG, "Environment template"),
    (".env.template", FileCategory.ENV_CONFIG, "Environment template"),

    # Configuration files
    ("pyproject.toml", FileCategory.CONFIG, "Python project config"),
    ("tsconfig.json", FileCategory.CONFIG, "TypeScript config"),
    ("jsconfig.json", FileCategory.CONFIG, "JavaScript config"),
    (".eslintrc*", FileCategory.CONFIG, "ESLint config"),
    (".prettierrc*", FileCategory.CONFIG, "Prettier config"),
    ("Makefile", FileCategory.CONFIG, "Make build config"),
    ("Dockerfile", FileCategory.CONFIG, "Docker build file"),
    ("docker-compose*.yml", FileCategory.CONFIG, "Docker Compose config"),
    ("docker-compose*.yaml", FileCategory.CONFIG, "Docker Compose config"),

    # Test files (check before generic source to properly categorize)
    ("test_*.py", FileCategory.TEST_FILE, "Python test file"),
    ("*_test.py", FileCategory.TEST_FILE, "Python test file"),
    ("tests/*.py", FileCategory.TEST_FILE, "Python test file"),
    ("test/*.py", FileCategory.TEST_FILE, "Python test file"),
    ("*.test.js", FileCategory.TEST_FILE, "JavaScript test file"),
    ("*.spec.js", FileCategory.TEST_FILE, "JavaScript spec file"),
    ("*.test.ts", FileCategory.TEST_FILE, "TypeScript test file"),
    ("*.spec.ts", FileCategory.TEST_FILE, "TypeScript spec file"),
    ("*_test.go", FileCategory.TEST_FILE, "Go test file"),
    ("*_test.rs", FileCategory.TEST_FILE, "Rust test file"),

    # Entry point candidates (common names)
    ("main.py", FileCategory.ENTRY_POINT, "Python main entry"),
    ("__main__.py", FileCategory.ENTRY_POINT, "Python package entry"),
    ("cli.py", FileCategory.ENTRY_POINT, "Python CLI entry"),
    ("app.py", FileCategory.ENTRY_POINT, "Python app entry"),
    ("index.js", FileCategory.ENTRY_POINT, "JavaScript entry"),
    ("index.ts", FileCategory.ENTRY_POINT, "TypeScript entry"),
    ("main.js", FileCategory.ENTRY_POINT, "JavaScript main entry"),
    ("main.ts", FileCategory.ENTRY_POINT, "TypeScript main entry"),
    ("main.go", FileCategory.ENTRY_POINT, "Go main entry"),
    ("main.rs", FileCategory.ENTRY_POINT, "Rust main entry"),
    ("src/main.rs", FileCategory.ENTRY_POINT, "Rust src main entry"),
    ("src/lib.rs", FileCategory.ENTRY_POINT, "Rust library entry"),

    # Source code (generic, checked last)
    ("*.py", FileCategory.SOURCE_CODE, "Python source"),
    ("*.js", FileCategory.SOURCE_CODE, "JavaScript source"),
    ("*.ts", FileCategory.SOURCE_CODE, "TypeScript source"),
    ("*.jsx", FileCategory.SOURCE_CODE, "React JSX source"),
    ("*.tsx", FileCategory.SOURCE_CODE, "React TSX source"),
    ("*.go", FileCategory.SOURCE_CODE, "Go source"),
    ("*.rs", FileCategory.SOURCE_CODE, "Rust source"),
    ("*.java", FileCategory.SOURCE_CODE, "Java source"),
    ("*.c", FileCategory.SOURCE_CODE, "C source"),
    ("*.cpp", FileCategory.SOURCE_CODE, "C++ source"),
    ("*.h", FileCategory.SOURCE_CODE, "C/C++ header"),
    ("*.hpp", FileCategory.SOURCE_CODE, "C++ header"),
    ("*.rb", FileCategory.SOURCE_CODE, "Ruby source"),
    ("*.php", FileCategory.SOURCE_CODE, "PHP source"),
    ("*.swift", FileCategory.SOURCE_CODE, "Swift source"),
    ("*.kt", FileCategory.SOURCE_CODE, "Kotlin source"),
    ("*.scala", FileCategory.SOURCE_CODE, "Scala source"),
    ("*.sh", FileCategory.SOURCE_CODE, "Shell script"),
    ("*.bash", FileCategory.SOURCE_CODE, "Bash script"),
]

# Directories to always skip, regardless of .gitignore.
# These are either build artifacts, dependencies, or version control.
DEFAULT_IGNORE_DIRS: set[str] = {
    # Version control
    ".git",
    ".svn",
    ".hg",

    # Dependencies
    "node_modules",
    "vendor",
    ".venv",
    "venv",
    "env",
    ".env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "target",           # Rust build output
    ".cargo",

    # Build outputs
    "build",
    "dist",
    "out",
    ".next",
    ".nuxt",
    ".output",

    # IDE directories
    ".idea",
    ".vscode",
    ".vs",

    # OS files
    ".DS_Store",
    "Thumbs.db",

    # Coverage and test artifacts
    "coverage",
    ".coverage",
    "htmlcov",
    ".tox",
    ".nox",

    # Eggs and distributions
    "*.egg-info",
    ".eggs",
}


@dataclass
class DiscoveredFile:
    """
    Represents a single discovered file with its metadata.

    Attributes:
        path: Absolute path to the file
        relative_path: Path relative to the repository root
        category: The file's category (determines which extractors care about it)
        size_bytes: File size in bytes (useful for skipping huge files)
        category_note: Human-readable explanation of why this category was assigned
    """
    path: Path
    relative_path: Path
    category: FileCategory
    size_bytes: int
    category_note: str = ""

    def __str__(self) -> str:
        return f"{self.relative_path} [{self.category.name}]"


@dataclass
class DiscoveryResult:
    """
    Complete result of a file discovery operation.

    Contains all discovered files organized by category, along with
    warnings and statistics about the discovery process.

    Attributes:
        root_path: The repository root that was scanned
        files: All discovered files
        total_file_count: Number of files discovered (for scope checking)
        skipped_dirs: Directories that were skipped and why
        warnings: Any warnings generated during discovery
        exceeded_limit: True if file count exceeded MAX_FILES
    """
    root_path: Path
    files: list[DiscoveredFile] = field(default_factory=list)
    total_file_count: int = 0
    skipped_dirs: list[tuple[str, str]] = field(default_factory=list)  # (path, reason)
    warnings: list[str] = field(default_factory=list)
    exceeded_limit: bool = False

    def get_files_by_category(self, category: FileCategory) -> list[DiscoveredFile]:
        """
        Filter files by a specific category.

        Args:
            category: The FileCategory to filter by

        Returns:
            List of DiscoveredFile objects matching the category
        """
        return [f for f in self.files if f.category == category]

    def get_category_counts(self) -> dict[FileCategory, int]:
        """
        Count files in each category.

        Returns:
            Dictionary mapping each FileCategory to its file count
        """
        counts: dict[FileCategory, int] = {}
        for f in self.files:
            counts[f.category] = counts.get(f.category, 0) + 1
        return counts

    def has_category(self, category: FileCategory) -> bool:
        """
        Check if any files were found in a given category.

        Args:
            category: The FileCategory to check

        Returns:
            True if at least one file exists in that category
        """
        return any(f.category == category for f in self.files)


class FileDiscovery:
    """
    Discovers and categorizes files in a repository.

    This class handles the main logic of walking a directory tree,
    applying ignore patterns, categorizing files, and enforcing
    scope constraints.

    Usage:
        discovery = FileDiscovery("/path/to/repo")
        result = discovery.discover()

        # Get all Python package manifests
        manifests = result.get_files_by_category(FileCategory.PACKAGE_MANIFEST)

        # Check if tests exist
        if result.has_category(FileCategory.TEST_FILE):
            print("Repository has tests")

    Attributes:
        root_path: The repository root to scan
        max_files: Maximum number of files before warning (default 500)
        gitignore_patterns: Parsed patterns from .gitignore
    """

    # Default maximum file count before warning
    # Based on project scope: small to medium repositories (10-500 files)
    MAX_FILES_DEFAULT = 500

    def __init__(
        self,
        root_path: str | Path,
        max_files: int = MAX_FILES_DEFAULT,
        respect_gitignore: bool = True,
    ):
        """
        Initialize the file discovery.

        Args:
            root_path: Path to the repository root
            max_files: Maximum file count before issuing a warning
            respect_gitignore: Whether to parse and respect .gitignore
        """
        self.root_path = Path(root_path).resolve()
        self.max_files = max_files
        self.respect_gitignore = respect_gitignore
        self.gitignore_patterns: list[str] = []

        # Validate the root path exists
        if not self.root_path.exists():
            raise ValueError(f"Path does not exist: {self.root_path}")
        if not self.root_path.is_dir():
            raise ValueError(f"Path is not a directory: {self.root_path}")

    def _load_gitignore(self) -> list[str]:
        """
        Load and parse the .gitignore file from the repository root.

        Returns a list of patterns. Each pattern is a glob-style string.
        Comments (lines starting with #) and empty lines are skipped.

        Limitations:
            - Only reads root-level .gitignore
            - Does not handle negation patterns (!)
            - Simplified pattern matching compared to git

        Returns:
            List of gitignore patterns
        """
        gitignore_path = self.root_path / ".gitignore"
        patterns: list[str] = []

        if not gitignore_path.exists():
            return patterns

        try:
            with open(gitignore_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()

                    # Skip empty lines and comments
                    if not line or line.startswith("#"):
                        continue

                    # Skip negation patterns (not supported in this simple implementation)
                    if line.startswith("!"):
                        continue

                    patterns.append(line)

        except (IOError, UnicodeDecodeError) as e:
            # If we cannot read gitignore, just continue without it
            # This will be logged as a warning in the result
            pass

        return patterns

    def _should_ignore_path(self, path: Path, is_dir: bool = False) -> tuple[bool, str]:
        """
        Check if a path should be ignored based on default and gitignore patterns.

        Args:
            path: The path to check (relative to root)
            is_dir: Whether the path is a directory

        Returns:
            Tuple of (should_ignore, reason)
        """
        path_str = str(path)
        name = path.name

        # Check default ignore directories
        if is_dir and name in DEFAULT_IGNORE_DIRS:
            return True, f"Default ignore: {name}"

        # Check for hidden files/directories (starting with .)
        # except for important config files
        if name.startswith(".") and name not in {
            ".github",
            ".gitlab",
            ".gitignore",
            ".env.example",
            ".env.sample",
            ".env.template",
            ".eslintrc",
            ".eslintrc.js",
            ".eslintrc.json",
            ".prettierrc",
            ".prettierrc.js",
            ".prettierrc.json",
        }:
            # Skip most hidden files, but allow hidden config directories
            if is_dir and name not in {".github", ".gitlab", ".circleci"}:
                return True, f"Hidden directory: {name}"

        # Check gitignore patterns
        for pattern in self.gitignore_patterns:
            # Handle directory-specific patterns (ending with /)
            if pattern.endswith("/"):
                if is_dir and fnmatch.fnmatch(name, pattern.rstrip("/")):
                    return True, f"Gitignore pattern: {pattern}"
            else:
                # Check if pattern matches the file/directory name or path
                if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(path_str, pattern):
                    return True, f"Gitignore pattern: {pattern}"

                # Handle patterns with directory prefixes
                if "/" in pattern:
                    if fnmatch.fnmatch(path_str, pattern):
                        return True, f"Gitignore pattern: {pattern}"

        return False, ""

    def _categorize_file(self, relative_path: Path) -> tuple[FileCategory, str]:
        """
        Determine the category of a file based on its path and name.

        Uses the CATEGORIZATION_PATTERNS list to match files.
        First matching pattern wins.

        Args:
            relative_path: Path relative to repository root

        Returns:
            Tuple of (category, description)
        """
        path_str = str(relative_path)
        name = relative_path.name

        for pattern, category, description in CATEGORIZATION_PATTERNS:
            # Check if pattern matches the filename or the full relative path
            if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(path_str, pattern):
                return category, description

        # No pattern matched; file is uncategorized
        return FileCategory.OTHER, "Uncategorized file"

    def discover(self) -> DiscoveryResult:
        """
        Perform file discovery on the repository.

        Walks the directory tree, applies ignore patterns, categorizes files,
        and checks scope constraints.

        Returns:
            DiscoveryResult containing all discovered files and metadata
        """
        result = DiscoveryResult(root_path=self.root_path)

        # Load gitignore patterns if configured
        if self.respect_gitignore:
            self.gitignore_patterns = self._load_gitignore()

        # Walk the directory tree
        # Using os.walk instead of pathlib.rglob for better control over recursion
        for dirpath, dirnames, filenames in os.walk(self.root_path):
            current_dir = Path(dirpath)
            relative_dir = current_dir.relative_to(self.root_path)

            # Filter directories in-place to prevent walking into ignored dirs
            # Modifying dirnames in-place affects which subdirs os.walk visits
            dirs_to_remove = []
            for dirname in dirnames:
                dir_relative = relative_dir / dirname if str(relative_dir) != "." else Path(dirname)
                should_ignore, reason = self._should_ignore_path(dir_relative, is_dir=True)
                if should_ignore:
                    dirs_to_remove.append(dirname)
                    result.skipped_dirs.append((str(dir_relative), reason))

            for dirname in dirs_to_remove:
                dirnames.remove(dirname)

            # Process files in the current directory
            for filename in filenames:
                file_path = current_dir / filename
                file_relative = relative_dir / filename if str(relative_dir) != "." else Path(filename)

                # Check if file should be ignored
                should_ignore, reason = self._should_ignore_path(file_relative, is_dir=False)
                if should_ignore:
                    continue

                # Skip symlinks to avoid cycles and potential issues
                if file_path.is_symlink():
                    continue

                # Get file size (skip if we cannot access)
                try:
                    size_bytes = file_path.stat().st_size
                except OSError:
                    result.warnings.append(f"Could not access file: {file_relative}")
                    continue

                # Categorize the file
                category, category_note = self._categorize_file(file_relative)

                # Create the discovered file entry
                discovered = DiscoveredFile(
                    path=file_path,
                    relative_path=file_relative,
                    category=category,
                    size_bytes=size_bytes,
                    category_note=category_note,
                )
                result.files.append(discovered)
                result.total_file_count += 1

                # Check if we have exceeded the file limit
                if result.total_file_count > self.max_files and not result.exceeded_limit:
                    result.exceeded_limit = True
                    result.warnings.append(
                        f"Repository exceeds recommended size limit of {self.max_files} files. "
                        f"AutoDoc is designed for small to medium repositories. "
                        f"Results may be incomplete or take longer to process."
                    )

        # Add summary information
        if result.total_file_count == 0:
            result.warnings.append("No files discovered. The repository may be empty or fully ignored.")

        return result


def discover_files(
    path: str | Path,
    max_files: int = FileDiscovery.MAX_FILES_DEFAULT,
    respect_gitignore: bool = True,
) -> DiscoveryResult:
    """
    Convenience function to discover files in a repository.

    This is the main entry point for file discovery.

    Args:
        path: Path to the repository root
        max_files: Maximum file count before issuing a warning (default 500)
        respect_gitignore: Whether to parse and respect .gitignore (default True)

    Returns:
        DiscoveryResult containing all discovered files and metadata

    Example:
        result = discover_files("/path/to/my/project")

        # Check if the repository has a license
        if result.has_category(FileCategory.LICENSE):
            license_files = result.get_files_by_category(FileCategory.LICENSE)
            print(f"Found license: {license_files[0].relative_path}")

        # Get all Python source files
        python_files = result.get_files_by_category(FileCategory.SOURCE_CODE)
        python_files = [f for f in python_files if f.path.suffix == ".py"]

        # Check for warnings
        for warning in result.warnings:
            print(f"Warning: {warning}")
    """
    discovery = FileDiscovery(
        root_path=path,
        max_files=max_files,
        respect_gitignore=respect_gitignore,
    )
    return discovery.discover()
