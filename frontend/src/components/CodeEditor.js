import React, { useRef, useEffect } from 'react';
import { Box } from '@chakra-ui/react';

// We're using a simple approach here with a textarea and syntax highlighting
// In a production app, you'd use a more robust solution like Monaco Editor or CodeMirror
const CodeEditor = ({ code, language, onChange }) => {
  const editorRef = useRef(null);
  
  // Update the height of the textarea to fit the content
  useEffect(() => {
    if (editorRef.current) {
      editorRef.current.style.height = 'auto';
      editorRef.current.style.height = `${editorRef.current.scrollHeight}px`;
    }
  }, [code]);
  
  const handleChange = (e) => {
    onChange(e.target.value);
  };
  
  return (
    <Box
      position="relative"
      height="400px"
      borderWidth="1px"
      borderRadius="md"
      overflow="hidden"
    >
      <textarea
        ref={editorRef}
        value={code}
        onChange={handleChange}
        style={{
          width: '100%',
          height: '100%',
          padding: '1rem',
          fontFamily: 'monospace',
          fontSize: '14px',
          lineHeight: '1.5',
          border: 'none',
          resize: 'none',
          outline: 'none',
          backgroundColor: '#f5f5f5',
        }}
        spellCheck="false"
        data-language={language}
      />
    </Box>
  );
};

export default CodeEditor; 