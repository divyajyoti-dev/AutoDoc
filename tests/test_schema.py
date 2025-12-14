"""
Tests for autodoc.schema module.

Tests the core data structures: Confidence, MetadataField, ProjectMetadata.
"""

import pytest

from autodoc.schema import (
    Author,
    Confidence,
    Dependency,
    EntryPoint,
    MetadataField,
    ProjectMetadata,
)


class TestConfidence:
    """Tests for the Confidence enum."""

    def test_confidence_values(self):
        """Verify confidence levels have correct numeric values."""
        assert Confidence.EXPLICIT.value == 1.0
        assert Confidence.STRONG.value == 0.8
        assert Confidence.REASONABLE.value == 0.6
        assert Confidence.WEAK.value == 0.4
        assert Confidence.GUESS.value == 0.2
        assert Confidence.UNKNOWN.value == 0.0

    def test_confidence_ordering(self):
        """Verify confidence levels are properly ordered."""
        assert Confidence.EXPLICIT.value > Confidence.STRONG.value
        assert Confidence.STRONG.value > Confidence.REASONABLE.value
        assert Confidence.REASONABLE.value > Confidence.WEAK.value
        assert Confidence.WEAK.value > Confidence.GUESS.value
        assert Confidence.GUESS.value > Confidence.UNKNOWN.value

    def test_confidence_to_float(self):
        """Verify confidence can be converted to float."""
        assert float(Confidence.EXPLICIT) == 1.0
        assert float(Confidence.UNKNOWN) == 0.0

    def test_confidence_to_string(self):
        """Verify confidence string representation."""
        assert str(Confidence.EXPLICIT) == "explicit"
        assert str(Confidence.UNKNOWN) == "unknown"


class TestMetadataField:
    """Tests for the MetadataField dataclass."""

    def test_field_with_value(self):
        """Test creating a field with a value."""
        field = MetadataField(
            value="test-project",
            confidence=Confidence.EXPLICIT,
            source="package.json",
        )
        assert field.value == "test-project"
        assert field.confidence == Confidence.EXPLICIT
        assert field.source == "package.json"
        assert field.note is None

    def test_field_is_placeholder(self):
        """Test placeholder detection."""
        # Field with no value is a placeholder
        field_none = MetadataField(value=None, confidence=Confidence.UNKNOWN)
        assert field_none.is_placeholder() is True

        # Field with UNKNOWN confidence is a placeholder
        field_unknown = MetadataField(value="something", confidence=Confidence.UNKNOWN)
        assert field_unknown.is_placeholder() is True

        # Field with value and non-UNKNOWN confidence is not a placeholder
        field_valid = MetadataField(value="test", confidence=Confidence.EXPLICIT)
        assert field_valid.is_placeholder() is False

    def test_field_needs_review(self):
        """Test review detection based on confidence threshold."""
        # Low confidence needs review
        field_weak = MetadataField(value="test", confidence=Confidence.WEAK)
        assert field_weak.needs_review() is True

        field_guess = MetadataField(value="test", confidence=Confidence.GUESS)
        assert field_guess.needs_review() is True

        # High confidence does not need review
        field_explicit = MetadataField(value="test", confidence=Confidence.EXPLICIT)
        assert field_explicit.needs_review() is False

        field_strong = MetadataField(value="test", confidence=Confidence.STRONG)
        assert field_strong.needs_review() is False


class TestProjectMetadata:
    """Tests for the ProjectMetadata dataclass."""

    def test_default_metadata(self):
        """Test that default metadata has expected values."""
        metadata = ProjectMetadata()

        # All MetadataFields should be placeholders by default
        assert metadata.name.is_placeholder() is True
        assert metadata.description.is_placeholder() is True
        assert metadata.version.is_placeholder() is True
        assert metadata.license.is_placeholder() is True

        # Lists should be empty
        assert metadata.authors == []
        assert metadata.dependencies == []
        assert metadata.entry_points == []

        # Boolean hints should be False
        assert metadata.has_tests is False
        assert metadata.has_ci_config is False

    def test_get_placeholder_fields(self):
        """Test getting list of placeholder fields."""
        metadata = ProjectMetadata()

        # All fields are placeholders by default
        placeholders = metadata.get_placeholder_fields()
        assert "name" in placeholders
        assert "description" in placeholders
        assert "version" in placeholders

        # After setting a field, it should not be a placeholder
        metadata.name = MetadataField(
            value="test",
            confidence=Confidence.EXPLICIT,
        )
        placeholders = metadata.get_placeholder_fields()
        assert "name" not in placeholders

    def test_get_low_confidence_fields(self):
        """Test getting list of low-confidence fields."""
        metadata = ProjectMetadata()

        # Set some fields with different confidence levels
        metadata.name = MetadataField(
            value="test",
            confidence=Confidence.EXPLICIT,
        )
        metadata.description = MetadataField(
            value="A description",
            confidence=Confidence.WEAK,
        )

        low_conf = metadata.get_low_confidence_fields()
        field_names = [name for name, _ in low_conf]

        assert "name" not in field_names  # EXPLICIT is high confidence
        assert "description" in field_names  # WEAK is low confidence

    def test_merge_from_higher_confidence_wins(self):
        """Test that merge_from uses higher confidence values."""
        metadata1 = ProjectMetadata()
        metadata1.name = MetadataField(
            value="name-from-weak",
            confidence=Confidence.WEAK,
            source="source1",
        )

        metadata2 = ProjectMetadata()
        metadata2.name = MetadataField(
            value="name-from-explicit",
            confidence=Confidence.EXPLICIT,
            source="source2",
        )

        # Merge metadata2 into metadata1
        metadata1.merge_from(metadata2)

        # Higher confidence (EXPLICIT) should win
        assert metadata1.name.value == "name-from-explicit"
        assert metadata1.name.confidence == Confidence.EXPLICIT

    def test_merge_from_lower_confidence_ignored(self):
        """Test that merge_from ignores lower confidence values."""
        metadata1 = ProjectMetadata()
        metadata1.name = MetadataField(
            value="name-from-explicit",
            confidence=Confidence.EXPLICIT,
            source="source1",
        )

        metadata2 = ProjectMetadata()
        metadata2.name = MetadataField(
            value="name-from-weak",
            confidence=Confidence.WEAK,
            source="source2",
        )

        # Merge metadata2 into metadata1
        metadata1.merge_from(metadata2)

        # Higher confidence (original EXPLICIT) should be kept
        assert metadata1.name.value == "name-from-explicit"
        assert metadata1.name.confidence == Confidence.EXPLICIT

    def test_merge_from_lists(self):
        """Test that merge_from properly merges lists."""
        metadata1 = ProjectMetadata()
        metadata1.authors.append(Author(name="Alice"))
        metadata1.dependencies.append(Dependency(name="requests"))

        metadata2 = ProjectMetadata()
        metadata2.authors.append(Author(name="Bob"))
        metadata2.dependencies.append(Dependency(name="click"))

        metadata1.merge_from(metadata2)

        # Both authors should be present
        author_names = [a.name for a in metadata1.authors]
        assert "Alice" in author_names
        assert "Bob" in author_names

        # Both dependencies should be present
        dep_names = [d.name for d in metadata1.dependencies]
        assert "requests" in dep_names
        assert "click" in dep_names

    def test_merge_from_avoids_duplicates(self):
        """Test that merge_from avoids duplicate entries in lists."""
        metadata1 = ProjectMetadata()
        metadata1.authors.append(Author(name="Alice"))

        metadata2 = ProjectMetadata()
        metadata2.authors.append(Author(name="Alice"))  # Same name

        metadata1.merge_from(metadata2)

        # Should only have one Alice
        assert len(metadata1.authors) == 1

    def test_merge_from_boolean_flags(self):
        """Test that merge_from ORs boolean flags."""
        metadata1 = ProjectMetadata()
        metadata1.has_tests = True
        metadata1.has_ci_config = False

        metadata2 = ProjectMetadata()
        metadata2.has_tests = False
        metadata2.has_ci_config = True

        metadata1.merge_from(metadata2)

        # Both should be True (OR logic)
        assert metadata1.has_tests is True
        assert metadata1.has_ci_config is True


class TestDependency:
    """Tests for the Dependency dataclass."""

    def test_dependency_basic(self):
        """Test creating a basic dependency."""
        dep = Dependency(name="requests")
        assert dep.name == "requests"
        assert dep.version_constraint is None
        assert dep.is_dev is False

    def test_dependency_with_version(self):
        """Test dependency with version constraint."""
        dep = Dependency(
            name="requests",
            version_constraint=">=2.28.0",
            source="requirements.txt",
        )
        assert dep.name == "requests"
        assert dep.version_constraint == ">=2.28.0"

    def test_dev_dependency(self):
        """Test marking a dependency as dev-only."""
        dep = Dependency(name="pytest", is_dev=True)
        assert dep.is_dev is True


class TestAuthor:
    """Tests for the Author dataclass."""

    def test_author_basic(self):
        """Test creating an author with just a name."""
        author = Author(name="Jane Doe")
        assert author.name == "Jane Doe"
        assert author.email is None
        assert author.role is None

    def test_author_full(self):
        """Test creating an author with all fields."""
        author = Author(
            name="Jane Doe",
            email="jane@example.com",
            role="maintainer",
            source="pyproject.toml",
        )
        assert author.name == "Jane Doe"
        assert author.email == "jane@example.com"
        assert author.role == "maintainer"


class TestEntryPoint:
    """Tests for the EntryPoint dataclass."""

    def test_entry_point_basic(self):
        """Test creating a basic entry point."""
        entry = EntryPoint(path="main.py", entry_type="script")
        assert entry.path == "main.py"
        assert entry.entry_type == "script"
        assert entry.command is None

    def test_entry_point_cli(self):
        """Test CLI entry point with command."""
        entry = EntryPoint(
            path="myapp.cli:main",
            entry_type="cli",
            command="myapp",
            confidence=Confidence.EXPLICIT,
        )
        assert entry.command == "myapp"
        assert entry.confidence == Confidence.EXPLICIT
