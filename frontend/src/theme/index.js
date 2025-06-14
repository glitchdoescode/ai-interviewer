import { extendTheme } from '@chakra-ui/react';

// Professional Blue Theme Configuration
// Replaces the previous light green theme with a sophisticated blue palette

const PROFESSIONAL_BLUE_PALETTE = {
  50: '#EFF6FF',
  100: '#DBEAFE',
  200: '#BFDBFE',
  300: '#93C5FD',
  400: '#60A5FA',
  500: '#3B82F6',
  600: '#2563EB',
  700: '#1D4ED8',
  800: '#1E40AF',
  900: '#1E3A8A',
};

const SLATE_GRAY_PALETTE = {
  50: '#F8FAFC',
  100: '#F1F5F9',
  200: '#E2E8F0',
  300: '#CBD5E1',
  400: '#94A3B8',
  500: '#64748B',
  600: '#475569',
  700: '#334155',
  800: '#1E293B',
  900: '#0F172A',
};

const EMERALD_PALETTE = {
  50: '#ECFDF5',
  100: '#D1FAE5',
  200: '#A7F3D0',
  300: '#6EE7B7',
  400: '#34D399',
  500: '#10B981',
  600: '#059669',
  700: '#047857',
  800: '#065F46',
  900: '#064E3B',
};

const theme = extendTheme({
  fonts: {
    heading: `'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif`,
    body: `'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif`,
  },
  colors: {
    // Professional Blue as Primary
    primary: PROFESSIONAL_BLUE_PALETTE,
    blue: PROFESSIONAL_BLUE_PALETTE,
    
    // Slate Gray as Brand
    brand: SLATE_GRAY_PALETTE,
    gray: SLATE_GRAY_PALETTE,
    
    // Emerald for Success States
    success: EMERALD_PALETTE,
    green: EMERALD_PALETTE,
    
    // Status Colors
    warning: {
      50: '#FFFBEB',
      100: '#FEF3C7',
      200: '#FDE68A',
      300: '#FCD34D',
      400: '#FBBF24',
      500: '#F59E0B',
      600: '#D97706',
      700: '#B45309',
      800: '#92400E',
      900: '#78350F',
    },
    error: {
      50: '#FEF2F2',
      100: '#FEE2E2',
      200: '#FECACA',
      300: '#FCA5A5',
      400: '#F87171',
      500: '#EF4444',
      600: '#DC2626',
      700: '#B91C1C',
      800: '#991B1B',
      900: '#7F1D1D',
    },
    
    // Background Colors
    background: {
      primary: '#FFFFFF',
      secondary: '#F8FAFC',
      tertiary: '#F1F5F9',
    },
  },
  components: {
    Button: {
      baseStyle: {
        fontWeight: '600',
        borderRadius: 'md',
        _focus: {
          boxShadow: '0 0 0 2px var(--color-primary-500)',
        },
      },
      variants: {
        solid: (props) => {
          const { colorScheme } = props;
          if (colorScheme === 'primary' || colorScheme === 'blue') {
            return {
              bg: 'blue.600',
              color: 'white',
              _hover: {
                bg: 'blue.700',
                _disabled: {
                  bg: 'blue.600',
                },
              },
              _active: {
                bg: 'blue.800',
              },
            };
          }
          return {};
        },
        outline: (props) => {
          const { colorScheme } = props;
          if (colorScheme === 'primary' || colorScheme === 'blue') {
            return {
              border: '2px solid',
              borderColor: 'blue.600',
              color: 'blue.600',
              _hover: {
                bg: 'blue.50',
                _disabled: {
                  bg: 'transparent',
                },
              },
              _active: {
                bg: 'blue.100',
              },
            };
          }
          return {};
        },
        ghost: (props) => {
          const { colorScheme } = props;
          if (colorScheme === 'primary' || colorScheme === 'blue') {
            return {
              color: 'blue.600',
              _hover: {
                bg: 'blue.50',
                _disabled: {
                  bg: 'transparent',
                },
              },
              _active: {
                bg: 'blue.100',
              },
            };
          }
          return {};
        },
      },
      defaultProps: {
        colorScheme: 'blue',
      },
    },
    Input: {
      variants: {
        outline: {
          field: {
            borderColor: 'gray.300',
            _hover: {
              borderColor: 'gray.400',
            },
            _focus: {
              borderColor: 'blue.500',
              boxShadow: '0 0 0 1px var(--color-primary-500)',
            },
          },
        },
      },
      defaultProps: {
        focusBorderColor: 'blue.500',
      },
    },
    Textarea: {
      variants: {
        outline: {
          borderColor: 'gray.300',
          _hover: {
            borderColor: 'gray.400',
          },
          _focus: {
            borderColor: 'blue.500',
            boxShadow: '0 0 0 1px var(--color-primary-500)',
          },
        },
      },
      defaultProps: {
        focusBorderColor: 'blue.500',
      },
    },
    Select: {
      variants: {
        outline: {
          field: {
            borderColor: 'gray.300',
            _hover: {
              borderColor: 'gray.400',
            },
            _focus: {
              borderColor: 'blue.500',
              boxShadow: '0 0 0 1px var(--color-primary-500)',
            },
          },
        },
      },
      defaultProps: {
        focusBorderColor: 'blue.500',
      },
    },
    Card: {
      baseStyle: {
        container: {
          bg: 'background.primary',
          boxShadow: 'md',
          borderRadius: 'lg',
          border: '1px solid',
          borderColor: 'gray.200',
        },
      },
    },
  },
  styles: {
    global: {
      body: {
        bg: 'background.secondary',
        color: 'gray.900',
        lineHeight: 'normal',
      },
      a: {
        color: 'blue.600',
        _hover: {
          color: 'blue.700',
          textDecoration: 'underline',
        },
      },
    },
  },
  space: {
    1: '0.25rem',   // 4px
    2: '0.5rem',    // 8px
    3: '0.75rem',   // 12px
    4: '1rem',      // 16px
    5: '1.25rem',   // 20px
    6: '1.5rem',    // 24px
    8: '2rem',      // 32px
    10: '2.5rem',   // 40px
    12: '3rem',     // 48px
    16: '4rem',     // 64px
  },
  shadows: {
    sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
    md: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
    lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
    xl: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
  },
});

export default theme;

// Export individual palettes for use in custom components
export {
  PROFESSIONAL_BLUE_PALETTE,
  SLATE_GRAY_PALETTE,
  EMERALD_PALETTE,
}; 