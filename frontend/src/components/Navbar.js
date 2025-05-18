import React from 'react';
import { Link as RouterLink, useLocation } from 'react-router-dom';
import {
  Box,
  Flex,
  Text,
  Link,
  HStack,
  Button,
  useColorModeValue,
  Spacer,
  useColorMode,
  IconButton
} from '@chakra-ui/react';
import { FaMicrophone, FaMoon, FaSun } from 'react-icons/fa';
import { useConfig } from '../context/ConfigContext';

/**
 * Navbar component for site navigation
 */
const Navbar = () => {
  const location = useLocation();
  const bg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const { colorMode, toggleColorMode } = useColorMode();
  const { systemName, isLoading, error } = useConfig();

  React.useEffect(() => {
    console.log('Navbar Config:', { systemName, isLoading, error });
  }, [systemName, isLoading, error]);

  if (isLoading) {
    return (
      <Box as="nav" bg={bg} borderBottom="1px" borderBottomColor={borderColor} boxShadow="sm" position="sticky" top={0} zIndex={10} h={16} display="flex" alignItems="center" px={4}>
        <Text>Loading Navbar...</Text>
      </Box>
    );
  }

  if (error) {
    return (
      <Box as="nav" bg={bg} borderBottom="1px" borderBottomColor={borderColor} boxShadow="sm" position="sticky" top={0} zIndex={10} h={16} display="flex" alignItems="center" px={4}>
        <Text color="red.500">Error loading Navbar config</Text>
      </Box>
    );
  }

  return (
    <Box
      as="nav"
      bg={bg}
      borderBottom="1px"
      borderBottomColor={borderColor}
      boxShadow="sm"
      position="sticky"
      top={0}
      zIndex={10}
    >
      <Flex
        h={16}
        align="center"
        justify="space-between"
        maxW="container.xl"
        mx="auto"
        px={4}
      >
        {/* Logo/Brand */}
        <Link as={RouterLink} to="/" _hover={{ textDecoration: 'none' }}>
          <HStack spacing={2}>
            <FaMicrophone size={24} color="#00BCD4" />
            <Text fontWeight="bold" fontSize="xl" color="brand.700">
              {systemName || 'Default Name'}
            </Text>
          </HStack>
        </Link>

        {/* Navigation Links */}
        <HStack spacing={8} alignItems="center">
          <HStack as="nav" spacing={6}>
            <Link
              as={RouterLink}
              to="/"
              fontWeight={location.pathname === '/' ? 'bold' : 'normal'}
              color={location.pathname === '/' ? 'brand.600' : 'gray.500'}
              _hover={{ color: 'brand.500' }}
            >
              Home
            </Link>
            <Link
              as={RouterLink}
              to="/interview"
              fontWeight={location.pathname.includes('/interview') ? 'bold' : 'normal'}
              color={location.pathname.includes('/interview') ? 'brand.600' : 'gray.500'}
              _hover={{ color: 'brand.500' }}
            >
              Interview
            </Link>
            <Link
              as={RouterLink}
              to="/history"
              fontWeight={location.pathname === '/history' ? 'bold' : 'normal'}
              color={location.pathname === '/history' ? 'brand.600' : 'gray.500'}
              _hover={{ color: 'brand.500' }}
            >
              History
            </Link>
          </HStack>

          {/* Action Buttons */}
          <Button
            as={RouterLink}
            to="/interview"
            colorScheme="brand"
            leftIcon={<FaMicrophone />}
            size="sm"
          >
            Start Interview
          </Button>
        </HStack>

        {/* Color Mode Toggle */}
        <Spacer />
        <IconButton
          icon={colorMode === 'light' ? <FaMoon /> : <FaSun />}
          aria-label="Toggle color mode"
          onClick={toggleColorMode}
        />
      </Flex>
    </Box>
  );
};

export default Navbar; 