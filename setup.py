from setuptools import setup, find_packages
import os

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read version from VERSION file
version = "2.1.0"
if os.path.exists("VERSION"):
    with open("VERSION", "r") as f:
        version = f.read().strip()

# Find all packages in both src and cli directories
packages = []
for pkg in find_packages(where="src"):
    packages.append(pkg)
for pkg in find_packages(where="."):
    if pkg.startswith("cli") or pkg.startswith("src"):
        packages.append(pkg)

# Remove duplicates
packages = list(set(packages))

setup(
    name="iso-flowchart-generator",
    version=version,
    author="Aren Garro",
    author_email="aren@garrollc.com",
    description="NLP-driven ISO 5807 compliant flowchart generator with local AI extraction",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Aren-Garro/Flowcharts",
    project_urls={
        "Bug Tracker": "https://github.com/Aren-Garro/Flowcharts/issues",
        "Documentation": "https://github.com/Aren-Garro/Flowcharts/blob/main/QUICKSTART.md",
        "Source Code": "https://github.com/Aren-Garro/Flowcharts",
    },
    packages=packages,
    package_dir={"": "."},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "Intended Audience :: System Administrators",
        "Topic :: Software Development :: Documentation",
        "Topic :: Software Development :: Code Generators",
        "Topic :: Text Processing :: Linguistic",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Environment :: Console",
    ],
    keywords="flowchart diagram workflow iso-5807 documentation nlp ai llm process-mapping visualization graphviz mermaid d2",
    python_requires=">=3.9",
    install_requires=[
        "spacy>=3.8.0",
        "nltk>=3.8.0",
        "pydantic>=2.0.0",
        "typer>=0.9.0",
        "rich>=13.0.0",
        "python-dotenv>=1.0.0",
        "PyPDF2>=3.0.0",
        "pdfplumber>=0.10.0",
        "python-docx>=1.1.0",
        "pyperclip>=1.8.0",
        "flask>=3.0.0",
        "flask-cors>=4.0.0",
        "graphviz>=0.20.0",
    ],
    extras_require={
        "llm": [
            "llama-cpp-python>=0.2.0",
            "instructor>=1.0.0",
        ],
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "isort>=5.12.0",
            "mypy>=1.0.0",
        ],
        "all": [
            "llama-cpp-python>=0.2.0",
            "instructor>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "flowchart=cli.main:app",
            "flowchart-gen=cli.main:app",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
