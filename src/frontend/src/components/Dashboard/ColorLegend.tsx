/**
 * ColorLegend — contextual color legend for the 3D canvas.
 *
 * Material mode: shows unique tipologías from loaded parts with stone colors.
 * Textura mode:  shows Rhino layer colors parsed from the first available MTL file.
 */

import React, { useState, useEffect } from 'react';
import { usePartsStore } from '@/stores/parts.store';
import { getMaterialColorHex, MATERIAL_COLORS } from '@/constants/materials';

interface LegendItem {
  name: string;
  color: string;
}

const CONTAINER_STYLE: React.CSSProperties = {
  position: 'absolute',
  bottom: '84px',
  left: '16px',
  background: 'rgba(0,0,0,0.65)',
  backdropFilter: 'blur(4px)',
  WebkitBackdropFilter: 'blur(4px)',
  borderRadius: '12px',
  padding: '10px 14px',
  zIndex: 50,
  minWidth: '148px',
  maxWidth: '200px',
  maxHeight: '260px',
  overflowY: 'auto',
};

const TITLE_STYLE: React.CSSProperties = {
  fontSize: '10px',
  fontWeight: 600,
  color: 'rgba(255,255,255,0.45)',
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
  marginBottom: '8px',
};

const ROW_STYLE: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
};

const SWATCH_STYLE: React.CSSProperties = {
  width: '11px',
  height: '11px',
  borderRadius: '3px',
  flexShrink: 0,
  border: '1px solid rgba(255,255,255,0.12)',
};

const LABEL_STYLE: React.CSSProperties = {
  fontSize: '11px',
  color: 'rgba(255,255,255,0.85)',
  whiteSpace: 'nowrap',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
};

/** Parse MTL text into {name, color} items */
function parseMtlColors(mtlText: string): LegendItem[] {
  const items: LegendItem[] = [];
  const seen = new Set<string>();
  let currentMat = '';

  for (const line of mtlText.split('\n')) {
    const tokens = line.trim().split(/\s+/);
    if (tokens[0] === 'newmtl' && tokens[1]) {
      currentMat = tokens[1];
    } else if (tokens[0] === 'Kd' && currentMat && tokens.length >= 4 && !seen.has(currentMat)) {
      seen.add(currentMat);
      const r = Math.round(parseFloat(tokens[1]) * 255);
      const g = Math.round(parseFloat(tokens[2]) * 255);
      const b = Math.round(parseFloat(tokens[3]) * 255);
      // mat name is the Rhino layer name (spaces encoded as _)
      const label = currentMat.replace(/_/g, ' ');
      items.push({ name: label, color: `rgb(${r},${g},${b})` });
      // Don't reset currentMat here - keep it until next newmtl
    }
  }

  return items;
}

const ColorLegend: React.FC = () => {
  const parts = usePartsStore((state) => state.parts);
  const colorMode = usePartsStore((state) => state.colorMode);
  const [layerItems, setLayerItems] = useState<LegendItem[]>([]);

  // Fetch + parse MTL when entering Textura mode
  // Aggregate materials from ALL parts' MTL files to show complete legend
  useEffect(() => {
    if (colorMode !== 'layer') {
      setLayerItems([]);
      return;
    }

    // Collect all unique MTL URLs
    const mtlUrls = Array.from(
      new Set(
        parts
          .filter((p) => p.mtl_url)
          .map((p) => p.mtl_url!)
      )
    );

    if (mtlUrls.length === 0) return;

    let cancelled = false;
    const allItems = new Map<string, LegendItem>(); // name → item

    // Fetch and parse all MTL files in parallel
    Promise.all(
      mtlUrls.map((url) =>
        fetch(url)
          .then((r) => r.text())
          .then((text) => parseMtlColors(text))
          .catch(() => [] as LegendItem[])
      )
    ).then((itemsArrays) => {
      if (cancelled) return;
      
      // Merge all items, keeping unique materials by name
      itemsArrays.forEach((items) => {
        items.forEach((item) => {
          if (!allItems.has(item.name)) {
            allItems.set(item.name, item);
          }
        });
      });

      setLayerItems(Array.from(allItems.values()));
    });

    return () => { cancelled = true; };
  }, [colorMode, parts]);

  let items: LegendItem[] = [];
  let title = '';

  if (colorMode === 'material') {
    title = 'Tipo de piedra';
    const seen = new Set<string>();
    for (const p of parts) {
      // Read material from rhino_metadata.Material first, fallback to tipologia
      const materialKey = 
        (p.rhino_metadata && typeof p.rhino_metadata === 'object' && 'Material' in p.rhino_metadata
          ? String(p.rhino_metadata.Material)
          : p.tipologia) || null;
      
      if (materialKey && !seen.has(materialKey)) {
        seen.add(materialKey);
        // Only add to legend if color exists in MATERIAL_COLORS
        if (materialKey in MATERIAL_COLORS) {
          items.push({ 
            name: materialKey, 
            color: getMaterialColorHex(materialKey as keyof typeof MATERIAL_COLORS) 
          });
        }
      }
    }
  } else {
    title = 'Layer de Rhino';
    items = layerItems;
  }

  if (items.length === 0) return null;

  return (
    <div style={CONTAINER_STYLE}>
      <div style={TITLE_STYLE}>{title}</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
        {items.map(({ name, color }) => (
          <div key={name} style={ROW_STYLE}>
            <div style={{ ...SWATCH_STYLE, background: color }} />
            <span style={LABEL_STYLE} title={name}>{name}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ColorLegend;
