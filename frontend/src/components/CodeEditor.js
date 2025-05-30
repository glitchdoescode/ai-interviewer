import React from 'react';
import CodeMirror from '@uiw/react-codemirror';
import { python } from '@codemirror/lang-python';
import { javascript } from '@codemirror/lang-javascript';
import { java } from '@codemirror/lang-java';
import { Box } from '@chakra-ui/react';

// You can explore themes here: https://uiwjs.github.io/react-codemirror/#/theme/home
// For example, to use a dark theme like aiu:
// import { aiu } from '@uiw/codemirror-theme-aiu'; 
// Or for a material dark theme:
// import { materialDark } from '@uiw/codemirror-theme-material';

const CodeEditor = ({ code, language, onChange, theme = 'light' /* or your preferred theme e.g., aiu */ }) => {
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
        value={code}
        height="400px" // Or use CSS to make it flexible
        extensions={extensions}
        onChange={onChange} // `onChange` in react-codemirror passes the value directly
        theme={theme} // Example: 'light', 'dark', or imported themes like `aiu`
        // Common options you might want to set:
        // basicSetup={{
        //   foldGutter: true,
        //   dropCursor: true,
        //   allowMultipleSelections: true,
        //   indentOnInput: true,
        //   // You can disable lineNumbers, highlightActiveLineGutter, etc. here
        // }}
      />
    </Box>
  );
};

export default CodeEditor; 