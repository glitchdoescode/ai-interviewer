import React, { useState /*, useContext // useContext will be indirectly used by useAuth */ } from 'react';
import {
  Box,
  Flex,
  Heading,
  FormControl,
  FormLabel,
  Input,
  Button,
  Link,
  Text,
  VStack,
  useColorModeValue,
  // useToast, // Commented out as 'toast' is currently unused
} from '@chakra-ui/react';
import { Link as RouterLink, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext'; // Import useAuth instead of AuthContext directly
import { loginUser } from '../api/authService';
// import './LoginPage.css'; // Removed as the file is missing

const LoginPage = () => {
  const bgColor = useColorModeValue('gray.50', 'gray.800');
  const formBgColor = useColorModeValue('white', 'gray.700');
  // const toast = useToast(); // Commented out
  const navigate = useNavigate();
  const location = useLocation();
  const auth = useAuth(); // Use the useAuth hook

  const from = location.state?.from?.pathname || "/interview"; // Default redirect to /interview

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);
    try {
      const response = await loginUser(email, password);
      
      if (response && response.access_token) {
        auth.login(response.access_token, { email });
        console.log(`Login successful, navigating to ${from}.`);
        navigate(from, { replace: true }); // Use the 'from' variable for navigation
      } else {
        setError('Login failed: No access token received from server.');
      }
    } catch (err) {
      console.error('Login page error:', err);
      setError(err.message || 'Login failed. Please check your credentials.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Flex minH="100vh" align="center" justify="center" bg={bgColor}>
      <Box
        rounded="lg"
        bg={formBgColor}
        boxShadow="lg"
        p={8}
        width={{ base: '90%', sm: '400px' }}
      >
        <VStack spacing={4} as="form" onSubmit={handleSubmit}>
          <Heading fontSize="2xl" textAlign="center">
            Log In to Your Account
          </Heading>
          <FormControl id="email">
            <FormLabel>Email</FormLabel>
            <Input 
              type="email" 
              placeholder="e.g., johndoe@example.com" 
              value={email} 
              onChange={(e) => setEmail(e.target.value)} 
              isRequired
            />
          </FormControl>
          <FormControl id="password">
            <FormLabel>Password</FormLabel>
            <Input 
              type="password" 
              placeholder="••••••••" 
              value={password} 
              onChange={(e) => setPassword(e.target.value)} 
              isRequired
            />
          </FormControl>
          {error && <Text color="red.500" mt={2}>{error}</Text>} {/* Added mt={2} for spacing */}
          <Button 
            colorScheme="brand" 
            width="full" 
            type="submit" 
            isLoading={isLoading}
            mt={4} // Added margin top for the button
          >
            Log In
          </Button>
          <Text pt={2}>
            Don't have an account?{' '}
            <Link as={RouterLink} to="/signup" color="brand.500" fontWeight="medium">
              Sign Up
            </Link>
          </Text>
        </VStack>
      </Box>
    </Flex>
  );
};

export default LoginPage; 