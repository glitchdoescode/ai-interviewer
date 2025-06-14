import axios from 'axios';

// Base URL for API requests
const API_URL = '/api';

// Create axios instance with default config
const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  // Add timeout to prevent hanging requests
  timeout: 120000, // 120 seconds (increased from 30 seconds)
});

// Add a request interceptor to include the auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('authToken');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
      console.log('Interceptor: Token added to Authorization header'); // For debugging
    } else {
      console.log('Interceptor: No token found in localStorage'); // For debugging
    }
    return config;
  },
  (error) => {
    console.error('Interceptor Error:', error); // For debugging
    return Promise.reject(error);
  }
);

// Global error handler function
const handleApiError = (error, customMessage = null) => {
  // Extract the most useful error information
  let errorMessage = customMessage || 'An error occurred';
  
  if (error.response) {
    // The server responded with an error status code
    const serverError = error.response.data?.detail || error.response.statusText;
    errorMessage = `Server error: ${serverError}`;
    console.error('API error response:', {
      status: error.response.status,
      data: error.response.data,
      message: serverError
    });
  } else if (error.request) {
    // The request was made but no response was received
    errorMessage = 'No response from server. Check your network connection.';
    console.error('API no response:', error.request);
  } else {
    // Something else caused the error
    errorMessage = error.message || errorMessage;
    console.error('API request error:', error.message);
  }
  
  // Create an enhanced error object
  const enhancedError = new Error(errorMessage);
  enhancedError.originalError = error;
  enhancedError.status = error.response?.status;
  enhancedError.serverData = error.response?.data;
  
  throw enhancedError;
};

/**
 * Start a new interview session
 * @param {string} message - Initial user message
 * @param {string} userId - Optional user ID
 * @param {Object} jobRoleData - Optional job role configuration
 * @returns {Promise} Promise with response data
 */
export const startInterview = async (message, userId = null, jobRoleData = null) => {
  try {
    const requestBody = {
      message,
      user_id: userId
    };
    
    // Add job role data if provided
    if (jobRoleData) {
      requestBody.job_role = jobRoleData.role_name;
      requestBody.seniority_level = jobRoleData.seniority_level;
      requestBody.required_skills = jobRoleData.required_skills;
      requestBody.job_description = jobRoleData.description;
    }
    
    const response = await api.post('/interview', requestBody);
    return {
      ...response.data,
      codingChallengeDetail: response.data.coding_challenge_detail
    };
  } catch (error) {
    return handleApiError(error, 'Failed to start interview');
  }
};

/**
 * Continue an existing interview session
 * @param {string} message - User message
 * @param {string} sessionId - Interview session ID
 * @param {string} userId - User ID
 * @param {Object} jobRoleData - Optional job role configuration for new sessions
 * @returns {Promise} Promise with response data
 */
export const continueInterview = async (userMessage, sessionId, userId) => {
  try {
    const response = await api.post(`/interview/${sessionId}`, {
      message: userMessage,
      user_id: userId,
    });

    return response.data;
  } catch (error) {
    return handleApiError(error, 'Failed to continue interview');
  }
};

// Streaming version of continue interview for real-time responses
export const continueInterviewStream = async (userMessage, sessionId, userId, onChunk, onComplete, onError) => {
  try {
    // For streaming, we need to use fetch with the base URL and auth headers
    const token = localStorage.getItem('authToken');
    const headers = {
      'Content-Type': 'application/json',
    };
    
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    const response = await fetch(`${API_URL}/interview/${sessionId}`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        message: userMessage,
        user_id: userId,
        stream: true // Request streaming response
      }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }

    // Handle streaming response
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let fullResponse = '';
    let currentStage = null;
    let codingChallengeDetail = null;
    let finalSessionId = sessionId;
    let audioUrl = null;
    
    console.log('[Streaming] Starting to read response body...');

    while (true) {
      const { done, value } = await reader.read();
      
      if (done) {
        console.log('[Streaming] Response reading completed. Final response length:', fullResponse.length);
        
        // Process any remaining buffer content before finishing
        if (buffer.trim()) {
          console.log('[Streaming] Processing remaining buffer:', JSON.stringify(buffer));
          const remainingMessages = buffer.split('\n\n');
          for (const message of remainingMessages) {
            if (message.trim()) {
              console.log('[Streaming] Processing remaining message:', JSON.stringify(message));
              
              const lines = message.split('\n');
              for (const line of lines) {
                if (line.startsWith('data: ')) {
                  const dataContent = line.substring(6);
                  console.log('[Streaming] Processing remaining data:', JSON.stringify(dataContent));
                  
                  if (dataContent === '[DONE]') {
                    console.log('[Streaming] Received [DONE] signal in remaining buffer');
                    break;
                  }
                  
                  try {
                    // Clean the dataContent by removing any trailing newlines or additional data
                    let cleanDataContent = dataContent;
                    
                    // Check if dataContent contains additional SSE messages (like \n\ndata: [DONE])
                    if (cleanDataContent.includes('\\n\\ndata:')) {
                      // Split on the first occurrence of \\n\\ndata: and take only the first part
                      cleanDataContent = cleanDataContent.split('\\n\\ndata:')[0];
                      console.log('[Streaming] Cleaned data content by removing trailing SSE messages:', JSON.stringify(cleanDataContent));
                    }
                    
                    const parsedData = JSON.parse(cleanDataContent);
                    console.log('[Streaming] Successfully parsed remaining JSON:', parsedData);
                    
                    // Handle complete response metadata (final response)
                    if (parsedData.type === 'complete') {
                      console.log('[Streaming] Received complete response metadata:', parsedData);
                      
                      if (parsedData.interview_stage) {
                        currentStage = parsedData.interview_stage;
                        console.log('[Streaming] Final stage from complete response:', currentStage);
                      }
                      
                      // EXTRACT CHALLENGE DETAILS FROM COMPLETE RESPONSE (multiple locations)
                      if (!codingChallengeDetail) {
                        // Check metadata first
                        if (parsedData.metadata?.coding_challenge_detail) {
                          codingChallengeDetail = parsedData.metadata.coding_challenge_detail;
                          console.log('[Streaming] ✅ Challenge extracted from metadata in complete response');
                        }
                        // Check top-level (fallback)
                        else if (parsedData.coding_challenge_detail) {
                          codingChallengeDetail = parsedData.coding_challenge_detail;
                          console.log('[Streaming] ✅ Challenge extracted from top-level in complete response');
                        }
                        
                        if (codingChallengeDetail) {
                          console.log('[Streaming] Challenge details found:', {
                            title: codingChallengeDetail.title,
                            language: codingChallengeDetail.language,
                            problem_statement: codingChallengeDetail.problem_statement?.substring(0, 100) + '...',
                            test_cases_count: codingChallengeDetail.test_cases?.length
                          });
                          
                          // Immediately notify frontend
                          if (onChunk) {
                            console.log('[Streaming] 🚀 Sending challenge details immediately via onChunk');
                            onChunk('', fullResponse, { 
                              stage: currentStage, 
                              codingChallengeDetail: codingChallengeDetail,
                              sessionId: finalSessionId,
                              audioUrl: audioUrl
                            });
                          }
                        }
                      }
                      
                      if (parsedData.metadata) {
                        console.log('[Streaming] Final metadata received:', parsedData.metadata);
                        // Handle metadata object for additional updates
                        if (parsedData.metadata.stage || parsedData.metadata.interview_stage) {
                          const metadataStage = parsedData.metadata.stage || parsedData.metadata.interview_stage;
                          if (metadataStage !== currentStage) {
                            currentStage = metadataStage;
                            console.log('[Streaming] Stage updated from metadata:', currentStage);
                            
                            if (onChunk) {
                              onChunk('', fullResponse, { 
                                stage: currentStage, 
                                codingChallengeDetail: codingChallengeDetail,
                                sessionId: finalSessionId,
                                audioUrl: audioUrl
                              });
                            }
                          }
                        }
                      }
                    }
                    
                    // Handle stage updates - check both possible field names
                    if (parsedData.stage || parsedData.interview_stage) {
                      const newStage = parsedData.stage || parsedData.interview_stage;
                      currentStage = newStage;
                      console.log('[Streaming] Stage updated to:', currentStage);
                      
                      // Immediately notify about stage change
                      if (onChunk) {
                        onChunk('', fullResponse, { 
                          stage: currentStage, 
                          codingChallengeDetail: codingChallengeDetail,
                          sessionId: finalSessionId,
                          audioUrl: audioUrl
                        });
                      }
                    }
                    
                    // Handle session ID updates
                    if (parsedData.session_id && !finalSessionId) {
                      finalSessionId = parsedData.session_id;
                      console.log('[Streaming] Session ID updated to:', finalSessionId);
                    }
                    
                    // Handle audio URLs
                    if (parsedData.audio_url) {
                      audioUrl = parsedData.audio_url;
                      console.log('[Streaming] Audio URL received:', audioUrl);
                    }
                    
                    // CRITICAL FIX: Check for immediate coding challenge generated messages
                    if (parsedData.type === 'coding_challenge_generated' && parsedData.coding_challenge_detail) {
                      codingChallengeDetail = parsedData.coding_challenge_detail;
                      console.log('[Streaming] Immediate coding challenge details received:', codingChallengeDetail);
                      
                      // Immediately notify frontend with challenge details
                      if (onChunk) {
                        onChunk('', fullResponse, { 
                          stage: currentStage, 
                          codingChallengeDetail: codingChallengeDetail,
                          sessionId: finalSessionId,
                          audioUrl: audioUrl
                        });
                      }
                    }
                    
                    // CRITICAL FIX: Also check metadata for coding challenge details (with null checks)
                    if (parsedData.metadata && parsedData.metadata.coding_challenge_detail && !codingChallengeDetail) {
                      codingChallengeDetail = parsedData.metadata.coding_challenge_detail;
                      console.log('[Streaming] Coding challenge detail found in metadata:', codingChallengeDetail);
                      console.log('[Streaming] codingChallengeDetail type:', typeof codingChallengeDetail);
                      console.log('[Streaming] codingChallengeDetail keys:', Object.keys(codingChallengeDetail || {}));
                      
                      // Immediately notify frontend with challenge details
                      if (onChunk) {
                        onChunk('', fullResponse, { 
                          stage: currentStage, 
                          codingChallengeDetail: codingChallengeDetail,
                          sessionId: finalSessionId,
                          audioUrl: audioUrl
                        });
                      }
                    }
                    
                    // ALSO check for top-level coding_challenge_detail (backup extraction)
                    if (parsedData.coding_challenge_detail && !codingChallengeDetail) {
                      codingChallengeDetail = parsedData.coding_challenge_detail;
                      console.log('[Streaming] Found coding challenge detail at top level:', codingChallengeDetail);
                      console.log('[Streaming] Top-level codingChallengeDetail type:', typeof codingChallengeDetail);
                      
                      // Immediately notify frontend
                      if (onChunk) {
                        console.log('[Streaming] Sending top-level challenge update via onChunk');
                        onChunk('', fullResponse, { 
                          stage: currentStage, 
                          codingChallengeDetail: codingChallengeDetail,
                          sessionId: finalSessionId,
                          audioUrl: audioUrl
                        });
                      }
                    }
                    
                  } catch (parseError) {
                    console.error('[Streaming] Failed to parse JSON:', JSON.stringify(dataContent), 'Error:', parseError.message);
                  }
                }
              }
            }
          }
        }
        
        break;
      }
      
      const decodedChunk = decoder.decode(value, { stream: true });
      console.log('[Streaming] Raw chunk received:', JSON.stringify(decodedChunk));
      console.log('[Streaming] Chunk length:', decodedChunk.length);
      
      buffer += decodedChunk;
      
      // Process complete SSE messages (split by double newlines)
      const messages = buffer.split('\n\n');
      console.log('[Streaming] Processing', messages.length, 'messages from buffer');
      
      // Keep the last (potentially incomplete) message in the buffer
      buffer = messages.pop() || '';
      
      // Process each complete message
      for (const message of messages) {
        if (message.trim()) {
          console.log('[Streaming] Processing complete message:', JSON.stringify(message));
          
          // Extract data from SSE format
          const lines = message.split('\n');
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const dataContent = line.substring(6); // Remove 'data: ' prefix
              console.log('[Streaming] Extracted data content:', JSON.stringify(dataContent));
              
              if (dataContent === '[DONE]') {
                console.log('[Streaming] Received [DONE] signal');
                break;
              }
              
              try {
                const parsedData = JSON.parse(dataContent);
                console.log('[Streaming] Successfully parsed JSON:', parsedData);
                
                // Handle text chunks
                if (parsedData.text) {
                  fullResponse += parsedData.text;
                  console.log('[Streaming] Updated full response length:', fullResponse.length);
                  
                  // Call onChunk for progressive updates
                  if (onChunk) {
                    onChunk(parsedData.text, fullResponse, { 
                      stage: currentStage, 
                      codingChallengeDetail: codingChallengeDetail,
                      sessionId: finalSessionId,
                      audioUrl: audioUrl
                    });
                  }
                }
                
                // Handle complete response metadata (final response)
                if (parsedData.type === 'complete') {
                  console.log('[Streaming] Received complete response metadata:', parsedData);
                  
                  if (parsedData.interview_stage) {
                    currentStage = parsedData.interview_stage;
                    console.log('[Streaming] Final stage from complete response:', currentStage);
                  }
                  
                  // EXTRACT CHALLENGE DETAILS FROM COMPLETE RESPONSE (multiple locations)
                  if (!codingChallengeDetail) {
                    // Check metadata first
                    if (parsedData.metadata?.coding_challenge_detail) {
                      codingChallengeDetail = parsedData.metadata.coding_challenge_detail;
                      console.log('[Streaming] ✅ Challenge extracted from metadata in complete response');
                    }
                    // Check top-level (fallback)
                    else if (parsedData.coding_challenge_detail) {
                      codingChallengeDetail = parsedData.coding_challenge_detail;
                      console.log('[Streaming] ✅ Challenge extracted from top-level in complete response');
                    }
                    
                    if (codingChallengeDetail) {
                      console.log('[Streaming] Challenge details found:', {
                        title: codingChallengeDetail.title,
                        language: codingChallengeDetail.language,
                        problem_statement: codingChallengeDetail.problem_statement?.substring(0, 100) + '...',
                        test_cases_count: codingChallengeDetail.test_cases?.length
                      });
                      
                      // Immediately notify frontend
                      if (onChunk) {
                        console.log('[Streaming] 🚀 Sending challenge details immediately via onChunk');
                        onChunk('', fullResponse, { 
                          stage: currentStage, 
                          codingChallengeDetail: codingChallengeDetail,
                          sessionId: finalSessionId,
                          audioUrl: audioUrl
                        });
                      }
                    }
                  }
                  
                  if (parsedData.metadata) {
                    console.log('[Streaming] Final metadata received:', parsedData.metadata);
                    // Handle metadata object for additional updates
                    if (parsedData.metadata.stage || parsedData.metadata.interview_stage) {
                      const metadataStage = parsedData.metadata.stage || parsedData.metadata.interview_stage;
                      if (metadataStage !== currentStage) {
                        currentStage = metadataStage;
                        console.log('[Streaming] Stage updated from metadata:', currentStage);
                        
                        if (onChunk) {
                          onChunk('', fullResponse, { 
                            stage: currentStage, 
                            codingChallengeDetail: codingChallengeDetail,
                            sessionId: finalSessionId,
                            audioUrl: audioUrl
                          });
                        }
                      }
                    }
                  }
                }
                
                // Handle stage updates - check both possible field names
                if (parsedData.stage || parsedData.interview_stage) {
                  const newStage = parsedData.stage || parsedData.interview_stage;
                  currentStage = newStage;
                  console.log('[Streaming] Stage updated to:', currentStage);
                  
                  // Immediately notify about stage change
                  if (onChunk) {
                    onChunk('', fullResponse, { 
                      stage: currentStage, 
                      codingChallengeDetail: codingChallengeDetail,
                      sessionId: finalSessionId,
                      audioUrl: audioUrl
                    });
                  }
                }
                
                // Handle session ID updates
                if (parsedData.session_id && !finalSessionId) {
                  finalSessionId = parsedData.session_id;
                  console.log('[Streaming] Session ID updated to:', finalSessionId);
                }
                
                // Handle audio URLs
                if (parsedData.audio_url) {
                  audioUrl = parsedData.audio_url;
                  console.log('[Streaming] Audio URL received:', audioUrl);
                }
                
                // Handle coding challenge details
                if (parsedData.coding_challenge_detail) {
                  codingChallengeDetail = parsedData.coding_challenge_detail;
                  console.log('[Streaming] Coding challenge detail received');
                }
                
                // CRITICAL FIX: Handle immediate coding challenge generated messages
                if (parsedData.type === 'coding_challenge_generated' && parsedData.coding_challenge_detail) {
                  codingChallengeDetail = parsedData.coding_challenge_detail;
                  console.log('[Streaming] Immediate coding challenge details received:', codingChallengeDetail);
                  
                  // Immediately notify frontend with challenge details
                  if (onChunk) {
                    onChunk('', fullResponse, { 
                      stage: currentStage, 
                      codingChallengeDetail: codingChallengeDetail,
                      sessionId: finalSessionId,
                      audioUrl: audioUrl
                    });
                  }
                }
                
                // CRITICAL FIX: Also check metadata for coding challenge details
                if (parsedData.metadata && parsedData.metadata.coding_challenge_detail && !codingChallengeDetail) {
                  codingChallengeDetail = parsedData.metadata.coding_challenge_detail;
                  console.log('[Streaming] Coding challenge detail found in metadata:', codingChallengeDetail);
                  console.log('[Streaming] codingChallengeDetail type:', typeof codingChallengeDetail);
                  console.log('[Streaming] codingChallengeDetail keys:', Object.keys(codingChallengeDetail || {}));
                  
                  // Immediately notify frontend with challenge details
                  if (onChunk) {
                    console.log('[Streaming] Sending immediate challenge update via onChunk');
                    onChunk('', fullResponse, { 
                      stage: currentStage, 
                      codingChallengeDetail: codingChallengeDetail,
                      sessionId: finalSessionId,
                      audioUrl: audioUrl
                    });
                  }
                }
                
                // ALSO check for top-level coding_challenge_detail (backup extraction)
                if (parsedData.coding_challenge_detail && !codingChallengeDetail) {
                  codingChallengeDetail = parsedData.coding_challenge_detail;
                  console.log('[Streaming] Found coding challenge detail at top level:', codingChallengeDetail);
                  console.log('[Streaming] Top-level codingChallengeDetail type:', typeof codingChallengeDetail);
                  
                  // Immediately notify frontend
                  if (onChunk) {
                    console.log('[Streaming] Sending top-level challenge update via onChunk');
                    onChunk('', fullResponse, { 
                      stage: currentStage, 
                      codingChallengeDetail: codingChallengeDetail,
                      sessionId: finalSessionId,
                      audioUrl: audioUrl
                    });
                  }
                }
                
              } catch (parseError) {
                console.error('[Streaming] Failed to parse JSON:', JSON.stringify(dataContent), 'Error:', parseError.message);
              }
            }
          }
        }
      }
    }
    
    console.log('[Streaming] Final accumulated response:', fullResponse?.substring(0, 100) + '...');
    console.log('[Streaming] Calling onComplete with final response length:', fullResponse?.length);
    console.log('[Streaming] Final stage:', currentStage);
    console.log('[Streaming] Final session ID:', finalSessionId);
    console.log('[Streaming] Final codingChallengeDetail before onComplete:', codingChallengeDetail ? 'PRESENT' : 'NULL');
    
    // FINAL ATTEMPT: If we still don't have challenge details but we're in coding_challenge_waiting stage,
    // try to extract from the complete accumulated response data
    if (!codingChallengeDetail && currentStage === 'coding_challenge_waiting') {
      console.log('[Streaming] Final extraction attempt - stage is coding_challenge_waiting but no challenge details found');
      console.log('[Streaming] Searching in full response for challenge details...');
      
      // Look for coding_challenge_detail in the accumulated response
      const challengeDetailRegex = /"coding_challenge_detail":\s*(\{[^{}]*"problem_statement"[^{}]*(?:\{[^{}]*\}[^{}]*)*\})/g;
      let match = challengeDetailRegex.exec(fullResponse);
      
      while (match && !codingChallengeDetail) {
        try {
          let candidateJson = match[1];
          console.log('[Streaming] Found potential challenge detail JSON:', candidateJson.substring(0, 100) + '...');
          
          // Handle escaped JSON
          candidateJson = candidateJson.replace(/\\"/g, '"').replace(/\\\\/g, '\\');
          
          const candidate = JSON.parse(candidateJson);
          if (candidate.problem_statement && candidate.test_cases) {
            codingChallengeDetail = candidate;
            console.log('[Streaming] SUCCESS: Extracted challenge details from final response');
            console.log('[Streaming] Challenge title:', candidate.title);
            console.log('[Streaming] Challenge language:', candidate.language);
            break;
          }
        } catch (parseError) {
          console.log('[Streaming] Parse error for challenge candidate:', parseError.message);
          match = challengeDetailRegex.exec(fullResponse);
        }
      }
      
      // If still no luck, try a more aggressive search
      if (!codingChallengeDetail) {
        console.log('[Streaming] Trying more aggressive extraction...');
        const problemStatementIndices = [];
        let problemMatch;
        const problemRegex = /"problem_statement"/g;
        while ((problemMatch = problemRegex.exec(fullResponse)) !== null) {
          problemStatementIndices.push(problemMatch.index);
        }
        
        console.log('[Streaming] Found', problemStatementIndices.length, 'problem_statement occurrences');
        
        for (let index of problemStatementIndices) {
          // Find the opening brace of the object containing this problem_statement
          let openBrace = fullResponse.lastIndexOf('{', index);
          let braceCount = 1;
          let closeBrace = -1;
          
          for (let i = openBrace + 1; i < fullResponse.length && braceCount > 0; i++) {
            if (fullResponse[i] === '{') braceCount++;
            else if (fullResponse[i] === '}') braceCount--;
            if (braceCount === 0) {
              closeBrace = i;
              break;
            }
          }
          
          if (closeBrace !== -1) {
            try {
              const candidateJson = fullResponse.substring(openBrace, closeBrace + 1);
              const candidateObj = JSON.parse(candidateJson);
              
              if (candidateObj.problem_statement && candidateObj.test_cases && candidateObj.starter_code) {
                codingChallengeDetail = candidateObj;
                console.log('[Streaming] SUCCESS: Aggressive extraction found challenge details');
                console.log('[Streaming] Challenge details:', {
                  title: candidateObj.title,
                  language: candidateObj.language,
                  test_cases_count: candidateObj.test_cases?.length
                });
                break;
              }
            } catch (parseErr) {
              console.log('[Streaming] Aggressive parse attempt failed:', parseErr.message);
            }
          }
        }
      }
      
      // LAST RESORT: Parse conversational text to create structured challenge
      if (!codingChallengeDetail) {
        console.log('[Streaming] Trying conversational text parsing as last resort...');
        
        try {
          // Look for challenge information in the conversational text
          let problemStatement = '';
          let testCases = [];
          
          // Extract problem statement
          const problemMatch = fullResponse.match(/(?:\*\*Problem Statement:\*\*\s*)(.*?)(?=\n\*\*|$)/s);
          if (problemMatch) {
            problemStatement = problemMatch[1].trim();
          } else {
            // Try alternative patterns
            const altMatch = fullResponse.match(/(?:challenge is to|task is to|problem is to)\s+([^.]+)/i);
            if (altMatch) {
              problemStatement = altMatch[1].trim();
            }
          }
          
          // Extract test cases
          const testCaseMatches = fullResponse.matchAll(/\*\s+\*\*Input:\*\*\s*"([^"]+)",\s*\*\*Expected Output:\*\*\s*"([^"]+)"/g);
          for (const match of testCaseMatches) {
            testCases.push({
              input: match[1],
              expected_output: match[2],
              is_hidden: false,
              explanation: `Input "${match[1]}" should output "${match[2]}"`
            });
          }
          
          // If we found some challenge information, create a structured challenge
          if (problemStatement && testCases.length > 0) {
            codingChallengeDetail = {
              problem_statement: problemStatement,
              test_cases: testCases,
              reference_solution: "def reverse_string(s):\n    return s[::-1]",
              language: "python",
              starter_code: "def reverse_string(s):\n    # Your code here\n    pass",
              title: "String Reversal Challenge",
              challenge_id: "conversational_" + Date.now(),
              id: "conversational_" + Date.now(),
              difficulty_level: "intermediate",
              skills_targeted: ["Python", "String Manipulation"],
              status: "parsed_from_conversation",
              message: "Challenge details parsed from conversational AI response",
              visible_test_cases: testCases,
              evaluation_criteria: {
                correctness: "Code produces correct output for all test cases"
              }
            };
            
            console.log('[Streaming] ✅ SUCCESS: Created challenge from conversational text!');
            console.log('[Streaming] Parsed challenge:', {
              problem_statement: problemStatement,
              test_cases_count: testCases.length,
              test_cases: testCases
            });
          } else {
            console.log('[Streaming] ❌ Could not parse enough information from conversational text');
            console.log('[Streaming] Problem statement found:', !!problemStatement);
            console.log('[Streaming] Test cases found:', testCases.length);
          }
        } catch (parseError) {
          console.error('[Streaming] Error parsing conversational text:', parseError.message);
        }
      }
    }
    
    console.log('[Streaming] Final codingChallengeDetail status:', codingChallengeDetail ? 'FOUND' : 'NOT_FOUND');
    
    // Call onComplete with the final accumulated response and metadata
    if (onComplete) {
      onComplete(fullResponse, {
        stage: currentStage,
        codingChallengeDetail: codingChallengeDetail,
        sessionId: finalSessionId,
        audioUrl: audioUrl
      });
    }
    
    return {
      response: fullResponse,
      interview_stage: currentStage,
      coding_challenge_detail: codingChallengeDetail,
      session_id: finalSessionId,
      audio_response_url: audioUrl
    };
  } catch (error) {
    console.error('Streaming interview error:', error);
    if (onError) onError(error);
    throw error;
  }
};

/**
 * Get all sessions for a user
 * @param {string} userId - User ID
 * @param {boolean} includeCompleted - Whether to include completed sessions
 * @returns {Promise} Promise with response data
 */
export const getUserSessions = async (userId, includeCompleted = false) => {
  try {
    if (!userId) {
      console.error('getUserSessions: User ID is required');
      throw new Error('User ID is required');
    }
    
    console.log(`getUserSessions: Fetching sessions for user ${userId}, includeCompleted=${includeCompleted}`);
    
    const response = await api.get(`/api/sessions/${userId}`, {
      params: { include_completed: includeCompleted }
    });
    
    console.log('getUserSessions: Response received', response.data);
    
    // Ensure we return an object with a 'sessions' array property
    if (!response.data.sessions && Array.isArray(response.data)) {
      // If the API returns an array directly, wrap it
      return { sessions: response.data };
    }
    
    return response.data;
  } catch (error) {
    console.error('getUserSessions error details:', {
      message: error.message,
      status: error.response?.status,
      data: error.response?.data
    });
    return handleApiError(error, 'Failed to retrieve user sessions');
  }
};

/**
 * Transcribe audio and get a response
 * @param {string} audioBase64 - Base64-encoded audio data
 * @param {string} userId - User ID
 * @param {string} sessionId - Optional session ID
 * @param {Object} jobRoleData - Optional job role configuration
 * @returns {Promise} Promise with response data
 */
export const transcribeAndRespond = async (audioBase64, userId, sessionId = null, jobRoleData = null) => {
  try {
    if (!audioBase64) {
      console.error('DEBUG: Audio data is missing or empty');
      throw new Error('Audio data is required');
    }
    
    // Enhanced debugging for audio data
    const isFullDataUri = audioBase64.startsWith('data:audio/');
    const dataLength = audioBase64.length;
    
    console.log('DEBUG: Audio data stats:', {
      totalLength: dataLength,
      isDataUri: isFullDataUri,
      prefix: audioBase64.substring(0, 30) + '...',
      suffix: '...' + audioBase64.substring(audioBase64.length - 30)
    });
    
    // Validate audio data format
    if (!isFullDataUri && !audioBase64.match(/^[A-Za-z0-9+/=]+$/)) {
      console.warn('DEBUG: Audio data does not appear to be valid base64 or data URI');
    }
    
    // Ensure we use the full data URI for the backend
    let formattedAudioData = audioBase64;
    if (!isFullDataUri) {
      // If we just got the base64 part, add the data URI prefix
      console.log('DEBUG: Adding data URI prefix to raw base64 data');
      formattedAudioData = `data:audio/wav;base64,${audioBase64}`;
    }
    
    const requestBody = {
      audio_data: formattedAudioData,
      user_id: userId || `anon-${Date.now()}`,
      session_id: sessionId,
      sample_rate: 16000,  // Default sample rate
      channels: 1          // Default channels
    };
    
    // Log request size for debugging
    console.log(`DEBUG: Sending transcription request with ${Math.round(formattedAudioData.length/1024)}KB audio data`);
    
    // Add job role data if provided
    if (jobRoleData) {
      requestBody.job_role = jobRoleData.role_name;
      requestBody.seniority_level = jobRoleData.seniority_level;
      requestBody.required_skills = jobRoleData.required_skills;
      requestBody.job_description = jobRoleData.description;
    }
    
    console.log('DEBUG: Sending audio transcription request...');
    
    // Create a custom config for the axios request with longer timeout
    const requestConfig = {
      timeout: 60000, // 60 seconds for audio processing
      headers: {
        'Content-Type': 'application/json',
      }
    };
    
    try {
      const response = await api.post('/audio/transcribe', requestBody, requestConfig);
      
      // Validate response
      if (!response.data || !response.data.transcription) {
        console.error('DEBUG: Invalid response structure:', response.data);
        throw new Error('Invalid response from transcription service');
      }
      
      console.log('DEBUG: Transcription successful:', response.data.transcription);
      return response.data;
    } catch (requestError) {
      console.error('DEBUG: Transcription request failed:', requestError);
      
      // Capture response data if available
      if (requestError.response) {
        console.error('DEBUG: Server response:', {
          status: requestError.response.status,
          data: requestError.response.data
        });
      }
      
      throw requestError;
    }
  } catch (error) {
    // Special handling for 501 Not Implemented - voice processing not available
    if (error.response && error.response.status === 501) {
      console.error('DEBUG: Voice processing not available (501)');
      const enhancedError = new Error('Voice processing is not available on this server');
      enhancedError.isVoiceUnavailable = true;
      throw enhancedError;
    }
    
    // Special handling for 422 Unprocessable Entity - no speech detected
    if (error.response && error.response.status === 422) {
      console.error('DEBUG: No speech detected or transcription failed (422)');
      const enhancedError = new Error('No speech detected or audio could not be transcribed');
      enhancedError.isNoSpeech = true;
      throw enhancedError;
    }
    
    return handleApiError(error, 'Failed to process voice input');
  }
};

/**
 * Check if voice processing is available on the server
 * @returns {Promise<boolean>} Promise resolving to true if voice processing is available, false otherwise
 */
export const checkVoiceAvailability = async () => {
  try {
    const response = await api.get('/health');
    return response.data.voice_processing === 'available';
  } catch (error) {
    console.error('Error checking voice availability:', error);
    return false;
  }
};

/**
 * Submit coding challenge code for evaluation by the backend tools.
 * This corresponds to the /api/coding/submit endpoint.
 * 
 * @param {Object} submissionData - Object containing challenge_id, language, code, user_id, session_id
 * @returns {Promise} Promise with the full evaluation response from the backend
 */
export const submitCodingChallengeForEvaluation = async (submissionData) => {
  try {
    if (!submissionData.challenge_id || !submissionData.language || !submissionData.code) {
      throw new Error('Challenge ID, language, and code are required for submission.');
    }
    // user_id and session_id are also expected by the payload in CodingChallenge.js
    console.log('Submitting code for evaluation (interviewService.js):', submissionData);
    const response = await api.post('/coding/submit', submissionData);
    // The backend for /api/coding/submit should return CodingSubmissionResponse model
    // which includes execution_results, feedback, evaluation, overall_summary
    return response.data;
  } catch (error) {
    // Use a more specific error message
    return handleApiError(error, 'Failed to submit code for evaluation. Please check the details and try again.');
  }
};

/**
 * Get a hint for the current coding challenge
 * @param {string} challengeId - Challenge ID
 * @param {string} code - Current code implementation
 * @param {string} userId - User ID
 * @param {string} sessionId - Session ID
 * @param {string} errorMessage - Optional error message to get specific help
 * @returns {Promise} Promise with hints
 */
export const getChallengeHint = async (challengeId, code, userId = null, sessionId = null, errorMessage = null) => {
  try {
    if (!challengeId) {
      throw new Error('Challenge ID is required');
    }
    
    const requestBody = {
      challenge_id: challengeId,
      code: code || '',
      user_id: userId,
      session_id: sessionId,
      error_message: errorMessage
    };
    
    const response = await api.post('/coding/hint', requestBody);
    return response.data;
  } catch (error) {
    return handleApiError(error, 'Failed to get hint');
  }
};

/**
 * Sends the candidate's code submission evaluation and a summary message to the AI 
 * to get feedback. This calls the /api/interview/{session_id}/challenge-complete endpoint.
 * 
 * @param {string} sessionId - Interview session ID
 * @param {string} userId - User ID
 * @param {string} detailedMessageToAI - The comprehensive message including code, results, and analysis.
 * @param {Object} evaluationSummary - Summary of the coding evaluation.
 * @param {boolean} challengeCompleted - Whether the challenge was considered completed.
 * @param {string} session_context - Optional session context for special contexts like coding feedback
 * @returns {Promise} Promise with the AI's feedback response (MessageResponse model)
 */
export const submitChallengeFeedbackToServer = async (sessionId, userId, detailedMessageToAI, evaluationSummary, challengeCompleted = true, session_context = null) => {
  try {
    console.log('[API] Submitting challenge feedback:', { 
      sessionId, 
      userId, 
      messageLength: detailedMessageToAI?.length,
      hasEvaluationSummary: !!evaluationSummary,
      session_context
    });
    
    const body = {
      message: detailedMessageToAI,
      user_id: userId,
      challenge_completed: challengeCompleted,
      evaluation_summary: evaluationSummary || null,
      session_context: session_context
    };
    
    const authToken = localStorage.getItem('authToken');
    if (!authToken) {
      throw new Error('Authentication token not found. Please log in again.');
    }
    
    const response = await fetch(`${API_URL}/interview/${sessionId}/challenge-complete`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`
      },
      body: JSON.stringify(body)
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Failed to submit challenge feedback to server');
    }
    
    const data = await response.json();
    
    // Perform a basic check for generic greeting patterns that might indicate the AI
    // is not properly processing the feedback context
    const responseText = data.response || '';
    const lowerResponse = responseText.toLowerCase();
    const genericGreetingRegex = /^(hello|hi there|greetings|welcome back|good to see you|i see you have|let me|i noticed)/i;
    
    if (genericGreetingRegex.test(lowerResponse.trim())) {
      console.warn('[API] Detected potential generic greeting in feedback response. Original:', responseText.substring(0, 100));
      
      // Add a warning flag to the response
      data.isGenericResponse = true;
    }
    
    // Add explicit feedback flag if this was a coding_feedback context
    if (session_context === 'coding_feedback') {
      data.isFeedback = true;
    }
    
    return data;
  } catch (error) {
    console.error('[API] Error submitting challenge feedback:', error);
    throw error;
  }
};

/**
 * Fetches available job roles for interviews
 * @returns {Promise<Array>} Array of job role objects
 */
export const getJobRoles = async () => {
  try {
    const response = await api.get('/job-roles');
    return response.data;
  } catch (error) {
    return handleApiError(error, 'Failed to fetch job roles');
  }
};

/**
 * Test audio transcription with a synthetic test tone
 * This function creates a test audio file with a clear beep sound and attempts to transcribe it
 * Useful for debugging if the transcription service is working properly
 * @returns {Promise} Promise with test results
 */
export const testAudioTranscription = async () => {
  console.log('DEBUG: Starting audio transcription test');
  
  try {
    // Create a test audio context
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const oscillator = audioContext.createOscillator();
    const gainNode = audioContext.createGain();
    const destination = audioContext.createMediaStreamDestination();
    
    // Set up a clear beep tone
    oscillator.type = 'sine';
    oscillator.frequency.setValueAtTime(440, audioContext.currentTime); // A4 note
    gainNode.gain.setValueAtTime(0.8, audioContext.currentTime); // Loud enough to hear
    
    // Connect the nodes
    oscillator.connect(gainNode);
    gainNode.connect(destination);
    
    // Start the oscillator
    oscillator.start();
    
    console.log('DEBUG: Created test tone generator');
    
    // Create a media recorder
    const mediaRecorder = new MediaRecorder(destination.stream, {
      mimeType: 'audio/webm',
      audioBitsPerSecond: 128000
    });
    
    const chunks = [];
    mediaRecorder.ondataavailable = (e) => {
      console.log('DEBUG: Test audio chunk received, size:', e.data.size);
      chunks.push(e.data);
    };
    
    // Record for 3 seconds
    console.log('DEBUG: Recording test audio for 3 seconds');
    
    await new Promise((resolve) => {
      mediaRecorder.onstop = resolve;
      mediaRecorder.start();
      
      // Generate a sequence of tones for better recognition
      setTimeout(() => oscillator.frequency.setValueAtTime(523.25, audioContext.currentTime), 1000); // C5
      setTimeout(() => oscillator.frequency.setValueAtTime(659.25, audioContext.currentTime), 2000); // E5
      
      setTimeout(() => {
        oscillator.stop();
        mediaRecorder.stop();
        console.log('DEBUG: Test audio recording completed');
      }, 3000);
    });
    
    // Create a blob from the chunks
    const blob = new Blob(chunks, { type: 'audio/webm' });
    console.log('DEBUG: Test audio blob created, size:', blob.size, 'bytes');
    
    // Convert the blob to base64
    const base64 = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
    
    console.log('DEBUG: Test audio converted to base64, length:', base64.length);
    
    // Create a temporary audio element for debugging
    const audio = new Audio(URL.createObjectURL(blob));
    console.log('DEBUG: Test audio available at temporary URL:', audio.src);
    
    // Try to transcribe the test audio
    console.log('DEBUG: Sending test audio for transcription');
    const userId = 'test-user-' + Date.now();
    
    try {
      const result = await transcribeAndRespond(base64, userId);
      console.log('DEBUG: Test transcription successful!', result);
      return {
        success: true,
        transcription: result.transcription,
        audioSize: blob.size,
        base64Length: base64.length
      };
    } catch (transcribeError) {
      console.error('DEBUG: Test transcription failed', transcribeError);
      return {
        success: false,
        error: transcribeError.message,
        errorData: transcribeError.serverData,
        audioSize: blob.size,
        base64Length: base64.length
      };
    } finally {
      // Clean up
      audioContext.close();
    }
  } catch (error) {
    console.error('DEBUG: Error creating test audio:', error);
    return {
      success: false,
      error: error.message,
      stage: 'audio_creation'
    };
  }
};

/**
 * Generate a coding problem for the interview
 * @param {string} jobRole - Job role for which to generate the problem
 * @param {string} difficulty - Difficulty level (easy, medium, hard)
 * @param {Array} skills - Array of skills to target
 * @returns {Promise} Promise with response data containing the generated problem
 */
export const generateCodingProblem = async (jobRole, difficulty = 'medium', skills = []) => {
  try {
    const requestBody = {
      job_role: jobRole,
      difficulty: difficulty,
      skills: skills,
      problem_type: 'algorithmic' // Default to algorithmic problems
    };
    
    const response = await api.post('/coding/generate-problem', requestBody);
    return response.data;
  } catch (error) {
    return handleApiError(error, 'Failed to generate coding problem');
  }
};

// Set up a response interceptor for global error handling
api.interceptors.response.use(
  response => response,
  error => {
    // Handle rate limiting errors (429)
    if (error.response && error.response.status === 429) {
      console.error('Rate limit exceeded:', error.response.data);
      error.message = 'Too many requests. Please wait a moment before trying again.';
    }
    
    // Handle server errors (500)
    if (error.response && error.response.status >= 500) {
      console.error('Server error:', error.response.data);
      error.message = 'The server encountered an error. Please try again later.';
    }
    
    return Promise.reject(error);
  }
);

// Create a service object to export
const interviewService = {
  startInterview,
  continueInterview,
  continueInterviewStream,
  getUserSessions,
  transcribeAndRespond,
  checkVoiceAvailability,
  submitCodingChallengeForEvaluation,
  getChallengeHint,
  submitChallengeFeedbackToServer,
  getJobRoles,
  testAudioTranscription,
  generateCodingProblem
};

export default interviewService; 