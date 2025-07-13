
export type DeploymentStatus = 'idle' | 'loading' | 'running' | 'success' | 'failed' | 'completed' | 'timeout';

export interface LogEntry {
  timestamp: string;
  message: string;
  level: 'info' | 'error' | 'warning' | 'debug';
}
