import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import ScreenActivityMonitor from '../ScreenActivityMonitor';
import { useProctoringWebSocket } from '../../../hooks/useProctoringWebSocket';
import { useScreenActivity } from '../../../hooks/useScreenActivity';

// Mock the hooks
jest.mock('../../../hooks/useProctoringWebSocket');
jest.mock('../../../hooks/useScreenActivity');

// Mock Chakra UI components to avoid dependency issues
jest.mock('@chakra-ui/react', () => ({
  Box: ({ children }) => <div data-testid="box">{children}</div>,
  VStack: ({ children }) => <div data-testid="vstack">{children}</div>,
  HStack: ({ children }) => <div data-testid="hstack">{children}</div>,
  Text: ({ children }) => <span data-testid="text">{children}</span>,
  Badge: ({ children }) => <span data-testid="badge">{children}</span>,
  Button: ({ children, onClick }) => <button onClick={onClick} data-testid="button">{children}</button>,
  Collapse: ({ children, in: isOpen }) => isOpen ? <div data-testid="collapse">{children}</div> : null,
  Alert: ({ children }) => <div data-testid="alert">{children}</div>,
  AlertIcon: () => <span data-testid="alert-icon">!</span>,
  AlertTitle: ({ children }) => <span data-testid="alert-title">{children}</span>,
  AlertDescription: ({ children }) => <span data-testid="alert-description">{children}</span>,
  Icon: ({ as }) => <span data-testid="icon">{as?.name || 'icon'}</span>,
  useDisclosure: () => ({ isOpen: false, onToggle: jest.fn() }),
}));

describe('ScreenActivityMonitor', () => {
  const mockProps = {
    sessionId: 'test-session',
    userId: 'test-user',
    isEnabled: true,
    onStatusChange: jest.fn(),
    onEventGenerated: jest.fn(),
  };

  const mockWebSocket = {
    sendEvent: jest.fn(),
    connectionStatus: 'connected',
  };

  const mockScreenActivity = {
    isMonitoring: true,
    activityCount: 0,
    suspiciousCount: 0,
    apiSupport: {
      visibilityAPI: true,
      clipboardAPI: true,
      keyboardAPI: true,
      focusAPI: true,
    },
    recentPatterns: {
      rapidTabSwitching: false,
      excessiveCopyPaste: false,
      frequentConsoleAccess: false,
    },
    getActivityStats: () => ({
      byType: {
        tabSwitches: 0,
        copyPaste: 0,
        consoleAccess: 0,
        screenshots: 0,
      },
    }),
  };

  beforeEach(() => {
    jest.clearAllMocks();
    useProctoringWebSocket.mockReturnValue(mockWebSocket);
    useScreenActivity.mockReturnValue(mockScreenActivity);
  });

  it('renders without crashing', () => {
    render(<ScreenActivityMonitor {...mockProps} />);
    expect(screen.getByText('Screen Activity')).toBeInTheDocument();
  });

  it('shows monitoring status when enabled', () => {
    render(<ScreenActivityMonitor {...mockProps} />);
    expect(screen.getByText('Monitoring')).toBeInTheDocument();
  });

  it('renders correctly when disabled', () => {
    render(<ScreenActivityMonitor {...mockProps} isEnabled={false} />);
    expect(screen.getByText('Screen Activity')).toBeInTheDocument();
  });

  it('calls the useScreenActivity hook with the correct callback', () => {
    render(<ScreenActivityMonitor {...mockProps} />);
    
    // Verify that useScreenActivity was called with proper parameters
    expect(useScreenActivity).toHaveBeenCalledWith(
      true, // isEnabled
      expect.any(Function) // handleActivityDetected callback
    );
  });
}); 