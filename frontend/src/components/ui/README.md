# Professional UI Component Library

A comprehensive set of reusable UI components for the AI Interviewer application, built with professional blue design system and accessibility in mind.

## Overview

This component library provides modern, accessible, and consistent UI components that match the professional mockup designs. All components use the design system tokens and follow WCAG 2.1 AA accessibility standards.

## Installation & Usage

```jsx
// Import individual components
import { Button, Card, FeatureCard } from './components/ui';

// Or import everything
import * as UI from './components/ui';
```

## Components

### Buttons

Professional button components with multiple variants and states.

```jsx
// Basic usage
<Button>Primary Button</Button>
<Button variant="secondary">Secondary Button</Button>
<Button variant="outline">Outline Button</Button>
<Button variant="ghost">Ghost Button</Button>

// With icons and states
<Button icon={<CheckIcon />} loading={isLoading}>
  Save Changes
</Button>

// Sizes
<Button size="sm">Small</Button>
<Button size="md">Medium</Button>
<Button size="lg">Large</Button>
<Button size="xl">Extra Large</Button>
```

**Props:**
- `variant`: `'primary' | 'secondary' | 'ghost' | 'outline' | 'danger'`
- `size`: `'sm' | 'md' | 'lg' | 'xl'`
- `disabled`: `boolean`
- `loading`: `boolean`
- `icon`: `ReactNode`
- `iconPosition`: `'left' | 'right'`
- `fullWidth`: `boolean`

### Cards

Flexible card components for different content types.

```jsx
// Basic card
<Card>
  <h3>Card Title</h3>
  <p>Card content goes here</p>
</Card>

// Feature card for services
<FeatureCard
  icon={<ServiceIcon />}
  title="AI-Powered Interviews"
  description="Conduct intelligent interviews with AI assistance"
/>

// Stats card for metrics
<StatsCard
  title="Total Interviews"
  value="1,247"
  icon={<ChartIcon />}
  trend="+12%"
  trendDirection="up"
/>

// Interview stage card
<InterviewStageCard
  stage={1}
  title="Introduction"
  description="Welcome and setup phase"
  status="completed"
  duration="5 min"
/>
```

**Card Props:**
- `variant`: `'default' | 'feature' | 'stats' | 'stage' | 'outlined' | 'elevated'`
- `elevation`: `'none' | 'sm' | 'md' | 'lg' | 'xl'`
- `padding`: `'none' | 'sm' | 'md' | 'lg' | 'xl'`
- `onClick`: `function` (makes card clickable)

### Progress Components

Components for showing progress and status.

```jsx
// Progress bar
<ProgressBar value={65} max={100} showLabel />

// Step indicator for multi-step processes
<StepIndicator
  steps={[
    { title: "Setup", description: "Initial configuration" },
    { title: "Interview", description: "Conduct the interview" },
    { title: "Review", description: "Review and feedback" }
  ]}
  currentStep={1}
  clickable
  onStepClick={(step) => console.log('Step clicked:', step)}
/>

// Circular progress
<CircularProgress value={75} size={100} showLabel />

// Status badges
<StatusBadge status="success">Completed</StatusBadge>
<StatusBadge status="warning" variant="soft">In Progress</StatusBadge>

// Timeline
<Timeline
  items={[
    {
      title: "Interview Started",
      description: "Candidate joined the session",
      timestamp: "2025-01-27 10:00 AM"
    },
    {
      title: "Technical Round",
      description: "Technical questions phase completed",
      timestamp: "2025-01-27 10:30 AM"
    }
  ]}
/>
```

**Progress Props:**
- `value`: `number` - Current progress value
- `max`: `number` - Maximum value (default: 100)
- `variant`: `'primary' | 'secondary' | 'success' | 'warning' | 'error'`
- `size`: `'sm' | 'md' | 'lg'`

## Design System Integration

All components use design system tokens:

```css
/* Colors */
var(--color-primary-500)    /* Professional blue */
var(--color-secondary-500)  /* Slate gray */
var(--color-success-500)    /* Emerald green */

/* Typography */
var(--font-family-primary)  /* Inter font */
var(--font-size-base)       /* 16px */
var(--font-weight-semibold) /* 600 */

/* Spacing */
var(--spacing-4)            /* 16px */
var(--spacing-6)            /* 24px */

/* Shadows */
var(--shadow-md)            /* Medium elevation */
var(--shadow-lg)            /* Large elevation */
```

## Accessibility Features

- **Keyboard Navigation**: All interactive components support keyboard navigation
- **Screen Reader Support**: Proper ARIA labels and roles
- **Focus Management**: Clear focus indicators and logical tab order
- **Color Contrast**: WCAG 2.1 AA compliant color combinations
- **Reduced Motion**: Respects `prefers-reduced-motion` setting

## Examples

### Interview Flow

```jsx
// Step indicator for interview stages
<StepIndicator
  steps={[
    { title: "Welcome", description: "Introduction and setup" },
    { title: "Technical", description: "Technical assessment" },
    { title: "Coding", description: "Live coding challenge" },
    { title: "Q&A", description: "Questions and answers" },
    { title: "Wrap-up", description: "Conclusion and next steps" }
  ]}
  currentStep={2}
  size="lg"
/>

// Interview stage cards
<div className="interview-stages">
  <InterviewStageCard
    stage={1}
    title="Introduction"
    description="Get to know the candidate"
    status="completed"
    duration="10 min"
  />
  <InterviewStageCard
    stage={2}
    title="Technical Questions"
    description="Assess technical knowledge"
    status="current"
    duration="20 min"
  />
  <InterviewStageCard
    stage={3}
    title="Coding Challenge"
    description="Live coding session"
    status="pending"
    duration="30 min"
  />
</div>
```

### Dashboard Metrics

```jsx
// Stats cards for dashboard
<div className="stats-grid">
  <StatsCard
    title="Total Interviews"
    value="1,247"
    icon={<UsersIcon />}
    trend="+12% from last month"
    trendDirection="up"
  />
  <StatsCard
    title="Success Rate"
    value="94%"
    icon={<CheckCircleIcon />}
    trend="+3% from last month"
    trendDirection="up"
  />
  <StatsCard
    title="Avg Duration"
    value="42 min"
    icon={<ClockIcon />}
    trend="-5 min from last month"
    trendDirection="down"
  />
</div>
```

## Best Practices

1. **Consistent Spacing**: Use design system spacing tokens
2. **Semantic Colors**: Use appropriate color variants for context
3. **Accessible Labels**: Always provide proper labels for screen readers
4. **Loading States**: Show loading states for async operations
5. **Error Handling**: Display clear error messages and states
6. **Responsive Design**: Components adapt to different screen sizes

## Contributing

When adding new components:

1. Follow the established component structure
2. Use design system tokens for styling
3. Include proper TypeScript/PropTypes definitions
4. Add accessibility attributes
5. Include usage examples in documentation
6. Test across different browsers and devices 