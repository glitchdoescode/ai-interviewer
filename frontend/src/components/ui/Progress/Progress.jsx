import React from 'react';
import PropTypes from 'prop-types';
import './Progress.css';

// Basic Progress Bar
const ProgressBar = ({
  value = 0,
  max = 100,
  size = 'md',
  variant = 'primary',
  showLabel = false,
  className = '',
  ...props
}) => {
  const percentage = Math.min(Math.max((value / max) * 100, 0), 100);
  
  const progressClasses = [
    'progress-bar',
    `progress-${size}`,
    `progress-${variant}`,
    className
  ].filter(Boolean).join(' ');

  return (
    <div className={progressClasses} {...props}>
      <div 
        className="progress-fill"
        style={{ width: `${percentage}%` }}
        role="progressbar"
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={max}
      />
      {showLabel && (
        <span className="progress-label">
          {Math.round(percentage)}%
        </span>
      )}
    </div>
  );
};

// Step Indicator for multi-step processes
const StepIndicator = ({
  steps = [],
  currentStep = 0,
  orientation = 'horizontal',
  size = 'md',
  clickable = false,
  onStepClick,
  className = '',
  ...props
}) => {
  const stepClasses = [
    'step-indicator',
    `step-${orientation}`,
    `step-${size}`,
    className
  ].filter(Boolean).join(' ');

  const handleStepClick = (stepIndex) => {
    if (clickable && onStepClick) {
      onStepClick(stepIndex);
    }
  };

  return (
    <div className={stepClasses} {...props}>
      {steps.map((step, index) => {
        const isCompleted = index < currentStep;
        const isCurrent = index === currentStep;
        const isPending = index > currentStep;
        
        const stepItemClasses = [
          'step-item',
          isCompleted && 'step-completed',
          isCurrent && 'step-current',
          isPending && 'step-pending',
          clickable && 'step-clickable'
        ].filter(Boolean).join(' ');

        return (
          <div 
            key={index} 
            className={stepItemClasses}
            onClick={() => handleStepClick(index)}
            role={clickable ? 'button' : undefined}
            tabIndex={clickable ? 0 : undefined}
          >
            <div className="step-circle">
              {isCompleted ? (
                <span className="step-check">✓</span>
              ) : (
                <span className="step-number">{index + 1}</span>
              )}
            </div>
            <div className="step-content">
              <div className="step-title">{step.title}</div>
              {step.description && (
                <div className="step-description">{step.description}</div>
              )}
            </div>
            {index < steps.length - 1 && (
              <div className="step-connector" />
            )}
          </div>
        );
      })}
    </div>
  );
};

// Circular Progress indicator
const CircularProgress = ({
  value = 0,
  max = 100,
  size = 80,
  strokeWidth = 8,
  variant = 'primary',
  showLabel = true,
  className = '',
  ...props
}) => {
  const percentage = Math.min(Math.max((value / max) * 100, 0), 100);
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const strokeDasharray = circumference;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

  const circularClasses = [
    'circular-progress',
    `circular-${variant}`,
    className
  ].filter(Boolean).join(' ');

  return (
    <div className={circularClasses} style={{ width: size, height: size }} {...props}>
      <svg width={size} height={size} className="circular-svg">
        {/* Background circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="var(--color-secondary-200)"
          strokeWidth={strokeWidth}
          fill="none"
        />
        {/* Progress circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="currentColor"
          strokeWidth={strokeWidth}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={strokeDasharray}
          strokeDashoffset={strokeDashoffset}
          className="circular-progress-circle"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      {showLabel && (
        <div className="circular-progress-label">
          {Math.round(percentage)}%
        </div>
      )}
    </div>
  );
};

// Status Badge
const StatusBadge = ({
  status = 'default',
  children,
  size = 'md',
  variant = 'filled',
  className = '',
  ...props
}) => {
  const badgeClasses = [
    'status-badge',
    `badge-${status}`,
    `badge-${size}`,
    `badge-${variant}`,
    className
  ].filter(Boolean).join(' ');

  return (
    <span className={badgeClasses} {...props}>
      {children}
    </span>
  );
};

// Timeline component for showing progress over time
const Timeline = ({
  items = [],
  className = '',
  ...props
}) => {
  return (
    <div className={`timeline ${className}`} {...props}>
      {items.map((item, index) => (
        <div key={index} className="timeline-item">
          <div className="timeline-marker">
            {item.icon || <div className="timeline-dot" />}
          </div>
          <div className="timeline-content">
            <div className="timeline-header">
              <h4 className="timeline-title">{item.title}</h4>
              {item.timestamp && (
                <span className="timeline-timestamp">{item.timestamp}</span>
              )}
            </div>
            {item.description && (
              <p className="timeline-description">{item.description}</p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};

// PropTypes
ProgressBar.propTypes = {
  value: PropTypes.number,
  max: PropTypes.number,
  size: PropTypes.oneOf(['sm', 'md', 'lg']),
  variant: PropTypes.oneOf(['primary', 'secondary', 'success', 'warning', 'error']),
  showLabel: PropTypes.bool,
  className: PropTypes.string
};

StepIndicator.propTypes = {
  steps: PropTypes.arrayOf(PropTypes.shape({
    title: PropTypes.string.isRequired,
    description: PropTypes.string
  })).isRequired,
  currentStep: PropTypes.number,
  orientation: PropTypes.oneOf(['horizontal', 'vertical']),
  size: PropTypes.oneOf(['sm', 'md', 'lg']),
  clickable: PropTypes.bool,
  onStepClick: PropTypes.func,
  className: PropTypes.string
};

CircularProgress.propTypes = {
  value: PropTypes.number,
  max: PropTypes.number,
  size: PropTypes.number,
  strokeWidth: PropTypes.number,
  variant: PropTypes.oneOf(['primary', 'secondary', 'success', 'warning', 'error']),
  showLabel: PropTypes.bool,
  className: PropTypes.string
};

StatusBadge.propTypes = {
  status: PropTypes.oneOf(['default', 'primary', 'secondary', 'success', 'warning', 'error']),
  children: PropTypes.node.isRequired,
  size: PropTypes.oneOf(['sm', 'md', 'lg']),
  variant: PropTypes.oneOf(['filled', 'outlined', 'soft']),
  className: PropTypes.string
};

Timeline.propTypes = {
  items: PropTypes.arrayOf(PropTypes.shape({
    title: PropTypes.string.isRequired,
    description: PropTypes.string,
    timestamp: PropTypes.string,
    icon: PropTypes.node
  })).isRequired,
  className: PropTypes.string
};

export default ProgressBar;
export { ProgressBar, StepIndicator, CircularProgress, StatusBadge, Timeline }; 