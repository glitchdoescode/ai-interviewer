import React from 'react';
import { Link as RouterLink, useLocation, useNavigate } from 'react-router-dom';
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
  IconButton,
  Spinner,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  MenuDivider,
} from '@chakra-ui/react';
import { FaMicrophone, FaMoon, FaSun, FaUserCircle } from 'react-icons/fa';
import { useAuth } from '../context/AuthContext';

/**
 * Navbar component for site navigation
 */
const Navbar = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const bg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const { colorMode, toggleColorMode } = useColorMode();
  const { user, token, logout, isLoading } = useAuth();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

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
              AI Interviewer
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

          {/* Action Buttons / User Menu */}
          <HStack spacing={2}>
            <Button
              as={RouterLink}
              to="/interview"
              colorScheme="brand"
              leftIcon={<FaMicrophone />}
              size="sm"
            >
              Start Interview
            </Button>

            {isLoading ? (
              <Spinner size="sm" />
            ) : user && token ? (
              <Menu>
                <MenuButton
                  as={Button}
                  rounded={'full'}
                  variant={'link'}
                  cursor={'pointer'}
                  minW={0}
                  size="sm"
                >
                  <HStack>
                    <FaUserCircle size="20px" />
                    <Text display={{ base: 'none', md: 'inline-flex' }}>{user.username}</Text>
                  </HStack>
                </MenuButton>
                <MenuList>
                  <MenuItem as={RouterLink} to="/profile">
                    Profile
                  </MenuItem>
                  <MenuItem as={RouterLink} to="/settings">
                    Settings
                  </MenuItem>
                  <MenuDivider />
                  <MenuItem onClick={handleLogout}>Log Out</MenuItem>
                </MenuList>
              </Menu>
            ) : (
              <>
                <Button
                  as={RouterLink}
                  to="/login"
                  variant="outline"
                  colorScheme="brand"
                  size="sm"
                >
                  Log In
                </Button>
                <Button
                  as={RouterLink}
                  to="/signup"
                  variant="ghost"
                  colorScheme="brand"
                  size="sm"
                >
                  Sign Up
                </Button>
              </>
            )}
          </HStack>
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