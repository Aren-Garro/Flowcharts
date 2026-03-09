# PyPI Deployment Guide

This guide explains how to publish the ISO Flowchart Generator to PyPI for easy `pip install` distribution.

## Prerequisites

1. **PyPI Account**: Create account at [pypi.org](https://pypi.org)
2. **PyPI API Token**: Generate at https://pypi.org/manage/account/token/
3. **Build Tools**: Install required packages

```bash
pip install build twine
```

## Pre-Deployment Checklist

- [ ] All tests passing: `python run_all_tests.py`
- [ ] Version updated in `pyproject.toml`, `setup.py`, and `VERSION`
- [ ] CHANGELOG.md updated with release notes
- [ ] README.md badges and links verified
- [ ] Documentation up to date
- [ ] Examples tested and working

## Build Package

### 1. Clean Previous Builds

```bash
rm -rf dist/ build/ *.egg-info
```

### 2. Build Distribution Files

```bash
python -m build
```

This creates:
- `dist/iso-flowchart-generator-X.Y.Z.tar.gz` (source distribution)
- `dist/iso_flowchart_generator-X.Y.Z-py3-none-any.whl` (wheel distribution)

### 3. Verify Package Contents

```bash
tar -tzf dist/iso-flowchart-generator-*.tar.gz
unzip -l dist/iso_flowchart_generator-*.whl
```

Ensure all necessary files are included:
- Source code (`src/`, `cli/`)
- Documentation (`README.md`, `QUICKSTART.md`, etc.)
- Examples (`examples/`)
- License and metadata

## Test Package Locally

### Install in Test Environment

```bash
# Create fresh virtual environment
python -m venv test_env
source test_env/bin/activate  # Windows: test_env\Scripts\activate

# Install from local build
pip install dist/iso_flowchart_generator-*.whl

# Test CLI command
flowchart --version
flowchart --help

# Test basic generation
echo "1. Start\n2. Process\n3. End" > test.txt
flowchart generate test.txt -o test.html --renderer html
```

### Deactivate and Clean Up

```bash
deactivate
rm -rf test_env
```

## Upload to TestPyPI (Optional)

Test the upload process without affecting production PyPI.

### 1. Create TestPyPI Account

Register at https://test.pypi.org/account/register/

### 2. Upload to TestPyPI

```bash
twine upload --repository testpypi dist/*
```

Enter your TestPyPI credentials when prompted.

### 3. Test Install from TestPyPI

```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple iso-flowchart-generator
```

## Upload to Production PyPI

### 1. Configure PyPI Token

**Option A: Interactive**
```bash
twine upload dist/*
# Username: __token__
# Password: <your-pypi-token>
```

**Option B: Using .pypirc**

Create `~/.pypirc`:
```ini
[pypi]
username = __token__
password = pypi-<your-token-here>
```

**Option C: Environment Variable**
```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-<your-token-here>
twine upload dist/*
```

### 2. Upload Package

```bash
twine upload dist/*
```

Verify upload at: https://pypi.org/project/iso-flowchart-generator/

## Post-Deployment

### 1. Create GitHub Release

```bash
git tag -a v2.1.0 -m "Release version 2.1.0"
git push origin v2.1.0
```

Then create release on GitHub with:
- Release notes from CHANGELOG.md
- Compiled binaries (if applicable)
- Link to PyPI package

### 2. Test Installation

```bash
# Fresh install
pip install iso-flowchart-generator

# Verify
flowchart --version
flowchart tutorial
```

### 3. Update Documentation

- [ ] Update README.md installation instructions
- [ ] Update QUICKSTART.md with PyPI install method
- [ ] Announce on GitHub Discussions
- [ ] Share on social media/communities

## Versioning Strategy

Follow [Semantic Versioning](https://semver.org/):

- **MAJOR** (X.0.0): Breaking API changes
- **MINOR** (x.Y.0): New features, backward compatible
- **PATCH** (x.y.Z): Bug fixes, backward compatible

### Version Update Checklist

1. Update `pyproject.toml`  `version = "X.Y.Z"`
2. Update `setup.py`  `version="X.Y.Z"`
3. Update `VERSION` file  `X.Y.Z`
4. Update `README.md`  Badge and version mentions
5. Update `CHANGELOG.md`  Add release section

## Automated Publishing (GitHub Actions)

Create `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install build twine
    
    - name: Build package
      run: python -m build
    
    - name: Publish to PyPI
      env:
        TWINE_USERNAME: __token__
        TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
      run: twine upload dist/*
```

Add `PYPI_API_TOKEN` to GitHub repository secrets.

## Troubleshooting

### Package Already Exists

You cannot re-upload the same version. Increment version number.

### Missing Files in Package

Check `MANIFEST.in` and `pyproject.toml` includes.

### Import Errors After Install

Verify package structure:
```bash
pip show -f iso-flowchart-generator
```

### Permission Errors

Verify your PyPI API token has upload permissions.

## Package Maintenance

### Monitor Package Health

- Check download stats: https://pypistats.org/packages/iso-flowchart-generator
- Monitor issues: https://github.com/Aren-Garro/Flowcharts/issues
- Review PyPI package page regularly

### Security Updates

Dependabot will create PRs for dependency updates. Review and merge promptly.

### Deprecation Notices

If deprecating features:
1. Add warnings in code
2. Document in CHANGELOG.md
3. Give users 2-3 minor versions before removal

## Resources

- [Python Packaging Guide](https://packaging.python.org/)
- [PyPI Help](https://pypi.org/help/)
- [Twine Documentation](https://twine.readthedocs.io/)
- [Semantic Versioning](https://semver.org/)

## Quick Reference

```bash
# Complete deployment workflow
rm -rf dist/ build/ *.egg-info
python run_all_tests.py
python -m build
twine check dist/*
twine upload dist/*
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

