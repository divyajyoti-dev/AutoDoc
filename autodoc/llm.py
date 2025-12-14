"""
LLM Integration for AutoDoc.

This module provides AI-powered enhancement of extracted metadata using
Large Language Models (Groq, Gemini, Claude, or OpenAI).

Features:
    - Generate project descriptions from code analysis
    - Create usage examples based on entry points
    - Summarize project purpose from README fragments
    - Enhance low-confidence fields

Supported Providers:
    - Groq (default - free, fast)
    - Google Gemini (free tier available)
    - Anthropic Claude
    - OpenAI GPT models

Environment Variables:
    - GROQ_API_KEY: API key for Groq (default, free at console.groq.com)
    - GOOGLE_API_KEY: API key for Gemini
    - ANTHROPIC_API_KEY: API key for Claude
    - OPENAI_API_KEY: API key for OpenAI

Note: LLM features are optional. AutoDoc works without them but produces
more placeholder content.
"""

import os
from pathlib import Path
from typing import Optional

from autodoc.schema import Confidence, MetadataField, ProjectMetadata


class LLMProvider:
    """
    Abstract interface for LLM providers.

    This allows swapping between different LLM backends while maintaining
    a consistent interface for the rest of AutoDoc.
    """

    def generate(self, prompt: str, max_tokens: int = 500) -> Optional[str]:
        """
        Generate text from a prompt.

        Args:
            prompt: The prompt to send to the LLM
            max_tokens: Maximum tokens in response

        Returns:
            Generated text, or None if generation failed
        """
        raise NotImplementedError


class ClaudeProvider(LLMProvider):
    """Claude API provider using the Anthropic SDK."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.client = None

        if self.api_key:
            try:
                from anthropic import Anthropic
                self.client = Anthropic(api_key=self.api_key)
            except ImportError:
                pass

    def is_available(self) -> bool:
        """Check if Claude is available."""
        return self.client is not None

    def generate(self, prompt: str, max_tokens: int = 500) -> Optional[str]:
        """Generate text using Claude."""
        if not self.client:
            return None

        try:
            response = self.client.messages.create(
                model="claude-3-haiku-20240307",  # Fast and cheap for simple tasks
                max_tokens=max_tokens,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.content[0].text
        except Exception as e:
            print(f"Claude API error: {e}")
            return None


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.client = None

        if self.api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
            except ImportError:
                pass

    def is_available(self) -> bool:
        """Check if OpenAI is available."""
        return self.client is not None

    def generate(self, prompt: str, max_tokens: int = 500) -> Optional[str]:
        """Generate text using OpenAI."""
        if not self.client:
            return None

        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",  # Fast and cheap
                max_tokens=max_tokens,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"OpenAI API error: {e}")
            return None


class GroqProvider(LLMProvider):
    """Groq API provider (free, very fast)."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self._available = bool(self.api_key)

    def is_available(self) -> bool:
        """Check if Groq is available."""
        return self._available

    def generate(self, prompt: str, max_tokens: int = 500) -> Optional[str]:
        """Generate text using Groq API."""
        if not self.api_key:
            return None

        import json
        import urllib.request
        import urllib.error

        url = "https://api.groq.com/openai/v1/chat/completions"

        payload = {
            "model": "llama-3.1-8b-instant",  # Fast, free model
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode())
                choices = result.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ""
            print(f"Groq API HTTP error {e.code}: {error_body[:200]}")
        except Exception as e:
            print(f"Groq API error: {e}")

        return None


class GeminiProvider(LLMProvider):
    """Google Gemini API provider (free tier available)."""

    # Default API key for AutoDoc (free tier)
    DEFAULT_API_KEY = "AIzaSyBZ7kR01WH8yP9pqN1YMarp7htYYP9pEDs"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY") or self.DEFAULT_API_KEY
        self.model = None

        if self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel("gemini-1.5-flash")
            except ImportError:
                # Try using requests directly if google-generativeai not installed
                self._use_requests = True
            except Exception:
                pass

    def is_available(self) -> bool:
        """Check if Gemini is available."""
        return self.model is not None or (hasattr(self, '_use_requests') and self._use_requests)

    def generate(self, prompt: str, max_tokens: int = 500) -> Optional[str]:
        """Generate text using Gemini."""
        # Try using the SDK first
        if self.model:
            try:
                response = self.model.generate_content(
                    prompt,
                    generation_config={
                        "max_output_tokens": max_tokens,
                        "temperature": 0.7,
                    }
                )
                return response.text
            except Exception as e:
                print(f"Gemini API error: {e}")
                return None

        # Fallback to direct HTTP requests
        if hasattr(self, '_use_requests') and self._use_requests:
            return self._generate_via_requests(prompt, max_tokens)

        return None

    def _generate_via_requests(self, prompt: str, max_tokens: int) -> Optional[str]:
        """Generate text using direct HTTP requests to Gemini API."""
        import json
        import urllib.request
        import urllib.error

        # Use gemini-2.0-flash-lite for better rate limits
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent?key={self.api_key}"

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": 0.7,
            }
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode())
                # Extract text from response
                candidates = result.get("candidates", [])
                if candidates:
                    content = candidates[0].get("content", {})
                    parts = content.get("parts", [])
                    if parts:
                        return parts[0].get("text", "")
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ""
            print(f"Gemini API HTTP error {e.code}: {error_body[:200]}")
        except Exception as e:
            print(f"Gemini API error: {e}")

        return None


class LLMEnhancer:
    """
    Enhances ProjectMetadata using LLM-generated content.

    This class coordinates LLM calls to fill in missing metadata fields
    that cannot be extracted from files alone.

    Usage:
        enhancer = LLMEnhancer()
        if enhancer.is_available():
            enhanced_metadata = enhancer.enhance(metadata, code_samples)
    """

    def __init__(self):
        """Initialize with available LLM provider."""
        self.provider: Optional[LLMProvider] = None

        # Try providers in order: Groq (free), Gemini (free), Claude, OpenAI
        groq = GroqProvider()
        if groq.is_available():
            self.provider = groq
        else:
            gemini = GeminiProvider()
            if gemini.is_available():
                self.provider = gemini
            else:
                claude = ClaudeProvider()
                if claude.is_available():
                    self.provider = claude
                else:
                    openai = OpenAIProvider()
                    if openai.is_available():
                        self.provider = openai

    def is_available(self) -> bool:
        """Check if any LLM provider is available."""
        return self.provider is not None

    def get_provider_name(self) -> str:
        """Get the name of the active provider."""
        if isinstance(self.provider, GroqProvider):
            return "Groq"
        elif isinstance(self.provider, GeminiProvider):
            return "Gemini"
        elif isinstance(self.provider, ClaudeProvider):
            return "Claude"
        elif isinstance(self.provider, OpenAIProvider):
            return "OpenAI"
        return "None"

    def enhance(
        self,
        metadata: ProjectMetadata,
        code_samples: dict[str, str],
        existing_readme: Optional[str] = None,
    ) -> ProjectMetadata:
        """
        Enhance metadata with LLM-generated content.

        Args:
            metadata: The extracted metadata to enhance
            code_samples: Dict of filename -> code content for context
            existing_readme: Existing README content if available

        Returns:
            Enhanced ProjectMetadata (modified in place)
        """
        if not self.provider:
            return metadata

        # Generate description if missing or too generic
        if self._needs_better_description(metadata.description):
            description = self._generate_description(metadata, code_samples, existing_readme)
            if description:
                metadata.description = MetadataField(
                    value=description,
                    confidence=Confidence.REASONABLE,
                    source=f"LLM ({self.get_provider_name()})",
                    note="AI-generated description - please review for accuracy",
                )

        # Generate key features if not present
        if not metadata.key_features:
            features = self.generate_key_features(metadata, code_samples)
            if features:
                metadata.key_features = features

        # Generate architecture summary if not present
        if not metadata.architecture_summary:
            arch = self.generate_architecture_summary(metadata, code_samples)
            if arch:
                metadata.architecture_summary = arch

        return metadata

    def _needs_better_description(self, desc_field: MetadataField) -> bool:
        """Check if the description is missing or too generic to be useful."""
        if desc_field.is_placeholder():
            return True

        if not desc_field.value:
            return True

        value = desc_field.value.lower().strip()

        # Too short to be meaningful
        if len(value) < 20:
            return True

        # Generic/unhelpful descriptions
        generic_patterns = [
            "final year",
            "major project",
            "minor project",
            "college project",
            "school project",
            "university project",
            "academic project",
            "demo project",
            "test project",
            "sample project",
            "example project",
            "my project",
            "a project",
            "this is a",
            "todo",
            "work in progress",
            "wip",
            "under construction",
            "coming soon",
            # Overly generic descriptions
            "generic python",
            "generic tools",
            "python tools",
            "utility functions",
            "misc utilities",
            "miscellaneous",
            "various tools",
            "helper functions",
            "common utilities",
            "scripts and tools",
            "collection of",
            "set of tools",
            "bunch of",
        ]

        for pattern in generic_patterns:
            if pattern in value:
                return True

        return False

    def _generate_description(
        self,
        metadata: ProjectMetadata,
        code_samples: dict[str, str],
        existing_readme: Optional[str],
    ) -> Optional[str]:
        """Generate a project description using LLM."""
        # Build context for the LLM
        context_parts = []

        # Add project name
        if metadata.name.value:
            context_parts.append(f"Project name: {metadata.name.value}")

        # Add primary language
        if metadata.primary_language.value:
            context_parts.append(f"Language: {metadata.primary_language.value}")

        # Add dependencies as hints
        if metadata.dependencies:
            deps = [d.name for d in metadata.dependencies[:10]]  # Limit to 10
            context_parts.append(f"Dependencies: {', '.join(deps)}")

        # Add existing README fragments
        if existing_readme:
            # Extract first 500 chars of existing README
            readme_preview = existing_readme[:500].strip()
            if readme_preview:
                context_parts.append(f"Existing README preview:\n{readme_preview}")

        # Add code samples (limited, skip binary files)
        samples_added = 0
        for filename, code in code_samples.items():
            if samples_added >= 3:
                break
            # Skip binary/non-text content
            if not code or '\x00' in code[:500]:
                continue
            # Skip non-code files
            if any(filename.endswith(ext) for ext in ['.sqlite3', '.db', '.pyc', '.so', '.dll']):
                continue
            # Take first 300 chars of each file
            code_preview = code[:300].strip()
            if code_preview:
                context_parts.append(f"File {filename}:\n```\n{code_preview}\n```")
                samples_added += 1

        context = "\n\n".join(context_parts)

        prompt = f"""You are writing a comprehensive README description for a software project. Based on the project information below, write a detailed description (5-7 sentences) that covers:

1. What the project does (its main purpose and core functionality)
2. Who would use it (target audience: developers, data scientists, etc.)
3. What problem it solves or what value it provides
4. Key technical approach or methodology used
5. Any notable constraints, requirements, or assumptions

Project Information:
{context}

IMPORTANT: Write ONLY plain text description as a cohesive paragraph. No bullet points, no code blocks, no file lists, no markdown formatting, no headers. Write professional, technical prose suitable for an open-source README."""

        result = self.provider.generate(prompt, max_tokens=300)

        # Validate the response - reject if it looks like code or file structure
        if result:
            result = result.strip()
            # Reject responses that look like code or file listings
            bad_patterns = ["```", "|---", "├──", "└──", "Project structure:", "def ", "class ", "import "]
            for pattern in bad_patterns:
                if pattern in result:
                    return None
            # Reject if too short or too long
            if len(result) < 100 or len(result) > 1000:
                return None

        return result

    def generate_usage_example(
        self,
        metadata: ProjectMetadata,
        entry_point_code: Optional[str] = None,
    ) -> Optional[str]:
        """
        Generate a usage example based on entry points.

        Args:
            metadata: Project metadata with entry points
            entry_point_code: Code from the main entry point file

        Returns:
            Generated usage example code, or None
        """
        if not self.provider:
            return None

        # Build context
        context_parts = []

        if metadata.name.value:
            context_parts.append(f"Package name: {metadata.name.value}")

        # Add entry points
        for ep in metadata.entry_points[:3]:
            context_parts.append(f"Entry point: {ep.path} (type: {ep.entry_type})")
            if ep.command:
                context_parts.append(f"CLI command: {ep.command}")

        # Add entry point code if available
        if entry_point_code:
            code_preview = entry_point_code[:500]
            context_parts.append(f"Entry point code:\n```python\n{code_preview}\n```")

        context = "\n".join(context_parts)

        prompt = f"""Based on the following project information, write a brief Python usage example (3-5 lines of code) showing how to use this package. Include necessary imports.

{context}

Write ONLY the code example in a Python code block. Keep it simple and practical."""

        result = self.provider.generate(prompt, max_tokens=200)

        # Clean up the response - extract code from markdown if present
        if result:
            # Remove markdown code blocks if present
            if "```python" in result:
                start = result.find("```python") + 9
                end = result.find("```", start)
                if end > start:
                    result = result[start:end].strip()
            elif "```" in result:
                start = result.find("```") + 3
                end = result.find("```", start)
                if end > start:
                    result = result[start:end].strip()

        return result

    def generate_key_features(
        self,
        metadata: ProjectMetadata,
        code_samples: dict[str, str],
    ) -> Optional[list[str]]:
        """
        Generate a list of key features based on project analysis.

        Args:
            metadata: Project metadata
            code_samples: Dict of filename -> code content

        Returns:
            List of feature strings (action-oriented), or None
        """
        if not self.provider:
            return None

        # Build context
        context_parts = []

        if metadata.name.value:
            context_parts.append(f"Project: {metadata.name.value}")

        if metadata.primary_language.value:
            context_parts.append(f"Language: {metadata.primary_language.value}")

        if metadata.dependencies:
            deps = [d.name for d in metadata.dependencies[:15]]
            context_parts.append(f"Dependencies: {', '.join(deps)}")

        if metadata.entry_points:
            eps = [f"{e.entry_type}: {e.path}" for e in metadata.entry_points[:5]]
            context_parts.append(f"Entry points: {', '.join(eps)}")

        # Add code samples
        for filename, code in list(code_samples.items())[:3]:
            if code and '\x00' not in code[:200]:
                context_parts.append(f"File {filename}:\n{code[:400]}")

        context = "\n\n".join(context_parts)

        prompt = f"""Based on the following project information, generate exactly 5-7 key features for a README. Each feature must:
1. Start with an action verb (e.g., "Provides", "Enables", "Supports", "Implements", "Generates")
2. Be specific and technical (no generic phrases like "Easy to use")
3. Describe actual functionality visible in the code/dependencies

Project Information:
{context}

Output ONLY a numbered list of features, one per line. Example format:
1. Implements neural network training with configurable architectures
2. Provides data preprocessing pipelines for medical imaging
3. Supports multiple output formats including DICOM and NIfTI"""

        result = self.provider.generate(prompt, max_tokens=300)

        if result:
            # Parse the numbered list
            features = []
            for line in result.strip().split('\n'):
                line = line.strip()
                # Remove numbering
                if line and line[0].isdigit():
                    # Remove "1. " or "1) " prefix
                    if '. ' in line[:4]:
                        line = line.split('. ', 1)[1]
                    elif ') ' in line[:4]:
                        line = line.split(') ', 1)[1]
                if line and len(line) > 10:
                    features.append(line)

            if len(features) >= 3:
                return features[:7]  # Cap at 7 features

        return None

    def generate_architecture_summary(
        self,
        metadata: ProjectMetadata,
        code_samples: dict[str, str],
    ) -> Optional[str]:
        """
        Generate an architecture/design summary.

        Args:
            metadata: Project metadata
            code_samples: Dict of filename -> code content

        Returns:
            Architecture description, or None
        """
        if not self.provider:
            return None

        # Build context with file structure hints
        context_parts = []

        if metadata.name.value:
            context_parts.append(f"Project: {metadata.name.value}")

        if metadata.primary_language.value:
            context_parts.append(f"Language: {metadata.primary_language.value}")

        # List files by directory structure
        file_list = list(code_samples.keys())[:20]
        if file_list:
            context_parts.append(f"Project files: {', '.join(file_list)}")

        if metadata.dependencies:
            deps = [d.name for d in metadata.dependencies[:10]]
            context_parts.append(f"Key dependencies: {', '.join(deps)}")

        # Add code samples for context
        for filename, code in list(code_samples.items())[:2]:
            if code and '\x00' not in code[:200]:
                context_parts.append(f"Sample from {filename}:\n{code[:500]}")

        context = "\n\n".join(context_parts)

        prompt = f"""Based on the following project information, write a brief architecture/design overview (3-4 sentences) for a README. Describe:
1. The major components or modules
2. How data flows through the system
3. Key abstractions or patterns used

Project Information:
{context}

Write professional technical prose. No bullet points, no code blocks, no markdown. Just clear paragraphs describing the architecture."""

        result = self.provider.generate(prompt, max_tokens=250)

        if result:
            result = result.strip()
            # Reject if too short or contains code
            if len(result) > 50 and "```" not in result and "def " not in result:
                return result

        return None


def get_llm_enhancer() -> LLMEnhancer:
    """
    Get a configured LLM enhancer.

    Returns:
        LLMEnhancer instance (may not have an active provider)
    """
    return LLMEnhancer()
