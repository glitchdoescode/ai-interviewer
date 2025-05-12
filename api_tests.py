#!/usr/bin/env python
"""
API testing script for the AI Interviewer FastAPI server.

This script tests the main API endpoints to ensure they are working correctly.
"""
import os
import sys
import json
import time
import asyncio
import logging
import unittest
import requests
from uuid import uuid4
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# API URL
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

class AIInterviewerAPITest(unittest.TestCase):
    """Test case for the AI Interviewer API endpoints."""
    
    def setUp(self):
        """Set up test case."""
        self.user_id = f"test-user-{uuid4()}"
        self.session_id = None
    
    def test_01_health_check(self):
        """Test health check endpoint."""
        response = requests.get(f"{API_BASE_URL}/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        logger.info("Health check passed")
    
    def test_02_start_interview(self):
        """Test starting a new interview session."""
        payload = {
            "message": "Hello, I'm here for the interview",
            "user_id": self.user_id
        }
        response = requests.post(f"{API_BASE_URL}/api/interview", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("response", data)
        self.assertIn("session_id", data)
        self.session_id = data["session_id"]
        logger.info(f"Started interview session: {self.session_id}")
    
    def test_03_continue_interview(self):
        """Test continuing an interview session."""
        if not self.session_id:
            self.test_02_start_interview()
        
        payload = {
            "message": "I have experience with Python and JavaScript",
            "user_id": self.user_id
        }
        response = requests.post(f"{API_BASE_URL}/api/interview/{self.session_id}", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("response", data)
        self.assertIn("session_id", data)
        logger.info(f"Continued interview session: {self.session_id}")
    
    def test_04_get_user_sessions(self):
        """Test retrieving user sessions."""
        if not self.session_id:
            self.test_02_start_interview()
        
        response = requests.get(f"{API_BASE_URL}/api/sessions/{self.user_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        # Should have at least the session we created
        self.assertGreaterEqual(len(data), 1)
        logger.info(f"Retrieved {len(data)} sessions for user {self.user_id}")
    
    def test_05_invalid_session(self):
        """Test continuing an invalid session."""
        invalid_session_id = f"invalid-session-{uuid4()}"
        payload = {
            "message": "This should fail",
            "user_id": self.user_id
        }
        response = requests.post(f"{API_BASE_URL}/api/interview/{invalid_session_id}", json=payload)
        self.assertEqual(response.status_code, 404)
        logger.info("Invalid session test passed")
    
    def test_06_rate_limiting(self):
        """Test rate limiting."""
        payload = {
            "message": "Test message",
            "user_id": self.user_id
        }
        
        # Send multiple requests to trigger rate limiting
        for i in range(15):
            response = requests.post(f"{API_BASE_URL}/api/interview", json=payload)
            if response.status_code == 429:
                logger.info("Rate limiting test passed")
                return
            time.sleep(0.1)  # Small delay between requests
        
        # If we didn't hit rate limiting, the test fails
        self.fail("Rate limiting not triggered")
    
    def test_07_error_handling(self):
        """Test error handling with an invalid payload."""
        payload = {
            # Missing required "message" field
            "user_id": self.user_id
        }
        response = requests.post(f"{API_BASE_URL}/api/interview", json=payload)
        self.assertIn(response.status_code, [400, 422])  # Either is acceptable
        logger.info("Error handling test passed")

def run_tests():
    """Run the API tests."""
    # Check if the API is available
    try:
        response = requests.get(f"{API_BASE_URL}/api/health", timeout=5)
        if response.status_code != 200:
            logger.error(f"API not available at {API_BASE_URL}")
            sys.exit(1)
    except requests.exceptions.RequestException:
        logger.error(f"API not available at {API_BASE_URL}")
        sys.exit(1)
    
    # Run tests
    unittest.main(argv=['first-arg-is-ignored'], exit=False)

if __name__ == "__main__":
    run_tests() 