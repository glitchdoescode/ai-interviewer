import os
import logging
from livekit import api

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LIVEKIT_HOST = os.environ.get("LIVEKIT_HOST", "http://localhost:7880")
LIVEKIT_API_KEY = os.environ.get("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.environ.get("LIVEKIT_API_SECRET")

class LiveKitService:
    def __init__(self):
        if not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
            raise ValueError("LIVEKIT_API_KEY and LIVEKIT_API_SECRET must be set in environment variables.")
        self.livekit_api = api.LiveKitAPI(LIVEKIT_HOST)
        self.active_rooms = {}  # Track active rooms and their participants

    async def create_room_if_not_exists(self, room_name: str):
        try:
            await self.livekit_api.room.create_room(
                api.CreateRoomRequest(name=room_name)
            )
            logger.info(f"Room '{room_name}' created.")
            self.active_rooms[room_name] = {
                'participants': {},
                'tracks': {}
            }
        except Exception as e:
            if "already exists" in str(e):
                logger.info(f"Room '{room_name}' already exists.")
                if room_name not in self.active_rooms:
                    self.active_rooms[room_name] = {
                        'participants': {},
                        'tracks': {}
                    }
            else:
                logger.error(f"Error creating room '{room_name}': {e}")
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

        # Create access token with the specified permissions
        token = api.AccessToken() \
            .with_identity(participant_identity) \
            .with_name(participant_name or participant_identity)

        if participant_metadata:
            token = token.with_metadata(participant_metadata)

        # Add video grants
        token = token.with_grants(api.VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=can_publish,
            can_subscribe=can_subscribe,
            hidden=hidden
        ))

        return token.to_jwt()

    def handle_participant_joined(self, room_name: str, participant_id: str, participant_name: str = None):
        """Handle a new participant joining a room."""
        if room_name not in self.active_rooms:
            self.active_rooms[room_name] = {'participants': {}, 'tracks': {}}
        
        self.active_rooms[room_name]['participants'][participant_id] = {
            'name': participant_name,
            'tracks': []
        }
        logger.info(f"Participant {participant_name or participant_id} joined room {room_name}")

    def handle_participant_left(self, room_name: str, participant_id: str):
        """Handle a participant leaving a room."""
        if room_name in self.active_rooms and participant_id in self.active_rooms[room_name]['participants']:
            participant = self.active_rooms[room_name]['participants'].pop(participant_id)
            logger.info(f"Participant {participant.get('name', participant_id)} left room {room_name}")

    def handle_track_published(self, room_name: str, participant_id: str, track_id: str, track_type: str):
        """Handle a new track being published."""
        if room_name not in self.active_rooms:
            return

        room = self.active_rooms[room_name]
        if participant_id in room['participants']:
            room['participants'][participant_id]['tracks'].append(track_id)
            room['tracks'][track_id] = {
                'type': track_type,
                'participant_id': participant_id
            }
            
            participant_name = room['participants'][participant_id].get('name', participant_id)
            logger.info(f"Received {track_type} track from participant {participant_name} in room {room_name}")
            
            # For this sprint, we're just logging audio tracks
            if track_type == 'audio':
                logger.info(f"Audio track {track_id} received from participant {participant_name} in room {room_name}")

    def handle_track_unpublished(self, room_name: str, track_id: str):
        """Handle a track being unpublished."""
        if room_name in self.active_rooms and track_id in self.active_rooms[room_name]['tracks']:
            track_info = self.active_rooms[room_name]['tracks'].pop(track_id)
            participant_id = track_info['participant_id']
            if participant_id in self.active_rooms[room_name]['participants']:
                tracks = self.active_rooms[room_name]['participants'][participant_id]['tracks']
                if track_id in tracks:
                    tracks.remove(track_id)
            logger.info(f"Track {track_id} unpublished from room {room_name}")

    def get_room_participants(self, room_name: str):
        """Get all participants in a room."""
        if room_name in self.active_rooms:
            return self.active_rooms[room_name]['participants']
        return {}

    def get_room_tracks(self, room_name: str):
        """Get all tracks in a room."""
        if room_name in self.active_rooms:
            return self.active_rooms[room_name]['tracks']
        return {}

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