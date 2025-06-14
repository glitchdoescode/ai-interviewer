import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import {
  Box,
  Container,
  Heading,
  Text,
  Button,
  useColorModeValue,
  Flex,
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  useToast,
  Spinner,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
} from '@chakra-ui/react';
import { FaArrowLeft, FaHome } from 'react-icons/fa';
import { useReactToPrint } from 'react-to-print';
import { useAuth } from '../context/AuthContext';

// Import the DetailedReport component
import DetailedReport from '../components/reports/DetailedReport';

// Mock data for when the API fails
const mockReportData = {
  session_id: "mock-session-id",
  candidate_name: "Sample Candidate",
  job_role: "Software Engineer",
  timestamp: new Date().toISOString(),
  interview_data: {
    total_duration_minutes: 45,
    questions_asked: [
      { id: 1, question: "Explain the concept of closures in JavaScript", answer: "Closures are functions that remember the environment in which they were created. They allow a function to access variables from an outer function even after the outer function has completed execution." },
      { id: 2, question: "What is the difference between var, let, and const?", answer: "var is function-scoped, while let and const are block-scoped. const creates a variable whose reference cannot be changed, unlike var and let." },
      { id: 3, question: "Explain event bubbling in the DOM", answer: "Event bubbling is a mechanism where an event triggered on a child element also triggers the same event on all parent elements up to the root of the document." }
    ],
    coding_challenge: {
      title: "Array Sum Problem",
      description: "Write a function that finds two numbers in an array that add up to a target value",
      solution_submitted: "function twoSum(nums, target) {\n  const map = {};\n  for (let i = 0; i < nums.length; i++) {\n    const complement = target - nums[i];\n    if (map[complement] !== undefined) {\n      return [map[complement], i];\n    }\n    map[nums[i]] = i;\n  }\n  return null;\n}",
      language: "javascript",
      time_spent_minutes: 12
    }
  },
  evaluation_data: {
    qa_evaluation: [
      { question_id: 1, score: 4.5, feedback: "Excellent explanation of closures with clear examples" },
      { question_id: 2, score: 4.0, feedback: "Good understanding of variable declarations in JavaScript" },
      { question_id: 3, score: 3.5, feedback: "Correct explanation, but could provide more context on capturing vs. bubbling" }
    ],
    coding_evaluation: {
      correctness: 4.5,
      efficiency: 4.0,
      code_quality: 3.5,
      problem_solving: 4.0,
      feedback: "Implemented an efficient O(n) solution using a hash map. Good variable naming and structure. Could improve error handling."
    },
    overall_evaluation: {
      technical_knowledge: 4.2,
      communication: 4.0,
      problem_solving: 4.0,
      cultural_fit: 3.8,
      overall_score: 4.0,
      strengths: ["Strong JavaScript knowledge", "Efficient problem-solving approach", "Clear communication"],
      areas_for_improvement: ["Could expand on DOM event handling", "Consider edge cases more thoroughly"]
    },
    current_stage: "conclusion"
  },
  summary_statistics: {
    qa_average: 4.0,
    coding_average: 4.0,
    overall_average: 4.0,
    total_questions: 3,
    questions_answered: 3,
    coding_completed: true,
    trust_score: 0.85,
    completion_percentage: 100
  }
};

/**
 * ReportPage component for displaying detailed interview reports
 * Fetches report data for a specific session and renders the DetailedReport component
 */
const ReportPage = () => {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const { token } = useAuth(); // Get token from auth context
  
  const [reportData, setReportData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [candidateName, setCandidateName] = useState('');
  const [jobRole, setJobRole] = useState('');
  const [useFallbackData, setUseFallbackData] = useState(false);
  
  const reportRef = useRef();
  
  // Fetch report data when component mounts
  useEffect(() => {
    const fetchReportData = async () => {
      setIsLoading(true);
      setError(null);
      
      try {
        // Fetch detailed report data from the API
        const response = await axios.get(`/api/interview/${sessionId}/detailed-report`, {
          headers: {
            Authorization: `Bearer ${token}`
          }
        });
        
        setReportData(response.data);
        setCandidateName(response.data.candidate_name || 'Candidate');
        setJobRole(response.data.job_role || 'Not specified');
        setUseFallbackData(false);
      } catch (error) {
        console.error('Error fetching report data:', error);
        
        // Set error message
        setError(
          error.response?.data?.detail || 
          error.message || 
          'An error occurred while fetching the report data'
        );
        
        // Use mock data as fallback
        setUseFallbackData(true);
        setReportData(mockReportData);
        setCandidateName(mockReportData.candidate_name);
        setJobRole(mockReportData.job_role);
        
        toast({
          title: 'Using sample data',
          description: 'Could not load real report data. Showing sample visualization.',
          status: 'warning',
          duration: 5000,
          isClosable: true,
        });
      } finally {
        setIsLoading(false);
      }
    };

    fetchReportData();
  }, [sessionId, token, toast]);

  // Handle print functionality
  const handlePrint = useReactToPrint({
    content: () => reportRef.current,
    documentTitle: `Interview Report - ${candidateName} - ${jobRole}`,
    onBeforeGetContent: () => {
      return new Promise((resolve) => {
        toast({
          title: 'Preparing document...',
          status: 'info',
          duration: 2000,
        });
        resolve();
      });
    },
    onAfterPrint: () => {
      toast({
        title: 'Print successful!',
        status: 'success',
        duration: 2000,
      });
    },
  });

  // Handle download functionality
  const handleDownload = async () => {
    try {
      toast({
        title: 'Generating PDF...',
        status: 'info',
        duration: 2000,
      });
      
      // This would typically call an API endpoint to generate and download the PDF
      // For simplicity, we'll just use the print functionality for now
      handlePrint();
    } catch (error) {
      toast({
        title: 'Download failed',
        description: error.message || 'Failed to download report',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
    }
  };

  return (
    <Container maxW="container.xl" py={5}>
      {/* Breadcrumb navigation */}
      <Breadcrumb mb={4} fontSize="sm">
        <BreadcrumbItem>
          <BreadcrumbLink onClick={() => navigate('/')}>
            <FaHome /> Home
          </BreadcrumbLink>
        </BreadcrumbItem>
        <BreadcrumbItem>
          <BreadcrumbLink onClick={() => navigate('/history')}>
            Interview History
          </BreadcrumbLink>
        </BreadcrumbItem>
        <BreadcrumbItem isCurrentPage>
          <BreadcrumbLink>Report</BreadcrumbLink>
        </BreadcrumbItem>
      </Breadcrumb>
      
      {/* Back button */}
      <Button 
        leftIcon={<FaArrowLeft />} 
        mb={4} 
        onClick={() => navigate('/history')}
        size="sm"
      >
        Back to History
      </Button>
      
      {/* Title */}
      <Heading as="h1" size="xl" mb={6} textAlign="center">
        Detailed Interview Report
      </Heading>

      {/* Display fallback data notice if using mock data */}
      {useFallbackData && (
        <Alert status="warning" mb={6}>
          <AlertIcon />
          <Box>
            <AlertTitle>Using Sample Data</AlertTitle>
            <AlertDescription>
              The actual report data could not be loaded. Showing sample visualization.
            </AlertDescription>
          </Box>
        </Alert>
      )}
      
      {/* Report content */}
      {isLoading ? (
        <Flex justify="center" align="center" minH="300px">
          <Spinner size="xl" thickness="4px" color="blue.500" />
        </Flex>
      ) : reportData ? (
        <Box ref={reportRef}>
          <DetailedReport
            sessionId={sessionId}
            candidateName={candidateName}
            jobRole={jobRole}
            reportData={reportData}
            onPrint={handlePrint}
            onDownload={handleDownload}
          />
        </Box>
      ) : (
        <Alert 
          status="error" 
          variant="solid" 
          flexDirection="column" 
          alignItems="center" 
          justifyContent="center" 
          textAlign="center" 
          borderRadius="md"
          py={5}
        >
          <AlertIcon boxSize="40px" mr={0} />
          <AlertTitle mt={4} mb={1} fontSize="lg">
            Error Loading Report
          </AlertTitle>
          <AlertDescription maxWidth="sm">
            {error}
          </AlertDescription>
        </Alert>
      )}
    </Container>
  );
};

export default ReportPage; 