import React from 'react';
import PropTypes from 'prop-types';
import './Card.css';

const Card = ({
  children,
  variant = 'default',
  elevation = 'md',
  padding = 'md',
  className = '',
  onClick,
  header = null,
  footer = null,
  ...props
}) => {
  const cardClasses = [
    'card',
    `card-${variant}`,
    `card-elevation-${elevation}`,
    `card-padding-${padding}`,
    onClick && 'card-clickable',
    className
  ].filter(Boolean).join(' ');

  const handleClick = (e) => {
    if (onClick) {
      onClick(e);
    }
  };

  return (
    <div
      className={cardClasses}
      onClick={handleClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      {...props}
    >
      {header && (
        <div className="card-header">
          {header}
        </div>
      )}
      <div className="card-body">
        {children}
      </div>
      {footer && (
        <div className="card-footer">
          {footer}
        </div>
      )}
    </div>
  );
};

// Feature Card for services/features display
const FeatureCard = ({
  icon,
  title,
  description,
  variant = 'default',
  className = '',
  ...props
}) => {
  return (
    <Card variant={variant} className={`feature-card ${className}`} {...props}>
      <div className="feature-card-content">
        {icon && (
          <div className="feature-card-icon">
            {icon}
          </div>
        )}
        {title && (
          <h3 className="feature-card-title">
            {title}
          </h3>
        )}
        {description && (
          <p className="feature-card-description">
            {description}
          </p>
        )}
      </div>
    </Card>
  );
};

// Stats Card for metrics display
const StatsCard = ({
  title,
  value,
  subtitle,
  icon,
  trend,
  trendDirection,
  className = '',
  ...props
}) => {
  return (
    <Card variant="stats" className={`stats-card ${className}`} {...props}>
      <div className="stats-card-content">
        <div className="stats-card-header">
          {icon && (
            <div className="stats-card-icon">
              {icon}
            </div>
          )}
          <div className="stats-card-info">
            <h3 className="stats-card-title">{title}</h3>
            {subtitle && (
              <p className="stats-card-subtitle">{subtitle}</p>
            )}
          </div>
        </div>
        <div className="stats-card-value">
          {value}
        </div>
        {trend && (
          <div className={`stats-card-trend trend-${trendDirection}`}>
            {trend}
          </div>
        )}
      </div>
    </Card>
  );
};

// Interview Stage Card
const InterviewStageCard = ({
  stage,
  title,
  description,
  status = 'pending',
  duration,
  className = '',
  ...props
}) => {
  return (
    <Card 
      variant="stage" 
      className={`interview-stage-card stage-${status} ${className}`} 
      {...props}
    >
      <div className="stage-card-content">
        <div className="stage-card-header">
          <div className="stage-card-number">
            {stage}
          </div>
          <div className="stage-card-info">
            <h3 className="stage-card-title">{title}</h3>
            {duration && (
              <span className="stage-card-duration">{duration}</span>
            )}
          </div>
          <div className={`stage-card-status status-${status}`}>
            {status === 'completed' && '✓'}
            {status === 'current' && '●'}
            {status === 'pending' && '○'}
          </div>
        </div>
        {description && (
          <p className="stage-card-description">{description}</p>
        )}
      </div>
    </Card>
  );
};

Card.propTypes = {
  children: PropTypes.node.isRequired,
  variant: PropTypes.oneOf(['default', 'feature', 'stats', 'stage', 'outlined', 'elevated']),
  elevation: PropTypes.oneOf(['none', 'sm', 'md', 'lg', 'xl']),
  padding: PropTypes.oneOf(['none', 'sm', 'md', 'lg', 'xl']),
  className: PropTypes.string,
  onClick: PropTypes.func,
  header: PropTypes.node,
  footer: PropTypes.node
};

FeatureCard.propTypes = {
  icon: PropTypes.node,
  title: PropTypes.string,
  description: PropTypes.string,
  variant: PropTypes.oneOf(['default', 'feature', 'stats', 'stage', 'outlined', 'elevated']),
  className: PropTypes.string
};

StatsCard.propTypes = {
  title: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number, PropTypes.node]).isRequired,
  subtitle: PropTypes.string,
  icon: PropTypes.node,
  trend: PropTypes.string,
  trendDirection: PropTypes.oneOf(['up', 'down', 'neutral']),
  className: PropTypes.string
};

InterviewStageCard.propTypes = {
  stage: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  title: PropTypes.string.isRequired,
  description: PropTypes.string,
  status: PropTypes.oneOf(['pending', 'current', 'completed']),
  duration: PropTypes.string,
  className: PropTypes.string
};

export default Card;
export { FeatureCard, StatsCard, InterviewStageCard }; 