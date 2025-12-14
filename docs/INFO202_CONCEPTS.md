# AutoDoc: Connections to INFO 202 Concepts

This document maps AutoDoc's design and implementation to key concepts from **Information Organization and Retrieval (INFO 202)** at UC Berkeley.

---

## Week 1: Information as Thing (Buckland)

**Concept**: Buckland distinguishes between information-as-process, information-as-knowledge, and information-as-thing. Documents and data become "informative" when they can inform someone.

**AutoDoc Connection**:
- AutoDoc treats code repositories as **information-as-thing** — tangible artifacts (files, configs, code) that contain latent knowledge about a project
- The tool transforms implicit information (scattered across files) into explicit, structured documentation
- README files serve as **surrogates** for the repository itself — a condensed representation that informs potential users

```
Repository (thing) → Metadata Extraction → README (informative document)
```

---

## Week 2: Collections & Datasheets for Datasets

**Concept**: Organizing systems require consistent description of resources. Datasheets provide standardized metadata for datasets to ensure transparency and usability.

**AutoDoc Connection**:
- AutoDoc generates **standardized documentation** similar to datasheets — ensuring every project has consistent sections (purpose, installation, dependencies, license, authors)
- The `ProjectMetadata` schema acts as a **controlled template** for describing software projects:

```python
@dataclass
class ProjectMetadata:
    name: MetadataField
    description: MetadataField
    version: MetadataField
    license: MetadataField
    authors: list[Author]
    dependencies: list[Dependency]
    # ... standardized fields
```

- Like datasheets, AutoDoc promotes **transparency** by surfacing often-overlooked metadata (license terms, Python version requirements, entry points)

---

## Week 3: Categorization

**Concept**: Categories help organize resources into meaningful groups. Categorization can be classical (clear boundaries) or prototype-based (fuzzy membership).

**AutoDoc Connection**:
- **File Discovery** uses categorization to classify files:

```python
class FileCategory(Enum):
    CONFIG = "config"           # pyproject.toml, package.json
    SOURCE = "source"           # .py, .js, .java files
    DOCUMENTATION = "docs"      # README, docs/
    BUILD = "build"             # Makefile, CMakeLists.txt
    TEST = "test"               # tests/, *_test.py
```

- **Language Detection** categorizes projects by primary language using file extension patterns
- **Confidence Levels** represent fuzzy categorization — not all extractions are equally certain:

```python
class Confidence(Enum):
    EXPLICIT = 1.0    # Directly stated in config
    STRONG = 0.8      # High confidence inference
    REASONABLE = 0.6  # Likely correct
    WEAK = 0.4        # Uncertain
    GUESS = 0.2       # Low confidence
```

---

## Week 4: Hierarchical Structures & Taxonomies

**Concept**: Taxonomies organize concepts into hierarchical parent-child relationships. Faceted classification allows multiple independent dimensions.

**AutoDoc Connection**:
- **Extractor Hierarchy** follows a taxonomic structure:

```
BaseExtractor (abstract)
├── GenericExtractor (language-agnostic)
├── PythonExtractor
│   └── handles: pyproject.toml, setup.py, requirements.txt
├── JavaScriptExtractor
│   └── handles: package.json
├── JavaExtractor
│   └── handles: pom.xml, build.gradle
└── CppExtractor
    └── handles: CMakeLists.txt, Makefile
```

- **Faceted Metadata**: Projects are described across multiple independent facets:
  - Language facet: Python, JavaScript, Java, C++
  - License facet: MIT, Apache-2.0, GPL-3.0
  - Framework facet: Django, React, Spring
  - Project type facet: CLI, library, web app

---

## Week 5: Ontologies & Information Architecture

**Concept**: Ontologies define relationships between concepts. Information architecture structures content for findability and usability.

**AutoDoc Connection**:
- **Schema as Ontology**: The `ProjectMetadata` schema defines relationships:
  - A Project *has* Dependencies
  - A Dependency *has* version constraints
  - An EntryPoint *belongs to* a Project
  - An Author *maintains* a Project

- **README Information Architecture**: Sections follow a logical hierarchy optimized for user tasks:

```
1. Title + Description  → "What is this?"
2. Installation         → "How do I get it?"
3. Usage               → "How do I use it?"
4. Testing             → "How do I verify it works?"
5. Dependencies        → "What does it need?"
6. Contributing        → "How can I help?"
7. License             → "Can I use this?"
8. Authors             → "Who made this?"
```

---

## Week 6: Structured Data, Metadata, Schemas

**Concept**: Structured data follows defined schemas. Metadata is "data about data." Semi-structured formats (JSON, XML) provide flexibility.

**AutoDoc Connection**:
- AutoDoc **extracts metadata** from semi-structured config files:

| File Format | Structure Type | Example Fields |
|------------|----------------|----------------|
| pyproject.toml | TOML (structured) | name, version, dependencies |
| package.json | JSON (semi-structured) | name, scripts, devDependencies |
| pom.xml | XML (structured) | groupId, artifactId, version |
| requirements.txt | Plain text (unstructured) | package==version |

- **Schema Normalization**: Different formats are normalized into a unified `ProjectMetadata` schema:

```python
# From pyproject.toml
[project]
name = "autodoc"
dependencies = ["flask>=3.0"]

# Normalized to:
metadata.name = MetadataField(value="autodoc", confidence=EXPLICIT)
metadata.dependencies = [Dependency(name="flask", version=">=3.0")]
```

---

## Week 7: Vocabulary Problem & Lexical Relations

**Concept**: Users and systems often use different terms for the same concept. Controlled vocabularies and thesauri help bridge this gap.

**AutoDoc Connection**:
- **License Normalization**: Different ways to express licenses are mapped to standard SPDX identifiers:

```python
LICENSE_PATTERNS = {
    r"MIT": "MIT",
    r"Apache.*2": "Apache-2.0",
    r"GPL.*3": "GPL-3.0",
    r"BSD.*3": "BSD-3-Clause",
}
# "MIT License" → "MIT"
# "Apache License, Version 2.0" → "Apache-2.0"
```

- **Framework Detection**: Multiple naming conventions map to canonical framework names:

```python
# Vocabulary normalization for frameworks
"django" in deps → "Django"
"flask" in deps → "Flask"
"react" in deps → "React"
"@angular/core" in deps → "Angular"
```

---

## Week 8: Automated Classification & Word Embeddings

**Concept**: Machine learning can automatically classify documents. Word embeddings capture semantic similarity.

**AutoDoc Connection**:
- **LLM-Powered Description Generation**: When explicit descriptions are missing, AutoDoc uses LLMs to generate them:

```python
def _generate_description(self, metadata, code_samples):
    prompt = f"""Based on the project information below,
    write a clear description explaining:
    1. What the project does
    2. Who would use it

    Project: {metadata.name}
    Dependencies: {metadata.dependencies}
    Code samples: {code_samples}"""

    return self.llm.generate(prompt)
```

- **Generic Description Detection**: Patterns identify low-quality descriptions that need enhancement:

```python
generic_patterns = [
    "final year project",
    "demo project",
    "work in progress",
    "todo",
]
# If description matches → trigger LLM enhancement
```

---

## Week 9: Grounded Coding & Inter-rater Reliability

**Concept**: Grounded coding develops categories from data. Inter-rater reliability measures agreement between coders.

**AutoDoc Connection**:
- **Confidence Scores as Reliability Measure**: Each extracted field has a confidence level indicating extraction reliability:

```python
# High agreement (explicit in config)
name = MetadataField(
    value="autodoc",
    confidence=Confidence.EXPLICIT,  # 1.0
    source="pyproject.toml"
)

# Lower agreement (inferred from code)
description = MetadataField(
    value="A CLI tool for...",
    confidence=Confidence.REASONABLE,  # 0.6
    source="LLM (Groq)"
)
```

- **Source Provenance**: Like coding memos, AutoDoc tracks where each piece of metadata came from:

```python
# Provenance tracking
field.source = "pyproject.toml [project.name]"
field.note = "Extracted from explicit configuration"
```

---

## Week 10: Information Seeking & Foraging

**Concept**: Users forage for information, following "information scent." Search interfaces should reduce cognitive load.

**AutoDoc Connection**:
- **README as Information Scent**: A good README provides strong scent for developers evaluating whether to use a project:
  - Clear description → "Is this what I need?"
  - Installation steps → "Can I use this easily?"
  - Usage examples → "How does this work?"

- **Reducing Foraging Cost**: Instead of developers searching through files to understand a project, AutoDoc aggregates key information:

```
Without AutoDoc:
Developer must forage: pyproject.toml → setup.py →
                       LICENSE → src/*.py → tests/

With AutoDoc:
Developer reads: README.md (all key info in one place)
```

---

## Week 11: Standards

**Concept**: Standards enable interoperability and shared understanding. Web standards (HTML, CSS) ensure consistent rendering.

**AutoDoc Connection**:
- **Markdown as Documentation Standard**: README.md uses CommonMark standard for portable formatting
- **SPDX License Identifiers**: Standardized license naming (MIT, Apache-2.0, GPL-3.0)
- **Semantic Versioning**: Version constraints follow semver standard (>=3.0.0, ^1.2.3)
- **Package Manager Standards**: pyproject.toml (PEP 621), package.json (npm), pom.xml (Maven)

---

## Week 12: IR Basics - Crawling & Indexing

**Concept**: Information retrieval systems crawl documents, extract content, and build indexes for search.

**AutoDoc Connection**:
- **File Discovery as Crawling**: AutoDoc "crawls" the repository file system:

```python
def discover_files(root_path: Path) -> DiscoveryResult:
    """Crawl directory tree, respecting .gitignore"""
    for path in root_path.rglob("*"):
        if should_include(path):
            yield FileInfo(path, category, size)
```

- **Metadata Extraction as Indexing**: Extractors parse files and build a metadata "index":

```python
class ExtractorRegistry:
    def extract_all(self, files) -> ProjectMetadata:
        """Extract and merge metadata from all files"""
        for extractor in self.extractors:
            extractor.extract(files, metadata)
        return metadata
```

---

## Week 13: Relevance, Ranking, TF-IDF, RAG

**Concept**: Search systems rank results by relevance. TF-IDF weighs term importance. RAG augments LLMs with retrieved context.

**AutoDoc Connection**:
- **Confidence as Relevance Ranking**: Fields are ranked by extraction confidence:

```python
# Higher confidence = more reliable = shown more prominently
if field.confidence >= REASONABLE:
    show_value(field)
else:
    show_with_review_marker(field)
```

- **RAG-like Context Augmentation**: LLM prompts are augmented with retrieved code context:

```python
def enhance(self, metadata, code_samples, readme):
    # Retrieve relevant context
    context = []
    context.append(f"Project: {metadata.name}")
    context.append(f"Dependencies: {metadata.dependencies}")
    context.append(f"Code: {code_samples[:3]}")

    # Augment LLM prompt with context
    prompt = f"Given this context:\n{context}\n\nGenerate description..."
    return llm.generate(prompt)
```

---

## Week 14: Misinformation

**Concept**: Misinformation spreads false information. Verification and source tracking help combat it.

**AutoDoc Connection**:
- **Provenance Tracking**: Every field includes its source for verification:

```python
MetadataField(
    value="MIT",
    source="LICENSE file (line 1)",  # Verifiable source
    confidence=Confidence.EXPLICIT
)
```

- **Human-in-the-Loop Design**: AutoDoc explicitly marks generated content for human review:

```markdown
<!-- Review suggested: reasonable confidence from LLM -->
This project is a web-based voting system...

<!-- TODO: Add license information -->
```

- **Confidence Transparency**: Users can see how reliable each piece of information is

---

## Week 15: Fairness, Bias, and Intellectual Property

**Concept**: AI systems can exhibit bias. Intellectual property rights govern content reuse.

**AutoDoc Connection**:
- **License Extraction**: AutoDoc surfaces license information prominently, helping users understand IP terms:

```markdown
## License
This project is licensed under the **MIT** license.
```

- **Attribution**: Generated READMEs credit AutoDoc, promoting transparency:

```markdown
This README was automatically generated by AutoDoc.
**Important**: This is a *draft* document. Please review...
```

- **Bias Awareness**: LLM-generated descriptions are marked as requiring human review to catch potential biases or inaccuracies

---

## Summary: Course Concept Integration

| INFO 202 Week | Concept | AutoDoc Implementation |
|---------------|---------|------------------------|
| 1 | Information as Thing | Repos as artifacts → READMEs as surrogates |
| 2 | Datasheets | Standardized ProjectMetadata schema |
| 3 | Categorization | FileCategory enum, Confidence levels |
| 4 | Taxonomies | Extractor hierarchy, faceted metadata |
| 5 | Ontologies | Schema relationships, IA of README |
| 6 | Structured Data | TOML/JSON/XML parsing, schema normalization |
| 7 | Vocabulary Problem | License normalization, framework detection |
| 8 | Classification | LLM description generation |
| 9 | Grounded Coding | Confidence scores, source provenance |
| 10 | Information Foraging | README reduces foraging cost |
| 11 | Standards | Markdown, SPDX, SemVer, PEP 621 |
| 12 | Crawling/Indexing | File discovery, metadata extraction |
| 13 | Relevance/RAG | Confidence ranking, context augmentation |
| 14 | Misinformation | Provenance tracking, human review |
| 15 | Fairness/IP | License extraction, attribution |

---

## Conclusion

AutoDoc is fundamentally an **information organization tool** that applies core IO&R principles to the domain of software documentation. It:

1. **Organizes** scattered project metadata into a structured schema
2. **Retrieves** information from diverse file formats
3. **Categorizes** files and confidence levels
4. **Normalizes** vocabulary across different ecosystems
5. **Augments** missing information with AI
6. **Presents** information in an architecture optimized for developer needs

The tool embodies the course's central theme: **making information findable, usable, and trustworthy**.
