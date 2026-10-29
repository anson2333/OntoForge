/**
 * Electron Preload Script
 * Secure bridge between main process and renderer
 */

const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods to renderer process
contextBridge.exposeInMainWorld('electronAPI', {
  // App info
  ping: () => ipcRenderer.invoke('ping'),
  getAppVersion: () => ipcRenderer.invoke('get-app-version'),
  
  // Workspace
  getWorkspacePath: () => ipcRenderer.invoke('get-workspace-path'),
  setWindowTitle: (title) => ipcRenderer.invoke('set-window-title', title),
  
  // SSP Server communication (to be implemented)
  sspRequest: (method, params) => {
    // For now, this will communicate with backend via HTTP
    // Later can be optimized to use IPC for local backend
    return null;
  },
  
  // Notification listeners
  onAuditConflict: (callback) => {
    ipcRenderer.on('ssp:audit-conflict', (_event, data) => callback(data));
  },
  
  onProgressUpdate: (callback) => {
    ipcRenderer.on('ssp:progress', (_event, data) => callback(data));
  }
});

// Log preload script loaded
console.log('Preload script loaded successfully');
