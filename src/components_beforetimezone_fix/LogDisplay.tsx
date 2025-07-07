
import React, { useRef, useEffect, useState } from 'react';
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Loader2 } from "lucide-react";

interface LogDisplayProps {
  logs: string[];
  height?: string;
  fixedHeight?: boolean;
  title?: string;
  status?: 'idle' | 'loading' | 'running' | 'success' | 'failed' | 'completed';
}

const LogDisplay: React.FC<LogDisplayProps> = ({ 
  logs, 
  height = "400px", 
  fixedHeight = true,
  title = "Logs",
  status = 'idle'
}) => {
  const logEndRef = useRef<HTMLDivElement>(null);
  const [previousLogsLength, setPreviousLogsLength] = useState<number>(0);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const scrollViewportRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when logs change - scroll only within the log container
  useEffect(() => {
    if (logs.length !== previousLogsLength) {
      setTimeout(() => {
        // Try to find the actual scrollable viewport within ScrollArea
        const scrollArea = scrollAreaRef.current;
        if (scrollArea) {
          const viewport = scrollArea.querySelector('[data-radix-scroll-area-viewport]') as HTMLElement;
          if (viewport) {
            viewport.scrollTop = viewport.scrollHeight;
          }
        }
        // Fallback to our ref
        if (scrollViewportRef.current) {
          scrollViewportRef.current.scrollTop = scrollViewportRef.current.scrollHeight;
        }
        setPreviousLogsLength(logs.length);
      }, 10);
    }
  }, [logs, previousLogsLength]);

  // Force scroll when status changes to success/completed - scroll only within the log container
  useEffect(() => {
    if (status === 'success' || status === 'completed') {
      setTimeout(() => {
        // Try to find the actual scrollable viewport within ScrollArea
        const scrollArea = scrollAreaRef.current;
        if (scrollArea) {
          const viewport = scrollArea.querySelector('[data-radix-scroll-area-viewport]') as HTMLElement;
          if (viewport) {
            viewport.scrollTop = viewport.scrollHeight;
          }
        }
        // Fallback to our ref
        if (scrollViewportRef.current) {
          scrollViewportRef.current.scrollTop = scrollViewportRef.current.scrollHeight;
        }
      }, 10);
    }
  }, [status]);

  // Get badge color based on status
  const getBadgeColorClass = () => {
    switch (status) {
      case 'success':
      case 'completed':
        return 'bg-green-500 hover:bg-green-600';
      case 'failed':
        return 'bg-red-500 hover:bg-red-600';
      case 'running':
        return 'bg-yellow-500 hover:bg-yellow-600';
      case 'loading':
        return 'bg-blue-500 hover:bg-blue-600';
      default:
        return 'bg-gray-500 hover:bg-gray-600';
    }
  };

  // Detect if log content contains errors
  const hasErrors = logs.some(log => 
    log.includes('ERROR') || 
    log.includes('FAILED') || 
    log.includes('failed') ||
    log.includes('error')
  );

  // Set appropriate status if there are errors but status isn't set yet
  const effectiveStatus = hasErrors && status === 'running' ? 'failed' : status;

  return (
    <div className="space-y-2 h-full">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="font-medium text-[#F79B72]">{title}</h3>
          {effectiveStatus !== 'idle' && (
            <Badge className={`${getBadgeColorClass()} text-white`}>
              {effectiveStatus === 'running' || effectiveStatus === 'loading' ? (
                <div className="flex items-center gap-1">
                  <Loader2 className="h-3 w-3 animate-spin mr-1" />
                  {effectiveStatus === 'loading' ? 'Loading' : 'Running'}
                </div>
              ) : (
                effectiveStatus.charAt(0).toUpperCase() + effectiveStatus.slice(1)
              )}
            </Badge>
          )}
        </div>
      </div>
      <ScrollArea 
        ref={scrollAreaRef}
        className="bg-[#0A1929] rounded-md p-4 font-mono text-sm shadow-md border border-[#2A4759]" 
        style={{ 
          height: fixedHeight ? height : "auto", 
          maxHeight: height,
          minHeight: fixedHeight ? height : "auto"
        }}
      >
        <div 
          ref={scrollViewportRef}
          className="h-full overflow-auto"
          onScroll={(e) => {
            // Prevent event bubbling to avoid page scroll
            e.stopPropagation();
          }}
          onWheel={(e) => {
            // Prevent wheel events from bubbling to parent
            e.stopPropagation();
          }}
          onTouchMove={(e) => {
            // Prevent touch scroll events from bubbling to parent
            e.stopPropagation();
          }}
        >
          {logs.length === 0 ? (
            <p className="text-gray-400">No logs available. Start an operation to see logs here.</p>
          ) : (
            logs.map((log, index) => (
              <div key={index} className="mb-1">
                {log.includes('ERROR') || log.includes('FAILED') || log.includes('failed') || log.includes('error') ? (
                  <span className="text-red-400">{log}</span>
                ) : log.includes('SUCCESS') || log.includes('COMPLETED') || log.includes('successfully') ? (
                  <span className="text-green-400">{log}</span>
                ) : log.includes('WARNING') ? (
                  <span className="text-yellow-300">{log}</span>
                ) : log.includes('Checksum=') ? (
                  <span className="text-blue-300">{log}</span>
                ) : (
                  <span className="text-gray-200">{log}</span>
                )}
              </div>
            ))
          )}
          <div ref={logEndRef} />
        </div>
      </ScrollArea>
    </div>
  );
};

export default LogDisplay;
