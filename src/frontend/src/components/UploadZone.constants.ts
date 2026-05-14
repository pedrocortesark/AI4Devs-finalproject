/**
 * UploadZone Component Constants
 * 
 * Centralized configuration and messages for the UploadZone component.
 * Following the project pattern of extracting magic strings and numbers.
 */

import type { CSSProperties } from 'react';

/**
 * Default validation constraints
 */
export const UPLOAD_ZONE_DEFAULTS = {
  MAX_FILE_SIZE: 500 * 1024 * 1024, // 500MB in bytes
  ACCEPTED_MIME_TYPES: ['application/x-rhino', 'application/octet-stream'],
  ACCEPTED_EXTENSIONS: ['.3dm'],
} as const;

/**
 * Error messages for file validation failures
 */
export const ERROR_MESSAGES = {
  FILE_TOO_LARGE: (maxSizeMB: number) => 
    `File is too large. Maximum size is ${maxSizeMB}MB.`,
  INVALID_FILE_TYPE: (extensions: string[]) => 
    `Invalid file type. Only ${extensions.join(', ')} files are accepted.`,
  TOO_MANY_FILES: 'Only one file can be uploaded at a time.',
  INVALID_FILE_OBJECT: 'Invalid file object.',
} as const;

/**
 * CSS class names for component states
 */
export const CLASS_NAMES = {
  CONTAINER: 'upload-zone-container',
  DROPZONE: 'upload-zone',
  ACTIVE: 'upload-zone--active',
  DISABLED: 'upload-zone--disabled',
  ERROR: 'upload-zone--error',
  ERROR_MESSAGE: 'upload-zone-error',
} as const;

/**
 * Inline styles for the dropzone component — Mac OS Dark Mode design system
 */
export const STYLES = {
  dropzone: {
    base: {
      border: '2px dashed rgba(255, 255, 255, 0.12)',
      borderRadius: '12px',
      padding: '48px 32px',
      textAlign: 'center' as const,
      transition: 'all 0.2s ease-in-out',
    },
    idle: {
      backgroundColor: 'rgba(255, 255, 255, 0.03)',
      borderColor: 'rgba(255, 255, 255, 0.12)',
      cursor: 'pointer' as const,
      opacity: 1,
    },
    active: {
      backgroundColor: 'rgba(0, 122, 255, 0.08)',
      borderColor: 'rgba(0, 122, 255, 0.6)',
    },
    error: {
      backgroundColor: 'rgba(255, 59, 48, 0.06)',
      borderColor: 'rgba(255, 59, 48, 0.5)',
    },
    disabled: {
      cursor: 'not-allowed' as const,
      opacity: 0.4,
    },
  },
  dragText: {
    margin: 0,
    color: '#007AFF',
    fontWeight: 500,
    fontSize: '15px',
  },
  instructionText: {
    primary: {
      margin: '0 0 8px 0',
      fontSize: '15px',
      color: 'rgba(255, 255, 255, 0.85)',
      fontWeight: 500,
    },
    secondary: {
      margin: 0,
      fontSize: '13px',
      color: 'rgba(255, 255, 255, 0.4)',
    },
  },
  errorContainer: {
    marginTop: '12px',
    padding: '12px 16px',
    backgroundColor: 'rgba(255, 59, 48, 0.1)',
    border: '1px solid rgba(255, 59, 48, 0.35)',
    borderRadius: '8px',
    color: '#FF6B60',
    fontSize: '14px',
  },
} as const;

/**
 * Helper function to format file size in MB
 * @param bytes - File size in bytes
 * @returns Formatted size in MB (rounded)
 */
export function formatSizeInMB(bytes: number): number {
  return Math.round(bytes / (1024 * 1024));
}

/**
 * Helper function to build dropzone styles based on current state
 * @param isDragActive - Whether a file is being dragged over the dropzone
 * @param hasError - Whether there's a validation error
 * @param isDisabled - Whether the dropzone is disabled
 * @returns Combined style object
 */
export function buildDropzoneStyles(
  isDragActive: boolean,
  hasError: boolean,
  isDisabled: boolean
): CSSProperties {
  return {
    ...STYLES.dropzone.base,
    ...(isDragActive && STYLES.dropzone.active),
    ...(hasError && !isDragActive && STYLES.dropzone.error),
    ...(isDisabled ? STYLES.dropzone.disabled : STYLES.dropzone.idle),
  };
}
