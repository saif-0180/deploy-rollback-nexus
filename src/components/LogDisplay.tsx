
import React from 'react';
import { cn } from '@/lib/utils';

interface LogDisplayProps {
  logs: string[];
  height?: string;
  fixedHeight?: boolean;
  title?: string;
  status?: 'idle' | 'loading' | 'running' | 'success' | 'failed' | 'completed';
}

const LogDisplay: React.FC<LogDisplayProps> = ({ 
  logs, 
  height = "300px", 
  fixedHeight = false, 
  title = "Logs",
  status = 'idle'
}) => {
  const getStatusColor = () => {
    switch (status) {
      case 'loading':
      case 'running':
        return 'text-blue-600';
      case 'success':
      case 'completed':
        return 'text-green-600';
      case 'failed':
        return 'text-red-600';
      default:
        return 'text-[#2A4759]';
    }
  };

  const getStatusText = () => {
    switch (status) {
      case 'loading':
        return 'Loading...';
      case 'running':
        return 'Running...';
      case 'success':
        return 'Completed Successfully';
      case 'completed':
        return 'Completed';
      case 'failed':
        return 'Failed';
      default:
        return 'Ready';
    }
  };

  return (
    <div className="bg-[#EEEEEE] p-4 rounded-md">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-lg font-medium text-[#F79B72]">{title}</h3>
        <span className={cn("text-sm font-medium", getStatusColor())}>
          {getStatusText()}
        </span>
      </div>
      <div 
        className={cn(
          "bg-black text-green-400 p-4 rounded font-mono text-sm overflow-y-auto",
          fixedHeight && "resize-none"
        )}
        style={{ height }}
      >
        {logs.length === 0 ? (
          <div className="text-gray-500">No logs yet...</div>
        ) : (
          logs.map((log, index) => (
            <div key={index} className="mb-1">
              {log}
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default LogDisplay;
