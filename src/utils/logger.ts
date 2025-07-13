
/**
 * Centralized logging utility for Fix Deployment Orchestrator
 */

// Log levels
export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

// Log entry interface
export interface LogEntry {
  timestamp: string;
  level: LogLevel;
  message: string;
  context?: Record<string, any>;
}

class Logger {
  private static instance: Logger;
  
  private constructor() {
    // Singleton pattern
  }

  public static getInstance(): Logger {
    if (!Logger.instance) {
      Logger.instance = new Logger();
    }
    return Logger.instance;
  }

  /**
   * Log a message with specified level
   */
  public log(level: LogLevel, message: string, context?: Record<string, any>): void {
    const timestamp = new Date().toISOString();
    const logEntry: LogEntry = {
      timestamp,
      level,
      message,
      context
    };
    
    // Log to console with consistent formatting
    const consoleMessage = `[${timestamp}] [${level.toUpperCase()}] ${message}`;
    const contextStr = context ? JSON.stringify(context) : '';
    
    switch (level) {
      case 'debug':
        console.debug(consoleMessage, contextStr);
        break;
      case 'info':
        console.info(consoleMessage, contextStr);
        break;
      case 'warn':
        console.warn(consoleMessage, contextStr);
        break;
      case 'error':
        console.error(consoleMessage, contextStr);
        break;
    }
  }

  public debug(message: string, context?: Record<string, any>): void {
    this.log('debug', message, context);
  }

  public info(message: string, context?: Record<string, any>): void {
    this.log('info', message, context);
  }

  public warn(message: string, context?: Record<string, any>): void {
    this.log('warn', message, context);
  }

  public error(message: string, context?: Record<string, any>): void {
    this.log('error', message, context);
  }
}

export const logger = Logger.getInstance();
export default logger;
