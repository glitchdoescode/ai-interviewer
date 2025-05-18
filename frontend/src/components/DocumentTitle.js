import { useEffect } from 'react';
import { useConfig } from '../context/ConfigContext';

/**
 * Component that updates document title and meta description based on the system name
 * This component doesn't render anything visible, it just updates the document head
 */
const DocumentTitle = () => {
  const { systemName, isLoading } = useConfig();
  
  useEffect(() => {
    if (!isLoading && systemName) {
      // Update document title
      document.title = systemName;
      
      // Update meta description
      const metaDescription = document.querySelector('meta[name="description"]');
      if (metaDescription) {
        metaDescription.setAttribute('content', `${systemName} - Practice technical interviews with AI`);
      }
    }
  }, [systemName, isLoading]);
  
  // This component doesn't render anything
  return null;
};

export default DocumentTitle; 