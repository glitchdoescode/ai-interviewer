# AI Interviewer

A LangGraph-based application for conducting technical interviews with AI. This system helps candidates practice for technical interviews by simulating a real interview experience with voice capabilities.

## Features

- AI-powered technical interviewer 
- Voice interface (speech-to-text and text-to-speech)
- Chat-based interface
- Session persistence with MongoDB
- Coding challenges with real-time feedback
- Interview progress tracking and history

## Architecture

The application consists of:
1. A backend built with LangGraph, FastAPI, and MongoDB
2. A frontend built with React, Chakra UI, and React Router

## Installation

### Prerequisites

- Python 3.9+
- Node.js 14+
- MongoDB (optional, can be configured to use memory storage)

### Backend Setup

1. Clone the repository
   ```
   git clone https://github.com/yourusername/ai-interviewer.git
   cd ai-interviewer
   ```

2. Create and activate a virtual environment
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies
   ```
   pip install -r requirements.txt
   ```

4. Set up environment variables
   - Create a `.env` file in the root directory
   - Add the following variables:
     ```
     OPENAI_API_KEY=your_openai_api_key
     MONGODB_URI=your_mongodb_uri  # Optional
     ```

### Frontend Setup

1. Install dependencies
   ```
   cd frontend
   npm install
   ```

2. Build the frontend
   ```
   npm run build
   ```

## Running the Application

Once you've set up the backend and built the frontend, you can run the full application:

```
python -m ai_interviewer.server
```

The application will be available at:
- Web interface: http://localhost:8000
- API documentation: http://localhost:8000/docs

## Development

### Backend Development

To run only the backend API server during development:

```
python -m ai_interviewer.server
```

### Frontend Development

To run the frontend in development mode with hot reloading:

```
cd frontend
npm start
```

This will start the React development server at http://localhost:3000. API requests will be proxied to the backend at http://localhost:8000.

## Usage

1. Open the application in your browser
2. Start a new interview or continue a previous session
3. Respond to the AI interviewer's questions via text or voice
4. Complete the interview process including coding challenges
5. Review your performance and feedback

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
