const configuredBackendUrl = import.meta.env.VITE_ONTOFORGE_BACKEND_URL?.trim();

export const BACKEND_URL = (configuredBackendUrl || 'http://localhost:8765').replace(/\/+$/, '');
export const JSONRPC_URL = `${BACKEND_URL}/jsonrpc`;
