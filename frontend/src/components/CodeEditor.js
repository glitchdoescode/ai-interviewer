import React, { useEffect } from 'react';
import CodeMirror from '@uiw/react-codemirror';
import { python } from '@codemirror/lang-python';
import { javascript } from '@codemirror/lang-javascript';
import { java } from '@codemirror/lang-java';
import { Box } from '@chakra-ui/react';

// Import a dark theme
import { materialDark } from '@uiw/codemirror-theme-material';

// You can explore themes here: https://uiwjs.github.io/react-codemirror/#/theme/home
// For example, to use a dark theme like aiu:
// import { aiu } from '@uiw/codemirror-theme-aiu'; 
// Or for a material dark theme:
// import { materialDark } from '@uiw/codemirror-theme-material';

const CodeEditor = ({ code, language, onChange, theme = 'light', height = '400px', readOnly = false }) => {
  // Log on every render, to see what props it gets
  console.log(`CodeEditor.js: Component rendered. 'code' prop is: "${code}", Language: "${language}", ReadOnly: ${readOnly}`);

  // Log when the 'code' prop specifically changes
  useEffect(() => {
    console.log(`CodeEditor.js: (useEffect) 'code' prop received/changed to: "${code}"`);
  }, [code]);

  const getLanguageExtension = (lang) => {
    const langLower = lang?.toLowerCase();
    if (langLower === 'python' || langLower === 'py') return [python()];
    if (langLower === 'javascript' || langLower === 'js') return [javascript({ jsx: true, typescript: false })];
    if (langLower === 'java') return [java()];
    // Add more languages here as needed
    // e.g., if (langLower === 'html') return [html()];
    // e.g., if (langLower === 'css') return [css()];
    return []; // Default to no specific language extension if not mapped
  };

  const extensions = getLanguageExtension(language);

  return (
    <Box borderWidth="1px" borderRadius="md" overflow="hidden">
      <CodeMirror
        value={code || ''} // Ensure value is never null/undefined for CodeMirror
        height={height}
        extensions={extensions}
        onChange={onChange}
        theme={theme === 'materialDark' ? materialDark : theme} // Apply imported theme
        readOnly={readOnly}
      />
    </Box>
  );
};

export default CodeEditor;