# Evaluation Assumptions

This document explicitly states all assumptions made during the AutoDoc evaluation process.

## Data Assumptions

### A1: Gold Dataset Completeness
- **Assumption:** The gold dataset (`autodoc_gold_annotations.csv`) represents a representative sample of repository types that AutoDoc targets.
- **Justification:** The dataset includes 30 repositories spanning 7 languages (Python, JavaScript, Java, C, C++, Go, Generic), 3 size categories, and various project types (library, CLI, framework, service).
- **Limitation:** Sample size is small for statistical power; results should be interpreted as indicative rather than definitive.

### A2: Gold Annotation Quality
- **Assumption:** Human annotations in the gold dataset are correct and represent ground truth.
- **Justification:** Annotations were created following consistent guidelines.
- **Limitation:** No inter-annotator agreement metrics available; single-annotator bias possible.

### A3: Repository Processing
- **Assumption:** AutoDoc is run directly on each repository via GitHub clone.
- **Justification:** This provides authentic extraction results rather than simulated outputs.
- **Limitation:** Some repositories may fail due to size (timeout), network issues, or unsupported structures. Failed repos are marked as "skipped" with reason documented.

---

## Metric Assumptions

### A4: String Normalization
- **Assumption:** Normalized string comparison (lowercase, trim, collapse spaces) is appropriate for exact-match fields.
- **Justification:** Minor formatting differences (case, whitespace) are not meaningful errors.
- **Trade-off:** May incorrectly mark as correct when formatting carries semantic meaning.

### A5: License Alias Equivalence
- **Assumption:** License name variants refer to the same license (e.g., "MIT" = "MIT License" = "The MIT License").
- **Justification:** These are common variations of standard license identifiers.
- **Mapping:**
  - MIT variants: `mit`, `mit license`, `the mit license`
  - Apache variants: `apache-2.0`, `apache 2.0`, `apache license 2.0`
  - BSD variants: `bsd-3-clause`, `bsd 3-clause`, `new bsd`

### A6: Semantic Similarity Threshold
- **Assumption:** A cosine similarity threshold of 0.70 (using sentence-transformers) indicates semantically equivalent descriptions.
- **Justification:** Based on empirical studies of sentence embedding models; 0.70 represents "similar meaning" while allowing paraphrasing.
- **Sensitivity:** Results reported at 0.70; additional thresholds (0.60, 0.80) reported for sensitivity analysis.
- **Fallback:** If sentence-transformers unavailable, ROUGE-L with threshold 0.50 is used.

### A7: Entry Point Plausibility
- **Assumption:** An entry point is "correct" if it represents a plausible way to invoke the project.
- **Criteria:**
  - For Python libraries: `import X` or `from X import Y` pattern
  - For CLIs: command name matches package name
  - For JavaScript: `require('X')` or `import X from 'X'` pattern
- **Conservative approach:** When uncertain, mark as incorrect and document reasoning.

---

## Technical Assumptions

### A8: API Availability
- **Assumption:** The AutoDoc API (`/api/generate`) is functional and returns consistent outputs.
- **Action:** Health check performed before evaluation; failures logged.

### A9: GitHub Rate Limiting
- **Assumption:** GitHub API rate limits may prevent evaluation of all repositories in one run.
- **Mitigation:** Evaluation script supports incremental runs and caches successful outputs.

### A10: Deterministic Outputs
- **Assumption:** AutoDoc produces deterministic outputs for the same input repository.
- **Justification:** Core extraction is rule-based; LLM enhancement (if enabled) may introduce variability.
- **Note:** Evaluation should be run with LLM enhancement disabled for reproducibility, or results averaged over multiple runs.

---

## Scope Limitations

### L1: Fields Not Evaluated
The following gold dataset fields are **not** directly evaluated against AutoDoc outputs:
- `installation_command` - Too variable; evaluated as part of installation_method
- `license_source` - Internal provenance tracking
- `maintainers` - Author extraction varies by source
- `security_risk_type` - Requires deep code analysis beyond current scope
- `repo_size_bucket` - Ground truth annotation, not extracted

### L2: Runtime Dependencies
- **Assumption:** Dependencies are not evaluated in this version due to complexity of parsing and normalizing dependency lists across package managers.
- **Future work:** Precision/recall metrics for dependency extraction.

### L3: Repository Accessibility
- Some repositories in the gold dataset may be:
  - Private (not accessible without authentication)
  - Deleted or renamed
  - Temporarily unavailable
- **Handling:** These are marked as "skipped" with reason documented.

---

## Statistical Assumptions

### S1: Independence
- **Assumption:** Evaluation results across repositories are independent.
- **Limitation:** Repositories from same organization or ecosystem may share patterns.

### S2: Confidence Intervals
- **Assumption:** With 30 samples, confidence intervals are wide; we report point estimates with standard errors where applicable.

### S3: No Multiple Testing Correction
- **Assumption:** P-values (if reported) are not corrected for multiple comparisons across fields.
- **Justification:** This is an exploratory evaluation, not hypothesis testing.

---

## Versioning

- **Evaluation Spec Version:** 1.0
- **Gold Dataset Version:** 1.0 (30 repositories)
- **AutoDoc Version:** Evaluated as of current commit
- **Date:** Created for INFO-202 Fall 2024

---

## Change Log

| Date | Change | Rationale |
|------|--------|-----------|
| Initial | Created assumptions document | Transparency for evaluation |
