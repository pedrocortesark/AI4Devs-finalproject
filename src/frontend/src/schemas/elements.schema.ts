/**
 * T-1505-FRONT: Zod Validation Schemas for Element API
 * 
 * Purpose: Runtime validation of API responses (fail-fast on contract mismatch)
 * Pattern: Zod schemas mirror Pydantic schemas EXACTLY
 * 
 * Usage:
 * - Service layer: Parse API responses with schema.parse()
 * - Type inference: z.infer<typeof ElementSchema> → Element type
 * - Error handling: ZodError → user-friendly validation errors
 */

import { z } from 'zod';
import { MATERIAL_COLORS } from '../constants/materials';

// ===== Enums =====

/**
 * ElementStatus enum schema (8 lifecycle states)
 */
export const ElementStatusSchema = z.enum([
  'uploaded',
  'processing',
  'validated',
  'rejected',
  'error_processing',
  'in_fabrication',
  'completed',
  'archived',
]);

/**
 * MaterialType enum schema (62 real stone types from Sagrada Família)
 */
const materialKeys = Object.keys(MATERIAL_COLORS) as [string, ...string[]];
export const MaterialTypeSchema = z.enum(materialKeys);

// ===== Bounding Box =====

/**
 * BoundingBox schema: min/max as 3-element tuples [x, y, z]
 */
export const BoundingBoxSchema = z.object({
  min: z.tuple([z.number(), z.number(), z.number()]),
  max: z.tuple([z.number(), z.number(), z.number()]),
});

// ===== Element (Canvas Item) =====

/**
 * Element schema: Minimal info optimized for 3D canvas rendering + LOD system (US-015)
 */
export const ElementSchema = z.object({
  id: z.string().uuid(),
  iso_code: z.string(),
  status: ElementStatusSchema,
  material_type: MaterialTypeSchema,
  high_poly_url: z.string().url().nullable().optional(),  // US-015: High-detail GLB (~7k tris, 0-15m)
  mid_poly_url: z.string().url().nullable().optional(),   // US-015: Mid-detail GLB (~2k tris, 15-40m)
  low_poly_url: z.string().url().nullable(),              // US-015: Low-detail GLB (~500 tris, 40-100m)
  bbox: BoundingBoxSchema.nullable(),
});

// ===== Elements List Response =====

/**
 * ElementsListResponse schema: Paginated list with filters and metadata
 */
export const ElementsListResponseSchema = z.object({
  elements: z.array(ElementSchema),
  filters_applied: z.record(z.string().nullable()),
  meta: z.object({
    total: z.number().int().nonnegative(),
    filtered: z.number().int().nonnegative(),
  }),
});

// ===== Element Detail =====

/**
 * ValidationReport schema (matches backend ValidationReport exactly)
 */
export const ValidationReportSchema = z.object({
  is_valid: z.boolean(),
  errors: z.array(z.any()),  // ValidationErrorItem[] - simplified for now
  metadata: z.record(z.any()),
  validated_at: z.string().datetime().nullable().optional(),
  validated_by: z.string().nullable().optional(),
});

/**
 * ElementDetail schema: Full element data with relationships and metadata
 */
export const ElementDetailSchema = z.object({
  id: z.string().uuid(),
  iso_code: z.string(),
  status: ElementStatusSchema,
  material_type: MaterialTypeSchema,
  created_at: z.string().datetime(),
  high_poly_url: z.string().url().nullable().optional(),  // US-015: High-detail GLB
  mid_poly_url: z.string().url().nullable().optional(),   // US-015: Mid-detail GLB
  low_poly_url: z.string().url().nullable(),              // US-015: Low-detail GLB
  bbox: BoundingBoxSchema.nullable(),
  validation_report: ValidationReportSchema.nullable(),
  glb_size_bytes: z.number().int().nonnegative().nullable().optional(),
  triangle_count: z.number().int().nonnegative().nullable().optional(),
});

// ===== Element Navigation =====

/**
 * ElementNavigationResponse schema: Prev/Next IDs for carousel navigation
 */
export const ElementNavigationResponseSchema = z.object({
  prev_id: z.string().uuid().nullable(),
  next_id: z.string().uuid().nullable(),
  current_index: z.number().int().nonnegative(),
  total_count: z.number().int().nonnegative(),
});

// ===== Type Inference =====

/**
 * Inferred TypeScript types from Zod schemas
 */
export type Element = z.infer<typeof ElementSchema>;
export type ElementsListResponse = z.infer<typeof ElementsListResponseSchema>;
export type ElementDetail = z.infer<typeof ElementDetailSchema>;
export type ElementNavigationResponse = z.infer<typeof ElementNavigationResponseSchema>;
export type ElementStatus = z.infer<typeof ElementStatusSchema>;
export type MaterialType = z.infer<typeof MaterialTypeSchema>;

/**
 * Query parameters for GET /api/elements (all optional)
 */
export interface ElementsQueryParams {
  status?: z.infer<typeof ElementStatusSchema>;
  material_type?: z.infer<typeof MaterialTypeSchema>;
}
