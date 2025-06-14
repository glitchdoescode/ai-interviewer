import React from 'react';
import {
  Box,
  Heading,
  Text,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Badge,
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
  useColorModeValue,
  Flex,
  Divider,
} from '@chakra-ui/react';

/**
 * Helper function to render score badges with appropriate colors
 */
const ScoreBadge = ({ score }) => {
  // Return N/A badge if score is undefined or null
  if (score === undefined || score === null) {
    return (
      <Badge colorScheme="gray" fontSize="md" px={2} py={1} borderRadius="md">
        N/A
      </Badge>
    );
  }
  
  let colorScheme = 'red';
  if (score >= 4.5) colorScheme = 'green';
  else if (score >= 3.5) colorScheme = 'blue';
  else if (score >= 2.5) colorScheme = 'yellow';
  
  return (
    <Badge colorScheme={colorScheme} fontSize="md" px={2} py={1} borderRadius="md">
      {score.toFixed(1)}
    </Badge>
  );
};

/**
 * DetailedEvaluationTable component for displaying structured interview evaluation data
 * Shows Q&A evaluations and coding challenge evaluations in an accordion format
 */
const DetailedEvaluationTable = ({
  evaluation,
  title = 'Detailed Evaluation',
}) => {
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const headerBgColor = useColorModeValue('gray.50', 'gray.700');
  const textColor = useColorModeValue('gray.800', 'gray.100');
  const secondaryTextColor = useColorModeValue('gray.600', 'gray.400');
  const hoverBgColor = useColorModeValue('gray.100', 'gray.600');
  
  // Extract data from evaluation
  const { qa_evaluations = [], coding_evaluation = null, overall_notes = '' } = evaluation || {};
  
  if (!evaluation || (qa_evaluations.length === 0 && !coding_evaluation)) {
    return (
      <Box
        bg={bgColor}
        borderRadius="lg"
        borderWidth="1px"
        borderColor={borderColor}
        p={4}
        boxShadow="sm"
        width="100%"
      >
        <Heading size="md" mb={4} textAlign="center" color={textColor}>
          {title}
        </Heading>
        <Text color={secondaryTextColor} textAlign="center">
          No evaluation data available
        </Text>
      </Box>
    );
  }
  
  return (
    <Box
      bg={bgColor}
      borderRadius="lg"
      borderWidth="1px"
      borderColor={borderColor}
      p={4}
      boxShadow="sm"
      width="100%"
    >
      <Heading size="md" mb={4} textAlign="center" color={textColor}>
        {title}
      </Heading>
      
      <Accordion allowMultiple defaultIndex={[0]}>
        {/* Q&A Evaluations */}
        {qa_evaluations.length > 0 && (
          <AccordionItem border="none" mb={4}>
            <AccordionButton
              bg={headerBgColor}
              borderRadius="md"
              _hover={{ bg: hoverBgColor }}
            >
              <Box flex="1" textAlign="left" fontWeight="semibold">
                Q&A Evaluations ({qa_evaluations.length})
              </Box>
              <AccordionIcon />
            </AccordionButton>
            <AccordionPanel pb={4}>
              {qa_evaluations.map((qaItem, qaIndex) => {
                // Extract question and criteria
                const question = Object.keys(qaItem)[0];
                const criteria = qaItem[question];
                
                return (
                  <Box key={`qa-${qaIndex}`} mb={qaIndex < qa_evaluations.length - 1 ? 6 : 0}>
                    <Heading size="sm" mb={2} color={textColor}>
                      Question {qaIndex + 1}: {question}
                    </Heading>
                    
                    <Table variant="simple" size="sm">
                      <Thead>
                        <Tr>
                          <Th>Criterion</Th>
                          <Th isNumeric>Score</Th>
                          <Th>Justification</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        <Tr>
                          <Td fontWeight="medium">Clarity</Td>
                          <Td isNumeric><ScoreBadge score={criteria.clarity.score} /></Td>
                          <Td>{criteria.clarity.justification}</Td>
                        </Tr>
                        <Tr>
                          <Td fontWeight="medium">Technical Accuracy</Td>
                          <Td isNumeric><ScoreBadge score={criteria.technical_accuracy.score} /></Td>
                          <Td>{criteria.technical_accuracy.justification}</Td>
                        </Tr>
                        <Tr>
                          <Td fontWeight="medium">Depth of Understanding</Td>
                          <Td isNumeric><ScoreBadge score={criteria.depth_of_understanding.score} /></Td>
                          <Td>{criteria.depth_of_understanding.justification}</Td>
                        </Tr>
                        <Tr>
                          <Td fontWeight="medium">Communication</Td>
                          <Td isNumeric><ScoreBadge score={criteria.communication.score} /></Td>
                          <Td>{criteria.communication.justification}</Td>
                        </Tr>
                      </Tbody>
                    </Table>
                  </Box>
                );
              })}
            </AccordionPanel>
          </AccordionItem>
        )}
        
        {/* Coding Evaluation */}
        {coding_evaluation && (
          <AccordionItem border="none" mb={4}>
            <AccordionButton
              bg={headerBgColor}
              borderRadius="md"
              _hover={{ bg: hoverBgColor }}
            >
              <Box flex="1" textAlign="left" fontWeight="semibold">
                Coding Challenge Evaluation
              </Box>
              <AccordionIcon />
            </AccordionButton>
            <AccordionPanel pb={4}>
              <Table variant="simple" size="sm">
                <Thead>
                  <Tr>
                    <Th>Criterion</Th>
                    <Th isNumeric>Score</Th>
                    <Th>Justification</Th>
                  </Tr>
                </Thead>
                <Tbody>
                  <Tr>
                    <Td fontWeight="medium">Correctness</Td>
                    <Td isNumeric><ScoreBadge score={coding_evaluation.correctness.score} /></Td>
                    <Td>{coding_evaluation.correctness.justification}</Td>
                  </Tr>
                  <Tr>
                    <Td fontWeight="medium">Code Quality</Td>
                    <Td isNumeric><ScoreBadge score={coding_evaluation.code_quality.score} /></Td>
                    <Td>{coding_evaluation.code_quality.justification}</Td>
                  </Tr>
                  <Tr>
                    <Td fontWeight="medium">Efficiency</Td>
                    <Td isNumeric><ScoreBadge score={coding_evaluation.efficiency.score} /></Td>
                    <Td>{coding_evaluation.efficiency.justification}</Td>
                  </Tr>
                  <Tr>
                    <Td fontWeight="medium">Problem Solving</Td>
                    <Td isNumeric><ScoreBadge score={coding_evaluation.problem_solving.score} /></Td>
                    <Td>{coding_evaluation.problem_solving.justification}</Td>
                  </Tr>
                </Tbody>
              </Table>
            </AccordionPanel>
          </AccordionItem>
        )}
        
        {/* Overall Notes */}
        {overall_notes && (
          <AccordionItem border="none">
            <AccordionButton
              bg={headerBgColor}
              borderRadius="md"
              _hover={{ bg: hoverBgColor }}
            >
              <Box flex="1" textAlign="left" fontWeight="semibold">
                Overall Notes
              </Box>
              <AccordionIcon />
            </AccordionButton>
            <AccordionPanel pb={4}>
              <Text color={textColor} whiteSpace="pre-wrap">
                {overall_notes}
              </Text>
            </AccordionPanel>
          </AccordionItem>
        )}
      </Accordion>
    </Box>
  );
};

export default DetailedEvaluationTable; 