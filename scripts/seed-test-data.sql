-- Seed test data for T-1504-BACK validation
-- Creates 6 elements with geometry data for API testing

INSERT INTO blocks (id, iso_code, status, tipologia, material_type, low_poly_url, bbox, created_at) VALUES
  ('c2fe5121-1234-4321-8765-000000000001'::uuid, 'GLPER.B-PAE0720', 'validated', 'capitel', 'Montjuïc', 
   'https://example.com/models/test1.glb', 
   '{"min": [-1.5, -2.0, 0.0], "max": [1.5, 2.0, 3.5]}'::jsonb,
   NOW() - INTERVAL '10 days'),
  
  ('c2fe5121-1234-4321-8765-000000000002'::uuid, 'GLPER.B-PAE0721', 'validated', 'capitel', 'Ulldecona',
   'https://example.com/models/test2.glb',
   '{"min": [-0.8, -1.2, 0.0], "max": [0.8, 1.2, 2.1]}'::jsonb,
   NOW() - INTERVAL '9 days'),
  
  ('c2fe5121-1234-4321-8765-000000000003'::uuid, 'GLPER.B-PAE0722', 'validated', 'capitel', 'Floresta',
   'https://example.com/models/test3.glb',
   '{"min": [-2.0, -3.0, 0.0], "max": [2.0, 3.0, 4.0]}'::jsonb,
   NOW() - INTERVAL '8 days'),
  
  ('c2fe5121-1234-4321-8765-000000000004'::uuid, 'TEST-ELEM-001', 'validated', 'columna', 'Montjuïc',
   'https://example.com/models/test4.glb',
   '{"min": [-1.0, -1.0, -0.5], "max": [1.0, 1.0, 2.5]}'::jsonb,
   NOW() - INTERVAL '7 days'),
   
  ('c2fe5121-1234-4321-8765-000000000005'::uuid, 'TEST-ELEM-002', 'validated', 'columna', 'Vinaixa',
   'https://example.com/models/test5.glb',
   '{"min": [-1.2, -1.8, 0.0], "max": [1.2, 1.8, 3.2]}'::jsonb,
   NOW() - INTERVAL '6 days'),
   
  ('c2fe5121-1234-4321-8765-000000000006'::uuid, 'TEST-ELEM-003', 'validated', 'capitel', 'Montjuïc',
   'https://example.com/models/test6.glb',
   '{"min": [-0.5, -0.5, 0.0], "max": [0.5, 0.5, 1.5]}'::jsonb,
   NOW() - INTERVAL '5 days')
ON CONFLICT (id) DO NOTHING;

-- Verify insertion
SELECT COUNT(*) as total_blocks FROM blocks;
SELECT COUNT(*) as blocks_with_geometry FROM blocks WHERE low_poly_url IS NOT NULL AND bbox IS NOT NULL;
SELECT iso_code, material_type, status FROM blocks ORDER BY created_at DESC LIMIT 6;
