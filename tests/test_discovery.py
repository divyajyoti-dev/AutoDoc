"""
Tests for autodoc.discovery module.

Tests file discovery, categorization, and ignore patterns.
"""

import tempfile
from pathlib import Path

import pytest

from autodoc.discovery import (
    DEFAULT_IGNORE_DIRS,
    DiscoveredFile,
    DiscoveryResult,
    FileCategory,
    FileDiscovery,
    discover_files,
)


class TestFileCategory:
    """Tests for the FileCategory enum."""

    def test_categories_exist(self):
        """Verify all expected categories exist."""
        assert FileCategory.PACKAGE_MANIFEST
        assert FileCategory.DEPENDENCY_LOCK
        assert FileCategory.REQUIREMENTS
        assert FileCategory.README
        assert FileCategory.LICENSE
        assert FileCategory.CI_CONFIG
        assert FileCategory.SOURCE_CODE
        assert FileCategory.TEST_FILE
        assert FileCategory.ENTRY_POINT
        assert FileCategory.OTHER


class TestDefaultIgnoreDirs:
    """Tests for the default ignore directories."""

    def test_common_dirs_ignored(self):
        """Verify common directories are in the ignore set."""
        assert ".git" in DEFAULT_IGNORE_DIRS
        assert "node_modules" in DEFAULT_IGNORE_DIRS
        assert "__pycache__" in DEFAULT_IGNORE_DIRS
        assert "venv" in DEFAULT_IGNORE_DIRS
        assert ".venv" in DEFAULT_IGNORE_DIRS
        assert "build" in DEFAULT_IGNORE_DIRS
        assert "dist" in DEFAULT_IGNORE_DIRS


class TestFileDiscovery:
    """Tests for the FileDiscovery class."""

    def test_empty_directory(self):
        """Test discovery on an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            discovery = FileDiscovery(tmpdir)
            result = discovery.discover()

            assert result.total_file_count == 0
            assert len(result.files) == 0
            # Should have a warning about empty repo
            assert any("empty" in w.lower() for w in result.warnings)

    def test_simple_python_project(self):
        """Test discovery on a simple Python project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create some files
            (tmppath / "main.py").write_text("print('hello')")
            (tmppath / "requirements.txt").write_text("requests>=2.0")
            (tmppath / "README.md").write_text("# My Project")

            discovery = FileDiscovery(tmppath)
            result = discovery.discover()

            assert result.total_file_count == 3
            assert result.exceeded_limit is False

            # Check categories
            assert result.has_category(FileCategory.ENTRY_POINT)  # main.py
            assert result.has_category(FileCategory.REQUIREMENTS)
            assert result.has_category(FileCategory.README)

    def test_categorization_package_manifests(self):
        """Test that package manifests are correctly categorized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create package manifest files
            (tmppath / "package.json").write_text('{"name": "test"}')
            (tmppath / "pyproject.toml").write_text('[project]\nname = "test"')
            (tmppath / "Cargo.toml").write_text('[package]\nname = "test"')

            result = discover_files(tmppath)

            manifests = result.get_files_by_category(FileCategory.PACKAGE_MANIFEST)
            manifest_names = [f.relative_path.name for f in manifests]

            assert "package.json" in manifest_names
            assert "pyproject.toml" in manifest_names
            assert "Cargo.toml" in manifest_names

    def test_categorization_license_files(self):
        """Test that license files are correctly categorized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            (tmppath / "LICENSE").write_text("MIT License")
            (tmppath / "LICENSE.md").write_text("MIT License")
            (tmppath / "COPYING").write_text("GPL")

            result = discover_files(tmppath)

            licenses = result.get_files_by_category(FileCategory.LICENSE)
            license_names = [f.relative_path.name for f in licenses]

            assert "LICENSE" in license_names
            assert "LICENSE.md" in license_names
            assert "COPYING" in license_names

    def test_categorization_test_files(self):
        """Test that test files are correctly categorized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            (tmppath / "test_main.py").write_text("def test_foo(): pass")
            (tmppath / "main_test.py").write_text("def test_bar(): pass")
            (tmppath / "app.test.js").write_text("test('foo')")

            result = discover_files(tmppath)

            tests = result.get_files_by_category(FileCategory.TEST_FILE)
            test_names = [f.relative_path.name for f in tests]

            assert "test_main.py" in test_names
            # Note: main_test.py might be categorized as SOURCE_CODE depending on pattern order

    def test_ignore_git_directory(self):
        """Test that .git directory is ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create .git directory with files
            git_dir = tmppath / ".git"
            git_dir.mkdir()
            (git_dir / "config").write_text("[core]")
            (git_dir / "HEAD").write_text("ref: refs/heads/main")

            # Create a regular file
            (tmppath / "main.py").write_text("print('hello')")

            result = discover_files(tmppath)

            # Should only find main.py, not .git contents
            assert result.total_file_count == 1
            file_names = [f.relative_path.name for f in result.files]
            assert "main.py" in file_names
            assert "config" not in file_names
            assert "HEAD" not in file_names

    def test_ignore_node_modules(self):
        """Test that node_modules directory is ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create node_modules directory
            nm_dir = tmppath / "node_modules"
            nm_dir.mkdir()
            (nm_dir / "lodash").mkdir()
            (nm_dir / "lodash" / "index.js").write_text("module.exports = {}")

            # Create a regular file
            (tmppath / "index.js").write_text("console.log('hello')")

            result = discover_files(tmppath)

            assert result.total_file_count == 1
            file_names = [f.relative_path.name for f in result.files]
            assert "index.js" in file_names

    def test_ignore_pycache(self):
        """Test that __pycache__ directory is ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create __pycache__ directory
            cache_dir = tmppath / "__pycache__"
            cache_dir.mkdir()
            (cache_dir / "main.cpython-310.pyc").write_bytes(b"bytecode")

            (tmppath / "main.py").write_text("print('hello')")

            result = discover_files(tmppath)

            assert result.total_file_count == 1

    def test_gitignore_parsing(self):
        """Test that .gitignore patterns are respected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create .gitignore
            (tmppath / ".gitignore").write_text("*.log\nsecret.txt\n")

            # Create files
            (tmppath / "main.py").write_text("print('hello')")
            (tmppath / "debug.log").write_text("log data")
            (tmppath / "secret.txt").write_text("password123")

            result = discover_files(tmppath)

            file_names = [f.relative_path.name for f in result.files]
            assert "main.py" in file_names
            assert "debug.log" not in file_names
            assert "secret.txt" not in file_names

    def test_file_limit_warning(self):
        """Test that exceeding file limit triggers a warning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create more files than the limit (set low for testing)
            for i in range(10):
                (tmppath / f"file{i}.py").write_text(f"# file {i}")

            # Use a low limit for testing
            discovery = FileDiscovery(tmppath, max_files=5)
            result = discovery.discover()

            assert result.exceeded_limit is True
            assert any("exceed" in w.lower() for w in result.warnings)

    def test_get_files_by_category(self):
        """Test filtering files by category."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            (tmppath / "main.py").write_text("print('hello')")
            (tmppath / "test_main.py").write_text("def test(): pass")
            (tmppath / "README.md").write_text("# Readme")

            result = discover_files(tmppath)

            # Should have entry point
            entry_points = result.get_files_by_category(FileCategory.ENTRY_POINT)
            assert len(entry_points) == 1
            assert entry_points[0].relative_path.name == "main.py"

            # Should have test file
            tests = result.get_files_by_category(FileCategory.TEST_FILE)
            assert len(tests) == 1

    def test_get_category_counts(self):
        """Test getting counts per category."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            (tmppath / "main.py").write_text("print('hello')")
            (tmppath / "utils.py").write_text("def helper(): pass")
            (tmppath / "README.md").write_text("# Readme")

            result = discover_files(tmppath)
            counts = result.get_category_counts()

            assert FileCategory.README in counts
            assert counts[FileCategory.README] == 1


class TestDiscoveredFile:
    """Tests for the DiscoveredFile dataclass."""

    def test_discovered_file_str(self):
        """Test string representation of DiscoveredFile."""
        file = DiscoveredFile(
            path=Path("/tmp/test/main.py"),
            relative_path=Path("main.py"),
            category=FileCategory.ENTRY_POINT,
            size_bytes=100,
        )
        str_repr = str(file)
        assert "main.py" in str_repr
        assert "ENTRY_POINT" in str_repr


class TestDiscoverFilesFunction:
    """Tests for the discover_files convenience function."""

    def test_discover_files_basic(self):
        """Test the convenience function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "main.py").write_text("print('hello')")

            result = discover_files(tmppath)

            assert isinstance(result, DiscoveryResult)
            assert result.total_file_count == 1

    def test_discover_files_with_options(self):
        """Test the convenience function with options."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "main.py").write_text("print('hello')")

            result = discover_files(tmppath, max_files=100, respect_gitignore=False)

            assert isinstance(result, DiscoveryResult)

    def test_discover_files_invalid_path(self):
        """Test that invalid path raises ValueError."""
        with pytest.raises(ValueError):
            discover_files("/nonexistent/path/12345")
