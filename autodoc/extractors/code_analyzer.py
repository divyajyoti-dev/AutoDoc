"""
Code Analyzer Extractor

This module analyzes source code files directly to extract metadata when
standard configuration files (package.json, pom.xml, etc.) are not available.

Features:
    - Detect imports/dependencies from source code
    - Identify main entry points from file patterns and content
    - Extract docstrings and comments for descriptions
    - Detect frameworks and libraries from code patterns
    - Analyze file structure for project organization

This extractor runs with lower priority and fills in gaps left by
language-specific extractors.
"""

import re
from collections import Counter
from pathlib import Path
from typing import Optional

from autodoc.discovery import DiscoveryResult, FileCategory
from autodoc.extractors.base import BaseExtractor
from autodoc.schema import (
    Confidence,
    Dependency,
    EntryPoint,
    MetadataField,
    ProjectMetadata,
)


class CodeAnalyzerExtractor(BaseExtractor):
    """
    Analyzes source code files to extract metadata.

    This extractor is language-agnostic and works by analyzing:
    - Import statements to detect dependencies
    - File patterns to detect entry points
    - Code patterns to detect frameworks
    - Comments and docstrings for descriptions

    Usage:
        extractor = CodeAnalyzerExtractor()
        metadata = extractor.extract(discovery_result, root_path)
    """

    name = "CodeAnalyzer"

    # Language extensions and their import patterns
    LANGUAGE_PATTERNS = {
        "Python": {
            "extensions": {".py"},
            "import_patterns": [
                r'^import\s+(\w+)',
                r'^from\s+(\w+)',
            ],
            "main_patterns": [
                r'if\s+__name__\s*==\s*["\']__main__["\']\s*:',
            ],
            "docstring_pattern": r'^"""([^"]*?)"""',
        },
        "JavaScript": {
            "extensions": {".js", ".mjs", ".cjs"},
            "import_patterns": [
                r'require\s*\(\s*["\']([^"\']+)["\']',
                r'import\s+.*?\s+from\s+["\']([^"\']+)["\']',
                r'import\s+["\']([^"\']+)["\']',
            ],
            "main_patterns": [],
            "docstring_pattern": r'^/\*\*([^*]*?)\*/',
        },
        "TypeScript": {
            "extensions": {".ts", ".tsx"},
            "import_patterns": [
                r'import\s+.*?\s+from\s+["\']([^"\']+)["\']',
                r'import\s+["\']([^"\']+)["\']',
            ],
            "main_patterns": [],
            "docstring_pattern": r'^/\*\*([^*]*?)\*/',
        },
        "Java": {
            "extensions": {".java"},
            "import_patterns": [
                r'^import\s+(?:static\s+)?([a-zA-Z_][\w.]*)',
            ],
            "main_patterns": [
                r'public\s+static\s+void\s+main\s*\(',
            ],
            "docstring_pattern": r'^/\*\*([^*]*?)\*/',
        },
        "C++": {
            "extensions": {".cpp", ".cc", ".cxx", ".hpp", ".hxx"},
            "import_patterns": [
                r'#include\s*<([^>]+)>',
                r'#include\s*"([^"]+)"',
            ],
            "main_patterns": [
                r'int\s+main\s*\(',
            ],
            "docstring_pattern": r'^/\*\*([^*]*?)\*/',
        },
        "C": {
            "extensions": {".c", ".h"},
            "import_patterns": [
                r'#include\s*<([^>]+)>',
                r'#include\s*"([^"]+)"',
            ],
            "main_patterns": [
                r'int\s+main\s*\(',
            ],
            "docstring_pattern": r'^/\*([^*]*?)\*/',
        },
        "Go": {
            "extensions": {".go"},
            "import_patterns": [
                r'import\s+"([^"]+)"',
                r'import\s+\(\s*"([^"]+)"',
            ],
            "main_patterns": [
                r'func\s+main\s*\(\s*\)',
            ],
            "docstring_pattern": r'^//\s*(.+)$',
        },
        "Rust": {
            "extensions": {".rs"},
            "import_patterns": [
                r'use\s+(\w+)',
                r'extern\s+crate\s+(\w+)',
            ],
            "main_patterns": [
                r'fn\s+main\s*\(\s*\)',
            ],
            "docstring_pattern": r'^///\s*(.+)$',
        },
        "Ruby": {
            "extensions": {".rb"},
            "import_patterns": [
                r'require\s+["\']([^"\']+)["\']',
                r'require_relative\s+["\']([^"\']+)["\']',
                r'gem\s+["\']([^"\']+)["\']',
            ],
            "main_patterns": [],
            "docstring_pattern": r'^#\s*(.+)$',
        },
    }

    # Known frameworks/libraries and their signatures
    FRAMEWORK_SIGNATURES = {
        "Flask": ["from flask import", "Flask(__name__)", "@app.route"],
        "Django": ["from django", "django.conf.settings", "INSTALLED_APPS"],
        "FastAPI": ["from fastapi import", "FastAPI()", "@app.get", "@app.post"],
        "React": ["import React", "from 'react'", "useState", "useEffect"],
        "Vue": ["import Vue", "from 'vue'", "createApp", "defineComponent"],
        "Angular": ["@angular/core", "@Component", "@NgModule"],
        "Express": ["require('express')", "from 'express'", "app.listen"],
        "Spring": ["org.springframework", "@SpringBootApplication", "@RestController"],
        "TensorFlow": ["import tensorflow", "from tensorflow", "tf.keras"],
        "PyTorch": ["import torch", "from torch", "nn.Module"],
        "NumPy": ["import numpy", "from numpy", "np.array"],
        "Pandas": ["import pandas", "from pandas", "pd.DataFrame"],
    }

    def can_handle(self, discovery_result: DiscoveryResult) -> bool:
        """Always returns True - this extractor can analyze any project."""
        return True

    def extract(
        self,
        discovery_result: DiscoveryResult,
        root_path: Path,
    ) -> ProjectMetadata:
        """
        Extract metadata by analyzing source code files.

        Args:
            discovery_result: The result of file discovery
            root_path: The repository root path

        Returns:
            ProjectMetadata with code-analysis-based information
        """
        self.root_path = root_path
        metadata = ProjectMetadata()

        # Detect languages from file extensions
        language_counts = self._count_languages(discovery_result)
        if language_counts:
            primary_lang = language_counts.most_common(1)[0][0]
            # Only set if not already set with high confidence
            if metadata.primary_language.is_placeholder():
                metadata.primary_language = MetadataField(
                    value=primary_lang,
                    confidence=Confidence.REASONABLE,
                    source="File extension analysis",
                    note=f"Based on {sum(language_counts.values())} source files",
                )

        # Analyze source files for imports/dependencies
        imports = self._analyze_imports(discovery_result, root_path)
        for imp_name, count in imports.most_common(20):
            # Filter out standard library and local imports
            if self._is_external_dependency(imp_name):
                dep = Dependency(
                    name=imp_name,
                    source="Code import analysis",
                )
                # Check for duplicates
                if not any(d.name == imp_name for d in metadata.dependencies):
                    metadata.dependencies.append(dep)

        # Detect frameworks from code patterns
        frameworks = self._detect_frameworks(discovery_result, root_path)
        if frameworks:
            note = f"Detected frameworks: {', '.join(frameworks)}"
            metadata.extraction_warnings.append(note)

        # Find entry points from main patterns
        entry_points = self._find_entry_points(discovery_result, root_path)
        for ep in entry_points:
            metadata.entry_points.append(ep)

        # Extract description from main file docstring
        description = self._extract_description(discovery_result, root_path)
        if description and metadata.description.is_placeholder():
            metadata.description = MetadataField(
                value=description,
                confidence=Confidence.REASONABLE,
                source="Code docstring analysis",
            )

        # Derive name from directory if not set
        if metadata.name.is_placeholder():
            # Use root directory name as project name
            metadata.name = MetadataField(
                value=root_path.name,
                confidence=Confidence.WEAK,
                source="Directory name",
                note="Derived from project directory",
            )

        return metadata

    def _count_languages(self, discovery_result: DiscoveryResult) -> Counter:
        """Count source files by programming language."""
        counts: Counter = Counter()

        for f in discovery_result.files:
            ext = f.path.suffix.lower()
            for lang, config in self.LANGUAGE_PATTERNS.items():
                if ext in config["extensions"]:
                    counts[lang] += 1
                    break

        return counts

    def _analyze_imports(
        self,
        discovery_result: DiscoveryResult,
        root_path: Path,
    ) -> Counter:
        """Analyze import statements across all source files."""
        imports: Counter = Counter()

        for f in discovery_result.files:
            ext = f.path.suffix.lower()

            # Find matching language
            lang_config = None
            for lang, config in self.LANGUAGE_PATTERNS.items():
                if ext in config["extensions"]:
                    lang_config = config
                    break

            if not lang_config:
                continue

            # Read file and extract imports
            try:
                content = f.path.read_text(errors="ignore")
                for pattern in lang_config["import_patterns"]:
                    for match in re.finditer(pattern, content, re.MULTILINE):
                        import_name = match.group(1)
                        # Get root module name
                        root_module = import_name.split(".")[0].split("/")[0]
                        if root_module and not root_module.startswith("."):
                            imports[root_module] += 1
            except Exception:
                pass

        return imports

    def _is_external_dependency(self, import_name: str) -> bool:
        """Check if an import is likely an external dependency."""
        # Standard library modules (common ones)
        stdlib = {
            "os", "sys", "re", "json", "typing", "collections", "itertools",
            "functools", "pathlib", "datetime", "time", "math", "random",
            "logging", "unittest", "io", "string", "copy", "pickle",
            "subprocess", "threading", "multiprocessing", "socket", "http",
            "urllib", "email", "html", "xml", "sqlite3", "csv", "hashlib",
            "base64", "struct", "codecs", "locale", "gettext", "argparse",
            "configparser", "abc", "contextlib", "dataclasses", "enum",
            "warnings", "traceback", "inspect", "ast", "dis", "gc",
            # C/C++ standard headers
            "stdio", "stdlib", "string", "math", "time", "ctype", "errno",
            "signal", "stdarg", "setjmp", "locale", "assert", "limits",
            "float", "stddef", "iostream", "vector", "map", "set", "list",
            "algorithm", "memory", "utility", "functional", "iterator",
            "cstdlib", "cstdio", "cstring", "cmath", "ctime",
            # Java standard packages
            "java", "javax", "sun",
            # Node.js built-ins
            "fs", "path", "http", "https", "crypto", "stream", "events",
            "buffer", "util", "os", "child_process", "cluster", "dgram",
            "dns", "domain", "net", "readline", "repl", "tls", "tty",
            "url", "vm", "zlib", "assert", "console", "process",
        }

        return import_name.lower() not in stdlib and len(import_name) > 1

    def _detect_frameworks(
        self,
        discovery_result: DiscoveryResult,
        root_path: Path,
    ) -> list[str]:
        """Detect frameworks/libraries from code patterns."""
        detected = []

        # Sample first 10 source files
        source_files = [
            f for f in discovery_result.files
            if f.path.suffix in {".py", ".js", ".ts", ".java", ".jsx", ".tsx"}
        ][:10]

        combined_content = ""
        for f in source_files:
            try:
                combined_content += f.path.read_text(errors="ignore")[:2000]
            except Exception:
                pass

        for framework, signatures in self.FRAMEWORK_SIGNATURES.items():
            for sig in signatures:
                if sig in combined_content:
                    detected.append(framework)
                    break

        return detected

    def _find_entry_points(
        self,
        discovery_result: DiscoveryResult,
        root_path: Path,
    ) -> list[EntryPoint]:
        """Find entry points by analyzing code patterns."""
        entry_points = []

        for f in discovery_result.files:
            ext = f.path.suffix.lower()

            # Find matching language
            lang_config = None
            lang_name = None
            for lang, config in self.LANGUAGE_PATTERNS.items():
                if ext in config["extensions"]:
                    lang_config = config
                    lang_name = lang
                    break

            if not lang_config or not lang_config["main_patterns"]:
                continue

            # Check for main patterns
            try:
                content = f.path.read_text(errors="ignore")
                for pattern in lang_config["main_patterns"]:
                    if re.search(pattern, content):
                        entry = EntryPoint(
                            path=str(f.relative_path),
                            entry_type="main",
                            confidence=Confidence.REASONABLE,
                            note=f"{lang_name} main entry point",
                        )
                        entry_points.append(entry)
                        break
            except Exception:
                pass

        return entry_points

    def _extract_description(
        self,
        discovery_result: DiscoveryResult,
        root_path: Path,
    ) -> Optional[str]:
        """Extract description from main file docstring."""
        # Priority files to check for docstrings
        priority_names = [
            "__init__.py", "main.py", "app.py", "index.py",
            "main.js", "index.js", "app.js",
            "Main.java", "App.java",
            "main.go", "main.rs",
        ]

        for f in discovery_result.files:
            if f.relative_path.name in priority_names:
                try:
                    content = f.path.read_text(errors="ignore")[:2000]

                    # Try to extract docstring based on language
                    ext = f.path.suffix.lower()

                    if ext == ".py":
                        # Python docstring
                        match = re.search(r'^"""(.*?)"""', content, re.DOTALL)
                        if not match:
                            match = re.search(r"^'''(.*?)'''", content, re.DOTALL)
                        if match:
                            docstring = match.group(1).strip()
                            # Take first paragraph
                            first_para = docstring.split("\n\n")[0].strip()
                            if len(first_para) > 20:
                                return first_para[:300]

                    elif ext in {".js", ".ts", ".java", ".jsx", ".tsx"}:
                        # JSDoc/JavaDoc style
                        match = re.search(r'/\*\*(.*?)\*/', content, re.DOTALL)
                        if match:
                            docstring = match.group(1).strip()
                            # Clean up * prefixes
                            lines = [
                                line.strip().lstrip("*").strip()
                                for line in docstring.split("\n")
                            ]
                            clean = " ".join(lines).strip()
                            if len(clean) > 20:
                                return clean[:300]

                except Exception:
                    pass

        return None
