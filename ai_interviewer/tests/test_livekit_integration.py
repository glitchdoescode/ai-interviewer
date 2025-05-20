import pytest
import os
from unittest.mock import Mock, patch
from ai_interviewer.core.integrations.livekit_service import LiveKitService

@pytest.fixture
def mock_env_vars():
    """Set up mock environment variables for testing."""
    with patch.dict(os.environ, {
        'LIVEKIT_HOST': 'http://test-livekit:7880',
        'LIVEKIT_API_KEY': 'test-key',
        'LIVEKIT_API_SECRET': 'test-secret'
    }):
        yield

@pytest.fixture
def livekit_service(mock_env_vars):
    """Create a LiveKitService instance with mocked RoomServiceClient."""
    with patch('ai_interviewer.core.integrations.livekit_service.RoomServiceClient') as mock_client:
        service = LiveKitService()
        service.room_service = mock_client
        return service

@pytest.mark.asyncio
async def test_create_room_if_not_exists(livekit_service):
    """Test room creation functionality."""
    room_name = "test-room"
    
    # Test successful room creation
    await livekit_service.create_room_if_not_exists(room_name)
    assert room_name in livekit_service.active_rooms
    assert 'participants' in livekit_service.active_rooms[room_name]
    assert 'tracks' in livekit_service.active_rooms[room_name]

    # Test room already exists
    livekit_service.room_service.create_room.side_effect = api.RoomAlreadyExistsError()
    await livekit_service.create_room_if_not_exists(room_name)
    assert room_name in livekit_service.active_rooms

@pytest.mark.asyncio
async def test_generate_join_token(livekit_service):
    """Test token generation."""
    room_name = "test-room"
    participant_id = "test-user"
    participant_name = "Test User"
    
    token = await livekit_service.generate_join_token(
        room_name=room_name,
        participant_identity=participant_id,
        participant_name=participant_name
    )
    
    assert token is not None
    assert isinstance(token, str)

def test_handle_participant_joined(livekit_service):
    """Test participant join handling."""
    room_name = "test-room"
    participant_id = "test-user"
    participant_name = "Test User"
    
    livekit_service.handle_participant_joined(room_name, participant_id, participant_name)
    
    assert room_name in livekit_service.active_rooms
    assert participant_id in livekit_service.active_rooms[room_name]['participants']
    assert livekit_service.active_rooms[room_name]['participants'][participant_id]['name'] == participant_name

def test_handle_participant_left(livekit_service):
    """Test participant leave handling."""
    room_name = "test-room"
    participant_id = "test-user"
    
    # Add participant first
    livekit_service.handle_participant_joined(room_name, participant_id)
    assert participant_id in livekit_service.active_rooms[room_name]['participants']
    
    # Test removal
    livekit_service.handle_participant_left(room_name, participant_id)
    assert participant_id not in livekit_service.active_rooms[room_name]['participants']

def test_handle_track_published(livekit_service):
    """Test track publication handling."""
    room_name = "test-room"
    participant_id = "test-user"
    track_id = "test-track"
    track_type = "audio"
    
    # Add participant first
    livekit_service.handle_participant_joined(room_name, participant_id)
    
    # Test track publication
    livekit_service.handle_track_published(room_name, participant_id, track_id, track_type)
    
    assert track_id in livekit_service.active_rooms[room_name]['tracks']
    assert livekit_service.active_rooms[room_name]['tracks'][track_id]['type'] == track_type
    assert track_id in livekit_service.active_rooms[room_name]['participants'][participant_id]['tracks']

def test_handle_track_unpublished(livekit_service):
    """Test track unpublication handling."""
    room_name = "test-room"
    participant_id = "test-user"
    track_id = "test-track"
    track_type = "audio"
    
    # Set up track first
    livekit_service.handle_participant_joined(room_name, participant_id)
    livekit_service.handle_track_published(room_name, participant_id, track_id, track_type)
    
    # Test track unpublication
    livekit_service.handle_track_unpublished(room_name, track_id)
    
    assert track_id not in livekit_service.active_rooms[room_name]['tracks']
    assert track_id not in livekit_service.active_rooms[room_name]['participants'][participant_id]['tracks']

def test_get_room_participants(livekit_service):
    """Test getting room participants."""
    room_name = "test-room"
    participant_id = "test-user"
    
    livekit_service.handle_participant_joined(room_name, participant_id)
    participants = livekit_service.get_room_participants(room_name)
    
    assert participant_id in participants
    assert participants[participant_id]['tracks'] == []

def test_get_room_tracks(livekit_service):
    """Test getting room tracks."""
    room_name = "test-room"
    participant_id = "test-user"
    track_id = "test-track"
    track_type = "audio"
    
    livekit_service.handle_participant_joined(room_name, participant_id)
    livekit_service.handle_track_published(room_name, participant_id, track_id, track_type)
    
    tracks = livekit_service.get_room_tracks(room_name)
    assert track_id in tracks
    assert tracks[track_id]['type'] == track_type 