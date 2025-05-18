import React, { createContext, useContext, useState, useEffect } from 'react';
import { fetchSystemConfig } from '../api/configService';

const ConfigContext = createContext();

export const useConfig = () => {
    const context = useContext(ConfigContext);
    if (!context) {
        throw new Error('useConfig must be used within a ConfigProvider');
    }
    return context;
};

export const ConfigProvider = ({ children }) => {
    const [config, setConfig] = useState({
        systemName: 'AI Interviewer',
        version: '1.0.0',
        voiceEnabled: false,
        features: {},
        isLoading: true,
        error: null
    });

    useEffect(() => {
        const loadConfig = async () => {
            try {
                const data = await fetchSystemConfig();
                setConfig({
                    systemName: data.system_name,
                    version: data.version,
                    voiceEnabled: data.voice_enabled,
                    features: data.features,
                    isLoading: false,
                    error: null
                });
            } catch (error) {
                setConfig(prev => ({
                    ...prev,
                    isLoading: false,
                    error: error.message
                }));
            }
        };

        loadConfig();
    }, []);

    return (
        <ConfigContext.Provider value={config}>
            {children}
        </ConfigContext.Provider>
    );
}; 