"""
Flask-based Web API for AutoDoc.

Provides REST endpoints for README generation from uploaded repositories
or GitHub URLs.

Endpoints:
    POST /api/generate - Generate README from uploaded zip or GitHub URL
    GET /api/health - Health check endpoint
    GET /api/metadata - Get raw metadata without rendering
"""

import json
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, render_template, request

from autodoc.discovery import discover_files
from autodoc.extractors import (
    CodeAnalyzerExtractor,
    CppExtractor,
    ExtractorRegistry,
    GenericExtractor,
    JavaExtractor,
    JavaScriptExtractor,
    PythonExtractor,
)
from autodoc.github import GitHubEnhancer
from autodoc.llm import LLMEnhancer
from autodoc.renderer import ReadmeRenderer, RenderOptions
from autodoc.schema import Confidence, ProjectMetadata

# Create Flask application with template folder
template_dir = Path(__file__).parent / "templates"
app = Flask(__name__, template_folder=str(template_dir))
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB max upload


def create_extractor_registry() -> ExtractorRegistry:
    """Create and configure the extractor registry with all available extractors."""
    registry = ExtractorRegistry()
    registry.register(GenericExtractor())  # Language-agnostic (LICENSE, git, etc.)
    registry.register(PythonExtractor())   # Python projects
    registry.register(JavaScriptExtractor())  # JavaScript/Node.js projects
    registry.register(JavaExtractor())     # Java (Maven/Gradle) projects
    registry.register(CppExtractor())      # C/C++ projects
    registry.register(CodeAnalyzerExtractor())  # Fallback: analyze source code directly
    return registry


def metadata_to_dict(metadata: ProjectMetadata) -> dict[str, Any]:
    """
    Convert ProjectMetadata to a JSON-serializable dictionary.

    Handles the conversion of Confidence enums and nested dataclasses.
    """
    result: dict[str, Any] = {}

    # Convert MetadataField attributes
    field_names = [
        "name",
        "description",
        "version",
        "license",
        "python_version",
        "primary_language",
        "repository_url",
        "homepage_url",
    ]

    for field_name in field_names:
        field = getattr(metadata, field_name)
        result[field_name] = {
            "value": field.value,
            "confidence": field.confidence.name,
            "confidence_score": field.confidence.value,
            "source": field.source,
            "note": field.note,
            "is_placeholder": field.is_placeholder(),
            "needs_review": field.needs_review(),
        }

    # Convert lists
    result["authors"] = [asdict(a) for a in metadata.authors]
    result["dependencies"] = [
        {
            "name": d.name,
            "version_constraint": d.version_constraint,
            "is_dev": d.is_dev,
            "source": d.source,
        }
        for d in metadata.dependencies
    ]
    result["dev_dependencies"] = [
        {
            "name": d.name,
            "version_constraint": d.version_constraint,
            "is_dev": d.is_dev,
            "source": d.source,
        }
        for d in metadata.dev_dependencies
    ]
    result["entry_points"] = [
        {
            "path": e.path,
            "entry_type": e.entry_type,
            "command": e.command,
            "confidence": e.confidence.name if e.confidence else None,
        }
        for e in metadata.entry_points
    ]

    # Boolean flags
    result["has_tests"] = metadata.has_tests
    result["has_ci_config"] = metadata.has_ci_config
    result["has_docs_folder"] = metadata.has_docs_folder

    return result


def clone_github_repo(github_url: str, target_dir: Path) -> None:
    """
    Clone a GitHub repository to a target directory.

    Args:
        github_url: The GitHub repository URL (HTTPS or SSH).
        target_dir: The directory to clone into.

    Raises:
        ValueError: If git clone fails.
    """
    # Normalize URL (ensure .git suffix for cloning)
    if not github_url.endswith(".git"):
        github_url = github_url.rstrip("/") + ".git"

    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", github_url, str(target_dir)],
            check=True,
            capture_output=True,
            timeout=60,
        )
    except subprocess.CalledProcessError as e:
        raise ValueError(f"Failed to clone repository: {e.stderr.decode()}")
    except subprocess.TimeoutExpired:
        raise ValueError("Repository clone timed out (60s limit)")


def extract_zip(zip_file, target_dir: Path) -> None:
    """
    Extract a zip file to a target directory.

    Args:
        zip_file: The uploaded zip file object.
        target_dir: The directory to extract into.

    Raises:
        ValueError: If extraction fails or zip is invalid.
    """
    try:
        with zipfile.ZipFile(zip_file, "r") as zf:
            # Security check: prevent path traversal
            for member in zf.namelist():
                member_path = Path(member)
                if member_path.is_absolute() or ".." in member_path.parts:
                    raise ValueError(f"Invalid path in zip: {member}")
            zf.extractall(target_dir)
    except zipfile.BadZipFile:
        raise ValueError("Invalid or corrupted zip file")


def find_project_root(extracted_dir: Path) -> Path:
    """
    Find the actual project root after extraction.

    Many zip files contain a single top-level directory (e.g., repo-main/).
    This function finds the actual project root.

    Args:
        extracted_dir: The directory where files were extracted.

    Returns:
        The path to the project root directory.
    """
    contents = list(extracted_dir.iterdir())

    # If there's exactly one directory and no files, descend into it
    if len(contents) == 1 and contents[0].is_dir():
        return contents[0]

    return extracted_dir


def process_project(
    project_path: Path,
    options: RenderOptions,
    github_url: str | None = None,
    use_llm: bool = True,
) -> tuple[str, dict[str, Any]]:
    """
    Process a project directory and generate README content.

    Args:
        project_path: Path to the project directory.
        options: Render options for the README.
        github_url: Optional GitHub URL for fetching additional metadata.
        use_llm: Whether to use LLM for enhancing descriptions (default: True).

    Returns:
        Tuple of (rendered_readme, metadata_dict).
    """
    # Discover files
    discovery_result = discover_files(project_path)

    # Extract metadata from files
    registry = create_extractor_registry()
    metadata = registry.extract_all(discovery_result, project_path)

    # Enhance with GitHub data (contributors, languages, description)
    if github_url:
        try:
            github_enhancer = GitHubEnhancer()
            github_enhancer.enhance(metadata, github_url)
        except Exception as e:
            metadata.extraction_warnings.append(f"GitHub enhancement failed: {e}")

    # Enhance with LLM-generated content (descriptions, usage examples)
    if use_llm:
        try:
            llm_enhancer = LLMEnhancer()
            if llm_enhancer.is_available():
                # Collect code samples for context
                code_samples = _collect_code_samples(discovery_result, project_path)
                # Read existing README if present
                existing_readme = _read_existing_readme(project_path)
                llm_enhancer.enhance(metadata, code_samples, existing_readme)
        except Exception as e:
            metadata.extraction_warnings.append(f"LLM enhancement failed: {e}")

    # Render README
    renderer = ReadmeRenderer(metadata, options)
    readme_content = renderer.render()

    # Convert metadata to dict
    metadata_dict = metadata_to_dict(metadata)
    metadata_dict["discovery"] = {
        "total_files": discovery_result.total_file_count,
        "exceeded_limit": discovery_result.exceeded_limit,
        "warnings": discovery_result.warnings + metadata.extraction_warnings,
        "category_counts": {
            cat.name: count for cat, count in discovery_result.get_category_counts().items()
        },
    }

    return readme_content, metadata_dict


def _collect_code_samples(discovery_result, project_path: Path) -> dict[str, str]:
    """Collect code samples from key files for LLM context."""
    samples = {}

    # Priority files to read for context
    priority_files = [
        "main.py", "app.py", "index.py", "__init__.py",
        "main.js", "index.js", "app.js",
        "main.ts", "index.ts", "app.ts",
        "Main.java", "App.java",
        "main.c", "main.cpp", "main.cc",
    ]

    for f in discovery_result.files:
        if f.relative_path.name in priority_files:
            try:
                content = f.path.read_text(errors="ignore")[:1000]  # First 1000 chars
                samples[str(f.relative_path)] = content
            except Exception:
                pass

        # Limit to 5 samples
        if len(samples) >= 5:
            break

    return samples


def _read_existing_readme(project_path: Path) -> str | None:
    """Read existing README if present."""
    readme_names = ["README.md", "README.rst", "README.txt", "README"]
    for name in readme_names:
        readme_path = project_path / name
        if readme_path.exists():
            try:
                return readme_path.read_text(errors="ignore")
            except Exception:
                pass
    return None


@app.route("/")
def index():
    """Serve the web interface."""
    return render_template("index.html")


@app.route("/api/health", methods=["GET"])
def health_check() -> Response:
    """Health check endpoint."""
    return jsonify({"status": "healthy", "version": "0.1.0"})


@app.route("/api/generate", methods=["POST"])
def generate_readme() -> tuple[Response, int]:
    """
    Generate a README from an uploaded zip file or GitHub URL.

    Request can be:
        - multipart/form-data with 'file' field containing a zip
        - JSON with 'github_url' field

    Optional parameters (query string or JSON):
        - include_badges: bool (default: false)
        - include_toc: bool (default: false)
        - include_provenance: bool (default: false)
        - include_generation_notice: bool (default: true)
        - format: 'markdown' | 'json' | 'both' (default: 'both')

    Returns:
        JSON response with:
            - readme: The generated README content (if format includes markdown)
            - metadata: The extracted metadata (if format includes json)
            - warnings: Any warnings from processing
    """
    # Parse options from request
    if request.is_json:
        data = request.get_json()
        github_url = data.get("github_url")
        include_badges = data.get("include_badges", False)
        include_toc = data.get("include_toc", False)
        include_provenance = data.get("include_provenance", False)
        include_generation_notice = data.get("include_generation_notice", True)
        output_format = data.get("format", "both")
    else:
        github_url = request.form.get("github_url")
        include_badges = request.args.get("include_badges", "false").lower() == "true"
        include_toc = request.args.get("include_toc", "false").lower() == "true"
        include_provenance = request.args.get("include_provenance", "false").lower() == "true"
        include_generation_notice = (
            request.args.get("include_generation_notice", "true").lower() == "true"
        )
        output_format = request.args.get("format", "both")

    render_options = RenderOptions(
        include_badges=include_badges,
        include_toc=include_toc,
        include_provenance=include_provenance,
        include_generation_notice=include_generation_notice,
    )

    # Create temporary directory for processing
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        project_path = tmppath / "project"
        project_path.mkdir()

        try:
            # Handle GitHub URL
            if github_url:
                clone_github_repo(github_url, project_path)
            # Handle file upload
            elif "file" in request.files:
                uploaded_file = request.files["file"]
                if not uploaded_file.filename:
                    return jsonify({"error": "No file selected"}), 400

                if not uploaded_file.filename.endswith(".zip"):
                    return jsonify({"error": "Only .zip files are supported"}), 400

                extract_zip(uploaded_file, project_path)
                project_path = find_project_root(project_path)
            else:
                return (
                    jsonify(
                        {"error": "Either 'github_url' or 'file' upload required"}
                    ),
                    400,
                )

            # Process the project (pass github_url for GitHub API enhancement)
            readme_content, metadata_dict = process_project(
                project_path, render_options, github_url=github_url
            )

            # Build response based on format
            response_data: dict[str, Any] = {"success": True}

            if output_format in ("markdown", "both"):
                response_data["readme"] = readme_content

            if output_format in ("json", "both"):
                response_data["metadata"] = metadata_dict

            response_data["warnings"] = metadata_dict.get("discovery", {}).get("warnings", [])

            return jsonify(response_data), 200

        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": f"Processing failed: {str(e)}"}), 500


@app.route("/api/metadata", methods=["POST"])
def get_metadata() -> tuple[Response, int]:
    """
    Get raw metadata without rendering to README.

    Same input options as /api/generate but only returns metadata.
    Useful for integrations that want to process the metadata themselves.
    """
    # This endpoint reuses generate but forces json format
    if request.is_json:
        data = request.get_json() or {}
        data["format"] = "json"
        # Temporarily modify request data
        original_data = request.data
        request._cached_data = json.dumps(data).encode()

    return generate_readme()


@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file too large errors."""
    return jsonify({"error": "File too large. Maximum size is 50MB."}), 413


@app.errorhandler(500)
def internal_server_error(error):
    """Handle internal server errors."""
    return jsonify({"error": "Internal server error"}), 500


def create_app() -> Flask:
    """
    Application factory for creating the Flask app.

    This allows for easier testing and configuration.

    Returns:
        Configured Flask application instance.
    """
    return app


def main() -> None:
    """Run the development server."""
    print("Starting AutoDoc API server...")
    print()
    print("Web Interface: http://localhost:5001")
    print()
    print("API Endpoints:")
    print("  POST /api/generate - Generate README from zip or GitHub URL")
    print("  POST /api/metadata - Get raw metadata only")
    print("  GET  /api/health   - Health check")
    print()
    app.run(host="0.0.0.0", port=5001, debug=True)


if __name__ == "__main__":
    main()
