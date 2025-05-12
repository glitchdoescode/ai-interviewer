#!/usr/bin/env python
"""
Test script for running the AI Interviewer FastAPI server.
"""
import os
import logging
from ai_interviewer.server import start_server

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    # Set Deepgram API key from environment if available
    api_key = os.environ.get("DEEPGRAM_API_KEY")
    if not api_key:
        logger.warning("DEEPGRAM_API_KEY environment variable not set. Voice features will be disabled.")
    
    logger.info("Starting AI Interviewer API server...")
    start_server(host="0.0.0.0", port=8000) 