"""
Setup file for the AI Interviewer package.
"""
from setuptools import setup, find_packages

setup(
    name="ai_interviewer",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "langchain>=0.1.0",
        "langgraph>=0.0.27",
        "langchain-google-genai>=0.0.5",
        "pydantic>=2.5.2",
        "python-dotenv>=1.0.0",
        "typing-extensions>=4.8.0",
    ],
    entry_points={
        "console_scripts": [
            "ai-interviewer=ai_interviewer.cli:run_interview_cli",
        ],
    },
    python_requires=">=3.9",
    author="AI Interviewer Team",
    author_email="your.email@example.com",
    description="An intelligent platform for conducting technical interviews",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
) 