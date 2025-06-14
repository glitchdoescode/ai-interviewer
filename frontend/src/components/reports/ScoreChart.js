import React from 'react';
import {
  Box,
  Heading,
  Text,
  useColorModeValue,
  Flex,
  Tooltip,
} from '@chakra-ui/react';
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Legend,
  LabelList,
} from 'recharts';

// Constants for chart configuration
const MAX_SCORE = 5;
const CHART_COLORS = {
  qa: '#3B82F6', // primary.500
  coding: '#10B981', // success.500
  overall: '#F59E0B', // warning.500
};

/**
 * ScoreChart component for displaying interview evaluation scores
 * Supports both radar chart and bar chart visualizations
 */
const ScoreChart = ({
  data,
  type = 'radar',
  height = 300,
  title = 'Evaluation Scores',
  showLegend = true,
}) => {
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const textColor = useColorModeValue('gray.800', 'gray.100');

  // Format data for charts if needed
  const formattedData = React.useMemo(() => {
    if (!data) return [];

    // If data is already in the right format, return it
    if (Array.isArray(data) && data.length > 0) {
      return data;
    }

    // Otherwise, transform the data
    if (data.qa_average !== undefined || data.coding_average !== undefined) {
      return [
        { name: 'Q&A', value: data.qa_average || 0, fill: CHART_COLORS.qa },
        { name: 'Coding', value: data.coding_average || 0, fill: CHART_COLORS.coding },
        { name: 'Overall', value: data.overall_average || 0, fill: CHART_COLORS.overall },
      ];
    }

    return [];
  }, [data]);

  // Render appropriate chart based on type
  const renderChart = () => {
    if (formattedData.length === 0) {
      return <Text color="gray.500">No data available</Text>;
    }

    if (type === 'radar') {
      return (
        <ResponsiveContainer width="100%" height={height}>
          <RadarChart outerRadius={90} data={formattedData}>
            <PolarGrid />
            <PolarAngleAxis dataKey="name" tick={{ fill: textColor }} />
            <PolarRadiusAxis angle={30} domain={[0, MAX_SCORE]} />
            <Radar
              name="Score"
              dataKey="value"
              stroke={CHART_COLORS.qa}
              fill={CHART_COLORS.qa}
              fillOpacity={0.6}
            />
            {showLegend && <Legend />}
          </RadarChart>
        </ResponsiveContainer>
      );
    }

    if (type === 'bar') {
      return (
        <ResponsiveContainer width="100%" height={height}>
          <BarChart
            data={formattedData}
            margin={{
              top: 5,
              right: 30,
              left: 20,
              bottom: 5,
            }}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" tick={{ fill: textColor }} />
            <YAxis domain={[0, MAX_SCORE]} tick={{ fill: textColor }} />
            <Tooltip />
            <Bar dataKey="value" fill={CHART_COLORS.qa}>
              <LabelList dataKey="value" position="top" fill={textColor} />
            </Bar>
            {showLegend && <Legend />}
          </BarChart>
        </ResponsiveContainer>
      );
    }

    return null;
  };

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
      {title && (
        <Heading size="md" mb={4} textAlign="center" color={textColor}>
          {title}
        </Heading>
      )}
      <Flex justify="center" align="center" width="100%">
        {renderChart()}
      </Flex>
    </Box>
  );
};

export default ScoreChart; 