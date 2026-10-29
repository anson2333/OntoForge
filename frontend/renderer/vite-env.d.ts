// Type declarations for CSS module imports
declare module '*.css' {
  const content: { [className: string]: string };
  export default content;
}

declare module '*.scss' {
  const content: { [className: string]: string };
  export default content;
}

declare module '*.sass' {
  const content: { [className: string]: string };
  export default content;
}

declare module '*.less' {
  const content: { [className: string]: string };
  export default content;
}

interface ElectronAPI {
  ping: () => Promise<string>;
  getAppVersion: () => Promise<string>;
  getWorkspacePath: () => Promise<string>;
  setWindowTitle: (title: string) => Promise<boolean>;
  sspRequest: (method: string, params: unknown) => unknown;
  onAuditConflict: (callback: (data: unknown) => void) => void;
  onProgressUpdate: (callback: (data: unknown) => void) => void;
}

interface Window {
  electronAPI?: ElectronAPI;
}
