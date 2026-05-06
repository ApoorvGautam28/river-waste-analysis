"""
Setup script for River Waste Analysis System
"""

from setuptools import setup, find_packages

with open("README_STREAMLIT.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements_streamlit.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="river-waste-analysis",
    version="1.0.0",
    author="Apoorv Gautam",
    author_email="apoorv.gautam@example.com",
    description="AI-powered River Waste Analysis System",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ApoorvGautam28/river-waste-analysis",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "river-waste-analysis=app_streamlit:main",
        ],
    },
)
