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
  const bg = useColorModeValue('brand.50', 'brand.900');
  const borderColor = useColorModeValue('brand.200', 'brand.700');
  const { colorMode, toggleColorMode } = useColorMode();
  const { user, token, logout, isLoading } = useAuth();

  // Define color mode dependent values at the top level
  const logoIconColor = useColorModeValue('secondary.500', 'secondary.300');
  const logoTextColor = useColorModeValue('primary.500', 'primary.300');
  
  const activeLinkColor = useColorModeValue('primary.500', 'primary.300');
  const inactiveLinkColor = useColorModeValue('brand.700', 'brand.300');
  const linkHoverColor = useColorModeValue('primary.600', 'primary.400');

  const userIconColor = useColorModeValue('brand.700', 'brand.300');
  const userTextColor = useColorModeValue('brand.800', 'brand.200');
  const menuBgColor = useColorModeValue('white', 'brand.800');
  const menuBorderColor = useColorModeValue('brand.200', 'brand.600');
  const menuItemHoverBgColor = useColorModeValue('brand.100', 'brand.700');

  const toggleIconColor = useColorModeValue('brand.600', 'brand.200');

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
            <FaMicrophone size={24} color={logoIconColor} />
            <Text fontWeight="bold" fontSize="xl" color={logoTextColor}>
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
              color={location.pathname === '/' ? activeLinkColor : inactiveLinkColor}
              _hover={{ color: linkHoverColor }}
            >
              Home
            </Link>
            <Link
              as={RouterLink}
              to="/interview"
              fontWeight={location.pathname.includes('/interview') ? 'bold' : 'normal'}
              color={location.pathname.includes('/interview') ? activeLinkColor : inactiveLinkColor}
              _hover={{ color: linkHoverColor }}
            >
              Interview
            </Link>
            <Link
              as={RouterLink}
              to="/history"
              fontWeight={location.pathname === '/history' ? 'bold' : 'normal'}
              color={location.pathname === '/history' ? activeLinkColor : inactiveLinkColor}
              _hover={{ color: linkHoverColor }}
            >
              History
            </Link>
          </HStack>

          {/* Action Buttons / User Menu */}
          <HStack spacing={3}>
            <Button
              as={RouterLink}
              to="/interview"
              colorScheme="secondary"
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
                    <FaUserCircle size="20px" color={userIconColor} />
                    <Text display={{ base: 'none', md: 'inline-flex' }} color={userTextColor}>{user.username}</Text>
                  </HStack>
                </MenuButton>
                <MenuList bg={menuBgColor} borderColor={menuBorderColor}>
                  <MenuItem _hover={{ bg: menuItemHoverBgColor }} as={RouterLink} to="/profile">
                    Profile
                  </MenuItem>
                  <MenuItem _hover={{ bg: menuItemHoverBgColor }} as={RouterLink} to="/settings">
                    Settings
                  </MenuItem>
                  <MenuDivider borderColor={menuBorderColor} />
                  <MenuItem _hover={{ bg: menuItemHoverBgColor }} onClick={handleLogout}>Log Out</MenuItem>
                </MenuList>
              </Menu>
            ) : (
              <>
                <Button
                  as={RouterLink}
                  to="/login"
                  variant="outline"
                  colorScheme="primary"
                  size="sm"
                >
                  Log In
                </Button>
                <Button
                  as={RouterLink}
                  to="/signup"
                  variant="ghost"
                  colorScheme="primary"
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
          variant="ghost"
          color={toggleIconColor}
        />
      </Flex>
    </Box>
  );
};

export default Navbar; 