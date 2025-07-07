
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

// Default log file path (will be mounted from host)
const LOG_FILE_PATH = process.env.LOG_FILE_PATH || '/app/logs/application.log';

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
    
    // Log to console
    const consoleMessage = `[${timestamp}] [${level.toUpperCase()}] ${message}`;
    switch (level) {
      case 'debug':
        console.debug(consoleMessage, context || '');
        break;
      case 'info':
        console.info(consoleMessage, context || '');
        break;
      case 'warn':
        console.warn(consoleMessage, context || '');
        break;
      case 'error':
        console.error(consoleMessage, context || '');
        break;
    }
    
    // In browser environment, we don't directly write to files
    // The backend will handle file logging
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
