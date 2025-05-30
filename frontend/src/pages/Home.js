import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Heading,
  Text,
  Button,
  VStack,
  Image,
  Flex,
  SimpleGrid,
  Icon,
  useColorModeValue,
} from '@chakra-ui/react';
import { FaMicrophone, FaRobot, FaCode, FaChartLine } from 'react-icons/fa';
import Navbar from '../components/Navbar';
import { useInterview } from '../context/InterviewContext';
import { v4 as uuid } from 'uuid';

/**
 * Home page component
 */
const Home = () => {
  const { userId, setUserId } = useInterview();
  const navigate = useNavigate();
  const bgGradient = useColorModeValue(
    'linear(to-b, brand.50, brand.100)',
    'linear(to-b, brand.900, brand.800)'
  );

  // Generate a user ID if not already set
  useEffect(() => {
    if (!userId) {
      setUserId(`user-${uuid()}`);
    }
  }, [userId, setUserId]);

  // Start the interview
  const handleStartInterview = () => {
    navigate('/interview');
  };

  return (
    <Box minH="100vh" bgGradient={bgGradient}>
      <Navbar />
      
      <Container maxW="container.xl" py={10}>
        {/* Hero Section */}
        <Flex
          direction={{ base: 'column', md: 'row' }}
          align="center"
          justify="space-between"
          mb={16}
          py={10}
        >
          <Box maxW={{ base: 'full', md: '50%' }} mb={{ base: 8, md: 0 }}>
            <Heading as="h1" size="2xl" fontWeight="bold" mb={4} color="primary.500">
              Practice Technical Interviews with AI
            </Heading>
            
            <Text fontSize="xl" mb={6} color="brand.700">
              Prepare for your next software engineering interview with our AI-powered
              interview platform. Get real-time feedback and improve your skills.
            </Text>
            
            <Button
              size="lg"
              colorScheme="primary"
              rightIcon={<FaMicrophone />}
              onClick={handleStartInterview}
            >
              Start Interview
            </Button>
          </Box>
          
          <Box maxW={{ base: 'full', md: '45%' }}>
            <Image
              src="https://images.unsplash.com/photo-1573164574572-cb89e39749b4?auto=format&fit=crop&q=80&w=600&h=400"
              alt="Technical Interview Illustration"
              borderRadius="lg"
              shadow="xl"
            />
          </Box>
        </Flex>
        
        {/* Features Section */}
        <Box mb={16}>
          <Heading as="h2" size="xl" textAlign="center" mb={10} color="primary.500">
            Features
          </Heading>
          
          <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={10}>
            <FeatureCard
              icon={FaMicrophone}
              title="Voice Interface"
              description="Natural conversation with voice recognition and text-to-speech capabilities."
            />
            
            <FeatureCard
              icon={FaRobot}
              title="AI Interviewer"
              description="Advanced AI that adapts to your responses and provides personalized feedback."
            />
            
            <FeatureCard
              icon={FaCode}
              title="Coding Challenges"
              description="Practice real coding problems with instant evaluation and suggestions."
            />
            
            <FeatureCard
              icon={FaChartLine}
              title="Progress Tracking"
              description="Track your improvement over time with detailed interview history."
            />
          </SimpleGrid>
        </Box>
        
        {/* Call to Action */}
        <Box textAlign="center" bg="primary.100" p={10} borderRadius="lg" shadow="md">
          <Heading as="h3" size="lg" mb={4} color="primary.700">
            Ready to ace your next interview?
          </Heading>
          
          <Text fontSize="lg" mb={6} color="brand.800">
            Start practicing now and build confidence for your technical interviews.
          </Text>
          
          <Button
            size="lg"
            colorScheme="secondary"
            onClick={handleStartInterview}
          >
            Start Practicing
          </Button>
        </Box>
      </Container>
    </Box>
  );
};

/**
 * Feature card component
 */
const FeatureCard = ({ icon, title, description }) => {
  return (
    <VStack
      p={6}
      bg={useColorModeValue('white', 'brand.700')}
      borderRadius="lg"
      boxShadow="lg"
      align="start"
      spacing={4}
      transition="all 0.3s ease-in-out"
      _hover={{ transform: 'translateY(-5px)', boxShadow: 'xl' }}
    >
      <Flex
        w={16}
        h={16}
        bg="secondary.500"
        borderRadius="full"
        align="center"
        justify="center"
        color="white"
        mb={2}
      >
        <Icon as={icon} boxSize={8} />
      </Flex>
      
      <Heading as="h3" size="md" color={useColorModeValue('primary.600', 'primary.200')}>
        {title}
      </Heading>
      
      <Text color={useColorModeValue('brand.700', 'brand.200')}>
        {description}
      </Text>
    </VStack>
  );
};

export default Home; 