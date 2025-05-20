import os
from livekit import api
from livekit.api import RoomServiceClient, AccessToken, VideoGrant

LIVEKIT_HOST = os.environ.get("LIVEKIT_HOST", "http://localhost:7880")
LIVEKIT_API_KEY = os.environ.get("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.environ.get("LIVEKIT_API_SECRET")

class LiveKitService:
    def __init__(self):
        if not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
            raise ValueError("LIVEKIT_API_KEY and LIVEKIT_API_SECRET must be set in environment variables.")
        self.room_service = RoomServiceClient(LIVEKIT_HOST, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)

    async def create_room_if_not_exists(self, room_name: str):
        try:
            await self.room_service.create_room(name=room_name)
            print(f"Room '{room_name}' created.")
        except api.RoomAlreadyExistsError:
            print(f"Room '{room_name}' already exists.")
        except Exception as e:
            print(f"Error creating room '{room_name}': {e}")
            raise

    async def generate_join_token(
        self, 
        room_name: str, 
        participant_identity: str,
        participant_name: str = None,
        participant_metadata: str = None,
        can_publish: bool = True,
        can_subscribe: bool = True,
        hidden: bool = False
    ) -> str:
        if not participant_identity:
            raise ValueError("Participant identity cannot be empty.")

        await self.create_room_if_not_exists(room_name)

        grant = VideoGrant(
            room_join=True,
            room=room_name,
            can_publish=can_publish,
            can_subscribe=can_subscribe,
            can_publish_data=True, # Important for potential future data channel use
            hidden=hidden,
        )
        
        access_token = AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        access_token.identity = participant_identity
        if participant_name:
            access_token.name = participant_name
        if participant_metadata:
            access_token.metadata = participant_metadata
        
        access_token.add_grant(grant)
        
        return access_token.to_jwt()

# Example usage (for testing purposes, remove later)
async def main():
    import asyncio
    # Ensure LIVEKIT_API_KEY and LIVEKIT_API_SECRET are set in your environment
    if not os.getenv("LIVEKIT_API_KEY") or not os.getenv("LIVEKIT_API_SECRET"):
        print("Please set LIVEKIT_API_KEY and LIVEKIT_API_SECRET environment variables to run this example.")
        print("You can get them from your LiveKit Cloud project or your self-hosted LiveKit server.")
        return

    service = LiveKitService()
    try:
        room_name = "test-interview-room"
        user_identity = "user123"
        ai_identity = "ai-interviewer"

        user_token = await service.generate_join_token(room_name, user_identity, participant_name="Test User")
        print(f"User Join Token for room '{room_name}', identity '{user_identity}': {user_token}")

        # AI might need to publish but could be hidden or have different metadata
        ai_token = await service.generate_join_token(
            room_name, 
            ai_identity, 
            participant_name="AI Interviewer",
            can_publish=True, # AI needs to publish its spoken response
            can_subscribe=True # AI needs to subscribe to user's audio
        )
        print(f"AI Join Token for room '{room_name}', identity '{ai_identity}': {ai_token}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    # This part is for manual testing of this script.
    # You'll need to have a LiveKit server running.
    # Set LIVEKIT_API_KEY and LIVEKIT_API_SECRET environment variables.
    # e.g. export LIVEKIT_API_KEY=your_key
    #      export LIVEKIT_API_SECRET=your_secret
    #      python ai_interviewer/core/integrations/livekit_service.py
    # Note: For asyncio to run in some environments, you might need:
    # import asyncio
    # asyncio.run(main())
    # However, to keep it simple for copy-pasting:
    print("To run the example: ensure LiveKit server is running and API keys are set, then execute:")
    print("import asyncio; from ai_interviewer.core.integrations.livekit_service import main as lk_main; asyncio.run(lk_main())") 