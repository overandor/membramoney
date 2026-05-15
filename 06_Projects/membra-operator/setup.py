"""
MEMBRA Operator macOS App Bundle
py2app setup
"""
from setuptools import setup

APP = ["main.py"]
DATA_FILES = []
OPTIONS = {
    "argv_emulation": False,
    "packages": ["requests", "speech_recognition"],
    "includes": ["tkinter", "sqlite3", "uuid", "json", "subprocess", "pathlib", "threading", "datetime"],
    "excludes": ["matplotlib", "numpy", "pandas", "scipy", "PIL", "pytest", "mypy"],
    "plist": {
        "CFBundleName": "MEMBRA Operator",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "0.1.0",
        "CFBundleIdentifier": "ai.membra.operator",
        "LSMinimumSystemVersion": "12.0",
        "NSMicrophoneUsageDescription": "MEMBRA Operator uses the microphone for speech-to-text input.",
        "NSRequiresAquaSystemAppearance": False,
    },
    "semi_standalone": True,
    "site_packages": True,
}

setup(
    name="MEMBRA Operator",
    version="0.1.0",
    description="Persistent AI pair-programmer for Windsurf / MEMBRA",
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
