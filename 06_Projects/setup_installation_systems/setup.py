#!/usr/bin/env python3
"""
BRUTALIST TRADING SUPERVISOR - Setup Script
GitHub-ready distribution package
"""

from setuptools import setup, find_packages
import os
import sys

# Check if running on macOS
if sys.platform != "darwin":
    print("❌ ERROR: This package is for macOS only!")
    sys.exit(1)

# Read README
def read_readme():
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "🎯 BRUTALIST TRADING SUPERVISOR\nmacOS Native Window Management + AI Control"

# Read requirements
def read_requirements():
    requirements_path = os.path.join(os.path.dirname(__file__), 'requirements.txt')
    if os.path.exists(requirements_path):
        with open(requirements_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    return []

setup(
    name="brutalist-trading-supervisor",
    version="1.0.0",
    description="🎯 Brutalist-designed macOS trading supervisor with advanced window management",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    author="Brutalist Trading Systems",
    author_email="brutalist@trading.systems",
    url="https://github.com/brutalist/trading-supervisor",
    
    # Package classification
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS :: MacOS X",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Office/Business :: Financial :: Investment",
        "Topic :: System :: Monitoring",
        "Topic :: System :: Systems Administration",
    ],
    
    # Python version requirement
    python_requires=">=3.8",
    
    # Install requirements
    install_requires=read_requirements(),
    
    # Package files
    py_modules=["macOS_brutal_trading_supervisor"],
    include_package_data=True,
    package_data={
        "": ["*.md", "*.txt", "*.sh", "*.json", "*.yml", "*.yaml"],
    },
    
    # Entry points
    entry_points={
        "console_scripts": [
            "brutalist-supervisor=macOS_brutal_trading_supervisor:main",
        ],
    },
    
    # Project URLs
    project_urls={
        "Bug Reports": "https://github.com/brutalist/trading-supervisor/issues",
        "Source": "https://github.com/brutalist/trading-supervisor",
        "Documentation": "https://github.com/brutalist/trading-supervisor/blob/main/README.md",
    },
    
    # Keywords
    keywords="trading supervisor macos window-management automation ai brutalist",
    
    # Project metadata
    zip_safe=False,
    platforms=["macOS"],
    
    # Additional metadata
    license="MIT",
    
    # Package data
    data_files=[
        ("share/brutalist-supervisor", [
            "README.md",
            "requirements.txt",
            "install_macOS_brutal.sh",
        ]),
    ],
)
