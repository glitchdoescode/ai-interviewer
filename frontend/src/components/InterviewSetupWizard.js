import React, { useState, useEffect } from 'react';
import { getJobRoles } from '../api/interviewService';
import { 
  Button, 
  Card, 
  StepIndicator, 
  Input, 
  Select, 
  Textarea, 
  RangeSlider, 
  FileUpload,
  StatusBadge
} from './ui';
import './InterviewSetupWizard.css';

/**
 * Modern multi-step interview setup wizard
 */
const InterviewSetupWizard = ({ onComplete, onCancel }) => {
  // Wizard state
  const [currentStep, setCurrentStep] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [errors, setErrors] = useState({});
  
  // Data state
  const [jobRoles, setJobRoles] = useState([]);
  const [formData, setFormData] = useState({
    // Step 1: Job Role & Experience
    jobRole: '',
    experienceLevel: 3,
    customRole: '',
    
    // Step 2: Job Description
    jobDescription: '',
    uploadedFiles: [],
    requiredSkills: [],
    
    // Step 3: Interview Configuration
    interviewDuration: 45,
    interviewType: 'technical',
    focusAreas: [],
    difficultyLevel: 'intermediate'
  });

  // Step configuration
  const steps = [
    {
      title: 'Job Role',
      description: 'Select your target position and experience level'
    },
    {
      title: 'Job Description',
      description: 'Provide job details and requirements'
    },
    {
      title: 'Interview Settings',
      description: 'Configure interview parameters'
    }
  ];

  // Load job roles on mount
  useEffect(() => {
    const fetchJobRoles = async () => {
      try {
        setIsLoading(true);
        const roles = await getJobRoles();
        setJobRoles(roles);
      } catch (error) {
        console.error('Failed to load job roles:', error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchJobRoles();
  }, []);

  // Form validation
  const validateStep = (stepIndex) => {
    const stepErrors = {};
    
    switch (stepIndex) {
      case 0:
        if (!formData.jobRole) {
          stepErrors.jobRole = 'Please select a job role';
        }
        if (formData.jobRole === 'custom' && !formData.customRole) {
          stepErrors.customRole = 'Please enter a custom role name';
        }
        break;
        
      case 1:
        if (!formData.jobDescription && formData.uploadedFiles.length === 0) {
          stepErrors.jobDescription = 'Please provide a job description or upload a file';
        }
        break;
        
      case 2:
        if (formData.interviewDuration < 15 || formData.interviewDuration > 120) {
          stepErrors.interviewDuration = 'Interview duration must be between 15 and 120 minutes';
        }
        break;
        
      default:
        break;
    }
    
    setErrors(stepErrors);
    return Object.keys(stepErrors).length === 0;
  };

  // Navigation handlers
  const handleNext = () => {
    if (validateStep(currentStep)) {
      if (currentStep < steps.length - 1) {
        setCurrentStep(currentStep + 1);
      } else {
        handleComplete();
      }
    }
  };

  const handlePrevious = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleStepClick = (stepIndex) => {
    if (stepIndex < currentStep || stepIndex === 0) {
      setCurrentStep(stepIndex);
    }
  };

  const handleComplete = async () => {
    try {
      setIsLoading(true);
      
      // Prepare the final job role data
      const roleData = {
        role_name: formData.jobRole === 'custom' ? formData.customRole : formData.jobRole,
        seniority_level: getSeniorityLabel(formData.experienceLevel),
        description: formData.jobDescription,
        required_skills: formData.requiredSkills,
        interview_config: {
          duration: formData.interviewDuration,
          type: formData.interviewType,
          focus_areas: formData.focusAreas,
          difficulty: formData.difficultyLevel
        }
      };
      
      onComplete(roleData);
    } catch (error) {
      console.error('Error completing setup:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Helper functions
  const getSeniorityLabel = (level) => {
    const levels = {
      1: 'Junior',
      2: 'Junior',
      3: 'Mid-level',
      4: 'Senior',
      5: 'Staff/Principal'
    };
    return levels[level] || 'Mid-level';
  };

  const updateFormData = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
    
    // Clear errors for this field
    if (errors[field]) {
      setErrors(prev => ({
        ...prev,
        [field]: undefined
      }));
    }
  };

  const getJobRoleOptions = () => {
    const options = jobRoles.map(role => ({
      value: role.role_name,
      label: `${role.role_name} (${role.seniority_level})`
    }));
    
    options.push({
      value: 'custom',
      label: 'Custom Role'
    });
    
    return options;
  };

  const handleFileUpload = (files) => {
    updateFormData('uploadedFiles', files);
    
    // Extract text from files if needed (placeholder)
    if (files.length > 0) {
      // In a real implementation, you'd process the files here
      console.log('Files uploaded:', files);
    }
  };

  return (
    <div className="interview-setup-wizard">
      <Card elevation="lg" className="wizard-container">
        {/* Header */}
        <div className="wizard-header">
          <h1 className="wizard-title">Interview Setup</h1>
          <p className="wizard-subtitle">
            Configure your interview preferences step by step
          </p>
        </div>

        {/* Progress Indicator */}
        <div className="wizard-progress">
          <StepIndicator
            steps={steps}
            currentStep={currentStep}
            clickable={true}
            onStepClick={handleStepClick}
            size="lg"
          />
        </div>

        {/* Step Content */}
        <div className="wizard-content">
          {currentStep === 0 && (
            <div className="wizard-step">
              <div className="step-header">
                <h2 className="step-title">Select Job Role & Experience</h2>
                <p className="step-description">
                  Choose the role you're interviewing for and your experience level
                </p>
              </div>

              <div className="step-form">
                <Select
                  label="Job Role"
                  placeholder="Select a job role"
                  value={formData.jobRole}
                  onChange={(e) => updateFormData('jobRole', e.target.value)}
                  options={getJobRoleOptions()}
                  error={errors.jobRole}
                  required
                />

                {formData.jobRole === 'custom' && (
                  <Input
                    label="Custom Role Name"
                    placeholder="e.g. Full Stack Developer"
                    value={formData.customRole}
                    onChange={(e) => updateFormData('customRole', e.target.value)}
                    error={errors.customRole}
                    required
                  />
                )}

                <RangeSlider
                  label="Experience Level"
                  value={formData.experienceLevel}
                  onChange={(e) => updateFormData('experienceLevel', parseInt(e.target.value))}
                  min={1}
                  max={5}
                  step={1}
                  showValue={false}
                />
                
                <div className="experience-labels">
                  <span className="experience-label">Junior (0-2 years)</span>
                  <span className="experience-label">Senior (8+ years)</span>
                </div>
                
                <StatusBadge status="primary" variant="soft">
                  Selected: {getSeniorityLabel(formData.experienceLevel)} Level
                </StatusBadge>
              </div>
            </div>
          )}

          {currentStep === 1 && (
            <div className="wizard-step">
              <div className="step-header">
                <h2 className="step-title">Job Description & Requirements</h2>
                <p className="step-description">
                  Provide details about the position and required skills
                </p>
              </div>

              <div className="step-form">
                <Textarea
                  label="Job Description"
                  placeholder="Paste the job description here or upload a file below..."
                  value={formData.jobDescription}
                  onChange={(e) => updateFormData('jobDescription', e.target.value)}
                  rows={6}
                  maxLength={2000}
                  showCharCount
                  error={errors.jobDescription}
                />

                <div className="upload-section">
                  <FileUpload
                    label="Or Upload Job Description File"
                    accept=".pdf,.doc,.docx,.txt"
                    onChange={handleFileUpload}
                    multiple={false}
                  />
                  
                  {formData.uploadedFiles.length > 0 && (
                    <div className="uploaded-files">
                      {formData.uploadedFiles.map((file, index) => (
                        <StatusBadge key={index} status="success" variant="soft">
                          {file.name}
                        </StatusBadge>
                      ))}
                    </div>
                  )}
                </div>

                <Input
                  label="Required Skills (comma-separated)"
                  placeholder="JavaScript, React, Node.js, MongoDB"
                  value={formData.requiredSkills.join(', ')}
                  onChange={(e) => updateFormData('requiredSkills', 
                    e.target.value.split(',').map(s => s.trim()).filter(s => s)
                  )}
                />
              </div>
            </div>
          )}

          {currentStep === 2 && (
            <div className="wizard-step">
              <div className="step-header">
                <h2 className="step-title">Interview Configuration</h2>
                <p className="step-description">
                  Set up interview duration, type, and focus areas
                </p>
              </div>

              <div className="step-form">
                <div className="form-row">
                  <RangeSlider
                    label="Interview Duration (minutes)"
                    value={formData.interviewDuration}
                    onChange={(e) => updateFormData('interviewDuration', parseInt(e.target.value))}
                    min={15}
                    max={120}
                    step={15}
                    showValue={true}
                  />
                </div>

                <Select
                  label="Interview Type"
                  value={formData.interviewType}
                  onChange={(e) => updateFormData('interviewType', e.target.value)}
                  options={[
                    { value: 'technical', label: 'Technical Interview' },
                    { value: 'behavioral', label: 'Behavioral Interview' },
                    { value: 'mixed', label: 'Mixed (Technical + Behavioral)' },
                    { value: 'coding', label: 'Coding Challenge Focus' }
                  ]}
                  required
                />

                <Select
                  label="Difficulty Level"
                  value={formData.difficultyLevel}
                  onChange={(e) => updateFormData('difficultyLevel', e.target.value)}
                  options={[
                    { value: 'beginner', label: 'Beginner' },
                    { value: 'intermediate', label: 'Intermediate' },
                    { value: 'advanced', label: 'Advanced' },
                    { value: 'expert', label: 'Expert' }
                  ]}
                  required
                />

                <Textarea
                  label="Additional Focus Areas (optional)"
                  placeholder="Any specific topics or technologies to focus on during the interview..."
                  value={formData.focusAreas.join(', ')}
                  onChange={(e) => updateFormData('focusAreas',
                    e.target.value.split(',').map(s => s.trim()).filter(s => s)
                  )}
                  rows={3}
                />
              </div>
            </div>
          )}
        </div>

        {/* Navigation */}
        <div className="wizard-navigation">
          <div className="nav-left">
            {currentStep > 0 && (
              <Button
                variant="outline"
                onClick={handlePrevious}
                disabled={isLoading}
              >
                Previous
              </Button>
            )}
          </div>

          <div className="nav-right">
            <Button
              variant="ghost"
              onClick={onCancel}
              disabled={isLoading}
            >
              Cancel
            </Button>
            
            <Button
              onClick={handleNext}
              loading={isLoading}
              disabled={isLoading}
            >
              {currentStep === steps.length - 1 ? 'Start Interview' : 'Next'}
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default InterviewSetupWizard; 