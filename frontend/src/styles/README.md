# AI Interviewer Design System

## Overview

This design system provides a comprehensive set of design tokens, components, and utilities for the AI Interviewer application. It implements a professional blue color scheme that replaces the previous light green theme.

## Color Palette

### Primary Colors (Professional Blue)
- `--color-primary-500: #3B82F6` - Main brand color
- `--color-primary-600: #2563EB` - Hover states, buttons
- `--color-primary-700: #1D4ED8` - Active states
- `--color-primary-50: #EFF6FF` - Light backgrounds
- `--color-primary-100: #DBEAFE` - Very light accents

### Secondary Colors (Slate Gray)
- `--color-secondary-500: #64748B` - Secondary text
- `--color-secondary-700: #334155` - Headings
- `--color-secondary-900: #0F172A` - Primary text
- `--color-secondary-50: #F8FAFC` - Light backgrounds
- `--color-secondary-100: #F1F5F9` - Card backgrounds

### Accent Colors (Emerald)
- `--color-accent-500: #10B981` - Success states
- `--color-accent-600: #059669` - Success buttons
- `--color-accent-50: #ECFDF5` - Success backgrounds

### Status Colors
- **Success**: Emerald palette (`#10B981`)
- **Warning**: Amber palette (`#F59E0B`)
- **Error**: Red palette (`#EF4444`)

## Typography

### Font Family
- Primary: `Inter` - Modern, clean, highly readable
- Fallback: System fonts for performance

### Font Sizes
```css
.text-xs    /* 12px */
.text-sm    /* 14px */
.text-base  /* 16px */
.text-lg    /* 18px */
.text-xl    /* 20px */
.text-2xl   /* 24px */
.text-3xl   /* 30px */
.text-4xl   /* 36px */
.text-5xl   /* 48px */
```

### Font Weights
```css
.font-normal    /* 400 */
.font-medium    /* 500 */
.font-semibold  /* 600 */
.font-bold      /* 700 */
```

## Spacing System

Based on 4px increments for consistent visual rhythm:

```css
.p-1, .m-1    /* 4px */
.p-2, .m-2    /* 8px */
.p-3, .m-3    /* 12px */
.p-4, .m-4    /* 16px */
.p-5, .m-5    /* 20px */
.p-6, .m-6    /* 24px */
.p-8, .m-8    /* 32px */
```

## Component Guidelines

### Buttons
- Primary: Blue background (`bg-blue-600`)
- Secondary: Blue outline (`border-blue-600`)
- Ghost: Blue text (`text-blue-600`)
- Border radius: `8px` (`.rounded`)

### Cards
- Background: White (`bg-primary`)
- Border: Light gray (`border-gray-200`)
- Shadow: Medium (`shadow-md`)
- Border radius: `12px` (`.rounded-lg`)

### Forms
- Focus color: Blue 500 (`#3B82F6`)
- Border: Gray 300 (`#CBD5E1`)
- Hover border: Gray 400 (`#94A3B8`)

## Usage Examples

### Using CSS Custom Properties
```css
.custom-button {
  background-color: var(--color-primary-600);
  color: var(--color-text-inverse);
  padding: var(--spacing-3) var(--spacing-6);
  border-radius: var(--radius-md);
}
```

### Using Chakra UI Theme
```jsx
<Button colorScheme="blue" size="lg">
  Primary Action
</Button>

<Box bg="background.secondary" p={6}>
  Content
</Box>
```

### Using Utility Classes
```jsx
<div className="bg-primary shadow-md rounded-lg p-6">
  <h2 className="text-2xl font-semibold text-primary mb-4">
    Card Title
  </h2>
  <p className="text-secondary">
    Card content with proper spacing and colors.
  </p>
</div>
```

## Accessibility

- All color combinations meet WCAG 2.1 AA contrast requirements
- Focus states are clearly visible with blue outline
- Semantic color usage (blue for interactive, emerald for success, etc.)
- Proper font sizes for readability

## Migration from Previous Theme

### Color Mapping
- Old green (`#8BC34A`) → New blue (`#3B82F6`)
- Old light backgrounds → New slate backgrounds
- Old accent colors → New emerald accents

### Component Updates
- All buttons automatically use new blue theme
- Form elements inherit new focus colors
- Cards use new shadow and border styling

## Best Practices

1. **Consistency**: Always use design tokens instead of hardcoded values
2. **Hierarchy**: Use proper font sizes and weights for content hierarchy
3. **Spacing**: Stick to the 4px spacing scale for visual consistency
4. **Colors**: Use semantic color names (primary, secondary, success, etc.)
5. **Accessibility**: Test color contrast and keyboard navigation 