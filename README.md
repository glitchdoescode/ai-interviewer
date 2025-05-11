# AI Interviewer Platform

An AI-powered technical interview platform built with LangGraph, featuring coding challenges, paired programming tools, and comprehensive interview assessments.

## Overview

The AI Interviewer platform is designed to simulate technical interviews for software engineering candidates. It leverages LLMs to conduct interviews, present coding challenges, provide real-time feedback, and evaluate candidate responses. The platform follows a modern architecture pattern based on LangGraph, making it easy to extend and maintain.

## Features

- **Technical Interviews**: Conduct realistic technical interviews with natural conversational flow
- **Coding Challenges**: Present coding challenges and evaluate solutions
- **Pair Programming**: Provide code improvements, completions, and reviews
- **Code Quality Analysis**: Analyze code for complexity, maintainability, and style
- **Session Management**: Persist and resume interview sessions
- **Transcript Generation**: Save interview transcripts for review
- **MongoDB Atlas Support**: Store session data in MongoDB Atlas cloud database

## Architecture

The platform is built around a unified `AIInterviewer` class that encapsulates the entire interview workflow:

- Uses LangGraph for orchestrating the interview process
- Implements a MessagesState-based state management
- Provides a set of specialized tools for coding tasks
- Supports asynchronous interview sessions
- Follows industry best practices for LLM application design
- Integrates with MongoDB for persistent storage (local or Atlas)

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/ai-interviewer.git
cd ai-interviewer

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# Set up configuration 
cp config.env.example .env
# Edit .env with your MongoDB Atlas URI or other settings
```

## Usage

### Command Line Interface

```bash
# Start a new interview
ai-interviewer

# Save the transcript to a file
ai-interviewer --save interview_transcript.txt

# Enable debug logging
ai-interviewer --debug
```

### Python API

```python
import asyncio
from ai_interviewer.core.ai_interviewer import AIInterviewer

async def main():
    # Initialize the interviewer
    interviewer = AIInterviewer()
    
    # Process a user message
    response = await interviewer.run_interview("user123", "Hello, I'm here for my interview.")
    print(response)
    
    # Continue the conversation
    response = await interviewer.run_interview("user123", "I have experience with Python and JavaScript.")
    print(response)

# Run the interview
asyncio.run(main())
```

## Tools

The platform includes several specialized tools:

1. **Coding Challenge Tools**
   - `start_coding_challenge`: Presents a coding challenge to the candidate
   - `submit_code_for_challenge`: Evaluates the candidate's solution
   - `get_coding_hint`: Provides hints if the candidate is stuck

2. **Pair Programming Tools**
   - `suggest_code_improvements`: Offers ways to improve code
   - `complete_code`: Helps complete partial code
   - `review_code_section`: Reviews specific parts of code

3. **Code Quality Tools**
   - Analyzes cyclomatic complexity
   - Checks maintainability index
   - Evaluates documentation coverage
   - Verifies style compliance

## Database Configuration

The platform supports both local MongoDB and MongoDB Atlas:

- **Local MongoDB**: By default, connects to `mongodb://localhost:27017`
- **MongoDB Atlas**: For cloud-based storage, update the `MONGODB_URI` in your `.env` file

For detailed instructions on setting up MongoDB Atlas, see [MongoDB Atlas Setup Guide](docs/mongodb_atlas_setup.md).

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
