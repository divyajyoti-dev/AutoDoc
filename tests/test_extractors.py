"""
Tests for autodoc.extractors module.

Tests the extractor framework and Python extractor.
"""

import tempfile
from pathlib import Path

import pytest

from autodoc.discovery import discover_files
from autodoc.extractors import ExtractorRegistry, GenericExtractor, PythonExtractor
from autodoc.schema import Confidence, ProjectMetadata


class TestExtractorRegistry:
    """Tests for the ExtractorRegistry class."""

    def test_empty_registry(self):
        """Test registry with no extractors."""
        registry = ExtractorRegistry()
        assert len(registry.get_extractors()) == 0

    def test_register_extractor(self):
        """Test registering an extractor."""
        registry = ExtractorRegistry()
        registry.register(PythonExtractor())

        assert len(registry.get_extractors()) == 1

    def test_get_applicable_extractors(self):
        """Test finding applicable extractors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "main.py").write_text("print('hello')")

            discovery = discover_files(tmppath)
            registry = ExtractorRegistry()
            registry.register(PythonExtractor())

            applicable = registry.get_applicable_extractors(discovery)
            assert len(applicable) == 1
            assert isinstance(applicable[0], PythonExtractor)

    def test_extract_all_merges_results(self):
        """Test that extract_all merges results from multiple extractors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create pyproject.toml
            (tmppath / "pyproject.toml").write_text("""
[project]
name = "test-project"
version = "1.0.0"
description = "A test project"
""")
            (tmppath / "main.py").write_text("print('hello')")

            discovery = discover_files(tmppath)
            registry = ExtractorRegistry()
            registry.register(GenericExtractor())
            registry.register(PythonExtractor())

            metadata = registry.extract_all(discovery, tmppath)

            # Python extractor should have higher confidence for name
            assert metadata.name.value == "test-project"
            assert metadata.name.confidence == Confidence.EXPLICIT


class TestPythonExtractor:
    """Tests for the PythonExtractor class."""

    def test_can_handle_python_project(self):
        """Test that Python extractor handles Python projects."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "pyproject.toml").write_text('[project]\nname = "test"')

            discovery = discover_files(tmppath)
            extractor = PythonExtractor()

            assert extractor.can_handle(discovery) is True

    def test_can_handle_non_python_project(self):
        """Test handling of non-Python projects."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "index.js").write_text("console.log('hello')")
            (tmppath / "package.json").write_text('{"name": "test"}')

            discovery = discover_files(tmppath)
            extractor = PythonExtractor()

            # Should return False since no Python files
            assert extractor.can_handle(discovery) is False

    def test_extract_pyproject_pep621(self):
        """Test extraction from PEP 621 pyproject.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "pyproject.toml").write_text("""
[project]
name = "my-package"
version = "2.0.0"
description = "A great package"
license = {text = "MIT"}
requires-python = ">=3.9"
authors = [
    {name = "Alice", email = "alice@example.com"}
]
dependencies = [
    "requests>=2.0.0",
    "click>=8.0.0",
]

[project.scripts]
myapp = "mypackage.cli:main"

[project.urls]
Homepage = "https://example.com"
Repository = "https://github.com/example/repo"
""")
            (tmppath / "main.py").write_text("print('hello')")

            discovery = discover_files(tmppath)
            extractor = PythonExtractor()
            metadata = extractor.extract(discovery, tmppath)

            assert metadata.name.value == "my-package"
            assert metadata.name.confidence == Confidence.EXPLICIT
            assert metadata.version.value == "2.0.0"
            assert metadata.description.value == "A great package"
            assert metadata.license.value == "MIT"
            assert metadata.python_version.value == ">=3.9"

            # Check authors
            assert len(metadata.authors) == 1
            assert metadata.authors[0].name == "Alice"
            assert metadata.authors[0].email == "alice@example.com"

            # Check dependencies
            assert len(metadata.dependencies) == 2
            dep_names = [d.name for d in metadata.dependencies]
            assert "requests" in dep_names
            assert "click" in dep_names

            # Check entry points
            assert len(metadata.entry_points) >= 1
            commands = [e.command for e in metadata.entry_points if e.command]
            assert "myapp" in commands

            # Check URLs
            assert metadata.homepage_url.value == "https://example.com"
            assert metadata.repository_url.value == "https://github.com/example/repo"

    def test_extract_requirements_txt(self):
        """Test extraction from requirements.txt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "requirements.txt").write_text("""
requests>=2.28.0
click==8.1.0
# Comment line
pydantic[email]>=2.0

-r other-requirements.txt
""")
            (tmppath / "main.py").write_text("print('hello')")

            discovery = discover_files(tmppath)
            extractor = PythonExtractor()
            metadata = extractor.extract(discovery, tmppath)

            dep_names = [d.name for d in metadata.dependencies]
            assert "requests" in dep_names
            assert "click" in dep_names
            assert "pydantic" in dep_names

    def test_extract_requirements_dev(self):
        """Test extraction from requirements-dev.txt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "requirements.txt").write_text("requests>=2.0")
            (tmppath / "requirements-dev.txt").write_text("""
pytest>=7.0.0
black>=23.0.0
""")
            (tmppath / "main.py").write_text("print('hello')")

            discovery = discover_files(tmppath)
            extractor = PythonExtractor()
            metadata = extractor.extract(discovery, tmppath)

            # Dev dependencies should be separate
            dev_names = [d.name for d in metadata.dev_dependencies]
            assert "pytest" in dev_names
            assert "black" in dev_names

            # Regular dependencies
            reg_names = [d.name for d in metadata.dependencies]
            assert "requests" in reg_names

    def test_detect_entry_points(self):
        """Test entry point detection from filename patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "main.py").write_text("if __name__ == '__main__': pass")
            (tmppath / "cli.py").write_text("import click")

            discovery = discover_files(tmppath)
            extractor = PythonExtractor()
            metadata = extractor.extract(discovery, tmppath)

            entry_paths = [e.path for e in metadata.entry_points]
            assert any("main.py" in p for p in entry_paths)


class TestGenericExtractor:
    """Tests for the GenericExtractor class."""

    def test_can_handle_any_project(self):
        """Test that generic extractor handles any project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "something.txt").write_text("content")

            discovery = discover_files(tmppath)
            extractor = GenericExtractor()

            assert extractor.can_handle(discovery) is True

    def test_extract_project_name_from_dir(self):
        """Test project name extraction from directory name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file.txt").write_text("content")

            discovery = discover_files(tmppath)
            extractor = GenericExtractor()
            metadata = extractor.extract(discovery, tmppath)

            # Should use directory name
            assert metadata.name.value is not None
            assert metadata.name.confidence == Confidence.WEAK

    def test_extract_license_mit(self):
        """Test MIT license detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "LICENSE").write_text("""
MIT License

Copyright (c) 2024 Example

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software...
""")
            (tmppath / "main.py").write_text("print('hello')")

            discovery = discover_files(tmppath)
            extractor = GenericExtractor()
            metadata = extractor.extract(discovery, tmppath)

            assert metadata.license.value == "MIT"
            assert metadata.license.confidence == Confidence.STRONG

    def test_extract_license_apache(self):
        """Test Apache 2.0 license detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "LICENSE").write_text("""
                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/
""")
            (tmppath / "main.py").write_text("print('hello')")

            discovery = discover_files(tmppath)
            extractor = GenericExtractor()
            metadata = extractor.extract(discovery, tmppath)

            assert metadata.license.value == "Apache-2.0"

    def test_detect_primary_language(self):
        """Test primary language detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            # Create more Python files than other types
            (tmppath / "main.py").write_text("print('hello')")
            (tmppath / "utils.py").write_text("def helper(): pass")
            (tmppath / "models.py").write_text("class Model: pass")
            (tmppath / "script.sh").write_text("echo hello")

            discovery = discover_files(tmppath)
            extractor = GenericExtractor()
            metadata = extractor.extract(discovery, tmppath)

            assert metadata.primary_language.value == "Python"

    def test_detect_docs_folder(self):
        """Test documentation folder detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            docs_dir = tmppath / "docs"
            docs_dir.mkdir()
            (docs_dir / "index.md").write_text("# Docs")
            (tmppath / "main.py").write_text("print('hello')")

            discovery = discover_files(tmppath)
            extractor = GenericExtractor()
            metadata = extractor.extract(discovery, tmppath)

            assert metadata.has_docs_folder is True

    def test_detect_tests(self):
        """Test test file detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "test_main.py").write_text("def test_foo(): pass")
            (tmppath / "main.py").write_text("print('hello')")

            discovery = discover_files(tmppath)
            extractor = GenericExtractor()
            metadata = extractor.extract(discovery, tmppath)

            assert metadata.has_tests is True
