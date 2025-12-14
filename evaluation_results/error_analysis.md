# Error Analysis Report

Generated: 2025-12-13T17:46:15.769794

Total errors analyzed: 33

## Error Type Distribution

| Error Type | Count | Percentage |
|------------|-------|------------|
| MISSING_INFORMATION | 13 | 39.4% |
| INCORRECT_INFERENCE | 10 | 30.3% |
| LANGUAGE_MISMATCH | 8 | 24.2% |
| OVERCONFIDENT_EXTRACTION | 2 | 6.1% |

## Top Error Patterns

### description (13 errors)

- **psf/requests-html**: Gold=`requests-html is a library project primarily written in Python. It is designed to provide
a focused ...`, Pred=`\n` (INCORRECT_INFERENCE)
- **curl/trurl**: Gold=`trurl is a cli project primarily written in C. It is designed to provide a focused and
reusable solu...`, Pred=`None` (MISSING_INFORMATION)
- **benhoyt/inih**: Gold=`inih is a library project primarily written in C. It is designed to provide a focused and
reusable s...`, Pred=`None` (MISSING_INFORMATION)

### primary_language (10 errors)

- **junit-team/junit4**: Gold=`Java`, Pred=`JavaScript` (OVERCONFIDENT_EXTRACTION)
- **curl/trurl**: Gold=`C`, Pred=`Python` (LANGUAGE_MISMATCH)
- **tensorflow/tensorflow**: Gold=`C++`, Pred=`Python` (LANGUAGE_MISMATCH)

### license_name (3 errors)

- **curl/trurl**: Gold=`curl`, Pred=`Custom` (INCORRECT_INFERENCE)
- **elastic/elasticsearch**: Gold=`Elastic License 2.0`, Pred=`Custom` (INCORRECT_INFERENCE)
- **dinocore1/DevsmartLib-Android**: Gold=`Apache-2.0`, Pred=`None` (MISSING_INFORMATION)

### usage_type (3 errors)

- **curl/trurl**: Gold=`cli`, Pred=`library` (INCORRECT_INFERENCE)
- **gohugoio/hugo**: Gold=`cli`, Pred=`library` (INCORRECT_INFERENCE)
- **elastic/elasticsearch**: Gold=`service`, Pred=`library` (INCORRECT_INFERENCE)

### project_title (2 errors)

- **torvalds/linux**: Gold=`Linux Kernel`, Pred=`Baby` (INCORRECT_INFERENCE)
- **gohugoio/hugo**: Gold=`Hugo`, Pred=`project` (INCORRECT_INFERENCE)

### installation_method (2 errors)

- **spring-projects/spring-boot**: Gold=`maven`, Pred=`npm` (INCORRECT_INFERENCE)
- **gpanther/fastutil-guava-tests**: Gold=`maven`, Pred=`pip` (INCORRECT_INFERENCE)

## Case Studies

### spring-projects/spring-boot

**Errors:** 3

- **primary_language** (OVERCONFIDENT_EXTRACTION)
  - Gold: `Java`
  - Predicted: `JavaScript`
  - Analysis: Partial match detected. AutoDoc may have extracted a related but not equivalent value.
- **description** (MISSING_INFORMATION)
  - Gold: `Spring Boot is a framework project primarily written in Java. It is designed to provide a
focused an...`
  - Predicted: `None`
  - Analysis: AutoDoc did not extract any value for description. This may indicate the field was not present in standard locations or the extractor does not support this project type.
- **installation_method** (INCORRECT_INFERENCE)
  - Gold: `maven`
  - Predicted: `npm`
  - Analysis: AutoDoc extracted 'npm' but gold standard is 'maven'. The extraction heuristics may have matched incorrect patterns.

### vuejs/core

**Errors:** 1

- **description** (MISSING_INFORMATION)
  - Gold: `Vue.js is a framework project primarily written in JavaScript. It is designed to provide a
focused a...`
  - Predicted: `None`
  - Analysis: AutoDoc did not extract any value for description. This may indicate the field was not present in standard locations or the extractor does not support this project type.

### protocolbuffers/protobuf

**Errors:** 1

- **primary_language** (LANGUAGE_MISMATCH)
  - Gold: `C++`
  - Predicted: `Python`
  - Analysis: Language detection returned 'Python' but expected 'C++'. This may be due to mixed-language projects or unconventional file structures.

### jarro2783/cxxopts

**Errors:** 1

- **description** (MISSING_INFORMATION)
  - Gold: `cxxopts is a library project primarily written in C++. It is designed to provide a focused
and reusa...`
  - Predicted: `None`
  - Analysis: AutoDoc did not extract any value for description. This may indicate the field was not present in standard locations or the extractor does not support this project type.

### curl/trurl

**Errors:** 4

- **primary_language** (LANGUAGE_MISMATCH)
  - Gold: `C`
  - Predicted: `Python`
  - Analysis: Language detection returned 'Python' but expected 'C'. This may be due to mixed-language projects or unconventional file structures.
- **license_name** (INCORRECT_INFERENCE)
  - Gold: `curl`
  - Predicted: `Custom`
  - Analysis: AutoDoc extracted 'Custom' but gold standard is 'curl'. The extraction heuristics may have matched incorrect patterns.
- **description** (MISSING_INFORMATION)
  - Gold: `trurl is a cli project primarily written in C. It is designed to provide a focused and
reusable solu...`
  - Predicted: `None`
  - Analysis: AutoDoc did not extract any value for description. This may indicate the field was not present in standard locations or the extractor does not support this project type.
- **usage_type** (INCORRECT_INFERENCE)
  - Gold: `cli`
  - Predicted: `library`
  - Analysis: AutoDoc extracted 'library' but gold standard is 'cli'. The extraction heuristics may have matched incorrect patterns.

