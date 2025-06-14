import React from 'react';
import PropTypes from 'prop-types';
import './Form.css';

// Input Component
const Input = ({
  type = 'text',
  label,
  placeholder,
  value,
  onChange,
  error,
  disabled = false,
  required = false,
  className = '',
  ...props
}) => {
  const inputClasses = [
    'input',
    error && 'input-error',
    disabled && 'input-disabled',
    className
  ].filter(Boolean).join(' ');

  return (
    <div className="form-field">
      {label && (
        <label className="form-label">
          {label}
          {required && <span className="form-required">*</span>}
        </label>
      )}
      <input
        type={type}
        className={inputClasses}
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        disabled={disabled}
        required={required}
        {...props}
      />
      {error && <span className="form-error">{error}</span>}
    </div>
  );
};

// Select Component
const Select = ({
  label,
  placeholder = 'Select an option',
  value,
  onChange,
  options = [],
  error,
  disabled = false,
  required = false,
  className = '',
  ...props
}) => {
  const selectClasses = [
    'select',
    error && 'select-error',
    disabled && 'select-disabled',
    className
  ].filter(Boolean).join(' ');

  return (
    <div className="form-field">
      {label && (
        <label className="form-label">
          {label}
          {required && <span className="form-required">*</span>}
        </label>
      )}
      <div className="select-wrapper">
        <select
          className={selectClasses}
          value={value}
          onChange={onChange}
          disabled={disabled}
          required={required}
          {...props}
        >
          <option value="" disabled>
            {placeholder}
          </option>
          {options.map((option, index) => (
            <option key={index} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <div className="select-arrow">
          <svg width="12" height="8" viewBox="0 0 12 8" fill="none">
            <path d="M1 1.5L6 6.5L11 1.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
      </div>
      {error && <span className="form-error">{error}</span>}
    </div>
  );
};

// Textarea Component
const Textarea = ({
  label,
  placeholder,
  value,
  onChange,
  error,
  disabled = false,
  required = false,
  rows = 4,
  maxLength,
  showCharCount = false,
  className = '',
  ...props
}) => {
  const textareaClasses = [
    'textarea',
    error && 'textarea-error',
    disabled && 'textarea-disabled',
    className
  ].filter(Boolean).join(' ');

  const charCount = value ? value.length : 0;

  return (
    <div className="form-field">
      {label && (
        <label className="form-label">
          {label}
          {required && <span className="form-required">*</span>}
        </label>
      )}
      <div className="textarea-wrapper">
        <textarea
          className={textareaClasses}
          placeholder={placeholder}
          value={value}
          onChange={onChange}
          disabled={disabled}
          required={required}
          rows={rows}
          maxLength={maxLength}
          {...props}
        />
        {(showCharCount || maxLength) && (
          <div className="char-count">
            {charCount}{maxLength && `/${maxLength}`}
          </div>
        )}
      </div>
      {error && <span className="form-error">{error}</span>}
    </div>
  );
};

// Range Slider Component
const RangeSlider = ({
  label,
  value,
  onChange,
  min = 0,
  max = 100,
  step = 1,
  showValue = true,
  disabled = false,
  className = '',
  ...props
}) => {
  const sliderClasses = [
    'range-slider',
    disabled && 'range-slider-disabled',
    className
  ].filter(Boolean).join(' ');

  return (
    <div className="form-field">
      {label && (
        <div className="range-slider-header">
          <label className="form-label">{label}</label>
          {showValue && <span className="range-value">{value}</span>}
        </div>
      )}
      <div className="range-slider-wrapper">
        <input
          type="range"
          className={sliderClasses}
          value={value}
          onChange={onChange}
          min={min}
          max={max}
          step={step}
          disabled={disabled}
          {...props}
        />
        <div className="range-track">
          <div 
            className="range-fill"
            style={{ width: `${((value - min) / (max - min)) * 100}%` }}
          />
        </div>
      </div>
    </div>
  );
};

// File Upload Component
const FileUpload = ({
  label,
  accept,
  onChange,
  error,
  disabled = false,
  multiple = false,
  className = '',
  ...props
}) => {
  const handleFileChange = (e) => {
    const files = Array.from(e.target.files);
    onChange(files);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files);
    onChange(files);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  return (
    <div className="form-field">
      {label && <label className="form-label">{label}</label>}
      <div 
        className={`file-upload ${error ? 'file-upload-error' : ''} ${disabled ? 'file-upload-disabled' : ''} ${className}`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
      >
        <input
          type="file"
          accept={accept}
          onChange={handleFileChange}
          disabled={disabled}
          multiple={multiple}
          className="file-input"
          {...props}
        />
        <div className="file-upload-content">
          <div className="file-upload-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
              <path d="M12 16L12 8" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              <path d="M9 11L12 8L15 11" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              <path d="M3 20H21V16H19V18H5V16H3V20Z" fill="currentColor"/>
            </svg>
          </div>
          <div className="file-upload-text">
            <span className="file-upload-main">Click to upload or drag and drop</span>
            <span className="file-upload-sub">Supports: PDF, DOC, DOCX, TXT</span>
          </div>
        </div>
      </div>
      {error && <span className="form-error">{error}</span>}
    </div>
  );
};

// PropTypes
Input.propTypes = {
  type: PropTypes.string,
  label: PropTypes.string,
  placeholder: PropTypes.string,
  value: PropTypes.string,
  onChange: PropTypes.func,
  error: PropTypes.string,
  disabled: PropTypes.bool,
  required: PropTypes.bool,
  className: PropTypes.string
};

Select.propTypes = {
  label: PropTypes.string,
  placeholder: PropTypes.string,
  value: PropTypes.string,
  onChange: PropTypes.func,
  options: PropTypes.arrayOf(PropTypes.shape({
    value: PropTypes.string,
    label: PropTypes.string
  })),
  error: PropTypes.string,
  disabled: PropTypes.bool,
  required: PropTypes.bool,
  className: PropTypes.string
};

Textarea.propTypes = {
  label: PropTypes.string,
  placeholder: PropTypes.string,
  value: PropTypes.string,
  onChange: PropTypes.func,
  error: PropTypes.string,
  disabled: PropTypes.bool,
  required: PropTypes.bool,
  rows: PropTypes.number,
  maxLength: PropTypes.number,
  showCharCount: PropTypes.bool,
  className: PropTypes.string
};

RangeSlider.propTypes = {
  label: PropTypes.string,
  value: PropTypes.number,
  onChange: PropTypes.func,
  min: PropTypes.number,
  max: PropTypes.number,
  step: PropTypes.number,
  showValue: PropTypes.bool,
  disabled: PropTypes.bool,
  className: PropTypes.string
};

FileUpload.propTypes = {
  label: PropTypes.string,
  accept: PropTypes.string,
  onChange: PropTypes.func,
  error: PropTypes.string,
  disabled: PropTypes.bool,
  multiple: PropTypes.bool,
  className: PropTypes.string
};

export { Input, Select, Textarea, RangeSlider, FileUpload }; 