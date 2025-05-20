import { useState, useCallback, useEffect } from 'react';
import { Room, RoomEvent, LocalTrack, createLocalTracks } from 'livekit-client';
import axios from 'axios';

/**
 * Hook for managing LiveKit client-side functionality
 * @param {string} userId - Unique identifier for the user
 * @param {string} userName - Display name for the user
 * @param {string} interviewId - Interview session ID
 * @returns {Object} LiveKit client state and functions
 */
export const useLiveKitClient = (userId, userName, interviewId) => {
  const [room, setRoom] = useState(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState(null);
  const [localAudioTrack, setLocalAudioTrack] = useState(null);
  const [isMicrophoneEnabled, setIsMicrophoneEnabled] = useState(false);

  // Function to fetch LiveKit token from backend
  const fetchToken = useCallback(async () => {
    try {
      const response = await axios.post(`/api/interview/${interviewId}/livekit-token`, {
        user_id: userId,
        participant_name: userName
      });
      return response.data;
    } catch (err) {
      console.error('Error fetching LiveKit token:', err);
      throw new Error('Failed to get LiveKit token');
    }
  }, [userId, userName, interviewId]);

  // Function to request microphone permissions and create local audio track
  const setupLocalAudio = useCallback(async () => {
    try {
      const tracks = await createLocalTracks({
        audio: true,
        video: false
      });
      const audioTrack = tracks.find(track => track.kind === 'audio');
      if (audioTrack) {
        setLocalAudioTrack(audioTrack);
        setIsMicrophoneEnabled(true);
        return audioTrack;
      }
      throw new Error('No audio track created');
    } catch (err) {
      console.error('Error setting up local audio:', err);
      setError('Failed to access microphone');
      throw err;
    }
  }, []);

  // Function to connect to LiveKit room
  const connect = useCallback(async () => {
    if (isConnecting || isConnected) return;
    
    setIsConnecting(true);
    setError(null);

    try {
      // Get token
      const { token, room_name } = await fetchToken();

      // Create and connect to room
      const newRoom = new Room({
        adaptiveStream: true,
        dynacast: true,
        // Add any additional room options here
      });

      // Set up room event listeners
      newRoom
        .on(RoomEvent.Connected, () => {
          console.log('Connected to LiveKit room');
          setIsConnected(true);
          setIsConnecting(false);
        })
        .on(RoomEvent.Disconnected, () => {
          console.log('Disconnected from LiveKit room');
          setIsConnected(false);
          setIsConnecting(false);
        })
        .on(RoomEvent.ConnectionStateChanged, (state) => {
          console.log('Connection state changed:', state);
        })
        .on(RoomEvent.MediaDevicesError, (e) => {
          console.error('Media device error:', e);
          setError('Media device error: ' + e.message);
        });

      // Connect to room
      await newRoom.connect(token, {
        autoSubscribe: true
      });

      // Set up local audio if not already done
      if (!localAudioTrack) {
        const audioTrack = await setupLocalAudio();
        await newRoom.localParticipant.publishTrack(audioTrack);
      } else {
        await newRoom.localParticipant.publishTrack(localAudioTrack);
      }

      setRoom(newRoom);
    } catch (err) {
      console.error('Error connecting to LiveKit:', err);
      setError(err.message);
      setIsConnecting(false);
    }
  }, [isConnecting, isConnected, fetchToken, localAudioTrack, setupLocalAudio]);

  // Function to disconnect from room
  const disconnect = useCallback(async () => {
    if (room) {
      await room.disconnect();
      setRoom(null);
      setIsConnected(false);
    }
    if (localAudioTrack) {
      localAudioTrack.stop();
      setLocalAudioTrack(null);
      setIsMicrophoneEnabled(false);
    }
  }, [room, localAudioTrack]);

  // Function to toggle microphone
  const toggleMicrophone = useCallback(async () => {
    if (!room || !localAudioTrack) return;

    if (isMicrophoneEnabled) {
      await localAudioTrack.mute();
    } else {
      await localAudioTrack.unmute();
    }
    setIsMicrophoneEnabled(!isMicrophoneEnabled);
  }, [room, localAudioTrack, isMicrophoneEnabled]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    isConnecting,
    isConnected,
    error,
    isMicrophoneEnabled,
    connect,
    disconnect,
    toggleMicrophone
  };
}; 