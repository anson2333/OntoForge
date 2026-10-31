/**
 * Service Status Hook
 * Monitors backend and LLM service status
 */

import { useState, useEffect } from 'react';
import { BACKEND_URL, JSONRPC_URL } from './runtime_config';
import { sspClient } from './ssp_client';
import { useAuthStore } from './auth';

export interface ServiceStatus {
  status: 'online' | 'offline' | 'degraded' | 'unknown';
  message?: string;
}

export interface LLMStatus extends ServiceStatus {
  provider?: string;
  model?: string;
  enabled: boolean;
  configured: boolean;
}

const CHECK_INTERVAL = 10000; // Check every 10 seconds

export function useServiceStatus() {
  const userId = useAuthStore(state => state.user?.user_id);
  const [backendStatus, setBackendStatus] = useState<ServiceStatus>({
    status: 'unknown',
    message: 'Checking...'
  });

  const [llmStatus, setLLMStatus] = useState<LLMStatus>({
    status: 'unknown',
    enabled: false,
    configured: false,
    message: 'Checking...'
  });

  const checkBackendHealth = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/health`, {
        method: 'GET'
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      
      setBackendStatus({
        status: data.status === 'healthy' ? 'online' : 'degraded',
        message: data.database === 'connected' 
          ? 'Backend and database connected' 
          : 'Backend online, database disconnected'
      });

      return true;
    } catch (error) {
      setBackendStatus({
        status: 'offline',
        message: 'Backend server not responding'
      });
      return false;
    }
  };

  const checkLLMStatus = async () => {
    try {
      const response = await fetch(JSONRPC_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(sspClient.getToken() ? { Authorization: `Bearer ${sspClient.getToken()}` } : {}) },
        body: JSON.stringify({
          jsonrpc: '2.0',
          method: 'getLLMStatus',
          params: {},
          id: Date.now()
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();

      if (data.error) {
        throw new Error(data.error.message);
      }

      const result = data.result;
      
      let status: 'online' | 'offline' | 'degraded' | 'unknown' = 'unknown';
      if (result.enabled && result.configured && result.healthy) {
        status = 'online';
      } else if (result.enabled && result.configured && !result.healthy) {
        status = 'degraded';
      } else if (!result.enabled) {
        status = 'offline';
      }

      setLLMStatus({
        status,
        provider: result.provider,
        model: result.model,
        enabled: result.enabled,
        configured: result.configured,
        message: result.message
      });
    } catch (error) {
      console.error('[LLM Status] Error checking LLM status:', error);
      setLLMStatus({
        status: 'unknown',
        enabled: false,
        configured: false,
        message: 'Unable to check LLM status'
      });
    }
  };

  const checkAllServices = async () => {
    const backendOnline = await checkBackendHealth();
    
    // Only check LLM if backend is online
    if (backendOnline) {
      await checkLLMStatus();
    } else {
      setLLMStatus({
        status: 'unknown',
        enabled: false,
        configured: false,
        message: 'Backend offline'
      });
    }
  };

  useEffect(() => {
    // Check immediately on mount
    checkAllServices();

    // Set up periodic checks
    const interval = setInterval(checkAllServices, CHECK_INTERVAL);

    return () => clearInterval(interval);
  }, [userId]);

  return {
    backendStatus,
    llmStatus,
    refresh: checkAllServices
  };
}
