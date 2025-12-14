# AutoDoc Evaluation Framework

This directory contains the evaluation framework for AutoDoc, designed to assess metadata extraction accuracy against a gold standard dataset.

## Quick Start

```bash
# From the AutoDoc root directory
cd evaluation

# Run full evaluation (generate outputs + analyze)
python run_evaluation.py --mode both

# Or run analysis only (if outputs already exist)
python run_evaluation.py --mode analyze

# View results
ls ../evaluation_results/
```

## Directory Structure

```
evaluation/
├── run_evaluation.py      # Main evaluation script
├── eval_spec.json         # Machine-readable evaluation specification
├── eval_spec.md           # Human-readable evaluation specification
├── ASSUMPTIONS.md         # Explicit assumptions documentation
└── README_EVAL.md         # This file

evaluation_results/        # Generated outputs
├── autodoc_outputs/       # Cached AutoDoc extraction results
├── field_level_results.csv
├── metrics_summary.csv
├── metrics_by_language.csv
├── metrics_by_repo_size.csv
├── metrics_by_support_level.csv
├── error_analysis.csv
├── error_analysis.md
├── evaluation_writeup.md  # Full report ready for INFO-202
└── figures/
    ├── accuracy_by_field.png
    └── accuracy_by_language.png
```

## Requirements

**Required:**
- Python 3.10+

**Optional (for enhanced functionality):**
- `numpy` - For statistical calculations
- `matplotlib` - For visualization generation
- `sentence-transformers` - For semantic similarity (falls back to ROUGE-L otherwise)

Install optional dependencies:
```bash
pip install numpy matplotlib sentence-transformers
```

## Usage

### Command Line Arguments

```bash
python run_evaluation.py [OPTIONS]

Options:
  --mode {generate,analyze,both}
      generate: Run AutoDoc against gold repos and save outputs
      analyze:  Analyze existing outputs against gold (default)
      both:     Generate outputs then analyze (default)

  --output-dir DIR
      Output directory for results (default: ../evaluation_results)

  --gold-csv PATH
      Path to gold annotations CSV (default: ../autodoc_gold_annotations.csv)
```

### Examples

```bash
# Full evaluation
python run_evaluation.py --mode both

# Re-analyze existing outputs
python run_evaluation.py --mode analyze

# Custom output directory
python run_evaluation.py --output-dir /path/to/output
```

## Output Files

### Core Results

| File | Description |
|------|-------------|
| `field_level_results.csv` | Every field comparison for every repo |
| `metrics_summary.csv` | Aggregate accuracy per field + overall |
| `error_analysis.csv` | Detailed error records with classification |
| `error_analysis.md` | Human-readable error report |

### Breakdown Analyses

| File | Description |
|------|-------------|
| `metrics_by_language.csv` | Accuracy stratified by programming language |
| `metrics_by_repo_size.csv` | Accuracy stratified by repository size |
| `metrics_by_support_level.csv` | Accuracy by expected AutoDoc support |

### Visualizations

| File | Description |
|------|-------------|
| `figures/accuracy_by_field.png` | Bar chart of per-field accuracy |
| `figures/accuracy_by_language.png` | Grouped bar chart by language |

## Evaluation Specification

The evaluation is defined in `eval_spec.json`. Key parameters:

### Exact Match Fields
- `project_title`
- `primary_language`
- `installation_method`
- `license_name`

### Semantic Similarity Fields
- `description` (threshold: 0.70 cosine similarity)

### Categorical Fields
- `usage_type`
- `supported_by_autodoc`

### Normalization Rules

1. **String normalization:**
   - Lowercase conversion
   - Whitespace trimming
   - Space collapsing
   - End punctuation stripping

2. **License aliases:**
   - MIT = MIT License = The MIT License
   - Apache-2.0 = Apache 2.0 = Apache License 2.0

3. **Language aliases:**
   - JavaScript = JS = Node = NodeJS
   - Python = Py = Python3

## Error Classification

Errors are classified into categories:

| Type | Description |
|------|-------------|
| `MISSING_INFORMATION` | AutoDoc returned null; gold has value |
| `INCORRECT_INFERENCE` | AutoDoc returned wrong value |
| `OVERCONFIDENT_EXTRACTION` | Partial/related but incorrect |
| `LANGUAGE_MISMATCH` | Language-specific extraction failure |
| `HEURISTIC_LIMITATION` | Known limitation of patterns |
| `OTHER` | Uncategorized |

## Gold Dataset

The gold dataset (`autodoc_gold_annotations.csv`) contains:
- 30 repositories
- 7 programming languages
- 3 size categories
- 15 annotated fields per repo

### Fields
```
repo, primary_language, project_title, description,
installation_method, installation_command, usage_type,
usage_entry_point, license_name, license_source,
maintainers, security_relevant, security_risk_type,
repo_size_bucket, supported_by_autodoc
```

## Extending the Evaluation

### Adding New Fields

1. Add field definition to `eval_spec.json`
2. Implement comparison logic in `evaluate_all_fields()`
3. Update `compute_aggregate_metrics()` if new metric type

### Adding New Repositories

1. Append rows to `autodoc_gold_annotations.csv`
2. Re-run evaluation with `--mode both`

### Custom Similarity Thresholds

Edit `SEMANTIC_SIMILARITY_THRESHOLD` in `run_evaluation.py`:
```python
SEMANTIC_SIMILARITY_THRESHOLD = 0.70  # Adjust as needed
```

## Troubleshooting

### "sentence-transformers not available"
Install with: `pip install sentence-transformers`
Or ignore - evaluation will fall back to ROUGE-L.

### "matplotlib not available"
Install with: `pip install matplotlib`
Or ignore - visualizations will be skipped.

### Empty results
Check that `autodoc_gold_annotations.csv` exists in the project root.

## Citation

If using this evaluation framework, please cite:
```
AutoDoc Evaluation Framework
INFO-202 Fall 2024
University of California, Berkeley
```
