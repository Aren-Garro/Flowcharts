from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="iso-flowchart-generator",
    version="0.1.0",
    author="Aren Garro",
    description="NLP-driven ISO 5807 compliant flowchart generator",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Aren-Garro/Flowcharts",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Documentation",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.9",
    install_requires=[
        "spacy>=3.8.0",
        "nltk>=3.8.0",
        "pydantic>=2.0.0",
        "typer>=0.9.0",
        "rich>=13.0.0",
        "python-dotenv>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "flowchart=cli.main:app",
        ],
    },
)
