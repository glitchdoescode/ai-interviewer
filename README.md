# AI Interviewer Platform

An intelligent, voice-driven interview platform with adaptive Q&A, interactive coding challenges, and objective evaluation.

## Features

- **Dynamic, Voice-Driven Interviews**: Real-time, adaptive question flows based on candidate responses
- **Interactive Coding Challenges**: Code execution with AI pair programming assistance ("vibe coding")
- **Rubric-Based Evaluation**: Detailed assessment of technical competency and soft skills
- **Cloud-Native Architecture**: Scalable microservices design with LangGraph and LLM orchestration

## Getting Started

### Prerequisites

- Python 3.9+
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/ai-interviewer.git
cd ai-interviewer

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create a .env file with your API keys
cp .env.example .env
# Edit .env with your API keys
```

### Running the Application

```bash
# Run the command-line test interface
python -m ai_interviewer.cli
```

## Project Structure

```
ai-interviewer/
├── core/            # Core LangGraph implementation
├── models/          # State definitions and schemas
├── tools/           # LangGraph tools for interviews
├── utils/           # Utility functions
├── logs/            # Application logs
└── tests/           # Unit and integration tests
```

## Development Status

This project is currently in development according to the planned phases in `checklist.md`. See `progress-report.md` for current status.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
