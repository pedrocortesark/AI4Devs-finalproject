# Plan: Rediseño del Panel de Detalles de Pieza (Tecla "D")

**Objetivo:** Reemplazar el modal de pantalla completa (`PartDetailModal`) por un panel lateral deslizante no-bloqueante, con visor 3D funcional, 4 tabs organizadas y diseño visual consistente.

**Referencia:** Requirements completos en el prompt de diseño (sesión 2026-03-11).
**Rama:** `finalproject-PCN`
**Solo frontend** — Ningún cambio de backend en este plan.

---

## Estado actual del código (pre-cambios)

| Componente | Ubicación | Estado |
|---|---|---|
| `PartDetailModal` | `Dashboard/PartDetailModal.tsx` | Modal full-screen con backdrop. Bloquea interacción con canvas. |
| `PartViewerCanvas` | `components/PartViewerCanvas.tsx` | Canvas 3D con Stage, OrbitControls. Usa `useGLTF` (GLB). |
| `ModelLoader` | `components/ModelLoader.tsx` | Carga GLB via `useGLTF`. NO usa OBJ. |
| `PartMetadataPanel` | `Dashboard/PartMetadataPanel.tsx` | 4 secciones colapsables. Reutilizable. |
| `ElementMesh` | `Dashboard/ElementMesh.tsx` | Referencia para OBJ + rotación Z→Y + material. |
| `MATERIAL_COLORS` | `constants/materials.ts` | 62 materiales con RGB. ✅ Listo. |
| `parts.store.ts` | `stores/parts.store.ts` | No tiene `isDetailsPanelOpen`. |
| `PartDetail` type | `types/parts.ts` | Sin campos `material_type` ni `rhino_metadata`. |

### Gaps identificados
- `PartDetail` no incluye `material_type` ni `rhino_metadata` — el visor usará material por defecto ("Montjuïc") y el tab Metadata mostrará datos de `validation_report` como fallback.
- `ModelLoader` usa GLB (`useGLTF`), pero el nuevo `PartViewer3D` debe usar OBJ (`OBJLoader`) igual que `ElementMesh`.
- El panel actual es modal (bloquea canvas). El nuevo debe ser side panel no-bloqueante.

---

## Fase 1 — Infraestructura: Store y Tipos ✅ COMPLETADA
*Prerequisito de todo lo demás. Cambios mínimos a archivos existentes.*

> **Decisión tomada (D2):** Estado `isOpen` queda en Dashboard3D local — no se contamina el store de parts con estado UI. Las acciones del store no son necesarias.

- [x] **1.1** ~~Añadir `isDetailsPanelOpen` al store~~ — Estado local en Dashboard3D (`showDetailsPanel`)
- [x] **1.5** Extender `PartDetail` en `types/parts.ts` con campos opcionales:
  ```typescript
  material_type?: string | null;       // Para color en visor 3D
  rhino_metadata?: Record<string, unknown> | null;  // Para tab Metadata
  ```
  > Estos campos son opcionales — si el backend no los retorna, la UI muestra fallback graceful.

---

## Fase 2 — Visor 3D Individual (`PartViewer3D.tsx`) ✅ COMPLETADA
*Componente Three.js que renderiza una sola pieza en OBJ con su material.*

Creado: `src/frontend/src/components/details/PartViewer3D.tsx`

- [x] **2.1** Scaffold del componente: `<Canvas>` + `<Suspense>` + `<OrbitControls>`
- [ ] **2.2** Cargar geometría OBJ via `useLoader(OBJLoader, url)` (mismo patrón que `ElementMesh`)
- [ ] **2.3** Aplicar rotación Z→Y: `rotation={[-Math.PI / 2, 0, 0]}` (igual que `ElementMesh`)
- [ ] **2.4** Calcular color del material:
  - Si `material_type` existe y está en `MATERIAL_COLORS` → usar ese color
  - Fallback: `MATERIAL_COLORS["Montjuïc"]` (default del sistema)
  - Helper: `getMaterialColor(material)` de `constants/materials.ts`
- [ ] **2.5** Aplicar `MeshStandardMaterial` con el color calculado (NO preservar materials Rhino — en visor de detalle queremos color consistente por material)
- [ ] **2.6** Centrar cámara en geometría usando `bbox` (si disponible):
  - Calcular centro como `(min + max) / 2`
  - Posicionar cámara a `distancia = maxDim * 2` del centro
- [ ] **2.7** Iluminación: ambient (intensity 0.6) + directional key light (position [5, 10, 5], intensity 1.2)
- [ ] **2.8** Fondo: `color="#1a1a2e"` (oscuro coherente con tema dashboard)
- [ ] **2.9** Grid helper opcional para referencia de escala (semi-transparente)
- [ ] **2.10** Loading state: `<Html center>` con spinner mientras suspense resuelve
- [ ] **2.11** Error state: si `low_poly_url` es null, mostrar mensaje "Geometría no disponible"
- [ ] **2.12** Props interface: `{ url: string | null; materialType?: string | null; bbox?: BoundingBox | null }`

---

## Fase 3 — Constantes y Estilos CSS ✅ COMPLETADA
*Definir el sistema de diseño del panel antes de construirlo.*

Creados: `src/frontend/src/components/details/DetailsPanel.constants.ts` y `DetailsPanel.module.css`

- [x] **3.1** Definir `TAB_CONFIG` con los 4 tabs:
  ```typescript
  general: { label: 'General', icon: '◉' }
  geometry: { label: 'Geometría', icon: '⬡' }
  metadata: { label: 'Metadata', icon: '{}' }
  raw: { label: 'JSON Raw', icon: '</>' }
  ```
- [ ] **3.2** Definir `PANEL_COLORS` (paleta del design system):
  - primary, secondary, background, surface, text, textSecondary, error, warning, success
  - Status badge colors: validated=green, error_processing=red, processing=yellow, uploaded=blue
- [ ] **3.3** Definir `PANEL_DIMENSIONS`: `width: '400px'`, `viewer3dHeight: '300px'`
- [ ] **3.4** Definir `ANIMATION`: `duration: '300ms'`, `easing: 'ease-out'`

Crear: `src/frontend/src/components/details/DetailsPanel.module.css`

- [ ] **3.5** `.panel` — `position: fixed; right: 0; top: 0; height: 100vh; width: 400px; background: #fff; box-shadow: -2px 0 12px rgba(0,0,0,0.15); z-index: 500; display: flex; flex-direction: column;`
- [ ] **3.6** `.panelOpen` + `.panelClosed` — animación slide-in desde derecha:
  ```css
  .panelOpen  { transform: translateX(0);     transition: transform 300ms ease-out; }
  .panelClosed { transform: translateX(100%); transition: transform 300ms ease-out; }
  ```
- [ ] **3.7** `.header` — flex row, padding, border-bottom, ISO code title + close button
- [ ] **3.8** `.viewer3d` — `height: 300px; flex-shrink: 0; background: #1a1a2e;`
- [ ] **3.9** `.tabBar` — flex row, border-bottom, sticky
- [ ] **3.10** `.tab` + `.tabActive` — style pill-style tabs con indicador azul abajo
- [ ] **3.11** `.content` — `flex: 1; overflow-y: auto; padding: 16px;`
- [ ] **3.12** `.badge` + variantes por status (validated, error, processing, uploaded)
- [ ] **3.13** `.fieldRow` — layout label/valor para campos de información
- [ ] **3.14** `.codeBlock` — monospace 12px para JSON raw
- [ ] **3.15** `.materialDot` — círculo de color para indicador de material (16px)
- [ ] **3.16** `.noSelection` — estado vacío cuando no hay pieza seleccionada

---

## Fase 4 — Componente Principal (`DetailsPanel.tsx`) ✅ COMPLETADA
*Orquestador del panel con todos los tabs.*

Creado: `src/frontend/src/components/details/DetailsPanel.tsx`

- [x] **4.1** Props interface: `{ partId: string | null; isOpen: boolean; onClose: () => void }`
- [ ] **4.2** Estado local: `activeTab: TabId` (default: `'general'`)
- [ ] **4.3** Fetch de datos: usar hook o efecto para llamar `getPartDetail(partId)` cuando `partId` cambia
  > Reutilizar `usePartDetail` hook de `PartDetailModal.hooks.ts` si aplica
- [ ] **4.4** Estructura del panel:
  ```
  <div class={panelOpen | panelClosed}>
    <Header />       ← ISO code + close button
    <PartViewer3D /> ← 300px viewer
    <TabBar />       ← 4 tabs
    <TabContent />   ← scrolleable
  </div>
  ```
- [ ] **4.5** Header: muestra `partData?.iso_code` o "Cargando..." + botón `×`
- [ ] **4.6** **Tab "General"** (contenido):
  - ISO Code grande (20px bold, color primary)
  - Status badge (pill con color semántico)
  - Material Type con `MaterialDot` (círculo del color + nombre)
  - Created At formateado: `formatDate` de `utils/formatters.ts`
  - Tipología
- [ ] **4.7** **Tab "Geometría"** (contenido):
  - Bounding Box Min: `[x.xx, y.xx, z.xx] mm`
  - Bounding Box Max: `[x.xx, y.xx, z.xx] mm`
  - Dimensiones calculadas: `Width × Height × Depth mm`
  - LOD URLs como links clicables (high_poly_url, mid_poly_url, low_poly_url)
  - Fallback "No disponible" para URLs null
- [ ] **4.8** **Tab "Metadata"** (contenido):
  - Si `rhino_metadata` existe: mostrar como árbol de key/value
    - Highlight keys: `SF_GEN_Material`, `SF_GEN_GrauEstructural`, `SF_GEN_Volum_m3`, `SF_GEN_Pes_t`
    - Resto: sección colapsable "Más campos"
  - Si `rhino_metadata` es null: mostrar `PartMetadataPanel` existente como fallback (reutilizar)
- [ ] **4.9** **Tab "JSON Raw"** (contenido):
  - `<pre>` con JSON.stringify completo del objeto `partData`
  - Botón "Copiar JSON" (usa `navigator.clipboard.writeText`)
  - Feedback visual al copiar: texto cambia a "¡Copiado!" por 2s
- [ ] **4.10** Loading state: skeleton o spinner mientras carga `partData`
- [ ] **4.11** Error state: mensaje con opción retry (reutilizar `renderErrorState` si aplica)
- [ ] **4.12** Sin pieza seleccionada (`partId === null`): mostrar `<NoSelectionState />`
  ```
  Selecciona una pieza en el visor principal
  para ver sus detalles aquí.
  ```
- [ ] **4.13** Keyboard: `useEffect` para Escape → `onClose()`
- [ ] **4.14** Reset `activeTab` a `'general'` cuando `partId` cambia

---

## Fase 5 — Integración en Dashboard3D ✅ COMPLETADA
*Conectar el nuevo panel al flujo existente. Reemplazar PartDetailModal.*

Modificado: `src/frontend/src/components/Dashboard/Dashboard3D.tsx`

- [x] **5.1** Importar `DetailsPanel` en lugar de (o además de) `PartDetailModal`
- [ ] **5.2** Reemplazar `showDetailsModal` + `setShowDetailsModal` por `isDetailsPanelOpen` + `closeDetailsPanel` del store
  > Alternativa si el store no se usa: mantener estado local en Dashboard3D
- [ ] **5.3** El handler de tecla `D` ya existe — conectar a `openDetailsPanel()` del store (o mantener `setShowDetailsModal`)
- [ ] **5.4** Renderizar `<DetailsPanel>` fuera del canvas (al mismo nivel que el sidebar de filtros):
  ```tsx
  <DetailsPanel
    partId={selectedId}
    isOpen={isDetailsPanelOpen}
    onClose={closeDetailsPanel}
  />
  ```
- [ ] **5.5** El panel NO tiene backdrop — no cierra al hacer click fuera (usuario puede seguir usando canvas)
- [ ] **5.6** Ajustar hint de selección: actualizar texto del badge inferior si cambia flujo
- [ ] **5.7** Decidir si deprecar `PartDetailModal` o mantenerlo:
  - **Opción A (recomendada):** Reemplazarlo completamente con `DetailsPanel`
  - **Opción B:** Mantener ambos temporalmente hasta validar el nuevo panel
  > Marcar aquí la decisión elegida: ______

---

## Fase 6 — Tests Unitarios (Vitest) ✅ COMPLETADA — 21/21 passing
*Tests para lógica de UI del panel.*

Creados: `src/frontend/src/components/details/DetailsPanel.test.tsx` y `PartViewer3D.test.tsx`

- [x] **6.1** Test: renderiza correctamente cuando `isOpen=false` (panel no visible / clase panelClosed)
- [ ] **6.2** Test: renderiza correctamente cuando `isOpen=true` con `partId=null` → muestra NoSelectionState
- [ ] **6.3** Test: muestra loading state mientras `partData` carga (mock del servicio)
- [ ] **6.4** Test: tab "General" muestra iso_code, status badge y created_at formateado
- [ ] **6.5** Test: cambio de tab actualiza contenido visible
- [ ] **6.6** Test: botón `×` en header llama `onClose`
- [ ] **6.7** Test: tecla Escape llama `onClose`
- [ ] **6.8** Test: tab "JSON Raw" muestra botón "Copiar JSON"

Crear: `src/frontend/src/components/details/PartViewer3D.test.tsx`

- [ ] **6.9** Test: renderiza fallback "Geometría no disponible" cuando `url=null`
- [ ] **6.10** Test: renderiza canvas cuando `url` es una string válida (mock OBJLoader)

---

## Fase 7 — Validación Manual (pendiente)
*Checklist de verificación post-implementación.*

- [ ] **7.1** El visor 3D renderiza la geometría OBJ con el color del material correcto
- [ ] **7.2** OrbitControls funciona: rotar, zoom, pan dentro del visor
- [ ] **7.3** Los 4 tabs cambian contenido sin errores de consola
- [ ] **7.4** Tab JSON muestra el objeto completo y el botón "Copiar JSON" funciona
- [ ] **7.5** Tecla `D` abre el panel con animación slide-in (300ms)
- [ ] **7.6** Tecla `Escape` cierra el panel
- [ ] **7.7** Con el panel abierto, el usuario PUEDE rotar el canvas 3D principal
- [ ] **7.8** El panel es scrolleable cuando el contenido supera el viewport
- [ ] **7.9** Sin pieza seleccionada + tecla `D`: panel abre con mensaje de selección
- [ ] **7.10** Al seleccionar otra pieza con panel abierto: panel actualiza datos
- [ ] **7.11** `make test-front` pasa sin errores nuevos

---

## Decisiones de Diseño a Confirmar

> Marcar antes de codificar Fase 4 y 5.

- [ ] **D1 — ¿Reemplazar `PartDetailModal` completamente?**
  Recomendado: sí, para evitar deuda técnica. Tests existentes de `PartDetailModal` se migran o eliminan.

- [ ] **D2 — ¿El estado `isDetailsPanelOpen` va en el store de Zustand o en estado local de `Dashboard3D`?**
  Recomendado: estado local en `Dashboard3D` (evita contaminar el store de parts con estado UI).

- [ ] **D3 — ¿`PartViewer3D` aplica color sólido por material o preserva materials Rhino?**
  Recomendado: color sólido del diccionario `MATERIAL_COLORS` (visor de detalle = inspeccion, no realismo). Si `material_type` es null → usar color por status.

- [ ] **D4 — ¿Tab "Metadata" usa `PartMetadataPanel` existente o nueva implementación?**
  Recomendado: nueva implementación simplificada para `rhino_metadata`; si ese campo es null, renderizar `PartMetadataPanel` existente como fallback para no perder información ya disponible.

---

## Orden de implementación sugerido

```
Fase 1 (20 min) → Fase 3 (30 min) → Fase 2 (45 min) → Fase 4 (60 min) → Fase 5 (20 min) → Fase 6 (30 min) → Fase 7 (15 min)
```

**Total estimado:** ~3.5h de desarrollo.

---

*Creado: 2026-03-11 | Rama: finalproject-PCN*
