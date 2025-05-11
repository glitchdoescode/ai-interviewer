# AI Interviewer Platform

An intelligent, voice-driven interview platform with adaptive Q&A, interactive coding challenges, and objective evaluation.

## Features

- **Dynamic, Voice-Driven Interviews**: Real-time, adaptive question flows based on candidate responses
- **Interactive Coding Challenges**: Code execution with AI pair programming assistance ("vibe coding")
- **Rubric-Based Evaluation**: Detailed assessment of technical competency and soft skills
- **LangGraph Orchestration**: State-managed interview workflow with checkpointing and persistence
- **Adaptive Question Generation**: Context-aware questions based on candidate skill level and responses
- **Multi-Stage Interview Process**: Structured flow from greeting through Q&A, coding, and feedback
- **Comprehensive Logging**: Detailed logging of interview progress and state transitions

## Getting Started

### Prerequisites

- Python 3.9+
- Git
- Google API key (for Gemini model)

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
python -m ai_interviewer.cli --topic python --skill-level intermediate
```

## Project Structure

```
ai-interviewer/
├── ai_interviewer/           # Main package directory
│   ├── core/                # Core LangGraph implementation
│   │   ├── agent.py        # Interview agent implementation
│   │   └── workflow.py     # LangGraph workflow definition
│   ├── models/             # State and data models
│   │   ├── state.py       # Interview state definitions
│   │   └── coding_challenge.py  # Coding challenge models
│   ├── tools/              # LangGraph tools
│   │   ├── basic_tools.py     # Core interview tools
│   │   ├── dynamic_tools.py   # Dynamic question generation
│   │   └── coding_tools.py    # Coding challenge tools
│   ├── utils/              # Utility functions
│   │   └── logging_utils.py   # Logging configuration
│   ├── tests/              # Test suite
│   │   └── test_workflow.py   # Workflow tests
│   └── cli.py             # Command-line interface
├── logs/                   # Application logs
├── requirements.txt        # Project dependencies
├── setup.py               # Package setup
├── README.md              # This file
├── progress-report.md     # Development progress tracking
└── checklist.md           # Development checklist and roadmap
```

## Development Status

This project is currently in active development. See:
- `progress-report.md` for current implementation status
- `checklist.md` for development roadmap and planned features

## License

This project is licensed under the MIT License - see the LICENSE file for details.
