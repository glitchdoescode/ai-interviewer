import React, { useState } from 'react';
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
  useToast,
} from '@chakra-ui/react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import { signupUser } from '../api/authService';

const SignupPage = () => {
  const bgColor = useColorModeValue('gray.50', 'gray.800');
  const formBgColor = useColorModeValue('white', 'gray.700');
  const toast = useToast();
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setIsLoading(true);
    try {
      const data = await signupUser(email, password, fullName);
      console.log('Signup successful:', data);
      toast({
        title: 'Account Created',
        description: "Your account has been successfully created! Please log in.",
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
      navigate('/login');
    } catch (error) {
      toast({
        title: 'Signup Failed',
        description: error.message || 'Could not create account. Please try again.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
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
            Create Your Account
          </Heading>
          <FormControl id="email" isRequired>
            <FormLabel>Email address</FormLabel>
            <Input 
              type="email" 
              placeholder="you@example.com" 
              value={email} 
              onChange={(e) => setEmail(e.target.value)} 
            />
          </FormControl>
          <FormControl id="fullName">
            <FormLabel>Full Name</FormLabel> 
            <Input 
              type="text" 
              placeholder="Your Full Name" 
              value={fullName} 
              onChange={(e) => setFullName(e.target.value)} 
            />
          </FormControl>
          <FormControl id="password" isRequired>
            <FormLabel>Password</FormLabel>
            <Input 
              type="password" 
              placeholder="••••••••" 
              value={password} 
              onChange={(e) => setPassword(e.target.value)} 
            />
          </FormControl>
          <Button 
            colorScheme="brand" 
            width="full" 
            type="submit" 
            isLoading={isLoading}
          >
            Sign Up
          </Button>
          <Text pt={2}>
            Already have an account?{' '}
            <Link as={RouterLink} to="/login" color="brand.500" fontWeight="medium">
              Log In
            </Link>
          </Text>
        </VStack>
      </Box>
    </Flex>
  );
};

export default SignupPage; 