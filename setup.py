"""
Setup script for the AI Interviewer package.
"""
from setuptools import setup, find_packages

# Read the long description from README.md
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="ai_interviewer",
    version="0.1.0",
    author="AI Interviewer Team",
    author_email="example@example.com",
    description="An AI-powered technical interview platform",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/ai-interviewer",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "langchain-core>=0.1.0",
        "python-dotenv>=1.0.0",
        "radon>=6.0.1",
        "pylint>=3.0.0",
        "black>=23.7.0",
        "pydantic>=2.5.2",
        "typing-extensions>=4.8.0",
        "langchain>=0.1.0",
        "langgraph>=0.0.27",
        "langchain-google-genai>=0.0.5",
        "reportlab>=4.1.0"
    ],
    entry_points={
        "console_scripts": [
            "ai-interviewer=ai_interviewer.cli:main",
        ],
    },
) 