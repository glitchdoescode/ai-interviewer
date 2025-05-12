import React, { useState, useEffect } from 'react';
import {
  Box,
  Heading,
  Select,
  Text,
  Tag,
  TagLabel,
  Wrap,
  WrapItem,
  FormControl,
  FormLabel,
  Button,
  useToast,
  Textarea,
  Skeleton,
} from '@chakra-ui/react';
import { getJobRoles } from '../api/interviewService';

/**
 * Component for selecting a job role before starting an interview
 * 
 * @param {Object} props Component props
 * @param {Function} props.onRoleSelect Callback when a role is selected, passing job role data
 * @param {Function} props.onStartInterview Callback to start the interview with selected role
 * @param {boolean} props.isLoading Whether the component is in loading state
 */
const JobRoleSelector = ({ onRoleSelect, onStartInterview, isLoading = false }) => {
  const [jobRoles, setJobRoles] = useState([]);
  const [selectedRole, setSelectedRole] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [customDescription, setCustomDescription] = useState('');
  
  const toast = useToast();

  // Fetch available job roles on component mount
  useEffect(() => {
    const fetchJobRoles = async () => {
      try {
        setLoading(true);
        const roles = await getJobRoles();
        setJobRoles(roles);
        setLoading(false);
      } catch (err) {
        setError('Failed to load job roles. Please try again later.');
        setLoading(false);
        toast({
          title: 'Error',
          description: 'Failed to load job roles',
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
      }
    };

    fetchJobRoles();
  }, [toast]);

  // Handle role selection
  const handleRoleChange = (e) => {
    const roleId = e.target.value;
    if (roleId === 'custom') {
      setSelectedRole({
        role_name: 'Custom Role',
        seniority_level: 'Mid-level',
        required_skills: [],
        description: ''
      });
    } else {
      const selected = jobRoles.find(role => role.role_name === roleId);
      setSelectedRole(selected);
      setCustomDescription('');
      
      // Call the onRoleSelect callback
      if (onRoleSelect && selected) {
        onRoleSelect(selected);
      }
    }
  };

  // Handle custom description change
  const handleDescriptionChange = (e) => {
    setCustomDescription(e.target.value);
    
    // Update selected role with custom description
    if (selectedRole) {
      const updatedRole = {
        ...selectedRole,
        description: e.target.value
      };
      setSelectedRole(updatedRole);
      
      // Call the onRoleSelect callback
      if (onRoleSelect) {
        onRoleSelect(updatedRole);
      }
    }
  };

  // Handle starting the interview
  const handleStartInterview = () => {
    if (!selectedRole) {
      toast({
        title: 'No role selected',
        description: 'Please select a job role before starting the interview',
        status: 'warning',
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    if (onStartInterview) {
      onStartInterview(selectedRole);
    }
  };

  return (
    <Box 
      borderWidth="1px" 
      borderRadius="lg" 
      p={6}
      boxShadow="md"
      bg="white"
      maxWidth="800px"
      mx="auto"
    >
      <Heading as="h2" size="lg" mb={4}>
        Select Job Role for Interview
      </Heading>
      
      <Text mb={4} color="gray.600">
        Choose a job role to customize the interview questions and evaluation criteria. 
        This helps the AI interviewer focus on relevant skills and experience.
      </Text>
      
      {loading ? (
        <>
          <Skeleton height="40px" mb={4} />
          <Skeleton height="120px" mb={4} />
          <Skeleton height="60px" />
        </>
      ) : error ? (
        <Text color="red.500">{error}</Text>
      ) : (
        <>
          <FormControl mb={6}>
            <FormLabel>Job Role</FormLabel>
            <Select 
              placeholder="Select job role" 
              onChange={handleRoleChange}
              isDisabled={isLoading}
            >
              {jobRoles.map((role) => (
                <option key={role.role_name} value={role.role_name}>
                  {role.role_name} ({role.seniority_level})
                </option>
              ))}
              <option value="custom">Custom Role</option>
            </Select>
          </FormControl>
          
          {selectedRole && (
            <>
              <Box mb={6}>
                <FormLabel>Required Skills</FormLabel>
                <Wrap spacing={2}>
                  {selectedRole.required_skills.map((skill) => (
                    <WrapItem key={skill}>
                      <Tag size="md" colorScheme="blue" borderRadius="full">
                        <TagLabel>{skill}</TagLabel>
                      </Tag>
                    </WrapItem>
                  ))}
                </Wrap>
              </Box>
              
              <FormControl mb={6}>
                <FormLabel>
                  {selectedRole.role_name === 'Custom Role' 
                    ? 'Job Description (required)' 
                    : 'Job Description (optional override)'}
                </FormLabel>
                <Textarea
                  value={customDescription || selectedRole.description}
                  onChange={handleDescriptionChange}
                  placeholder="Enter job description or specific requirements"
                  size="md"
                  rows={4}
                  isDisabled={isLoading}
                />
              </FormControl>
            </>
          )}
          
          <Button
            colorScheme="blue"
            size="lg"
            width="full"
            mt={4}
            onClick={handleStartInterview}
            isLoading={isLoading}
            isDisabled={!selectedRole}
          >
            Start Interview
          </Button>
        </>
      )}
    </Box>
  );
};

export default JobRoleSelector; 