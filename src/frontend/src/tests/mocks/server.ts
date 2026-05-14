/**
 * MSW Server Setup for T-1507-TEST Frontend Integration Tests
 * 
 * TDD Phase: RED
 * Purpose: Mock Service Worker server configuration for API mocking
 */

import { setupServer } from 'msw/node';
import { handlers } from './handlers';

/**
 * MSW Server instance with Element API handlers
 * 
 * Usage in tests:
 *   beforeAll(() => server.listen())
 *   afterEach(() => server.resetHandlers())
 *   afterAll(() => server.close())
 */
export const server = setupServer(...handlers);
