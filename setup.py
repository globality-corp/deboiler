from setuptools import find_packages, setup


project = "deboiler"
version = "0.1.0"  # DO NOT EDIT THIS LINE MANUALLY. LET bump2version UTILITY DO IT

with open("README.md") as readme_file:
    readme = readme_file.read()

setup(
    name="deboiler",
    version=version,
    description="Deboiler is an open-source package to clean HTML pages across an entire domain",
    long_description=readme,
    long_description_content_type="text/markdown",
    url="https://github.com/globality-corp/deboiler",
    author="Globality AI",
    keywords=["deboiler", "python", "html cleaning"],
    packages=find_packages(),
    include_package_data=True,
    license="MIT",
    install_requires=[
        "tqdm",
        "pandas",
        "fastavro",
        "lxml",
        "tldextract",
        "importlib-metadata<4.3",  # For flake8 compatibility with importlib-metadata
        "langdetect",
    ],
    extras_require={
        "lint": [
            "flake8-isort>=3.0.1",
            "flake8-print>=3.1.0",
            "flake8-logging-format",
            "globality-black",
        ],
        "typehinting": [
            "mypy",
            "types-setuptools",
        ],
    },
    tests_require=[],
    entry_points={
        "console_scripts": [],
    },
)
