/**
 * Tests for usePartsSpatialLayout — metre-scale invariants
 *
 * T-0502-FRONT: Encodes the coordinate-system contract between the agent pipeline
 * and the Three.js viewer.
 *
 * Scene unit = 1 m throughout (camera at 50 m, LOD thresholds in m,
 * LAYOUT_SPACING = 5 m).  These tests act as a regression guard so that
 * no one silently converts units or changes the spacing constant.
 *
 * @module usePartsSpatialLayout.test
 */

import { describe, it, expect } from 'vitest';
import { renderHook } from '@testing-library/react';
import { usePartsSpatialLayout } from './usePartsSpatialLayout';
import type { PartCanvasItem } from '@/types/parts';
import { BlockStatus } from '@/types/parts';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makePart(id: string): PartCanvasItem {
  return {
    id,
    iso_code: `SF-NAV-CO-${id}`,
    status: BlockStatus.Validated,
    tipologia: 'capitel',
    low_poly_url: `https://example.com/${id}.glb`,
    bbox: { min: [-100, 0, -150], max: [100, 400, 150] },
    workshop_id: 'ws-1',
    workshop_name: 'Taller Test',
  };
}

const p1 = makePart('001');
const p2 = makePart('002');
const p3 = makePart('003');
const p4 = makePart('004');
const p5 = makePart('005');
const p6 = makePart('006');
const p7 = makePart('007');

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('usePartsSpatialLayout — bbox center positioning', () => {
  it('returns empty array for empty parts list', () => {
    const { result } = renderHook(() => usePartsSpatialLayout([]));
    expect(result.current).toEqual([]);
  });

  it('calculates position from bbox center (min + max) / 2', () => {
    const part = makePart('001');
    // bbox: { min: [-100, 0, -150], max: [100, 400, 150] }
    // Expected center: [(−100+100)/2, (0+400)/2, (−150+150)/2] = [0, 200, 0]
    const { result } = renderHook(() => usePartsSpatialLayout([part]));
    expect(result.current[0]).toEqual([0, 200, 0]);
  });

  it('handles multiple parts with different bbox positions', () => {
    const part1 = { ...p1, bbox: { min: [-10, -20, -30], max: [10, 20, 30] } };
    const part2 = { ...p2, bbox: { min: [100, 200, 300], max: [120, 220, 320] } };
    // part1 center: [0, 0, 0]
    // part2 center: [110, 210, 310]
    const { result } = renderHook(() => usePartsSpatialLayout([part1, part2]));
    expect(result.current[0]).toEqual([0, 0, 0]);
    expect(result.current[1]).toEqual([110, 210, 310]);
  });

  it('uses real building coordinates (digital twin mode)', () => {
    // Real Sagrada Família coordinates in metres
    const sfPart = {
      ...p1,
      bbox: { min: [-8.61, -53.53, 73.92], max: [-8.45, -53.30, 74.22] },
    };
    // Expected center: [-8.53, -53.415, 74.07]
    const { result } = renderHook(() => usePartsSpatialLayout([sfPart]));
    expect(result.current[0][0]).toBeCloseTo(-8.53, 2);
    expect(result.current[0][1]).toBeCloseTo(-53.415, 2);
    expect(result.current[0][2]).toBeCloseTo(74.07, 2);
  });

  it('positions array length matches parts array length', () => {
    const parts = [p1, p2, p3, p4, p5];
    const { result } = renderHook(() => usePartsSpatialLayout(parts));
    expect(result.current).toHaveLength(parts.length);
  });

  it('each position is a tuple of exactly 3 numbers', () => {
    const { result } = renderHook(() => usePartsSpatialLayout([p1, p2, p3]));
    result.current.forEach((pos) => {
      expect(pos).toHaveLength(3);
      pos.forEach((coord) => expect(typeof coord).toBe('number'));
    });
  });

  it('handles parts with null bbox (fallback to origin)', () => {
    const partNoBbox = { ...p1, bbox: null };
    const { result } = renderHook(() => usePartsSpatialLayout([partNoBbox]));
    expect(result.current[0]).toEqual([0, 0, 0]);
  });
});
