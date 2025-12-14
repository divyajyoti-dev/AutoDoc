# luna16<!-- Source: GitHub repository name (confidence: strong) -->
![License: BSD](https://img.shields.io/badge/License-BSD-blue.svg)

The luna16 project is a computer-aided medical diagnosis system developed for the LUNA16 Lung Nodule Analysis competition. This system is designed to aid developers, data scientists, and medical professionals in the analysis and classification of lung nodules from computed tomography (CT) scans. The primary purpose of luna16 is to provide a robust and accurate solution for the detection and segmentation of lung nodules, thereby helping to improve the diagnosis and treatment of lung cancer. The system relies on a combination of machine learning algorithms, leveraging the power of deep learning, to classify lung nodules into malignant or benign categories. Notably, the project utilizes a range of popular Python libraries, including numpy, lasagne, and theano, to implement its core functionality. However, it is essential to note that the project is not extensively documented, and running it may require minor adjustments to file paths and other settings.<!-- Source: LLM (Groq) (confidence: reasonable) -->

## Key Features

- Implements neural network training with configurable architectures using Lasagne and Theano
- Provides data preprocessing pipelines for medical imaging using NumPy, SciPy, and scikit-image
- Generates segmentation evaluation metrics using SimpleITK and pandas
- Enables ensemble learning of multiple model predictions with joblib and scikit-learn
- Supports reading and writing medical images in various formats using image_read_write and SimpleITK
- Implements data subset selection tools using glob and pandas
- Generates volume analysis metrics using NumPy and pandas

**Primary Language:** Python

frameworks: NumPy, Pandas

Python: 89.2%, Shell: 10.8%, Batchfile: 0.0%

## Table of Contents

- [Key Features](#key-features)
- [Installation](#installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Architecture](#architecture)
- [Testing](#testing)
- [Dependencies](#dependencies)
- [Contributing](#contributing)
- [License](#license)
- [Authors](#authors)

## Installation

```bash
# Clone the repository
git clone https://github.com/gzuidhof/luna16
cd luna16

# Install the package
pip install .

# Or install in development mode
pip install -e .
```

## Usage

### Running Scripts

```bash
python src/evaluate_candidates.py
python src/ensembleSubmissions.py
python src/evaluate_segmentation.py
python src/volume.py
python src/subset.py
python src/process_candidates.py
python src/slice_orientation.py
python src/candidates.py
python src/pipeline_candidates.py
python src/make_candidatelist_with_unet_candidates.py
python src/froc/froc_score.py
python src/data_processing/create_xy_xz_yz.py
python src/data_processing/equalize_spacings.py
python src/data_processing/create_same_spacing_data_NODULE.py
python src/data_processing/create_same_spacing_data_ALL.py
python src/data_processing/xyz_utils.py
python src/data_processing/create_xy_xz_yz_CARTESIUS.py
python src/data_processing/OLD/create_lung_segmented_same_spacing_data.py
python src/data_processing/OLD/1_1_1_mm_512_x_512_to_Slice_Dataset.py
python src/data_processing/OLD/1_1_1mm_to_1_1_1_mm_512_x_512.py
python src/deep/predict_resnet.py
python src/deep/test_augment.py
python src/deep/dataset_3D.py
python src/deep/predict.py
python src/deep/predict_resnet_cartesius.py
python src/deep/loss_weighting.py
python src/deep/train.py
python src/deep/resnet/resnet_trainer.py
python src/deep/fr3dnet/test.py
python src/evaluation/noduleCADEvaluationLUNA16.py
python src/conv_net/visualize.py
python src/conv_net/learn.py
```


## Project Structure

```
luna16/
├── src/ensembleSubmissions.py     # Main entry point
├── src/evaluate_candidates.py     # Main entry point
├── src/evaluate_segmentation.py   # Main entry point
├── src/subset.py                  # Main entry point
├── src/volume.py                  # Main entry point
└── tests/                         # Test suite
```

<!-- TODO: Add project structure details - Annotate key directories and their purposes -->

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|----------|
<!-- TODO: Add environment variables - Document required and optional environment variables -->


## Architecture

The luna16 project is a Python-based system composed of several key components, including the src module, responsible for core functionality, and the src/evaluation/tools module, which facilitates generic tools for use with Python. The src/evaluation/tools module provides a csvTools module, offering a utility for working with comma-separated value files. Data flows through the system via a series of interactions between these modules, leveraging dependencies such as numpy, matplotlib, and lasagne to perform computations and visualize results. The system's architecture is built around a modular design, utilizing abstractions from the params and glob modules to manage configuration and file paths, and adhering to a pattern of separation of concerns to maintain a high degree of flexibility and maintainability.


## Testing

Run the test suite:

```bash
pytest
# or
python -m pytest
```

## Dependencies

### Runtime Dependencies

| Package | Version | Source |
|---------|---------|--------|
| numpy | ⚠️ Version unknown | Code import analysis |
| matplotlib | ⚠️ Version unknown | Code import analysis |
| lasagne | ⚠️ Version unknown | Code import analysis |
| params | ⚠️ Version unknown | Code import analysis |
| glob | ⚠️ Version unknown | Code import analysis |
| __future__ | ⚠️ Version unknown | Code import analysis |
| skimage | ⚠️ Version unknown | Code import analysis |
| scipy | ⚠️ Version unknown | Code import analysis |
| theano | ⚠️ Version unknown | Code import analysis |
| pandas | ⚠️ Version unknown | Code import analysis |
| SimpleITK | ⚠️ Version unknown | Code import analysis |
| tqdm | ⚠️ Version unknown | Code import analysis |
| joblib | ⚠️ Version unknown | Code import analysis |
| image_read_write | ⚠️ Version unknown | Code import analysis |
| cPickle | ⚠️ Version unknown | Code import analysis |
| gzip | ⚠️ Version unknown | Code import analysis |

> **Note:** 16 dependencies have unknown versions. Manual verification required.


## Contributing

Contributions are welcome! Here's how you can help:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the **BSD** license.<!-- Source: LICENSE (confidence: strong) -->

## Authors

- **gzuidhof** (contributor)
- **wollf92** (contributor)

---

## About This README

This README was automatically generated by [AutoDoc](https://github.com/divyajyoti/autodoc).

**Important**: This is a *draft* document. Please review and enhance it:

1. Verify all automatically extracted information is correct
2. Fill in any sections marked with `<!-- TODO: ... -->` comments
3. Add project-specific context, examples, and documentation
4. Review sections marked for low-confidence data
5. Remove this notice once you've reviewed the document

AutoDoc extracted metadata from your project files but cannot understand the
full context of your project. Human review is essential for quality documentation.
