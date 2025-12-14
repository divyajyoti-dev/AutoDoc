"""
Tests for autodoc.api module.

Tests the Flask REST API endpoints for README generation.
"""

import io
import json
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from autodoc.api import (
    app,
    create_app,
    create_extractor_registry,
    extract_zip,
    find_project_root,
    metadata_to_dict,
)
from autodoc.schema import Confidence, MetadataField, ProjectMetadata


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def sample_zip():
    """Create a sample zip file with a Python project."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add pyproject.toml
        zf.writestr(
            "pyproject.toml",
            """[project]
name = "test-project"
version = "1.0.0"
description = "A test project"
license = {text = "MIT"}
""",
        )
        # Add a Python file
        zf.writestr("main.py", "print('hello')")
        # Add a README (to show it's replaced)
        zf.writestr("README.md", "# Old README")

    zip_buffer.seek(0)
    return zip_buffer


@pytest.fixture
def nested_zip():
    """Create a zip file with a nested directory structure."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Simulate GitHub-style zip with top-level directory
        zf.writestr("repo-main/pyproject.toml", '[project]\nname = "nested-project"')
        zf.writestr("repo-main/main.py", "print('nested')")

    zip_buffer.seek(0)
    return zip_buffer


class TestIndexEndpoint:
    """Tests for the web interface index page."""

    def test_index_page(self, client):
        """Test index page returns HTML."""
        response = client.get("/")

        assert response.status_code == 200
        assert b"AutoDoc" in response.data
        assert b"README Generator" in response.data

    def test_index_contains_form(self, client):
        """Test index page contains the upload form."""
        response = client.get("/")

        assert b"github_url" in response.data.lower() or b"githuburl" in response.data.lower()
        assert b"file" in response.data.lower()


class TestHealthEndpoint:
    """Tests for the /api/health endpoint."""

    def test_health_check(self, client):
        """Test health check returns healthy status."""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "healthy"
        assert "version" in data


class TestGenerateEndpoint:
    """Tests for the /api/generate endpoint."""

    def test_generate_from_zip(self, client, sample_zip):
        """Test README generation from uploaded zip."""
        response = client.post(
            "/api/generate",
            data={"file": (sample_zip, "project.zip")},
            content_type="multipart/form-data",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "readme" in data
        assert "metadata" in data
        assert "# test-project" in data["readme"]

    def test_generate_from_nested_zip(self, client, nested_zip):
        """Test README generation from zip with nested directory."""
        response = client.post(
            "/api/generate",
            data={"file": (nested_zip, "repo.zip")},
            content_type="multipart/form-data",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "nested-project" in data["readme"]

    def test_generate_with_badges(self, client, sample_zip):
        """Test README generation with badges enabled."""
        response = client.post(
            "/api/generate?include_badges=true",
            data={"file": (sample_zip, "project.zip")},
            content_type="multipart/form-data",
        )

        assert response.status_code == 200
        data = response.get_json()
        # Badges should be in the output
        assert "img.shields.io" in data["readme"] or "MIT" in data["readme"]

    def test_generate_with_toc(self, client, sample_zip):
        """Test README generation with table of contents."""
        response = client.post(
            "/api/generate?include_toc=true",
            data={"file": (sample_zip, "project.zip")},
            content_type="multipart/form-data",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "Table of Contents" in data["readme"]

    def test_generate_markdown_only(self, client, sample_zip):
        """Test README generation returning only markdown."""
        response = client.post(
            "/api/generate?format=markdown",
            data={"file": (sample_zip, "project.zip")},
            content_type="multipart/form-data",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "readme" in data
        assert "metadata" not in data

    def test_generate_json_only(self, client, sample_zip):
        """Test README generation returning only metadata."""
        response = client.post(
            "/api/generate?format=json",
            data={"file": (sample_zip, "project.zip")},
            content_type="multipart/form-data",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "metadata" in data
        assert "readme" not in data

    def test_generate_json_request(self, client, sample_zip):
        """Test README generation with JSON request body."""
        # First we need to simulate a GitHub URL - we'll mock the clone
        with patch("autodoc.api.clone_github_repo") as mock_clone:
            # Setup mock to create files in the target dir
            def create_files(url, target_dir):
                (target_dir / "pyproject.toml").write_text('[project]\nname = "from-github"')
                (target_dir / "main.py").write_text("print('github')")

            mock_clone.side_effect = create_files

            response = client.post(
                "/api/generate",
                json={
                    "github_url": "https://github.com/example/repo",
                    "include_badges": True,
                    "format": "both",
                },
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert "from-github" in data["readme"]

    def test_generate_no_input(self, client):
        """Test error when no file or URL provided."""
        response = client.post("/api/generate")

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_generate_invalid_file_type(self, client):
        """Test error when non-zip file uploaded."""
        response = client.post(
            "/api/generate",
            data={"file": (io.BytesIO(b"not a zip"), "project.txt")},
            content_type="multipart/form-data",
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "zip" in data["error"].lower()

    def test_generate_corrupted_zip(self, client):
        """Test error when corrupted zip uploaded."""
        response = client.post(
            "/api/generate",
            data={"file": (io.BytesIO(b"not a zip"), "project.zip")},
            content_type="multipart/form-data",
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data


class TestMetadataEndpoint:
    """Tests for the /api/metadata endpoint."""

    def test_metadata_from_zip(self, client, sample_zip):
        """Test metadata extraction from uploaded zip."""
        response = client.post(
            "/api/metadata",
            data={"file": (sample_zip, "project.zip")},
            content_type="multipart/form-data",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "metadata" in data

        # Check metadata structure
        metadata = data["metadata"]
        assert "name" in metadata
        assert metadata["name"]["value"] == "test-project"
        assert metadata["name"]["confidence"] == "EXPLICIT"


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_create_extractor_registry(self):
        """Test extractor registry creation."""
        registry = create_extractor_registry()
        extractors = registry.get_extractors()

        assert len(extractors) >= 2  # At least GenericExtractor and PythonExtractor

    def test_metadata_to_dict(self):
        """Test metadata conversion to dictionary."""
        metadata = ProjectMetadata()
        metadata.name = MetadataField(
            value="test-project",
            confidence=Confidence.EXPLICIT,
            source="pyproject.toml",
        )

        result = metadata_to_dict(metadata)

        assert result["name"]["value"] == "test-project"
        assert result["name"]["confidence"] == "EXPLICIT"
        assert result["name"]["confidence_score"] == 1.0
        assert result["name"]["source"] == "pyproject.toml"
        assert result["name"]["is_placeholder"] is False

    def test_extract_zip_valid(self):
        """Test extracting a valid zip file."""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("test.txt", "content")
        zip_buffer.seek(0)

        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            extract_zip(zip_buffer, target)

            assert (target / "test.txt").exists()
            assert (target / "test.txt").read_text() == "content"

    def test_extract_zip_path_traversal(self):
        """Test that path traversal is prevented."""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            # Attempt to write outside the target directory
            zf.writestr("../../../etc/passwd", "malicious")
        zip_buffer.seek(0)

        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            with pytest.raises(ValueError, match="Invalid path"):
                extract_zip(zip_buffer, target)

    def test_find_project_root_flat(self):
        """Test finding project root in flat structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "main.py").write_text("print('hello')")
            (tmppath / "README.md").write_text("# Test")

            root = find_project_root(tmppath)
            assert root == tmppath

    def test_find_project_root_nested(self):
        """Test finding project root in nested structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            nested = tmppath / "repo-main"
            nested.mkdir()
            (nested / "main.py").write_text("print('hello')")

            root = find_project_root(tmppath)
            assert root == nested

    def test_create_app(self):
        """Test application factory."""
        flask_app = create_app()
        assert flask_app is not None
        assert flask_app.name == "autodoc.api"


class TestErrorHandling:
    """Tests for error handling."""

    def test_404_not_found(self, client):
        """Test 404 for unknown endpoints."""
        response = client.get("/api/unknown")
        assert response.status_code == 404

    def test_method_not_allowed(self, client):
        """Test 405 for wrong HTTP method."""
        response = client.get("/api/generate")
        assert response.status_code == 405
