"""
AutoDoc Markdown Renderer

This module generates README.md content from extracted ProjectMetadata.
It applies templates and formatting to produce a structured, human-readable
document that encourages review and refinement.

Design Principles:
    1. Human-in-the-Loop: Generated content is a draft, not a final product
    2. Transparency: Placeholders and low-confidence markers are clearly visible
    3. Flexibility: Sections are conditionally included based on available data
    4. Readability: Output follows common README conventions and formatting

Key Features:
    - Template-based section generation
    - TODO comments for missing fields
    - Review markers for low-confidence data
    - Conditional sections (only included when relevant data exists)
    - Metadata provenance comments (optional, for debugging)

Output Structure:
    1. Title and description
    2. Installation instructions
    3. Usage examples
    4. Dependencies (if any)
    5. License
    6. Authors
    7. (Optional sections based on detected features)
    8. Generation notice with review encouragement
"""

from dataclasses import dataclass
from typing import Optional

from autodoc.schema import Confidence, MetadataField, ProjectMetadata


@dataclass
class RenderOptions:
    """
    Configuration options for README rendering.

    Attributes:
        include_provenance: Add HTML comments showing data sources
        include_toc: Generate a table of contents
        include_badges: Add badge section (always on by default)
        include_generation_notice: Add notice that README was auto-generated
        include_key_features: Add key features section
        include_project_structure: Add project structure tree
        include_configuration: Add configuration section
        include_architecture: Add architecture/design section
        confidence_threshold: Fields below this confidence get review markers
        placeholder_style: How to format placeholders ("html_comment" or "markdown")
    """
    include_provenance: bool = False
    include_toc: bool = True  # Now defaults to True
    include_badges: bool = True  # Now defaults to True
    include_generation_notice: bool = True
    include_key_features: bool = True
    include_project_structure: bool = True
    include_configuration: bool = True
    include_architecture: bool = True
    confidence_threshold: float = Confidence.REASONABLE.value
    placeholder_style: str = "html_comment"  # "html_comment" or "markdown"


class ReadmeRenderer:
    """
    Renders ProjectMetadata into Markdown README content.

    This class takes extracted metadata and produces a structured README
    document. It handles missing data gracefully by inserting placeholders
    and marks low-confidence data for human review.

    Usage:
        renderer = ReadmeRenderer(metadata)
        readme_content = renderer.render()

        # With custom options
        options = RenderOptions(include_badges=True)
        renderer = ReadmeRenderer(metadata, options)
        readme_content = renderer.render()

    The generated README includes:
        - Project title and description
        - Installation instructions
        - Usage examples (if entry points exist)
        - Dependencies list
        - License information
        - Author credits
        - A notice encouraging human review
    """

    def __init__(
        self,
        metadata: ProjectMetadata,
        options: Optional[RenderOptions] = None,
    ):
        """
        Initialize the renderer.

        Args:
            metadata: The extracted project metadata
            options: Rendering options (uses defaults if not provided)
        """
        self.metadata = metadata
        self.options = options or RenderOptions()
        self._sections: list[str] = []

    def render(self) -> str:
        """
        Generate the complete README content.

        Returns:
            The rendered README as a Markdown string
        """
        self._sections = []

        # Build sections in order (mandatory sections per spec)
        self._add_title_section()
        self._add_badges_section()
        self._add_description_section()
        self._add_key_features_section()
        self._add_languages_section()
        self._add_toc_section()
        self._add_installation_section()
        self._add_usage_section()
        self._add_project_structure_section()
        self._add_configuration_section()
        self._add_architecture_section()
        self._add_testing_section()
        self._add_dependencies_section()
        self._add_contributing_section()
        self._add_license_section()
        self._add_authors_section()
        self._add_generation_notice()

        return "\n".join(self._sections)

    def _add_section(self, content: str) -> None:
        """Add a section to the output."""
        if content.strip():
            self._sections.append(content)

    def _format_placeholder(self, field_name: str, hint: str = "") -> str:
        """
        Format a placeholder for missing data.

        Args:
            field_name: Name of the missing field
            hint: Optional hint about what to add

        Returns:
            Formatted placeholder string
        """
        if self.options.placeholder_style == "html_comment":
            if hint:
                return f"<!-- TODO: Add {field_name} - {hint} -->"
            return f"<!-- TODO: Add {field_name} -->"
        else:
            # Markdown style (visible to readers)
            if hint:
                return f"*[TODO: Add {field_name} - {hint}]*"
            return f"*[TODO: Add {field_name}]*"

    def _format_review_marker(self, field: MetadataField) -> str:
        """
        Format a review marker for low-confidence data.

        Args:
            field: The MetadataField to mark

        Returns:
            HTML comment suggesting review
        """
        confidence_name = field.confidence.name.lower()
        source = field.source or "unknown source"
        note = f" ({field.note})" if field.note else ""
        return f"<!-- Review suggested: {confidence_name} confidence from {source}{note} -->"

    def _format_provenance(self, field: MetadataField) -> str:
        """
        Format provenance information as an HTML comment.

        Args:
            field: The MetadataField to document

        Returns:
            HTML comment with source information
        """
        if not self.options.include_provenance:
            return ""
        source = field.source or "unknown"
        confidence = field.confidence.name.lower()
        return f"<!-- Source: {source} (confidence: {confidence}) -->"

    def _needs_review(self, field: MetadataField) -> bool:
        """Check if a field's confidence is below the review threshold."""
        return field.confidence.value < self.options.confidence_threshold

    def _add_title_section(self) -> None:
        """Add the project title as an H1 heading."""
        name_field = self.metadata.name

        if name_field.value:
            title = f"# {name_field.value}"
            if self._needs_review(name_field):
                title += f"\n{self._format_review_marker(name_field)}"
            title += self._format_provenance(name_field)
        else:
            title = f"# Project Name\n{self._format_placeholder('project name', 'Replace with your project name')}"

        self._add_section(title)

    def _add_badges_section(self) -> None:
        """Add placeholder badges section if enabled."""
        if not self.options.include_badges:
            return

        badges = []

        # License badge
        if self.metadata.license.value:
            license_val = self.metadata.license.value
            # Simplified badge URL (shields.io format)
            badges.append(f"![License: {license_val}](https://img.shields.io/badge/License-{license_val.replace('-', '--')}-blue.svg)")

        # Python version badge
        if self.metadata.python_version.value:
            py_ver = self.metadata.python_version.value
            badges.append(f"![Python: {py_ver}](https://img.shields.io/badge/Python-{py_ver.replace('>=', '%3E%3D')}-blue.svg)")

        if badges:
            self._add_section("\n".join(badges) + "\n")
        else:
            self._add_section(self._format_placeholder("badges", "Add shields.io badges for license, build status, etc.") + "\n")

    def _add_description_section(self) -> None:
        """Add the project description (minimum 2 lines/5 sentences, with comprehensive code-based fallback)."""
        desc_field = self.metadata.description
        name = self.metadata.name.value or "This project"
        lang = self.metadata.primary_language.value or "software"

        content = ""
        base_desc = ""

        if desc_field.value and desc_field.value.strip():
            base_desc = desc_field.value.strip()

        # Count effective lines/sentences
        line_count = len([l for l in base_desc.split('\n') if l.strip()]) if base_desc else 0
        sentence_count = len([s for s in base_desc.replace('\n', ' ').split('.') if s.strip()]) if base_desc else 0

        # We need at least 2 lines OR 5 sentences of content
        needs_expansion = line_count < 2 and sentence_count < 5

        if base_desc and not needs_expansion:
            # Description is sufficient
            content = base_desc
            if self._needs_review(desc_field):
                content += f"\n\n{self._format_review_marker(desc_field)}"
            content += self._format_provenance(desc_field)
        else:
            # Build comprehensive description from code analysis
            paragraphs = []

            # Paragraph 1: Project identity and purpose
            if base_desc:
                paragraphs.append(base_desc)

            # Build project type description
            project_type = "project"
            if self.metadata.entry_points:
                cli_entries = [e for e in self.metadata.entry_points if e.entry_type == "cli"]
                module_entries = [e for e in self.metadata.entry_points if e.entry_type == "module"]
                if cli_entries:
                    project_type = "command-line tool"
                elif module_entries:
                    project_type = "library"

            identity_line = f"{name} is a {lang} {project_type}"

            # Add purpose based on dependencies
            purpose_hints = []
            if self.metadata.dependencies:
                dep_names = [d.name.lower() for d in self.metadata.dependencies]
                if any(d in dep_names for d in ['flask', 'django', 'fastapi', 'express']):
                    purpose_hints.append("web application development")
                if any(d in dep_names for d in ['pandas', 'numpy', 'scipy']):
                    purpose_hints.append("data processing and analysis")
                if any(d in dep_names for d in ['tensorflow', 'torch', 'pytorch', 'keras']):
                    purpose_hints.append("machine learning")
                if any(d in dep_names for d in ['requests', 'httpx', 'aiohttp']):
                    purpose_hints.append("HTTP client operations")
                if any(d in dep_names for d in ['click', 'argparse', 'typer']):
                    purpose_hints.append("command-line interface")
                if any(d in dep_names for d in ['sqlalchemy', 'psycopg2', 'pymongo']):
                    purpose_hints.append("database operations")

            if purpose_hints:
                identity_line += f" designed for {', '.join(purpose_hints[:2])}"
            identity_line += "."

            if not base_desc:
                paragraphs.append(identity_line)

            # Paragraph 2: Technical capabilities
            capabilities = []
            if self.metadata.entry_points:
                cli_entries = [e for e in self.metadata.entry_points if e.entry_type == "cli"]
                if cli_entries:
                    commands = [e.command for e in cli_entries if e.command]
                    if commands:
                        capabilities.append(f"provides {len(commands)} CLI command(s) ({', '.join(commands[:3])})")
                    else:
                        capabilities.append(f"provides {len(cli_entries)} command-line interface(s)")

            if self.metadata.dependencies:
                key_deps = [d.name for d in self.metadata.dependencies[:4]]
                if key_deps:
                    capabilities.append(f"leverages {', '.join(key_deps)} as core dependencies")

            if capabilities:
                cap_text = "It " + " and ".join(capabilities) + "."
                paragraphs.append(cap_text)

            # Paragraph 3: Quality and development features
            quality_features = []
            if self.metadata.has_tests:
                quality_features.append("comprehensive test coverage for reliability")
            if self.metadata.has_ci_config:
                quality_features.append("continuous integration for automated testing")
            if self.metadata.has_docs_folder:
                quality_features.append("detailed documentation for users")
            if self.metadata.has_examples:
                quality_features.append("usage examples for quick onboarding")

            if quality_features:
                quality_text = f"The project includes {', '.join(quality_features[:3])}."
                paragraphs.append(quality_text)

            # Paragraph 4: Installation/usage summary
            install_text = ""
            if lang.lower() == "python":
                install_text = f"Install {name} using pip for seamless integration into your Python environment."
            elif lang.lower() in ("javascript", "typescript"):
                install_text = f"Install {name} via npm to add it to your Node.js project."
            elif lang.lower() == "java":
                install_text = f"Add {name} to your project using Maven or Gradle."

            if install_text:
                paragraphs.append(install_text)

            # Paragraph 5: Target audience / use cases (fallback)
            if len(paragraphs) < 3:
                if self.metadata.entry_points:
                    use_case = f"{name} is suitable for developers looking to integrate {lang.lower()} functionality into their workflows."
                else:
                    use_case = f"{name} provides reusable components for {lang.lower()} development."
                paragraphs.append(use_case)

            # Ensure we have at least 2 substantial paragraphs
            if len(paragraphs) < 2:
                paragraphs.append(f"For more information, see the documentation and examples included in this repository.")

            content = "\n\n".join(paragraphs)

            # Add placeholder for additional details if we had to generate everything
            if not base_desc:
                content += "\n\n" + self._format_placeholder(
                    "detailed project description",
                    "Expand with specific use cases, key differentiators, and target audience"
                )

        self._add_section(content + "\n")

    def _add_key_features_section(self) -> None:
        """Add key features section with action-oriented bullet points."""
        if not self.options.include_key_features:
            return

        section = "## Key Features\n\n"

        if self.metadata.key_features:
            for feature in self.metadata.key_features:
                # Ensure feature starts with action verb
                section += f"- {feature}\n"
        else:
            # Generate basic features from detected capabilities
            features = []

            if self.metadata.entry_points:
                cli_entries = [e for e in self.metadata.entry_points if e.entry_type == "cli"]
                if cli_entries:
                    features.append("Provides command-line interface for easy integration")

            if self.metadata.has_tests:
                features.append("Includes comprehensive test suite for reliability")

            if self.metadata.has_ci_config:
                features.append("Supports continuous integration workflows")

            if self.metadata.has_docs_folder:
                features.append("Offers detailed documentation for users and contributors")

            # Add language-specific features
            lang = (self.metadata.primary_language.value or "").lower()
            if lang == "python":
                features.append("Implements type hints for improved code quality")
            elif lang == "javascript" or lang == "typescript":
                features.append("Enables modern JavaScript/TypeScript development patterns")

            if features:
                for feature in features:
                    section += f"- {feature}\n"
            else:
                section += self._format_placeholder(
                    "key features",
                    "Add 5-7 action-oriented feature descriptions"
                )
                section += "\n"

        self._add_section(section)

    def _add_languages_section(self) -> None:
        """Add detected languages and frameworks section."""
        lang_field = self.metadata.primary_language

        # Check if we have language info from GitHub (stored in extraction_warnings)
        detected_langs = []
        for warning in self.metadata.extraction_warnings:
            if warning.startswith("Languages detected:"):
                detected_langs.append(warning.replace("Languages detected: ", ""))
            elif warning.startswith("Detected frameworks:"):
                detected_langs.append(warning.replace("Detected ", ""))

        # Only show if we have language data
        if not lang_field.value and not detected_langs:
            return

        section = ""

        # Primary language badge
        if lang_field.value:
            section += f"**Primary Language:** {lang_field.value}"
            if self._needs_review(lang_field):
                section += f" {self._format_review_marker(lang_field)}"
            section += "\n"

        # Additional language stats from GitHub
        for info in detected_langs:
            section += f"\n{info}\n"

        if section:
            self._add_section(section)

    def _add_toc_section(self) -> None:
        """Add table of contents if enabled."""
        if not self.options.include_toc:
            return

        # Build TOC dynamically based on which sections will be included
        toc_items = []

        # Key Features (if enabled)
        if self.options.include_key_features:
            toc_items.append("- [Key Features](#key-features)")

        # Installation (always included)
        toc_items.append("- [Installation](#installation)")

        # Usage (always included)
        toc_items.append("- [Usage](#usage)")

        # Project Structure (if enabled)
        if self.options.include_project_structure:
            toc_items.append("- [Project Structure](#project-structure)")

        # Configuration (if enabled)
        if self.options.include_configuration:
            toc_items.append("- [Configuration](#configuration)")

        # Architecture (if enabled)
        if self.options.include_architecture:
            toc_items.append("- [Architecture](#architecture)")

        # Testing (if tests exist)
        if self.metadata.has_tests:
            toc_items.append("- [Testing](#testing)")

        # Dependencies (if any)
        if self.metadata.dependencies or self.metadata.dev_dependencies:
            toc_items.append("- [Dependencies](#dependencies)")

        # Contributing (if applicable)
        if self.metadata.has_ci_config or self.metadata.license.value:
            toc_items.append("- [Contributing](#contributing)")

        # License (always included)
        toc_items.append("- [License](#license)")

        # Authors (always included)
        toc_items.append("- [Authors](#authors)")

        toc = "## Table of Contents\n\n" + "\n".join(toc_items) + "\n"
        self._add_section(toc)

    def _add_installation_section(self) -> None:
        """Add installation instructions."""
        section = "## Installation\n\n"

        name = self.metadata.name.value or "package-name"
        python_ver = self.metadata.python_version.value

        # Add Python version requirement if known
        if python_ver:
            section += f"**Requires Python {python_ver}**\n\n"

        # Generate installation commands based on what we know
        has_pyproject = True  # We assume Python project for now

        if has_pyproject:
            section += "```bash\n"
            section += f"# Clone the repository\n"
            section += f"git clone {self.metadata.repository_url.value or '<repository-url>'}\n"
            section += f"cd {name}\n\n"
            section += f"# Install the package\n"
            section += f"pip install .\n\n"
            section += f"# Or install in development mode\n"
            section += f"pip install -e .\n"
            section += "```\n"

        # Add note about missing info
        if not self.metadata.repository_url.value:
            section += f"\n{self._format_placeholder('repository URL', 'Replace <repository-url> with actual URL')}\n"

        self._add_section(section)

    def _add_usage_section(self) -> None:
        """Add usage instructions based on detected entry points."""
        section = "## Usage\n\n"

        entry_points = self.metadata.entry_points

        if entry_points:
            # Group by type
            cli_entries = [e for e in entry_points if e.entry_type == "cli"]
            module_entries = [e for e in entry_points if e.entry_type == "module"]
            script_entries = [e for e in entry_points if e.entry_type in ("script", "main")]

            if cli_entries:
                section += "### Command Line\n\n"
                section += "```bash\n"
                for entry in cli_entries:
                    if entry.command:
                        section += f"{entry.command} --help\n"
                section += "```\n\n"
                section += self._format_placeholder(
                    "CLI usage examples",
                    "Add common usage examples and options"
                ) + "\n\n"

            if module_entries:
                section += "### As a Module\n\n"
                section += "```python\n"
                for entry in module_entries:
                    # Extract module name from path
                    module_name = entry.path.replace("/__main__.py", "").replace("/", ".")
                    section += f"python -m {module_name}\n"
                section += "```\n\n"

            if script_entries:
                section += "### Running Scripts\n\n"
                section += "```bash\n"
                for entry in script_entries:
                    section += f"python {entry.path}\n"
                section += "```\n\n"

            # Add review markers for low-confidence entries
            low_conf_entries = [e for e in entry_points if e.confidence.value < self.options.confidence_threshold]
            if low_conf_entries:
                section += f"<!-- Review suggested: Entry points detected heuristically. Verify these are correct. -->\n"
        else:
            section += self._format_placeholder(
                "usage examples",
                "Show how to use this project with code examples"
            ) + "\n\n"
            section += "```python\n"
            section += "# Example usage\n"
            section += "# from package import something\n"
            section += "# result = something.do_work()\n"
            section += "```\n"

        self._add_section(section)

    def _add_project_structure_section(self) -> None:
        """Add comprehensive project structure tree with elaborate, granular nested annotations."""
        if not self.options.include_project_structure:
            return

        name = self.metadata.name.value or "project"
        lang = (self.metadata.primary_language.value or "").lower()
        pkg_name = (self.metadata.name.value or "package").replace("-", "_").lower()

        section = "## Project Structure\n\n"
        section += "```\n"
        section += f"{name}/\n"

        # Build the full nested tree structure based on language
        if lang == "python":
            section += self._build_python_structure(pkg_name)
        elif lang in ("javascript", "typescript"):
            section += self._build_javascript_structure()
        elif lang == "java":
            section += self._build_java_structure()
        elif lang in ("c", "c++", "cpp"):
            section += self._build_cpp_structure()
        elif lang == "go":
            section += self._build_go_structure()
        elif lang == "rust":
            section += self._build_rust_structure()
        else:
            section += self._build_generic_structure(pkg_name)

        section += "```\n"

        # Add directory overview table
        section += self._build_directory_overview_table(lang, pkg_name)

        self._add_section(section)

    def _build_python_structure(self, pkg_name: str) -> str:
        """Build detailed Python project structure."""
        lines = []

        # Root config files
        lines.append("├── .gitignore                              # Git ignore patterns")
        lines.append("├── README.md                               # Project documentation")
        lines.append("├── LICENSE                                 # Open source license")
        lines.append("├── CHANGELOG.md                            # Version history")
        lines.append("├── CONTRIBUTING.md                         # Contribution guidelines")
        lines.append("│")

        # Build/dist directories
        lines.append("├── dist/                                   # Distribution packages")
        lines.append("│   ├── *.whl                               # Wheel distributions")
        lines.append("│   └── *.tar.gz                            # Source distributions")
        lines.append("│")

        # Documentation
        if self.metadata.has_docs_folder:
            lines.append("├── docs/                                   # Project documentation")
            lines.append("│   ├── index.md                            # Documentation home")
            lines.append("│   ├── getting-started.md                  # Quick start guide")
            lines.append("│   ├── api/                                # API reference")
            lines.append("│   │   ├── overview.md                     # API overview")
            lines.append("│   │   ├── endpoints.md                    # Endpoint documentation")
            lines.append("│   │   └── models.md                       # Data model docs")
            lines.append("│   ├── guides/                             # User guides")
            lines.append("│   │   ├── installation.md                 # Install instructions")
            lines.append("│   │   ├── configuration.md                # Config guide")
            lines.append("│   │   └── troubleshooting.md              # Common issues")
            lines.append("│   └── images/                             # Documentation assets")
            lines.append("│       └── architecture.png                # Architecture diagram")
            lines.append("│")

        # Main package
        lines.append(f"├── {pkg_name}/                              # Main package")
        lines.append(f"│   ├── __init__.py                         # Package initialization")
        lines.append(f"│   ├── __main__.py                         # CLI entry point")
        lines.append(f"│   ├── py.typed                            # PEP 561 type marker")
        lines.append(f"│   │")
        lines.append(f"│   ├── cli/                                 # Command-line interface")
        lines.append(f"│   │   ├── __init__.py                     # CLI module init")
        lines.append(f"│   │   ├── main.py                         # Main CLI entry")
        lines.append(f"│   │   ├── commands/                       # CLI commands")
        lines.append(f"│   │   │   ├── __init__.py                 # Commands init")
        lines.append(f"│   │   │   ├── run.py                      # Run command")
        lines.append(f"│   │   │   └── config.py                   # Config command")
        lines.append(f"│   │   └── utils.py                        # CLI utilities")
        lines.append(f"│   │")
        lines.append(f"│   ├── core/                                # Core business logic")
        lines.append(f"│   │   ├── __init__.py                     # Core module init")
        lines.append(f"│   │   ├── engine.py                       # Main processing engine")
        lines.append(f"│   │   ├── processor.py                    # Data processor")
        lines.append(f"│   │   └── validator.py                    # Input validation")
        lines.append(f"│   │")
        lines.append(f"│   ├── models/                              # Data models")
        lines.append(f"│   │   ├── __init__.py                     # Models init")
        lines.append(f"│   │   ├── base.py                         # Base model class")
        lines.append(f"│   │   ├── entities.py                     # Domain entities")
        lines.append(f"│   │   └── schemas.py                      # Pydantic schemas")
        lines.append(f"│   │")
        lines.append(f"│   ├── services/                            # Service layer")
        lines.append(f"│   │   ├── __init__.py                     # Services init")
        lines.append(f"│   │   ├── base.py                         # Base service class")
        lines.append(f"│   │   └── impl/                           # Implementations")
        lines.append(f"│   │       ├── __init__.py                 # Impl init")
        lines.append(f"│   │       └── default.py                  # Default service")
        lines.append(f"│   │")
        lines.append(f"│   ├── utils/                               # Utility modules")
        lines.append(f"│   │   ├── __init__.py                     # Utils init")
        lines.append(f"│   │   ├── helpers.py                      # Helper functions")
        lines.append(f"│   │   ├── decorators.py                   # Custom decorators")
        lines.append(f"│   │   └── constants.py                    # Constants")
        lines.append(f"│   │")
        lines.append(f"│   ├── config/                              # Configuration")
        lines.append(f"│   │   ├── __init__.py                     # Config init")
        lines.append(f"│   │   ├── settings.py                     # Settings management")
        lines.append(f"│   │   └── defaults.py                     # Default values")
        lines.append(f"│   │")
        lines.append(f"│   └── exceptions/                          # Custom exceptions")
        lines.append(f"│       ├── __init__.py                     # Exceptions init")
        lines.append(f"│       ├── base.py                         # Base exception")
        lines.append(f"│       └── errors.py                       # Error classes")
        lines.append("│")

        # Tests
        if self.metadata.has_tests:
            lines.append("├── tests/                                  # Test suite")
            lines.append("│   ├── __init__.py                         # Tests init")
            lines.append("│   ├── conftest.py                         # Pytest fixtures")
            lines.append("│   │")
            lines.append("│   ├── unit/                               # Unit tests")
            lines.append("│   │   ├── __init__.py                     # Unit tests init")
            lines.append("│   │   ├── test_core.py                    # Core module tests")
            lines.append("│   │   ├── test_models.py                  # Model tests")
            lines.append("│   │   └── test_utils.py                   # Utility tests")
            lines.append("│   │")
            lines.append("│   ├── integration/                        # Integration tests")
            lines.append("│   │   ├── __init__.py                     # Integration init")
            lines.append("│   │   └── test_api.py                     # API integration")
            lines.append("│   │")
            lines.append("│   └── fixtures/                           # Test fixtures")
            lines.append("│       ├── sample_data.json                # Sample test data")
            lines.append("│       └── mock_responses.py               # Mock responses")
            lines.append("│")

        # Examples
        if self.metadata.has_examples:
            lines.append("├── examples/                               # Usage examples")
            lines.append("│   ├── basic_usage.py                      # Basic example")
            lines.append("│   ├── advanced_usage.py                   # Advanced example")
            lines.append("│   └── README.md                           # Examples guide")
            lines.append("│")

        # Scripts
        lines.append("├── scripts/                                # Automation scripts")
        lines.append("│   ├── build.sh                            # Build script")
        lines.append("│   ├── test.sh                             # Test runner")
        lines.append("│   ├── lint.sh                             # Linting script")
        lines.append("│   └── release.sh                          # Release script")
        lines.append("│")

        # Config files
        lines.append("├── pyproject.toml                          # Project configuration (PEP 518/621)")
        lines.append("├── setup.py                                # Legacy setup (if needed)")
        lines.append("├── requirements.txt                        # Runtime dependencies")
        lines.append("├── requirements-dev.txt                    # Development dependencies")
        lines.append("├── pytest.ini                              # Pytest configuration")
        lines.append("├── mypy.ini                                # Type checker config")
        lines.append("├── .pre-commit-config.yaml                 # Pre-commit hooks")
        lines.append("└── tox.ini                                 # Multi-env testing")

        return "\n".join(lines) + "\n"

    def _build_javascript_structure(self) -> str:
        """Build detailed JavaScript/TypeScript project structure."""
        lines = []

        # Root config files
        lines.append("├── .gitignore                              # Git ignore patterns")
        lines.append("├── README.md                               # Project documentation")
        lines.append("├── LICENSE                                 # Open source license")
        lines.append("├── CHANGELOG.md                            # Version history")
        lines.append("├── CONTRIBUTING.md                         # Contribution guidelines")
        lines.append("│")

        # Build output
        lines.append("├── dist/                                   # Compiled output")
        lines.append("│   ├── index.js                            # Main bundle")
        lines.append("│   ├── index.d.ts                          # Type declarations")
        lines.append("│   └── index.js.map                        # Source maps")
        lines.append("│")

        # Documentation
        if self.metadata.has_docs_folder:
            lines.append("├── docs/                                   # Documentation")
            lines.append("│   ├── api/                                # API reference")
            lines.append("│   │   ├── README.md                       # API overview")
            lines.append("│   │   └── modules.md                      # Module docs")
            lines.append("│   └── guides/                             # User guides")
            lines.append("│       ├── getting-started.md              # Quick start")
            lines.append("│       └── configuration.md                # Config guide")
            lines.append("│")

        # Source code
        lines.append("├── src/                                    # Source code")
        lines.append("│   ├── index.ts                            # Main entry point")
        lines.append("│   │")
        lines.append("│   ├── components/                         # React/Vue components")
        lines.append("│   │   ├── index.ts                        # Components barrel")
        lines.append("│   │   ├── Button/                         # Button component")
        lines.append("│   │   │   ├── Button.tsx                  # Component impl")
        lines.append("│   │   │   ├── Button.styles.ts            # Styled components")
        lines.append("│   │   │   ├── Button.test.tsx             # Component tests")
        lines.append("│   │   │   └── index.ts                    # Component export")
        lines.append("│   │   └── Modal/                          # Modal component")
        lines.append("│   │       ├── Modal.tsx                   # Component impl")
        lines.append("│   │       └── index.ts                    # Component export")
        lines.append("│   │")
        lines.append("│   ├── hooks/                              # Custom React hooks")
        lines.append("│   │   ├── index.ts                        # Hooks barrel")
        lines.append("│   │   ├── useAuth.ts                      # Auth hook")
        lines.append("│   │   └── useApi.ts                       # API hook")
        lines.append("│   │")
        lines.append("│   ├── services/                           # API services")
        lines.append("│   │   ├── index.ts                        # Services barrel")
        lines.append("│   │   ├── api.ts                          # API client")
        lines.append("│   │   └── auth.ts                         # Auth service")
        lines.append("│   │")
        lines.append("│   ├── store/                              # State management")
        lines.append("│   │   ├── index.ts                        # Store setup")
        lines.append("│   │   ├── slices/                         # Redux slices")
        lines.append("│   │   │   ├── userSlice.ts                # User state")
        lines.append("│   │   │   └── appSlice.ts                 # App state")
        lines.append("│   │   └── hooks.ts                        # Typed hooks")
        lines.append("│   │")
        lines.append("│   ├── types/                              # TypeScript types")
        lines.append("│   │   ├── index.ts                        # Types barrel")
        lines.append("│   │   ├── api.ts                          # API types")
        lines.append("│   │   └── models.ts                       # Model types")
        lines.append("│   │")
        lines.append("│   ├── utils/                              # Utility functions")
        lines.append("│   │   ├── index.ts                        # Utils barrel")
        lines.append("│   │   ├── helpers.ts                      # Helper functions")
        lines.append("│   │   ├── validators.ts                   # Validation utils")
        lines.append("│   │   └── constants.ts                    # Constants")
        lines.append("│   │")
        lines.append("│   └── styles/                             # Global styles")
        lines.append("│       ├── global.css                      # Global CSS")
        lines.append("│       ├── variables.css                   # CSS variables")
        lines.append("│       └── themes/                         # Theme files")
        lines.append("│           ├── light.ts                    # Light theme")
        lines.append("│           └── dark.ts                     # Dark theme")
        lines.append("│")

        # Tests
        if self.metadata.has_tests:
            lines.append("├── __tests__/                              # Test files")
            lines.append("│   ├── setup.ts                            # Test setup")
            lines.append("│   ├── unit/                               # Unit tests")
            lines.append("│   │   └── utils.test.ts                   # Utils tests")
            lines.append("│   └── integration/                        # Integration tests")
            lines.append("│       └── api.test.ts                     # API tests")
            lines.append("│")
            lines.append("├── e2e/                                    # E2E tests")
            lines.append("│   ├── cypress.config.ts                   # Cypress config")
            lines.append("│   └── specs/                              # Test specs")
            lines.append("│       └── app.cy.ts                       # App E2E tests")
            lines.append("│")

        # Public/static
        lines.append("├── public/                                 # Static assets")
        lines.append("│   ├── index.html                          # HTML template")
        lines.append("│   ├── favicon.ico                         # Favicon")
        lines.append("│   └── assets/                             # Static assets")
        lines.append("│       ├── images/                         # Image files")
        lines.append("│       └── fonts/                          # Font files")
        lines.append("│")

        # Scripts
        lines.append("├── scripts/                                # Build scripts")
        lines.append("│   ├── build.js                            # Build script")
        lines.append("│   └── generate-types.js                   # Type generator")
        lines.append("│")

        # Config files
        lines.append("├── package.json                            # Package manifest")
        lines.append("├── package-lock.json                       # Locked dependencies")
        lines.append("├── tsconfig.json                           # TypeScript config")
        lines.append("├── tsconfig.build.json                     # Build TS config")
        lines.append("├── jest.config.js                          # Jest config")
        lines.append("├── .eslintrc.js                            # ESLint config")
        lines.append("├── .prettierrc                             # Prettier config")
        lines.append("└── vite.config.ts                          # Vite/bundler config")

        return "\n".join(lines) + "\n"

    def _build_java_structure(self) -> str:
        """Build detailed Java project structure."""
        lines = []

        # Root files
        lines.append("├── .gitignore                              # Git ignore patterns")
        lines.append("├── README.md                               # Project documentation")
        lines.append("├── LICENSE                                 # Open source license")
        lines.append("├── CHANGELOG.md                            # Version history")
        lines.append("├── CONTRIBUTING.md                         # Contribution guidelines")
        lines.append("│")

        # Build output directories
        lines.append("├── build/                                  # Gradle build output")
        lines.append("│   ├── classes/                            # Compiled classes")
        lines.append("│   ├── reports/                            # Test reports")
        lines.append("│   └── libs/                               # Generated JARs")
        lines.append("│")
        lines.append("├── target/                                 # Maven build output")
        lines.append("│   ├── classes/                            # Compiled classes")
        lines.append("│   ├── generated-sources/                  # Generated code")
        lines.append("│   └── test-classes/                       # Test classes")
        lines.append("│")

        # Documentation
        if self.metadata.has_docs_folder:
            lines.append("├── docs/                                   # Documentation")
            lines.append("│   ├── architecture/                       # Architecture docs")
            lines.append("│   │   ├── system-overview.md              # System overview")
            lines.append("│   │   ├── component-diagram.png           # Architecture diagram")
            lines.append("│   │   └── data-flow.md                    # Data flow docs")
            lines.append("│   ├── api/                                # API documentation")
            lines.append("│   │   ├── endpoints.md                    # REST endpoints")
            lines.append("│   │   ├── request-response.md             # Request/Response")
            lines.append("│   │   └── error-codes.md                  # Error codes")
            lines.append("│   └── setup/                              # Setup guides")
            lines.append("│       ├── local-setup.md                  # Local development")
            lines.append("│       ├── prod-deployment.md              # Production deploy")
            lines.append("│       └── troubleshooting.md              # Troubleshooting")
            lines.append("│")

        # Main source
        lines.append("├── src/")
        lines.append("│   ├── main/")
        lines.append("│   │   ├── java/")
        lines.append("│   │   │   └── com/example/project/")
        lines.append("│   │   │       ├── Application.java          # Main application")
        lines.append("│   │   │       │")
        lines.append("│   │   │       ├── config/                   # Configuration")
        lines.append("│   │   │       │   ├── AppConfig.java        # App config")
        lines.append("│   │   │       │   ├── SecurityConfig.java   # Security config")
        lines.append("│   │   │       │   └── DatabaseConfig.java   # Database config")
        lines.append("│   │   │       │")
        lines.append("│   │   │       ├── controller/               # REST controllers")
        lines.append("│   │   │       │   ├── UserController.java   # User endpoints")
        lines.append("│   │   │       │   ├── AdminController.java  # Admin endpoints")
        lines.append("│   │   │       │   └── HealthController.java # Health check")
        lines.append("│   │   │       │")
        lines.append("│   │   │       ├── service/                  # Business logic")
        lines.append("│   │   │       │   ├── UserService.java      # User service")
        lines.append("│   │   │       │   ├── AuthService.java      # Auth service")
        lines.append("│   │   │       │   └── impl/                 # Implementations")
        lines.append("│   │   │       │       ├── UserServiceImpl.java")
        lines.append("│   │   │       │       └── AuthServiceImpl.java")
        lines.append("│   │   │       │")
        lines.append("│   │   │       ├── repository/               # Data access")
        lines.append("│   │   │       │   ├── UserRepository.java   # User repo")
        lines.append("│   │   │       │   ├── RoleRepository.java   # Role repo")
        lines.append("│   │   │       │   └── impl/                 # JPA impls")
        lines.append("│   │   │       │       └── JpaUserRepository.java")
        lines.append("│   │   │       │")
        lines.append("│   │   │       ├── model/                    # Domain models")
        lines.append("│   │   │       │   ├── User.java             # User entity")
        lines.append("│   │   │       │   ├── Role.java             # Role entity")
        lines.append("│   │   │       │   └── AuditLog.java         # Audit entity")
        lines.append("│   │   │       │")
        lines.append("│   │   │       ├── dto/                      # DTOs")
        lines.append("│   │   │       │   ├── UserRequestDTO.java   # Request DTO")
        lines.append("│   │   │       │   ├── UserResponseDTO.java  # Response DTO")
        lines.append("│   │   │       │   └── ErrorResponseDTO.java # Error DTO")
        lines.append("│   │   │       │")
        lines.append("│   │   │       ├── exception/                # Exceptions")
        lines.append("│   │   │       │   ├── GlobalExceptionHandler.java")
        lines.append("│   │   │       │   ├── ResourceNotFoundException.java")
        lines.append("│   │   │       │   └── ValidationException.java")
        lines.append("│   │   │       │")
        lines.append("│   │   │       ├── util/                     # Utilities")
        lines.append("│   │   │       │   ├── DateUtils.java        # Date helpers")
        lines.append("│   │   │       │   ├── ValidationUtils.java  # Validation")
        lines.append("│   │   │       │   └── Constants.java        # Constants")
        lines.append("│   │   │       │")
        lines.append("│   │   │       └── security/                 # Security")
        lines.append("│   │   │           ├── JwtTokenProvider.java # JWT handler")
        lines.append("│   │   │           ├── AuthFilter.java       # Auth filter")
        lines.append("│   │   │           └── SecurityUtils.java    # Security utils")
        lines.append("│   │   │")
        lines.append("│   │   ├── resources/")
        lines.append("│   │   │   ├── application.yml               # Main config")
        lines.append("│   │   │   ├── application-dev.yml           # Dev config")
        lines.append("│   │   │   ├── application-prod.yml          # Prod config")
        lines.append("│   │   │   ├── logback.xml                   # Logging config")
        lines.append("│   │   │   ├── db/                           # Database")
        lines.append("│   │   │   │   ├── migration/                # Flyway migrations")
        lines.append("│   │   │   │   │   ├── V1__init.sql          # Initial schema")
        lines.append("│   │   │   │   │   └── V2__add_roles.sql     # Add roles")
        lines.append("│   │   │   │   └── seed/                     # Seed data")
        lines.append("│   │   │   │       └── test-data.sql         # Test data")
        lines.append("│   │   │   └── templates/                    # Templates")
        lines.append("│   │   │       ├── email/                    # Email templates")
        lines.append("│   │   │       │   ├── welcome.html          # Welcome email")
        lines.append("│   │   │       │   └── reset-password.html   # Reset password")
        lines.append("│   │   │       └── error/                    # Error pages")
        lines.append("│   │   │           └── error.html            # Error template")
        lines.append("│   │   │")
        lines.append("│   │   └── webapp/                           # Web resources")
        lines.append("│   │       ├── WEB-INF/")
        lines.append("│   │       │   ├── web.xml                   # Web config")
        lines.append("│   │       │   └── views/                    # JSP views")
        lines.append("│   │       │       ├── index.jsp             # Index page")
        lines.append("│   │       │       └── login.jsp             # Login page")
        lines.append("│   │       └── static/                       # Static assets")
        lines.append("│   │           ├── css/")
        lines.append("│   │           │   └── main.css              # Main styles")
        lines.append("│   │           ├── js/")
        lines.append("│   │           │   └── app.js                # Main script")
        lines.append("│   │           └── images/")
        lines.append("│   │               └── logo.png              # Logo image")
        lines.append("│   │")

        # Test source
        if self.metadata.has_tests:
            lines.append("│   └── test/")
            lines.append("│       ├── java/")
            lines.append("│       │   └── com/example/project/")
            lines.append("│       │       ├── controller/")
            lines.append("│       │       │   └── UserControllerTest.java")
            lines.append("│       │       ├── service/")
            lines.append("│       │       │   └── UserServiceTest.java")
            lines.append("│       │       └── repository/")
            lines.append("│       │           └── UserRepositoryTest.java")
            lines.append("│       └── resources/")
            lines.append("│           ├── application-test.yml      # Test config")
            lines.append("│           └── test-data.sql             # Test data")
            lines.append("│")

        # Scripts
        lines.append("├── scripts/                                # Automation scripts")
        lines.append("│   ├── build.sh                            # Build script")
        lines.append("│   ├── run-local.sh                        # Local run")
        lines.append("│   ├── deploy.sh                           # Deploy script")
        lines.append("│   └── cleanup.sh                          # Cleanup script")
        lines.append("│")

        # Build config files
        lines.append("├── pom.xml                                 # Maven config")
        lines.append("├── build.gradle                            # Gradle config")
        lines.append("├── settings.gradle                         # Gradle settings")
        lines.append("├── gradle.properties                       # Gradle properties")
        lines.append("├── gradlew                                 # Gradle wrapper")
        lines.append("└── gradlew.bat                             # Gradle wrapper (Win)")

        return "\n".join(lines) + "\n"

    def _build_cpp_structure(self) -> str:
        """Build detailed C/C++ project structure."""
        lines = []

        # Root files
        lines.append("├── .gitignore                              # Git ignore patterns")
        lines.append("├── README.md                               # Project documentation")
        lines.append("├── LICENSE                                 # Open source license")
        lines.append("├── CHANGELOG.md                            # Version history")
        lines.append("│")

        # Build directory
        lines.append("├── build/                                  # Build output")
        lines.append("│   ├── debug/                              # Debug build")
        lines.append("│   ├── release/                            # Release build")
        lines.append("│   └── CMakeFiles/                         # CMake cache")
        lines.append("│")

        # Documentation
        if self.metadata.has_docs_folder:
            lines.append("├── docs/                                   # Documentation")
            lines.append("│   ├── doxygen/                            # Doxygen output")
            lines.append("│   └── api/                                # API docs")
            lines.append("│")

        # Include headers
        lines.append("├── include/                                # Public headers")
        lines.append("│   └── project/")
        lines.append("│       ├── project.h                       # Main header")
        lines.append("│       ├── config.h                        # Config header")
        lines.append("│       ├── types.h                         # Type definitions")
        lines.append("│       └── utils/")
        lines.append("│           ├── string_utils.h              # String utilities")
        lines.append("│           └── math_utils.h                # Math utilities")
        lines.append("│")

        # Source files
        lines.append("├── src/                                    # Source files")
        lines.append("│   ├── main.cpp                            # Main entry point")
        lines.append("│   ├── project.cpp                         # Core implementation")
        lines.append("│   ├── config.cpp                          # Config handling")
        lines.append("│   ├── core/                               # Core modules")
        lines.append("│   │   ├── engine.cpp                      # Main engine")
        lines.append("│   │   ├── processor.cpp                   # Data processor")
        lines.append("│   │   └── validator.cpp                   # Validation")
        lines.append("│   └── utils/                              # Utility impl")
        lines.append("│       ├── string_utils.cpp                # String utils")
        lines.append("│       └── math_utils.cpp                  # Math utils")
        lines.append("│")

        # Libraries
        lines.append("├── lib/                                    # Libraries")
        lines.append("│   ├── static/                             # Static libs")
        lines.append("│   └── shared/                             # Shared libs")
        lines.append("│")

        # Tests
        if self.metadata.has_tests:
            lines.append("├── tests/                                  # Test files")
            lines.append("│   ├── CMakeLists.txt                      # Test build")
            lines.append("│   ├── main.cpp                            # Test main")
            lines.append("│   ├── test_core.cpp                       # Core tests")
            lines.append("│   ├── test_utils.cpp                      # Utils tests")
            lines.append("│   └── fixtures/                           # Test data")
            lines.append("│       └── test_data.json                  # Test fixtures")
            lines.append("│")

        # Third party
        lines.append("├── third_party/                            # Dependencies")
        lines.append("│   └── googletest/                         # Google Test")
        lines.append("│")

        # CMake modules
        lines.append("├── cmake/                                  # CMake modules")
        lines.append("│   ├── FindDependency.cmake                # Find scripts")
        lines.append("│   └── CompilerFlags.cmake                 # Compiler config")
        lines.append("│")

        # Scripts
        lines.append("├── scripts/                                # Build scripts")
        lines.append("│   ├── build.sh                            # Build script")
        lines.append("│   ├── test.sh                             # Test runner")
        lines.append("│   └── format.sh                           # Code formatter")
        lines.append("│")

        # Config files
        lines.append("├── CMakeLists.txt                          # CMake build")
        lines.append("├── Makefile                                # Make build")
        lines.append("├── conanfile.txt                           # Conan deps")
        lines.append("├── .clang-format                           # Format config")
        lines.append("└── .clang-tidy                             # Linter config")

        return "\n".join(lines) + "\n"

    def _build_go_structure(self) -> str:
        """Build detailed Go project structure."""
        lines = []

        # Root files
        lines.append("├── .gitignore                              # Git ignore patterns")
        lines.append("├── README.md                               # Project documentation")
        lines.append("├── LICENSE                                 # Open source license")
        lines.append("├── CHANGELOG.md                            # Version history")
        lines.append("│")

        # Commands
        lines.append("├── cmd/                                    # Application entrypoints")
        lines.append("│   ├── server/")
        lines.append("│   │   └── main.go                         # Server main")
        lines.append("│   └── cli/")
        lines.append("│       └── main.go                         # CLI main")
        lines.append("│")

        # Internal packages
        lines.append("├── internal/                               # Private packages")
        lines.append("│   ├── config/")
        lines.append("│   │   └── config.go                       # Config handling")
        lines.append("│   ├── handlers/")
        lines.append("│   │   ├── handlers.go                     # HTTP handlers")
        lines.append("│   │   └── middleware.go                   # Middleware")
        lines.append("│   ├── models/")
        lines.append("│   │   └── models.go                       # Data models")
        lines.append("│   ├── repository/")
        lines.append("│   │   └── repository.go                   # Data access")
        lines.append("│   └── service/")
        lines.append("│       └── service.go                      # Business logic")
        lines.append("│")

        # Public packages
        lines.append("├── pkg/                                    # Public packages")
        lines.append("│   ├── api/")
        lines.append("│   │   └── api.go                          # API definitions")
        lines.append("│   └── utils/")
        lines.append("│       └── utils.go                        # Utilities")
        lines.append("│")

        # API definitions
        lines.append("├── api/                                    # API specs")
        lines.append("│   ├── openapi.yaml                        # OpenAPI spec")
        lines.append("│   └── proto/                              # Protobuf")
        lines.append("│       └── service.proto                   # Service def")
        lines.append("│")

        # Web assets
        lines.append("├── web/                                    # Web assets")
        lines.append("│   ├── templates/")
        lines.append("│   │   └── index.html                      # HTML template")
        lines.append("│   └── static/")
        lines.append("│       ├── css/")
        lines.append("│       └── js/")
        lines.append("│")

        # Configs
        lines.append("├── configs/                                # Config files")
        lines.append("│   ├── config.yaml                         # Default config")
        lines.append("│   ├── config.dev.yaml                     # Dev config")
        lines.append("│   └── config.prod.yaml                    # Prod config")
        lines.append("│")

        # Scripts
        lines.append("├── scripts/                                # Scripts")
        lines.append("│   ├── build.sh                            # Build script")
        lines.append("│   ├── test.sh                             # Test script")
        lines.append("│   └── generate.sh                         # Code gen")
        lines.append("│")

        # Test data
        lines.append("├── testdata/                               # Test fixtures")
        lines.append("│   └── fixtures.json                       # Test data")
        lines.append("│")

        # Deployments
        lines.append("├── deployments/                            # Deploy configs")
        lines.append("│   ├── docker/")
        lines.append("│   │   └── Dockerfile                      # Docker build")
        lines.append("│   └── kubernetes/")
        lines.append("│       └── deployment.yaml                 # K8s manifest")
        lines.append("│")

        # Config files
        lines.append("├── go.mod                                  # Go modules")
        lines.append("├── go.sum                                  # Checksums")
        lines.append("├── Makefile                                # Make targets")
        lines.append("└── .golangci.yml                           # Linter config")

        return "\n".join(lines) + "\n"

    def _build_rust_structure(self) -> str:
        """Build detailed Rust project structure."""
        lines = []

        # Root files
        lines.append("├── .gitignore                              # Git ignore patterns")
        lines.append("├── README.md                               # Project documentation")
        lines.append("├── LICENSE                                 # Open source license")
        lines.append("├── CHANGELOG.md                            # Version history")
        lines.append("│")

        # Target directory
        lines.append("├── target/                                 # Build output")
        lines.append("│   ├── debug/                              # Debug builds")
        lines.append("│   └── release/                            # Release builds")
        lines.append("│")

        # Source
        lines.append("├── src/")
        lines.append("│   ├── lib.rs                              # Library root")
        lines.append("│   ├── main.rs                             # Binary entry")
        lines.append("│   │")
        lines.append("│   ├── bin/                                # Additional bins")
        lines.append("│   │   └── cli.rs                          # CLI binary")
        lines.append("│   │")
        lines.append("│   ├── config/")
        lines.append("│   │   ├── mod.rs                          # Config module")
        lines.append("│   │   └── settings.rs                     # Settings")
        lines.append("│   │")
        lines.append("│   ├── core/")
        lines.append("│   │   ├── mod.rs                          # Core module")
        lines.append("│   │   ├── engine.rs                       # Main engine")
        lines.append("│   │   └── processor.rs                    # Processor")
        lines.append("│   │")
        lines.append("│   ├── models/")
        lines.append("│   │   ├── mod.rs                          # Models module")
        lines.append("│   │   └── entities.rs                     # Entities")
        lines.append("│   │")
        lines.append("│   ├── utils/")
        lines.append("│   │   ├── mod.rs                          # Utils module")
        lines.append("│   │   └── helpers.rs                      # Helpers")
        lines.append("│   │")
        lines.append("│   └── error.rs                            # Error types")
        lines.append("│")

        # Tests
        lines.append("├── tests/                                  # Integration tests")
        lines.append("│   └── integration_test.rs                 # Integration")
        lines.append("│")

        # Benchmarks
        lines.append("├── benches/                                # Benchmarks")
        lines.append("│   └── benchmark.rs                        # Perf tests")
        lines.append("│")

        # Examples
        lines.append("├── examples/                               # Examples")
        lines.append("│   └── basic.rs                            # Basic example")
        lines.append("│")

        # Config files
        lines.append("├── Cargo.toml                              # Package manifest")
        lines.append("├── Cargo.lock                              # Locked deps")
        lines.append("├── rust-toolchain.toml                     # Toolchain")
        lines.append("├── rustfmt.toml                            # Format config")
        lines.append("└── clippy.toml                             # Clippy config")

        return "\n".join(lines) + "\n"

    def _build_generic_structure(self, pkg_name: str) -> str:
        """Build generic project structure for unknown languages."""
        lines = []

        # Root files
        lines.append("├── .gitignore                              # Git ignore patterns")
        lines.append("├── README.md                               # Project documentation")
        lines.append("├── LICENSE                                 # Open source license")
        lines.append("├── CHANGELOG.md                            # Version history")
        lines.append("├── CONTRIBUTING.md                         # Contribution guidelines")
        lines.append("│")

        # Source
        lines.append("├── src/                                    # Source code")
        lines.append("│   ├── main/                               # Main source")
        lines.append("│   │   └── ...                             # Implementation")
        lines.append("│   └── lib/                                # Library code")
        lines.append("│       └── ...                             # Modules")
        lines.append("│")

        # Tests
        if self.metadata.has_tests:
            lines.append("├── tests/                                  # Test suite")
            lines.append("│   ├── unit/                               # Unit tests")
            lines.append("│   └── integration/                        # Integration")
            lines.append("│")

        # Docs
        if self.metadata.has_docs_folder:
            lines.append("├── docs/                                   # Documentation")
            lines.append("│   ├── api/                                # API docs")
            lines.append("│   └── guides/                             # User guides")
            lines.append("│")

        # Config
        lines.append("├── config/                                 # Configuration")
        lines.append("│   └── ...                                 # Config files")
        lines.append("│")

        # Scripts
        lines.append("├── scripts/                                # Scripts")
        lines.append("│   ├── build.sh                            # Build")
        lines.append("│   └── test.sh                             # Test")
        lines.append("│")

        # Build output
        lines.append("└── build/                                  # Build output")
        lines.append("    └── ...                                 # Compiled files")

        return "\n".join(lines) + "\n"

    def _build_directory_overview_table(self, lang: str, pkg_name: str) -> str:
        """Build directory overview table for the project structure."""
        table = "\n### Directory Overview\n\n"
        table += "| Directory | Purpose |\n"
        table += "|-----------|--------|\n"

        if lang == "python":
            table += f"| `{pkg_name}/` | Main package containing all source modules |\n"
            table += f"| `{pkg_name}/cli/` | Command-line interface implementation |\n"
            table += f"| `{pkg_name}/core/` | Core business logic and processing |\n"
            table += f"| `{pkg_name}/models/` | Data models and schemas |\n"
            table += "| `tests/` | Unit and integration tests |\n"
        elif lang in ("javascript", "typescript"):
            table += "| `src/` | Source code directory |\n"
            table += "| `src/components/` | Reusable UI components |\n"
            table += "| `src/services/` | API clients and services |\n"
            table += "| `src/store/` | State management |\n"
            table += "| `dist/` | Compiled output |\n"
        elif lang == "java":
            table += "| `src/main/java/` | Java source files |\n"
            table += "| `src/main/resources/` | Configuration and resources |\n"
            table += "| `src/test/java/` | Test classes |\n"
            table += "| `target/` | Maven build output |\n"
            table += "| `build/` | Gradle build output |\n"
        elif lang in ("c", "c++", "cpp"):
            table += "| `src/` | Source files (.c, .cpp) |\n"
            table += "| `include/` | Public header files |\n"
            table += "| `tests/` | Test files |\n"
            table += "| `build/` | Build output |\n"
        elif lang == "go":
            table += "| `cmd/` | Application entry points |\n"
            table += "| `internal/` | Private packages |\n"
            table += "| `pkg/` | Public packages |\n"
            table += "| `api/` | API definitions |\n"
        elif lang == "rust":
            table += "| `src/` | Rust source files |\n"
            table += "| `tests/` | Integration tests |\n"
            table += "| `benches/` | Benchmarks |\n"
            table += "| `target/` | Build output |\n"
        else:
            table += "| `src/` | Source code |\n"
            table += "| `tests/` | Test files |\n"
            table += "| `docs/` | Documentation |\n"

        if self.metadata.has_docs_folder:
            table += "| `docs/` | Project documentation |\n"
        if self.metadata.has_examples:
            table += "| `examples/` | Usage examples |\n"

        return table

    def _add_configuration_section(self) -> None:
        """Add configuration section documenting config options."""
        if not self.options.include_configuration:
            return

        section = "## Configuration\n\n"

        # Check for config files in metadata
        config_files = self.metadata.config_files or []

        # Also check common config file patterns from entry points and dependencies
        common_configs = []
        for ep in self.metadata.entry_points:
            if "config" in ep.path.lower() or ".ini" in ep.path or ".yaml" in ep.path:
                common_configs.append(ep.path)

        all_configs = list(set(config_files + common_configs))

        if all_configs:
            section += "### Configuration Files\n\n"
            section += "| File | Purpose |\n"
            section += "|------|--------|\n"
            for cf in all_configs[:10]:
                section += f"| `{cf}` | Configuration settings |\n"
            section += "\n"

        # Environment variables section
        section += "### Environment Variables\n\n"

        # Check if we detected any environment variable references
        has_env_vars = False
        # Look for .env files in config files
        env_files = [cf for cf in all_configs if '.env' in cf.lower()]
        if env_files:
            has_env_vars = True
            section += "| Variable | Description | Default |\n"
            section += "|----------|-------------|----------|\n"
            section += "| *See `.env.example`* | *Environment template* | - |\n"
            section += "\n"

        if not has_env_vars:
            section += "No environment variables are required for basic usage.\n\n"

        self._add_section(section)

    def _add_architecture_section(self) -> None:
        """Add architecture/design overview section."""
        if not self.options.include_architecture:
            return

        section = "## Architecture\n\n"

        if self.metadata.architecture_summary:
            section += self.metadata.architecture_summary
            section += "\n\n"
        else:
            # Generate basic architecture from what we know
            components = []

            if self.metadata.entry_points:
                cli_count = len([e for e in self.metadata.entry_points if e.entry_type == "cli"])
                if cli_count:
                    components.append(f"CLI interface ({cli_count} commands)")

            if self.metadata.dependencies:
                key_deps = [d.name for d in self.metadata.dependencies[:5]]
                components.append(f"Core dependencies: {', '.join(key_deps)}")

            if components:
                section += "### Components\n\n"
                for comp in components:
                    section += f"- {comp}\n"
                section += "\n"
            else:
                section += self._format_placeholder(
                    "architecture overview",
                    "Describe major components, data flow, and key abstractions"
                )
                section += "\n"

        self._add_section(section)

    def _add_testing_section(self) -> None:
        """Add testing instructions if tests are detected."""
        if not self.metadata.has_tests:
            return

        section = "## Testing\n\n"

        # Detect test framework from dev dependencies
        test_frameworks = []
        for dep in self.metadata.dev_dependencies:
            dep_lower = dep.name.lower()
            if "pytest" in dep_lower:
                test_frameworks.append("pytest")
            elif "unittest" in dep_lower:
                test_frameworks.append("unittest")
            elif "jest" in dep_lower:
                test_frameworks.append("jest")
            elif "mocha" in dep_lower:
                test_frameworks.append("mocha")
            elif "junit" in dep_lower:
                test_frameworks.append("junit")

        # Provide test command based on detected framework or language
        lang = self.metadata.primary_language.value or ""

        if "pytest" in test_frameworks:
            section += "Run the test suite using pytest:\n\n"
            section += "```bash\n"
            section += "pytest\n"
            section += "```\n"
        elif "jest" in test_frameworks or lang.lower() == "javascript":
            section += "Run the test suite:\n\n"
            section += "```bash\n"
            section += "npm test\n"
            section += "```\n"
        elif lang.lower() == "python":
            section += "Run the test suite:\n\n"
            section += "```bash\n"
            section += "pytest\n"
            section += "# or\n"
            section += "python -m pytest\n"
            section += "```\n"
        elif lang.lower() == "java":
            section += "Run the test suite:\n\n"
            section += "```bash\n"
            section += "mvn test\n"
            section += "# or for Gradle\n"
            section += "gradle test\n"
            section += "```\n"
        else:
            section += "This project includes tests. "
            section += self._format_placeholder("testing instructions", "Add commands to run the test suite")
            section += "\n"

        self._add_section(section)

    def _add_dependencies_section(self) -> None:
        """Add dependencies section with validated versions."""
        deps = self.metadata.dependencies
        dev_deps = self.metadata.dev_dependencies

        if not deps and not dev_deps:
            # No dependencies to show
            return

        section = "## Dependencies\n\n"

        if deps:
            section += "### Runtime Dependencies\n\n"
            section += "| Package | Version | Source |\n"
            section += "|---------|---------|--------|\n"
            for dep in deps:
                # Never default to * - flag unknown versions explicitly
                if dep.version_constraint:
                    version = dep.version_constraint
                else:
                    version = "⚠️ Version unknown"
                source = dep.source or "detected"
                section += f"| {dep.name} | {version} | {source} |\n"
            section += "\n"

        if dev_deps:
            section += "### Development Dependencies\n\n"
            section += "| Package | Version | Source |\n"
            section += "|---------|---------|--------|\n"
            for dep in dev_deps:
                if dep.version_constraint:
                    version = dep.version_constraint
                else:
                    version = "⚠️ Version unknown"
                source = dep.source or "detected"
                section += f"| {dep.name} | {version} | {source} |\n"
            section += "\n"

        # Add note about unknown versions
        unknown_deps = [d for d in deps + dev_deps if not d.version_constraint]
        if unknown_deps:
            section += f"> **Note:** {len(unknown_deps)} dependencies have unknown versions. "
            section += "Manual verification required.\n\n"

        self._add_section(section)

    def _add_contributing_section(self) -> None:
        """Add contributing guidelines section."""
        # Only add if we have CI config or it's an open-source project (has license)
        if not (self.metadata.has_ci_config or self.metadata.license.value):
            return

        section = "## Contributing\n\n"
        section += "Contributions are welcome! Here's how you can help:\n\n"
        section += "1. Fork the repository\n"
        section += "2. Create a feature branch (`git checkout -b feature/amazing-feature`)\n"
        section += "3. Commit your changes (`git commit -m 'Add amazing feature'`)\n"
        section += "4. Push to the branch (`git push origin feature/amazing-feature`)\n"
        section += "5. Open a Pull Request\n"

        # Add CI note if detected
        if self.metadata.has_ci_config:
            section += "\nPlease ensure your code passes all CI checks before submitting.\n"

        self._add_section(section)

    def _add_license_section(self) -> None:
        """Add license information."""
        section = "## License\n\n"

        license_field = self.metadata.license

        if license_field.value and license_field.value.lower() not in ('none', 'unknown', 'custom'):
            section += f"This project is licensed under the **{license_field.value}** license."
            if self._needs_review(license_field):
                section += f"\n\n{self._format_review_marker(license_field)}"
            section += self._format_provenance(license_field)
        else:
            section += "No license information available.\n\n"
            section += "> ⚠️ **Note:** This project does not have a clearly identified license. "
            section += "Please check the repository for a LICENSE file or contact the maintainers "
            section += "before using this code in your projects."

        section += "\n"
        self._add_section(section)

    def _add_authors_section(self) -> None:
        """Add authors/maintainers section."""
        authors = self.metadata.authors

        if not authors:
            section = "## Authors\n\n"
            section += self._format_placeholder(
                "author information",
                "List the project authors and maintainers"
            )
            section += "\n"
            self._add_section(section)
            return

        section = "## Authors\n\n"

        for author in authors:
            if author.email:
                section += f"- **{author.name}** - {author.email}"
            else:
                section += f"- **{author.name}**"
            if author.role:
                section += f" ({author.role})"
            section += "\n"

        self._add_section(section)

    def _add_generation_notice(self) -> None:
        """Add notice about auto-generation and review encouragement."""
        if not self.options.include_generation_notice:
            return

        section = """---

## About This README

This README was automatically generated by [AutoDoc](https://github.com/divyajyoti/autodoc).

**Important**: This is a *draft* document. Please review and enhance it:

1. Verify all automatically extracted information is correct
2. Fill in any sections marked with `<!-- TODO: ... -->` comments
3. Add project-specific context, examples, and documentation
4. Review sections marked for low-confidence data
5. Remove this notice once you've reviewed the document

AutoDoc extracted metadata from your project files but cannot understand the
full context of your project. Human review is essential for quality documentation.
"""
        self._add_section(section)


def render_readme(
    metadata: ProjectMetadata,
    options: Optional[RenderOptions] = None,
) -> str:
    """
    Convenience function to render a README from metadata.

    Args:
        metadata: The extracted project metadata
        options: Optional rendering options

    Returns:
        Rendered README as a Markdown string

    Example:
        from autodoc.discovery import discover_files
        from autodoc.extractors import ExtractorRegistry, PythonExtractor
        from autodoc.renderer import render_readme

        # Extract metadata
        discovery = discover_files("/path/to/project")
        registry = ExtractorRegistry()
        registry.register(PythonExtractor())
        metadata = registry.extract_all(discovery, Path("/path/to/project"))

        # Render README
        readme_content = render_readme(metadata)
        print(readme_content)
    """
    renderer = ReadmeRenderer(metadata, options)
    return renderer.render()
