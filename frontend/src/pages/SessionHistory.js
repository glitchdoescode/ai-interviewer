import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Heading,
  Text,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Button,
  Badge,
  Flex,
  Alert,
  AlertIcon,
  Spinner,
  useToast,
  IconButton,
  Switch,
  FormControl,
  FormLabel,
} from '@chakra-ui/react';
import { FaArrowRight, FaCheck, FaClock, FaTrash, FaFileAlt, FaExclamationTriangle } from 'react-icons/fa';
import Navbar from '../components/Navbar';
import { useInterview } from '../context/InterviewContext';
import { getUserSessions } from '../api/interviewService';

// Sample data for development/demo purposes
const sampleSessions = [
  {
    session_id: "sample-session-1",
    user_id: "sample-user",
    created_at: new Date(Date.now() - 3600000).toISOString(), // 1 hour ago
    last_active: new Date(Date.now() - 1800000).toISOString(), // 30 minutes ago
    interview_stage: "conclusion",
    job_role: "Frontend Developer",
    requires_coding: true,
    status: "completed"
  },
  {
    session_id: "sample-session-2",
    user_id: "sample-user",
    created_at: new Date(Date.now() - 86400000).toISOString(), // 1 day ago
    last_active: new Date(Date.now() - 82800000).toISOString(), // 23 hours ago
    interview_stage: "technical_questions",
    job_role: "Backend Engineer",
    requires_coding: true,
    status: "in_progress"
  }
];

/**
 * Session History page component
 */
const SessionHistory = () => {
  const { userId } = useInterview();
  const navigate = useNavigate();
  const toast = useToast();
  
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [includeCompleted, setIncludeCompleted] = useState(true);
  const [useSampleData, setUseSampleData] = useState(false);

  // Fetch user sessions when the component mounts
  useEffect(() => {
    const fetchSessions = async () => {
      if (!userId) {
        setLoading(false);
        setError('No user ID available. Please start an interview first.');
        return;
      }
      
      try {
        setLoading(true);
        console.log('SessionHistory: Fetching sessions for user ID:', userId);
        const sessionsData = await getUserSessions(userId, includeCompleted);
        console.log('SessionHistory: Received sessions data:', sessionsData);
        
        // Handle different response formats
        let sessionsList = [];
        if (sessionsData.sessions) {
          sessionsList = sessionsData.sessions;
        } else if (Array.isArray(sessionsData)) {
          sessionsList = sessionsData;
        }
        
        console.log('SessionHistory: Processed sessions list:', sessionsList);
        
        if (sessionsList.length === 0 && !useSampleData) {
          // No real sessions found
          console.log('No real sessions found. Checking if sample data should be used.');
          
          // Check localStorage to see if we should automatically use sample data
          const autoUseSample = localStorage.getItem('useSampleSessionData') === 'true';
          
          if (autoUseSample) {
            console.log('Auto-using sample session data from localStorage preference');
            setUseSampleData(true);
            setSessions(sampleSessions);
            setError(null);
          } else {
            setSessions([]);
            // Don't set an error for empty sessions, it's a valid state
          }
        } else {
          setSessions(sessionsList);
          setError(null);
        }
      } catch (err) {
        console.error('Error fetching sessions:', err);
        setError('Failed to load interview history. Please try again later.');
        
        // Check if we should show sample data as a fallback
        const fallbackToSample = localStorage.getItem('fallbackToSampleSessionData') !== 'false';
        
        if (fallbackToSample) {
          console.log('Using sample session data as fallback due to error');
          setSessions(sampleSessions);
          setUseSampleData(true);
          
          toast({
            title: 'Using sample data',
            description: `Could not load real session data: ${err.message}`,
            status: 'warning',
            duration: 5000,
            isClosable: true,
          });
        } else {
          toast({
            title: 'Error',
            description: `Failed to load interview history: ${err.message}`,
            status: 'error',
            duration: 5000,
            isClosable: true,
          });
        }
      } finally {
        setLoading(false);
      }
    };
    
    fetchSessions();
  }, [userId, includeCompleted, toast, useSampleData]);

  // Function to format the date string
  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  // Function to handle resuming an interview session
  const handleResumeSession = (sessionId) => {
    navigate(`/interview/${sessionId}`);
  };
  
  // Function to view a report
  const handleViewReport = (sessionId) => {
    navigate(`/report/${sessionId}`);
  };

  // Function to handle deleting a session (this would need backend support)
  const handleDeleteSession = (sessionId) => {
    // This is a placeholder - actual implementation would require API support
    toast({
      title: 'Not Implemented',
      description: 'Session deletion is not implemented yet',
      status: 'info',
      duration: 3000,
      isClosable: true,
    });
  };

  // Function to get status badge color
  const getStatusColor = (status) => {
    switch (status) {
      case 'in_progress':
        return 'blue';
      case 'completed':
        return 'green';
      case 'abandoned':
        return 'red';
      default:
        return 'gray';
    }
  };

  // Function to format status text
  const formatStatus = (status) => {
    return status.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase());
  };
  
  // Toggle sample data
  const handleToggleSampleData = () => {
    const newValue = !useSampleData;
    setUseSampleData(newValue);
    localStorage.setItem('useSampleSessionData', newValue.toString());
    
    if (newValue) {
      setSessions(sampleSessions);
      setError(null);
      toast({
        title: 'Using sample data',
        description: 'Showing example interview sessions for demonstration',
        status: 'info',
        duration: 3000,
        isClosable: true,
      });
    } else {
      // Reset and fetch real data
      setSessions([]);
      setLoading(true);
    }
  };

  return (
    <Box minH="100vh" bg="gray.50">
      <Navbar />
      
      <Container maxW="container.xl" py={8}>
        <Heading as="h1" size="xl" mb={6} color="brand.600">
          Interview History
        </Heading>
        
        {useSampleData && (
          <Alert status="info" mb={4} borderRadius="md">
            <AlertIcon />
            Using sample data for demonstration purposes.
          </Alert>
        )}
        
        {!userId && !useSampleData ? (
          <Alert status="warning" borderRadius="md">
            <AlertIcon />
            You need to start an interview first to view your history.
            <Button ml={4} size="sm" colorScheme="blue" onClick={handleToggleSampleData}>
              Show Sample Data
            </Button>
          </Alert>
        ) : loading ? (
          <Flex justify="center" align="center" my={10}>
            <Spinner color="brand.500" mr={3} />
            <Text>Loading your interview history...</Text>
          </Flex>
        ) : error ? (
          <Alert status="error" borderRadius="md">
            <AlertIcon />
            {error}
            <Button ml={4} size="sm" colorScheme="blue" onClick={handleToggleSampleData}>
              {useSampleData ? 'Hide Sample Data' : 'Show Sample Data'}
            </Button>
          </Alert>
        ) : sessions.length === 0 ? (
          <Box textAlign="center" my={10} p={6} bg="white" borderRadius="md" boxShadow="sm">
            <Text fontSize="lg" mb={4}>You don't have any interview sessions yet.</Text>
            <Flex justify="center" gap={4}>
              <Button 
                colorScheme="brand" 
                onClick={() => navigate('/interview')}
                rightIcon={<FaArrowRight />}
              >
                Start Your First Interview
              </Button>
              {!useSampleData && (
                <Button 
                  variant="outline"
                  colorScheme="blue" 
                  onClick={handleToggleSampleData}
                  rightIcon={<FaFileAlt />}
                >
                  Show Sample Data
                </Button>
              )}
            </Flex>
          </Box>
        ) : (
          <>
            <Flex justify="space-between" align="center" mb={4} wrap="wrap" gap={2}>
              <Text color="gray.600">
                Showing {sessions.length} {sessions.length === 1 ? 'session' : 'sessions'}
              </Text>
              
              <Flex gap={4} align="center">
                {/* Toggle for sample data */}
                <FormControl display="flex" alignItems="center" width="auto">
                  <FormLabel htmlFor="sample-data-toggle" mb="0" fontSize="sm">
                    Sample Data
                  </FormLabel>
                  <Switch 
                    id="sample-data-toggle"
                    isChecked={useSampleData}
                    onChange={handleToggleSampleData}
                    colorScheme="blue"
                  />
                </FormControl>
                
                <Button
                  size="sm"
                  variant="outline"
                  leftIcon={includeCompleted ? <FaCheck /> : <FaClock />}
                  onClick={() => setIncludeCompleted(!includeCompleted)}
                >
                  {includeCompleted ? 'Show All Sessions' : 'Show Active Only'}
                </Button>
              </Flex>
            </Flex>
            
            <Box overflowX="auto" bg="white" borderRadius="md" boxShadow="md">
              <Table variant="simple">
                <Thead>
                  <Tr>
                    <Th>Session ID</Th>
                    <Th>Started</Th>
                    <Th>Last Activity</Th>
                    <Th>Status</Th>
                    <Th>Job Role</Th>
                    <Th isNumeric>Actions</Th>
                  </Tr>
                </Thead>
                <Tbody>
                  {sessions.map((session) => (
                    <Tr key={session.session_id}>
                      <Td fontFamily="mono" fontSize="sm">
                        {session.session_id.substring(0, 8)}...
                      </Td>
                      <Td fontSize="sm">{formatDate(session.created_at)}</Td>
                      <Td fontSize="sm">{formatDate(session.last_active)}</Td>
                      <Td>
                        <Badge colorScheme={getStatusColor(session.status || (session.interview_stage === 'conclusion' ? 'completed' : 'in_progress'))}>
                          {formatStatus(session.status || (session.interview_stage === 'conclusion' ? 'completed' : 'in_progress'))}
                        </Badge>
                      </Td>
                      <Td>
                        {session.job_role ? (
                          <Badge colorScheme="purple">
                            {session.job_role}
                          </Badge>
                        ) : (
                          <Text fontSize="sm" color="gray.500">Not specified</Text>
                        )}
                      </Td>
                      <Td isNumeric>
                        <Button
                          size="sm"
                          colorScheme="blue"
                          mr={2}
                          onClick={() => handleViewReport(session.session_id)}
                          isDisabled={session.interview_stage !== 'conclusion' && session.status !== 'completed'}
                          title={session.interview_stage === 'conclusion' || session.status === 'completed' ? 'View Detailed Report' : 'Complete the interview to view report'}
                        >
                          Report
                        </Button>
                        <Button
                          size="sm"
                          colorScheme="brand"
                          mr={2}
                          onClick={() => handleResumeSession(session.session_id)}
                          isDisabled={session.interview_stage === 'conclusion' || session.status === 'completed'}
                        >
                          {session.interview_stage === 'conclusion' || session.status === 'completed' ? 'View' : 'Resume'}
                        </Button>
                        <IconButton
                          size="sm"
                          colorScheme="red"
                          variant="ghost"
                          icon={<FaTrash />}
                          aria-label="Delete session"
                          onClick={() => handleDeleteSession(session.session_id)}
                        />
                      </Td>
                    </Tr>
                  ))}
                </Tbody>
              </Table>
            </Box>
          </>
        )}
      </Container>
    </Box>
  );
};

export default SessionHistory; 