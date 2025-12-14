# AutoDoc

A lightweight, metadata-driven documentation tool that automatically generates structured README.md files for software repositories by extracting and organizing project metadata.

## Overview

AutoDoc analyzes a repository's files to extract structured information (dependencies, license, entry points, etc.) and generates a README.md following established documentation best practices.

AutoDoc produces an initial draft that requires human review, not a final document. The goal is to formalize what information belongs in a good README and automate the tedious parts of gathering that information.

## Features

- **Metadata Extraction**: Parses package manifests (pyproject.toml, setup.py, package.json) to extract project information
- **Confidence Scoring**: Each extracted field includes a confidence level indicating reliability
- **Multi-Language Support**: Python, JavaScript, Java, C++, Go, Rust extractors with language-specific project structures
- **Flexible Output**: CLI tool, REST API, and web interface
- **Human-in-the-Loop**: Generates placeholders for missing information and marks low-confidence data for review

## Installation

```bash
# Clone the repository
git clone https://github.com/divyajyoti/autodoc
cd AutoDoc

# Install the package
pip install .

# Or install in development mode
pip install -e .
```

### Requirements

- Python 3.10 or higher
- Optional: Flask for API functionality (`pip install -e ".[api]"`)

## Usage

### Command Line

```bash
# Generate README for current directory
autodoc .

# Generate README for a specific repository
autodoc /path/to/repository

# Preview without writing (dry-run)
autodoc . --dry-run

# Generate with badges and table of contents
autodoc . --badges --toc

# Custom output location
autodoc . --output docs/README.md
```

### CLI Options

```
autodoc [path] [options]

Options:
  -o, --output PATH   Write to custom path (default: README.md in repo root)
  --dry-run           Print to stdout instead of writing file
  --force             Overwrite existing README without prompting
  --badges            Include shields.io badges
  --toc               Include table of contents
  --no-notice         Omit generation notice
  --provenance        Add source comments
  -v, --verbose       Show detailed progress
  -q, --quiet         Suppress non-error output
  --version           Show version
  --help              Show help
```

### Programmatic Usage

```python
from pathlib import Path
from autodoc.discovery import discover_files
from autodoc.extractors import ExtractorRegistry, PythonExtractor
from autodoc.renderer import render_readme, RenderOptions

# Discover and extract
root = Path("/path/to/project")
discovery = discover_files(root)

registry = ExtractorRegistry()
registry.register(PythonExtractor())
metadata = registry.extract_all(discovery, root)

# Render with options
options = RenderOptions(include_badges=True)
readme_content = render_readme(metadata, options)
print(readme_content)
```

### Web API

AutoDoc provides a REST API and web interface for generating READMEs over HTTP.

```bash
# Install with API dependencies
pip install -e ".[api]"

# Start the server
autodoc-api
```

The server runs on `http://localhost:5001`. Open in browser for the web interface, or use the API:

```bash
# From GitHub URL
curl -X POST http://localhost:5001/api/generate \
  -H "Content-Type: application/json" \
  -d '{"github_url": "https://github.com/example/repo"}'

# From zip file
curl -X POST http://localhost:5001/api/generate \
  -F "file=@myproject.zip"
```

## Architecture

### Pipeline

```
File Discovery → Metadata Extraction → Schema Normalization → Markdown Rendering
```

1. **File Discovery**: Walks directory tree, respects .gitignore, categorizes files
2. **Metadata Extraction**: Language-specific extractors parse package manifests
3. **Schema Normalization**: Maps to unified schema with confidence scoring
4. **Markdown Rendering**: Generates README with conditional sections

### Confidence Scoring

Every extracted field carries a confidence score:

| Level | Value | Meaning |
|-------|-------|---------|
| EXPLICIT | 1.0 | Directly stated in a file |
| STRONG | 0.8 | Strongly inferred |
| REASONABLE | 0.6 | Reasonably inferred |
| WEAK | 0.4 | Weakly inferred |
| GUESS | 0.2 | Educated guess |
| UNKNOWN | 0.0 | Placeholder needed |

### Module Structure

```
autodoc/
├── __init__.py         # Package initialization
├── api.py              # Flask REST API
├── cli.py              # Command-line interface
├── discovery.py        # File discovery and traversal
├── extractors/         # Metadata extraction modules
│   ├── base.py         # Base extractor interface
│   ├── python.py       # Python-specific extraction
│   ├── javascript.py   # JavaScript/TypeScript extraction
│   ├── java.py         # Java extraction
│   ├── cpp.py          # C/C++ extraction
│   └── generic.py      # Language-agnostic extraction
├── schema.py           # Unified metadata schema
└── renderer.py         # Markdown template rendering
```

## Supported Languages

| Language | Package Manifest | Confidence |
|----------|-----------------|------------|
| Python | pyproject.toml, setup.py, setup.cfg, requirements.txt | High |
| JavaScript | package.json | High |
| Java | pom.xml, build.gradle | High|
| C/C++ | CMakeLists.txt, Makefile | Medium |
| Go | go.mod | Medium |
| Rust | Cargo.toml | Medium |

## Limitations

- Designed for small to medium repositories (10-500 files)
- Relies on heuristics and common conventions
- Cannot analyze runtime behavior or dynamic configurations
- Human review recommended for generated content

## License

MIT License

Copyright (c) 2025 Divya Jyoti

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Author

Divya Jyoti
