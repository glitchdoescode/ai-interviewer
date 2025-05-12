# AI Interviewer Frontend

This is the React frontend for the AI Interviewer application. It provides a web interface for conducting technical interviews with an AI interviewer.

## Features

- Real-time chat interface for interviewing
- Voice input and output capabilities
- Session management and history
- Responsive design for all devices

## Technologies Used

- React.js
- Chakra UI for styling
- React Router for navigation
- Axios for API requests
- Recorder.js for audio recording

## Getting Started

### Prerequisites

- Node.js 14+ and npm

### Installation

1. Navigate to the frontend directory:
   ```
   cd frontend
   ```

2. Install dependencies:
   ```
   npm install
   ```

3. Configure the environment variables (if needed):
   Create a `.env` file in the root of the frontend directory with the following:
   ```
   REACT_APP_API_URL=http://localhost:8000
   ```

### Development

Start the development server:
```
npm start
```

This will run the app in development mode. Open [http://localhost:3000](http://localhost:3000) to view it in the browser.

### Building for Production

```
npm run build
```

This builds the app for production to the `build` folder. It correctly bundles React in production mode and optimizes the build for the best performance.

## Connecting with Backend

The frontend expects a backend API running at `/api` (or the URL specified in `REACT_APP_API_URL` environment variable). Make sure the backend server is running before using the frontend.

## Folder Structure

- `src/`: Source code
  - `api/`: API service functions
  - `components/`: Reusable React components
  - `context/`: React context providers
  - `hooks/`: Custom React hooks
  - `pages/`: Main application pages
- `public/`: Static assets and HTML template

## Contributing

1. Create a feature branch (`git checkout -b feature/amazing-feature`)
2. Commit your changes (`git commit -m 'Add some amazing feature'`)
3. Push to the branch (`git push origin feature/amazing-feature`)
4. Open a Pull Request 