import requests
import json

response = requests.post(
    "http://localhost:8000/api/coding/generate-problem",
    json={
        "job_description": "We're looking for a Python backend developer with strong experience in API development and data structures.",
        "skills_required": ["Python", "FastAPI", "Data Structures", "Algorithms"],
        "difficulty_level": "intermediate"
    }
)

print(json.dumps(response.json(), indent=2))