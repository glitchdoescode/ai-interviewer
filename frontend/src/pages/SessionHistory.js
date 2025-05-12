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
} from '@chakra-ui/react';
import { FaArrowRight, FaCheck, FaClock, FaTrash } from 'react-icons/fa';
import Navbar from '../components/Navbar';
import { useInterview } from '../context/InterviewContext';
import { getUserSessions } from '../api/interviewService';

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

  // Fetch user sessions when the component mounts
  useEffect(() => {
    const fetchSessions = async () => {
      if (!userId) {
        setLoading(false);
        return;
      }
      
      try {
        setLoading(true);
        const sessionsData = await getUserSessions(userId, includeCompleted);
        setSessions(sessionsData.sessions || []);
      } catch (err) {
        console.error('Error fetching sessions:', err);
        setError('Failed to load interview history. Please try again later.');
        toast({
          title: 'Error',
          description: 'Failed to load interview history',
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
      } finally {
        setLoading(false);
      }
    };
    
    fetchSessions();
  }, [userId, includeCompleted, toast]);

  // Function to format the date string
  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  // Function to handle resuming an interview session
  const handleResumeSession = (sessionId) => {
    navigate(`/interview/${sessionId}`);
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

  return (
    <Box minH="100vh" bg="gray.50">
      <Navbar />
      
      <Container maxW="container.xl" py={8}>
        <Heading as="h1" size="xl" mb={6} color="brand.600">
          Interview History
        </Heading>
        
        {!userId ? (
          <Alert status="warning" borderRadius="md">
            <AlertIcon />
            You need to start an interview first to view your history.
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
          </Alert>
        ) : sessions.length === 0 ? (
          <Box textAlign="center" my={10} p={6} bg="white" borderRadius="md" boxShadow="sm">
            <Text fontSize="lg" mb={4}>You don't have any interview sessions yet.</Text>
            <Button 
              colorScheme="brand" 
              onClick={() => navigate('/interview')}
              rightIcon={<FaArrowRight />}
            >
              Start Your First Interview
            </Button>
          </Box>
        ) : (
          <>
            <Flex justify="space-between" align="center" mb={4}>
              <Text color="gray.600">
                Showing {sessions.length} {sessions.length === 1 ? 'session' : 'sessions'}
              </Text>
              
              <Button
                size="sm"
                variant="outline"
                leftIcon={includeCompleted ? <FaCheck /> : <FaClock />}
                onClick={() => setIncludeCompleted(!includeCompleted)}
              >
                {includeCompleted ? 'Show All Sessions' : 'Show Active Only'}
              </Button>
            </Flex>
            
            <Box overflowX="auto" bg="white" borderRadius="md" boxShadow="md">
              <Table variant="simple">
                <Thead>
                  <Tr>
                    <Th>Session ID</Th>
                    <Th>Started</Th>
                    <Th>Last Activity</Th>
                    <Th>Status</Th>
                    <Th>Topics</Th>
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
                      <Td fontSize="sm">{formatDate(session.updated_at)}</Td>
                      <Td>
                        <Badge colorScheme={getStatusColor(session.status)}>
                          {formatStatus(session.status)}
                        </Badge>
                      </Td>
                      <Td>
                        {session.topics && session.topics.length > 0 ? (
                          session.topics.map((topic, index) => (
                            <Badge key={index} colorScheme="purple" mr={1} mb={1}>
                              {topic}
                            </Badge>
                          ))
                        ) : (
                          <Text fontSize="sm" color="gray.500">No topics</Text>
                        )}
                      </Td>
                      <Td isNumeric>
                        <Button
                          size="sm"
                          colorScheme="brand"
                          mr={2}
                          onClick={() => handleResumeSession(session.session_id)}
                          isDisabled={session.status === 'completed'}
                        >
                          {session.status === 'in_progress' ? 'Resume' : 'View'}
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