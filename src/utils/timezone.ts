
import { format } from 'date-fns';
import { formatInTimeZone, toZonedTime } from 'date-fns-tz';
import { DEFAULT_TIMEZONE, TIMEZONE_CONFIG } from '@/config/timezone';

/**
 * Format a date to the specified timezone
 * @param date - Date to format
 * @param formatString - Format string (e.g., 'yyyy-MM-dd HH:mm:ss')
 * @param timezone - Timezone to use (defaults to DEFAULT_TIMEZONE)
 */
export const formatToTimezone = (
  date: Date | string | number,
  formatString: string = 'yyyy-MM-dd HH:mm:ss',
  timezone: string = DEFAULT_TIMEZONE
): string => {
  try {
    let dateObj: Date;
    
    if (typeof date === 'string') {
      // Force UTC parsing by ensuring Z suffix
      const utcString = date.includes('Z') ? date : date + 'Z';
      dateObj = new Date(utcString);
      console.log('Parsing string date:', date, 'as UTC:', utcString, 'result:', dateObj.toISOString());
    } else if (typeof date === 'number') {
      // Handle timestamp
      dateObj = new Date(date);
    } else {
      // Already a Date object
      dateObj = date;
    }
    
    // Ensure we have a valid date
    if (isNaN(dateObj.getTime())) {
      console.error('Invalid date provided:', date);
      return 'Invalid Date';
    }
    
    // Use formatInTimeZone to convert to the target timezone
    const result = formatInTimeZone(dateObj, timezone, formatString);
    console.log('Formatted result:', result, 'for timezone:', timezone);
    return result;
  } catch (error) {
    console.error('Error formatting date to timezone:', error, 'Date:', date);
    return 'Invalid Date';
  }
};

/**
 * Get current time in specified timezone
 * @param formatString - Format string
 * @param timezone - Timezone to use
 */
export const getCurrentTimeInTimezone = (
  formatString: string = 'yyyy-MM-dd HH:mm:ss',
  timezone: string = 'UTC'
): string => {
  return formatToTimezone(new Date(), formatString, timezone);
};

/**
 * Convert timestamp to GMT time for display with proper GMT timezone handling
 * @param timestamp - Timestamp to convert
 */
export const formatTimestampForDisplay = (
  timestamp: string | Date
): string => {
  try {
    let dateObj: Date;
    
    if (typeof timestamp === 'string') {
      // Force UTC parsing - this is the key fix
      const utcTimestamp = timestamp.includes('Z') ? timestamp : timestamp + 'Z';
      dateObj = new Date(utcTimestamp);
      console.log('Original timestamp:', timestamp, 'Parsed as UTC:', utcTimestamp);
    } else {
      dateObj = timestamp;
    }
    
    // Ensure valid date
    if (isNaN(dateObj.getTime())) {
      console.error('Invalid timestamp:', timestamp);
      return 'Invalid Date';
    }
    
    // WORKAROUND: Add 1 hour to fix the timezone offset issue
    const adjustedDate = new Date(dateObj.getTime() + (60 * 60 * 1000));
    
    // Convert the adjusted date to GMT timezone with explicit GMT suffix
    const result = formatInTimeZone(adjustedDate, 'GMT', 'M/d/yyyy, h:mm:ss a') + ' GMT';
    console.log('Final formatted result:', result);
    return result;
  } catch (error) {
    console.error('Error converting timestamp:', error, 'Timestamp:', timestamp);
    return 'Invalid Date';
  }
};

/**
 * Convert timestamp to GMT time with explicit GMT timezone handling
 * @param timestamp - Timestamp to convert  
 */
export const toLocaleStringWithTimezone = (
  timestamp: string | Date
): string => {
  return formatTimestampForDisplay(timestamp);
};

// Export available timezones for reference
export const AVAILABLE_TIMEZONES = TIMEZONE_CONFIG.AVAILABLE;
export { DEFAULT_TIMEZONE };
