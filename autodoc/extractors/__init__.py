"""
Metadata extractors for different file types and languages.

This package contains extractors that parse project files and produce
ProjectMetadata objects. Each extractor is specialized for a particular
language ecosystem or file type.

Available Extractors:
    - GenericExtractor: Language-agnostic extraction (LICENSE, git remote, etc.)
    - PythonExtractor: Parses pyproject.toml, setup.py, setup.cfg, requirements.txt
    - JavaScriptExtractor: Parses package.json for Node.js/npm projects
    - JavaExtractor: Parses pom.xml, build.gradle for Maven/Gradle projects
    - CppExtractor: Parses CMakeLists.txt, Makefile for C/C++ projects
    - CodeAnalyzerExtractor: Analyzes source code directly for imports, entry points

Usage:
    from autodoc.extractors import ExtractorRegistry, PythonExtractor, GenericExtractor

    registry = ExtractorRegistry()
    registry.register(GenericExtractor())  # Run first for fallback values
    registry.register(PythonExtractor())   # Language-specific (higher confidence)
    registry.register(JavaScriptExtractor())
    registry.register(JavaExtractor())
    registry.register(CppExtractor())
    registry.register(CodeAnalyzerExtractor())  # Fallback code analysis

    metadata = registry.extract_all(discovery_result, root_path)
"""

from autodoc.extractors.base import BaseExtractor, ExtractorRegistry
from autodoc.extractors.code_analyzer import CodeAnalyzerExtractor
from autodoc.extractors.cpp import CppExtractor
from autodoc.extractors.generic import GenericExtractor
from autodoc.extractors.java import JavaExtractor
from autodoc.extractors.javascript import JavaScriptExtractor
from autodoc.extractors.python import PythonExtractor

__all__ = [
    "BaseExtractor",
    "CodeAnalyzerExtractor",
    "CppExtractor",
    "ExtractorRegistry",
    "GenericExtractor",
    "JavaExtractor",
    "JavaScriptExtractor",
    "PythonExtractor",
]
