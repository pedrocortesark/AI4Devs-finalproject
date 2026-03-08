-- Migration: Delete PENDING blocks
--
-- Context: The original upload flow created 1 block per upload with
-- iso_code = 'PENDING-{file_id[:8]}'. This was architecturally wrong:
-- a single .3dm file contains N InstanceDefinitions, each of which
-- must become its own block (with iso_code = InstanceDefinition.Name).
--
-- The new flow (register_3dm_blocks task) creates N blocks per upload,
-- one per InstanceDefinition, with idempotency via the UNIQUE constraint
-- on iso_code. PENDING blocks must be removed so they do not pollute
-- the parts dashboard.

DELETE FROM blocks WHERE iso_code LIKE 'PENDING-%';
