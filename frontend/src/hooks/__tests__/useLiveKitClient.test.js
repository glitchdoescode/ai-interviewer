import { renderHook, act } from '@testing-library/react-hooks';
import axios from 'axios';
import { Room, RoomEvent, createLocalTracks } from 'livekit-client';
import { useLiveKitClient } from '../useLiveKitClient';

// Mock axios
jest.mock('axios');

// Mock livekit-client
jest.mock('livekit-client', () => ({
  Room: jest.fn().mockImplementation(() => ({
    connect: jest.fn().mockResolvedValue(undefined),
    disconnect: jest.fn().mockResolvedValue(undefined),
    on: jest.fn().mockReturnThis(),
    localParticipant: {
      publishTrack: jest.fn().mockResolvedValue(undefined)
    }
  })),
  RoomEvent: {
    Connected: 'connected',
    Disconnected: 'disconnected',
    ConnectionStateChanged: 'connectionStateChanged',
    MediaDevicesError: 'mediaDevicesError'
  },
  createLocalTracks: jest.fn()
}));

describe('useLiveKitClient', () => {
  const mockUserId = 'test-user';
  const mockUserName = 'Test User';
  const mockInterviewId = 'test-interview';
  const mockToken = 'test-token';
  const mockRoomName = 'test-room';

  beforeEach(() => {
    // Reset all mocks
    jest.clearAllMocks();
    
    // Mock successful token fetch
    axios.post.mockResolvedValue({
      data: { token: mockToken, room_name: mockRoomName }
    });
    
    // Mock successful audio track creation
    createLocalTracks.mockResolvedValue([
      { kind: 'audio', mute: jest.fn(), unmute: jest.fn(), stop: jest.fn() }
    ]);
  });

  it('should initialize with default values', () => {
    const { result } = renderHook(() => 
      useLiveKitClient(mockUserId, mockUserName, mockInterviewId)
    );

    expect(result.current.isConnecting).toBe(false);
    expect(result.current.isConnected).toBe(false);
    expect(result.current.error).toBeNull();
    expect(result.current.isMicrophoneEnabled).toBe(false);
  });

  it('should connect successfully', async () => {
    const { result } = renderHook(() => 
      useLiveKitClient(mockUserId, mockUserName, mockInterviewId)
    );

    await act(async () => {
      await result.current.connect();
    });

    expect(axios.post).toHaveBeenCalledWith(
      `/api/interview/${mockInterviewId}/livekit-token`,
      {
        user_id: mockUserId,
        participant_name: mockUserName
      }
    );

    expect(createLocalTracks).toHaveBeenCalledWith({
      audio: true,
      video: false
    });

    expect(result.current.isConnected).toBe(true);
    expect(result.current.error).toBeNull();
  });

  it('should handle connection errors', async () => {
    // Mock a failed token fetch
    axios.post.mockRejectedValue(new Error('Failed to get token'));

    const { result } = renderHook(() => 
      useLiveKitClient(mockUserId, mockUserName, mockInterviewId)
    );

    await act(async () => {
      await result.current.connect();
    });

    expect(result.current.isConnected).toBe(false);
    expect(result.current.error).toBe('Failed to get LiveKit token');
  });

  it('should handle microphone toggle', async () => {
    const { result } = renderHook(() => 
      useLiveKitClient(mockUserId, mockUserName, mockInterviewId)
    );

    // Connect first
    await act(async () => {
      await result.current.connect();
    });

    // Toggle microphone
    await act(async () => {
      await result.current.toggleMicrophone();
    });

    expect(result.current.isMicrophoneEnabled).toBe(true);

    // Toggle again
    await act(async () => {
      await result.current.toggleMicrophone();
    });

    expect(result.current.isMicrophoneEnabled).toBe(false);
  });

  it('should disconnect and cleanup', async () => {
    const { result, unmount } = renderHook(() => 
      useLiveKitClient(mockUserId, mockUserName, mockInterviewId)
    );

    // Connect first
    await act(async () => {
      await result.current.connect();
    });

    // Disconnect
    await act(async () => {
      await result.current.disconnect();
    });

    expect(result.current.isConnected).toBe(false);
    expect(result.current.isMicrophoneEnabled).toBe(false);

    // Cleanup on unmount
    unmount();
  });
}); 