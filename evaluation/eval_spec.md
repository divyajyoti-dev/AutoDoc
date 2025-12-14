# AutoDoc Evaluation Specification

## Overview

This document specifies the evaluation methodology for AutoDoc, a metadata-driven README generation system. The evaluation compares AutoDoc's extracted metadata and generated documentation against human-annotated gold standard data.

## Evaluation Mode

**Mode B: Gold-only with Runtime Generation**

The gold dataset (`autodoc_gold_annotations.csv`) contains human-annotated ground truth. AutoDoc outputs are generated at evaluation time by running the system against each repository (via GitHub URL or cached clone).

---

## Field Definitions and Metrics

### 1. Exact Match Fields

These fields use normalized string comparison:

| Field | Gold Column | AutoDoc Source | Normalization Rules |
|-------|-------------|----------------|---------------------|
| `project_title` | `project_title` | `metadata.name.value` | lowercase, trim, collapse spaces, strip end punctuation |
| `primary_language` | `primary_language` | `metadata.primary_language.value` | lowercase, trim, alias mapping |
| `installation_method` | `installation_method` | Inferred from README/metadata | lowercase, trim, alias mapping |
| `license_name` | `license_name` | `metadata.license.value` | lowercase, trim, collapse spaces, alias mapping |

**Alias Mappings:**

- **Languages:** `javascript` = `js`, `node`; `python` = `py`, `python3`; `c++` = `cpp`
- **Licenses:** `mit` = `mit license`; `apache-2.0` = `apache 2.0`, `apache license 2.0`
- **Install methods:** `pip` = `pip3`; `npm` = `yarn`, `pnpm`

**Metric:** Accuracy = (# exact matches after normalization) / (# evaluated pairs)

---

### 2. Semantic Similarity Fields

| Field | Gold Column | AutoDoc Source | Primary Metric | Threshold |
|-------|-------------|----------------|----------------|-----------|
| `description` | `description` | `metadata.description.value` | Sentence-BERT cosine similarity | 0.70 |

**Fallback:** If sentence-transformers unavailable, use ROUGE-L with threshold 0.50.

**Metric:**
- Continuous: Average similarity score
- Binary: % of pairs exceeding threshold

---

### 3. Binary Accuracy Fields

| Field | Gold Column | AutoDoc Source |
|-------|-------------|----------------|
| `security_relevant` | `security_relevant` | Inferred from code analysis |

**Metric:** Standard binary classification metrics (accuracy, precision, recall, F1)

---

### 4. Categorical Fields

| Field | Gold Column | Categories |
|-------|-------------|------------|
| `usage_type` | `usage_type` | library, cli, framework, service, system, library+cli |
| `supported_by_autodoc` | `supported_by_autodoc` | full, partial, none |

**Metric:** Categorical accuracy, confusion matrix

---

### 5. Entry Point Plausibility

| Field | Gold Column | AutoDoc Source |
|-------|-------------|----------------|
| `usage_entry_point` | `usage_entry_point` | `metadata.entry_points` |

**Evaluation Criteria:**
1. Entry point exists (non-empty extraction)
2. Entry point is syntactically valid for the language
3. Entry point matches expected patterns (import statement, CLI command, etc.)

**Metric:** Binary correctness (plausible vs. implausible)

---

## Aggregate Metrics

### Per-Field Metrics

For each field:
- **Exact match fields:** Accuracy
- **Semantic fields:** Mean similarity, % above threshold
- **Binary fields:** Accuracy, Precision, Recall, F1
- **Categorical fields:** Accuracy, per-class F1

### Overall Metrics

- **Macro Average:** Unweighted average across all field accuracies
- **Micro Average:** Weighted by number of non-null comparisons per field

---

## Breakdown Dimensions

Results are stratified by:

1. **Primary Language:** Python, JavaScript, Java, C, C++, Go, Generic
2. **Repository Size:** small (<50 files), medium (50-500), large (>500)
3. **AutoDoc Support Level:** full, partial, none

---

## Error Categories

When predictions differ from gold:

| Error Type | Definition |
|------------|------------|
| `MISSING_INFORMATION` | AutoDoc returned null/empty; gold has value |
| `INCORRECT_INFERENCE` | AutoDoc returned wrong value; gold has different value |
| `OVERCONFIDENT_EXTRACTION` | AutoDoc returned value with high confidence but wrong |
| `LANGUAGE_MISMATCH` | Error due to unsupported language features |
| `HEURISTIC_LIMITATION` | Known limitation of pattern-based extraction |
| `OTHER` | Uncategorized error |

---

## Data Sources

- **Gold Dataset:** `autodoc_gold_annotations.csv` (30 repositories)
- **AutoDoc Outputs:** Generated at runtime via `/api/generate` endpoint
- **Metadata Schema:** `autodoc/schema.py` (ProjectMetadata class)

---

## Reproducibility

All evaluation artifacts are saved to `evaluation_results/`:
- `field_level_results.csv` - Per-repo, per-field results
- `metrics_summary.csv` - Aggregate metrics
- `metrics_by_*.csv` - Stratified breakdowns
- `error_analysis.csv` - Detailed error categorization
- `figures/` - Visualization outputs
