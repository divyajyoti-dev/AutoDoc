"""
Tests for autodoc.renderer module.

Tests README generation from ProjectMetadata.
"""

import pytest

from autodoc.renderer import ReadmeRenderer, RenderOptions, render_readme
from autodoc.schema import (
    Author,
    Confidence,
    Dependency,
    EntryPoint,
    MetadataField,
    ProjectMetadata,
)


class TestRenderOptions:
    """Tests for the RenderOptions dataclass."""

    def test_default_options(self):
        """Test default render options."""
        options = RenderOptions()

        assert options.include_provenance is False
        assert options.include_toc is False
        assert options.include_badges is False
        assert options.include_generation_notice is True
        assert options.confidence_threshold == 0.6

    def test_custom_options(self):
        """Test custom render options."""
        options = RenderOptions(
            include_badges=True,
            include_toc=True,
            include_provenance=True,
        )

        assert options.include_badges is True
        assert options.include_toc is True
        assert options.include_provenance is True


class TestReadmeRenderer:
    """Tests for the ReadmeRenderer class."""

    def test_render_basic_metadata(self):
        """Test rendering basic project metadata."""
        metadata = ProjectMetadata()
        metadata.name = MetadataField(
            value="my-project",
            confidence=Confidence.EXPLICIT,
        )
        metadata.description = MetadataField(
            value="A great project",
            confidence=Confidence.EXPLICIT,
        )

        renderer = ReadmeRenderer(metadata)
        output = renderer.render()

        assert "# my-project" in output
        assert "A great project" in output

    def test_render_with_placeholder_name(self):
        """Test rendering with missing project name."""
        metadata = ProjectMetadata()
        # name is placeholder by default

        renderer = ReadmeRenderer(metadata)
        output = renderer.render()

        assert "# Project Name" in output
        assert "TODO" in output

    def test_render_installation_section(self):
        """Test rendering installation section."""
        metadata = ProjectMetadata()
        metadata.name = MetadataField(
            value="mypackage",
            confidence=Confidence.EXPLICIT,
        )
        metadata.python_version = MetadataField(
            value=">=3.9",
            confidence=Confidence.EXPLICIT,
        )
        metadata.repository_url = MetadataField(
            value="https://github.com/example/mypackage",
            confidence=Confidence.EXPLICIT,
        )

        renderer = ReadmeRenderer(metadata)
        output = renderer.render()

        assert "## Installation" in output
        assert "pip install" in output
        assert ">=3.9" in output
        assert "github.com/example/mypackage" in output

    def test_render_usage_with_cli_entry_points(self):
        """Test rendering usage section with CLI entry points."""
        metadata = ProjectMetadata()
        metadata.name = MetadataField(
            value="myapp",
            confidence=Confidence.EXPLICIT,
        )
        metadata.entry_points.append(
            EntryPoint(
                path="myapp.cli:main",
                entry_type="cli",
                command="myapp",
                confidence=Confidence.EXPLICIT,
            )
        )

        renderer = ReadmeRenderer(metadata)
        output = renderer.render()

        assert "## Usage" in output
        assert "Command Line" in output
        assert "myapp --help" in output

    def test_render_usage_without_entry_points(self):
        """Test rendering usage section without entry points."""
        metadata = ProjectMetadata()
        metadata.name = MetadataField(
            value="mylib",
            confidence=Confidence.EXPLICIT,
        )
        # No entry points

        renderer = ReadmeRenderer(metadata)
        output = renderer.render()

        assert "## Usage" in output
        assert "TODO" in output  # Should have placeholder

    def test_render_dependencies_section(self):
        """Test rendering dependencies section."""
        metadata = ProjectMetadata()
        metadata.name = MetadataField(
            value="mypackage",
            confidence=Confidence.EXPLICIT,
        )
        metadata.dependencies.append(
            Dependency(name="requests", version_constraint=">=2.28.0")
        )
        metadata.dependencies.append(
            Dependency(name="click", version_constraint=">=8.0.0")
        )
        metadata.dev_dependencies.append(
            Dependency(name="pytest", version_constraint=">=7.0.0")
        )

        renderer = ReadmeRenderer(metadata)
        output = renderer.render()

        assert "## Dependencies" in output
        assert "Runtime Dependencies" in output
        assert "Development Dependencies" in output
        assert "requests" in output
        assert ">=2.28.0" in output
        assert "pytest" in output

    def test_render_no_dependencies_section_when_empty(self):
        """Test that dependencies section is omitted when empty."""
        metadata = ProjectMetadata()
        metadata.name = MetadataField(
            value="mypackage",
            confidence=Confidence.EXPLICIT,
        )
        # No dependencies

        renderer = ReadmeRenderer(metadata)
        output = renderer.render()

        # Dependencies section should not appear
        assert "Runtime Dependencies" not in output

    def test_render_license_section(self):
        """Test rendering license section."""
        metadata = ProjectMetadata()
        metadata.name = MetadataField(
            value="mypackage",
            confidence=Confidence.EXPLICIT,
        )
        metadata.license = MetadataField(
            value="MIT",
            confidence=Confidence.EXPLICIT,
        )

        renderer = ReadmeRenderer(metadata)
        output = renderer.render()

        assert "## License" in output
        assert "MIT" in output

    def test_render_license_placeholder(self):
        """Test rendering license placeholder when missing."""
        metadata = ProjectMetadata()
        metadata.name = MetadataField(
            value="mypackage",
            confidence=Confidence.EXPLICIT,
        )
        # license is placeholder by default

        renderer = ReadmeRenderer(metadata)
        output = renderer.render()

        assert "## License" in output
        assert "TODO" in output

    def test_render_authors_section(self):
        """Test rendering authors section."""
        metadata = ProjectMetadata()
        metadata.name = MetadataField(
            value="mypackage",
            confidence=Confidence.EXPLICIT,
        )
        metadata.authors.append(
            Author(name="Alice Smith", email="alice@example.com")
        )
        metadata.authors.append(
            Author(name="Bob Jones", role="maintainer")
        )

        renderer = ReadmeRenderer(metadata)
        output = renderer.render()

        assert "## Authors" in output
        assert "Alice Smith" in output
        assert "alice@example.com" in output
        assert "Bob Jones" in output
        assert "maintainer" in output

    def test_render_with_badges(self):
        """Test rendering with badges enabled."""
        metadata = ProjectMetadata()
        metadata.name = MetadataField(
            value="mypackage",
            confidence=Confidence.EXPLICIT,
        )
        metadata.license = MetadataField(
            value="MIT",
            confidence=Confidence.EXPLICIT,
        )
        metadata.python_version = MetadataField(
            value=">=3.9",
            confidence=Confidence.EXPLICIT,
        )

        options = RenderOptions(include_badges=True)
        renderer = ReadmeRenderer(metadata, options)
        output = renderer.render()

        assert "img.shields.io" in output
        assert "MIT" in output

    def test_render_with_toc(self):
        """Test rendering with table of contents."""
        metadata = ProjectMetadata()
        metadata.name = MetadataField(
            value="mypackage",
            confidence=Confidence.EXPLICIT,
        )

        options = RenderOptions(include_toc=True)
        renderer = ReadmeRenderer(metadata, options)
        output = renderer.render()

        assert "## Table of Contents" in output
        assert "[Installation]" in output
        assert "[Usage]" in output

    def test_render_with_provenance(self):
        """Test rendering with provenance comments."""
        metadata = ProjectMetadata()
        metadata.name = MetadataField(
            value="mypackage",
            confidence=Confidence.EXPLICIT,
            source="pyproject.toml",
        )

        options = RenderOptions(include_provenance=True)
        renderer = ReadmeRenderer(metadata, options)
        output = renderer.render()

        assert "<!-- Source:" in output
        assert "pyproject.toml" in output

    def test_render_without_generation_notice(self):
        """Test rendering without generation notice."""
        metadata = ProjectMetadata()
        metadata.name = MetadataField(
            value="mypackage",
            confidence=Confidence.EXPLICIT,
        )

        options = RenderOptions(include_generation_notice=False)
        renderer = ReadmeRenderer(metadata, options)
        output = renderer.render()

        assert "automatically generated" not in output.lower()

    def test_render_with_generation_notice(self):
        """Test rendering with generation notice (default)."""
        metadata = ProjectMetadata()
        metadata.name = MetadataField(
            value="mypackage",
            confidence=Confidence.EXPLICIT,
        )

        renderer = ReadmeRenderer(metadata)
        output = renderer.render()

        assert "automatically generated" in output.lower()
        assert "review" in output.lower()

    def test_render_low_confidence_marker(self):
        """Test that low-confidence fields get review markers."""
        metadata = ProjectMetadata()
        metadata.name = MetadataField(
            value="mypackage",
            confidence=Confidence.WEAK,  # Below threshold
            source="directory name",
        )

        renderer = ReadmeRenderer(metadata)
        output = renderer.render()

        assert "Review suggested" in output


class TestRenderReadmeFunction:
    """Tests for the render_readme convenience function."""

    def test_render_readme_basic(self):
        """Test the convenience function."""
        metadata = ProjectMetadata()
        metadata.name = MetadataField(
            value="test-project",
            confidence=Confidence.EXPLICIT,
        )

        output = render_readme(metadata)

        assert isinstance(output, str)
        assert "# test-project" in output

    def test_render_readme_with_options(self):
        """Test the convenience function with options."""
        metadata = ProjectMetadata()
        metadata.name = MetadataField(
            value="test-project",
            confidence=Confidence.EXPLICIT,
        )

        options = RenderOptions(include_badges=True)
        output = render_readme(metadata, options)

        assert "img.shields.io" in output or "TODO" in output
