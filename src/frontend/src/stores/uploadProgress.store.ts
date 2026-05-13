/**
 * Upload Progress Store - T-1807
 * 
 * Zustand store for managing real-time upload + validation progress.
 * Tracks StateGraph workflow execution (8 nodes) and calculates ETA.
 */

import { create } from 'zustand';
import type { UploadProgressState, StepStatus } from '../types/upload';
import { createInitialSteps } from '../constants/stategraph.constants';

interface UploadProgressStore extends UploadProgressState {
  // Actions
  
  /**
   * Start tracking progress for a new upload
   * @param blockId - Block UUID from /api/upload/confirm
   * @param filename - Original filename
   */
  startProgress: (blockId: string, filename: string) => void;
  
  /**
   * Update the status of a specific step
   * @param stepIndex - Index of the step (0-7)
   * @param status - New status
   * @param errorMessage - Optional error message
   */
  updateStepStatus: (stepIndex: number, status: StepStatus, errorMessage?: string) => void;
  
  /**
   * Move to the next step (increment currentStep)
   */
  advanceToNextStep: () => void;
  
  /**
   * Mark the entire workflow as completed (success)
   * @param message - Final validation message
   */
  markCompleted: (message: string) => void;
  
  /**
   * Mark the entire workflow as failed
   * @param message - Error message
   */
  markFailed: (message: string) => void;
  
  /**
   * Calculate ETA based on completed steps
   * Updates the eta field in state
   */
  calculateETA: () => void;
  
  /**
   * Reset state to idle (for new upload)
   */
  reset: () => void;
}

/**
 * Initial state
 */
const initialState: UploadProgressState = {
  blockId: null,
  filename: null,
  steps: createInitialSteps(),
  currentStep: 0,
  status: 'idle',
  startedAt: null,
  eta: null,
  finalMessage: undefined,
};

/**
 * Upload Progress Store
 */
export const useUploadProgressStore = create<UploadProgressStore>((set, get) => ({
  ...initialState,
  
  startProgress: (blockId: string, filename: string) => {
    set({
      blockId,
      filename,
      steps: createInitialSteps(),
      currentStep: 0,
      status: 'processing',
      startedAt: new Date().toISOString(),
      eta: null,
      finalMessage: undefined,
    });
  },
  
  updateStepStatus: (stepIndex: number, status: StepStatus, errorMessage?: string) => {
    const { steps } = get();
    
    if (stepIndex < 0 || stepIndex >= steps.length) {
      console.warn(`[UploadProgressStore] Invalid step index: ${stepIndex}`);
      return;
    }
    
    const updatedSteps = [...steps];
    const step = updatedSteps[stepIndex];
    
    // Update step status
    step.status = status;
    
    // Set timestamps
    if (status === 'active' && !step.startedAt) {
      step.startedAt = new Date().toISOString();
    }
    
    if ((status === 'completed' || status === 'error' || status === 'warning') && !step.completedAt) {
      step.completedAt = new Date().toISOString();
    }
    
    // Set error message
    if (errorMessage) {
      step.errorMessage = errorMessage;
    }
    
    set({ steps: updatedSteps });
    
    // Auto-calculate ETA after each update
    get().calculateETA();
  },
  
  advanceToNextStep: () => {
    const { currentStep, steps } = get();
    const nextStep = currentStep + 1;
    
    if (nextStep < steps.length) {
      set({ currentStep: nextStep });
    }
  },
  
  markCompleted: (message: string) => {
    set({
      status: 'completed',
      finalMessage: message,
      eta: 0,
    });
  },
  
  markFailed: (message: string) => {
    set({
      status: 'error',
      finalMessage: message,
      eta: null,
    });
  },
  
  calculateETA: () => {
    const { steps, currentStep, status } = get();
    
    // No ETA if already completed or failed
    if (status === 'completed' || status === 'error') {
      set({ eta: 0 });
      return;
    }
    
    // Get completed steps (up to currentStep)
    const completedSteps = steps
      .slice(0, currentStep + 1)
      .filter(step => step.status === 'completed' && step.startedAt && step.completedAt);
    
    if (completedSteps.length === 0) {
      // No completed steps yet, can't estimate
      set({ eta: null });
      return;
    }
    
    // Calculate average duration per step (in milliseconds)
    const totalDuration = completedSteps.reduce((sum, step) => {
      const start = new Date(step.startedAt!).getTime();
      const end = new Date(step.completedAt!).getTime();
      return sum + (end - start);
    }, 0);
    
    const avgDurationMs = totalDuration / completedSteps.length;
    
    // Remaining steps
    const remainingSteps = steps.length - (currentStep + 1);
    
    if (remainingSteps <= 0) {
      set({ eta: 0 });
      return;
    }
    
    // ETA in seconds
    const etaSeconds = Math.round((avgDurationMs * remainingSteps) / 1000);
    set({ eta: etaSeconds });
  },
  
  reset: () => {
    set(initialState);
  },
}));
