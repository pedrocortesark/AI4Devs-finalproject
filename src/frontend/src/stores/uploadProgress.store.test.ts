/**
 * UploadProgress Store - Unit Tests - T-1807
 * 
 * Tests for Zustand store managing upload + validation progress.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { useUploadProgressStore } from './uploadProgress.store';
import { createInitialSteps } from '../constants/stategraph.constants';

describe('UploadProgress Store', () => {
  beforeEach(() => {
    // Reset store to initial state before each test
    useUploadProgressStore.getState().reset();
  });

  describe('Initial State', () => {
    it('should have correct initial state', () => {
      const state = useUploadProgressStore.getState();
      
      expect(state.blockId).toBeNull();
      expect(state.filename).toBeNull();
      expect(state.steps).toHaveLength(8);
      expect(state.currentStep).toBe(0);
      expect(state.status).toBe('idle');
      expect(state.startedAt).toBeNull();
      expect(state.eta).toBeNull();
      expect(state.finalMessage).toBeUndefined();
    });

    it('should initialize with 8 idle steps', () => {
      const state = useUploadProgressStore.getState();
      
      state.steps.forEach((step, index) => {
        expect(step.index).toBe(index);
        expect(step.status).toBe('idle');
        expect(step.startedAt).toBeNull();
        expect(step.completedAt).toBeNull();
      });
    });
  });

  describe('startProgress', () => {
    it('should set blockId, filename, and status to processing', () => {
      const { startProgress } = useUploadProgressStore.getState();
      
      startProgress('block-123', 'test-file.3dm');
      
      const state = useUploadProgressStore.getState();
      expect(state.blockId).toBe('block-123');
      expect(state.filename).toBe('test-file.3dm');
      expect(state.status).toBe('processing');
      expect(state.currentStep).toBe(0);
      expect(state.startedAt).toBeTruthy();
    });

    it('should reset steps when starting new progress', () => {
      const { startProgress, updateStepStatus } = useUploadProgressStore.getState();
      
      // Start and update a step
      startProgress('block-1', 'file1.3dm');
      updateStepStatus(0, 'completed');
      
      // Start new progress
      startProgress('block-2', 'file2.3dm');
      
      const state = useUploadProgressStore.getState();
      expect(state.steps[0].status).toBe('idle');
      expect(state.currentStep).toBe(0);
    });
  });

  describe('updateStepStatus', () => {
    beforeEach(() => {
      useUploadProgressStore.getState().startProgress('block-123', 'test.3dm');
    });

    it('should update step status to active', () => {
      const { updateStepStatus } = useUploadProgressStore.getState();
      
      updateStepStatus(0, 'active');
      
      const state = useUploadProgressStore.getState();
      expect(state.steps[0].status).toBe('active');
      expect(state.steps[0].startedAt).toBeTruthy();
    });

    it('should update step status to completed and set timestamp', () => {
      const { updateStepStatus } = useUploadProgressStore.getState();
      
      updateStepStatus(0, 'active');
      
      // Wait a small delay
      const startTime = new Date(useUploadProgressStore.getState().steps[0].startedAt!).getTime();
      
      updateStepStatus(0, 'completed');
      
      const state = useUploadProgressStore.getState();
      expect(state.steps[0].status).toBe('completed');
      expect(state.steps[0].completedAt).toBeTruthy();
      
      const endTime = new Date(state.steps[0].completedAt!).getTime();
      expect(endTime).toBeGreaterThanOrEqual(startTime);
    });

    it('should set error message when status is error', () => {
      const { updateStepStatus } = useUploadProgressStore.getState();
      
      updateStepStatus(0, 'error', 'Validation failed');
      
      const state = useUploadProgressStore.getState();
      expect(state.steps[0].status).toBe('error');
      expect(state.steps[0].errorMessage).toBe('Validation failed');
    });

    it('should handle invalid step index gracefully', () => {
      const { updateStepStatus } = useUploadProgressStore.getState();
      
      // Should not throw, just log warning
      updateStepStatus(99, 'active');
      
      const state = useUploadProgressStore.getState();
      // State should remain unchanged
      expect(state.steps[0].status).toBe('idle');
    });
  });

  describe('advanceToNextStep', () => {
    beforeEach(() => {
      useUploadProgressStore.getState().startProgress('block-123', 'test.3dm');
    });

    it('should increment currentStep', () => {
      const { advanceToNextStep } = useUploadProgressStore.getState();
      
      expect(useUploadProgressStore.getState().currentStep).toBe(0);
      
      advanceToNextStep();
      
      expect(useUploadProgressStore.getState().currentStep).toBe(1);
    });

    it('should not exceed max steps', () => {
      const { advanceToNextStep } = useUploadProgressStore.getState();
      
      // Advance to last step
      for (let i = 0; i < 10; i++) {
        advanceToNextStep();
      }
      
      const state = useUploadProgressStore.getState();
      expect(state.currentStep).toBeLessThan(8);
    });
  });

  describe('markCompleted', () => {
    beforeEach(() => {
      useUploadProgressStore.getState().startProgress('block-123', 'test.3dm');
    });

    it('should set status to completed and finalMessage', () => {
      const { markCompleted } = useUploadProgressStore.getState();
      
      markCompleted('Validation successful');
      
      const state = useUploadProgressStore.getState();
      expect(state.status).toBe('completed');
      expect(state.finalMessage).toBe('Validation successful');
      expect(state.eta).toBe(0);
    });
  });

  describe('markFailed', () => {
    beforeEach(() => {
      useUploadProgressStore.getState().startProgress('block-123', 'test.3dm');
    });

    it('should set status to error and finalMessage', () => {
      const { markFailed } = useUploadProgressStore.getState();
      
      markFailed('Validation failed: geometry errors');
      
      const state = useUploadProgressStore.getState();
      expect(state.status).toBe('error');
      expect(state.finalMessage).toBe('Validation failed: geometry errors');
      expect(state.eta).toBeNull();
    });
  });

  describe('calculateETA', () => {
    beforeEach(() => {
      useUploadProgressStore.getState().startProgress('block-123', 'test.3dm');
    });

    it('should return null when no steps completed', () => {
      const { calculateETA } = useUploadProgressStore.getState();
      
      calculateETA();
      
      expect(useUploadProgressStore.getState().eta).toBeNull();
    });

    it('should calculate ETA based on completed steps', () => {
      const { updateStepStatus, advanceToNextStep, calculateETA } = useUploadProgressStore.getState();
      
      // Complete first step
      updateStepStatus(0, 'active');
      updateStepStatus(0, 'completed');
      advanceToNextStep();
      
      calculateETA();
      
      const state = useUploadProgressStore.getState();
      // Should have an ETA (not null, even if 0 due to fast completion)
      expect(state.eta).toBeGreaterThanOrEqual(0);
    });

    it('should return 0 ETA when status is completed', () => {
      const { markCompleted } = useUploadProgressStore.getState();
      
      markCompleted('Done');
      
      expect(useUploadProgressStore.getState().eta).toBe(0);
    });
  });

  describe('reset', () => {
    it('should reset all state to initial values', () => {
      const { startProgress, updateStepStatus, reset } = useUploadProgressStore.getState();
      
      // Modify state
      startProgress('block-123', 'test.3dm');
      updateStepStatus(0, 'completed');
      
      // Reset
      reset();
      
      const state = useUploadProgressStore.getState();
      expect(state.blockId).toBeNull();
      expect(state.filename).toBeNull();
      expect(state.status).toBe('idle');
      expect(state.currentStep).toBe(0);
      expect(state.steps[0].status).toBe('idle');
    });
  });
});
