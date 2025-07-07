
// Timezone configuration - change DEFAULT_TIMEZONE to use different timezone globally
export const TIMEZONE_CONFIG = {
  DEFAULT: 'UTC',
  AVAILABLE: {
    LONDON: 'Europe/London',
    UTC: 'UTC',
    GMT: 'GMT',
    NEW_YORK: 'America/New_York',
    TOKYO: 'Asia/Tokyo',
    SYDNEY: 'Australia/Sydney',
    PARIS: 'Europe/Paris',
    BERLIN: 'Europe/Berlin',
    MUMBAI: 'Asia/Kolkata',
    DUBAI: 'Asia/Dubai',
  } as const
};

// Export the default timezone for easy importing
export const DEFAULT_TIMEZONE = TIMEZONE_CONFIG.DEFAULT;
