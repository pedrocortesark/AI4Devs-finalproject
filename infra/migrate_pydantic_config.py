#!/usr/bin/env python3
"""
Script para migrar class Config a model_config = ConfigDict en schemas.py
Pydantic v2 deprecó class Config en favor de model_config
"""
import re
import os

# Determinar path correcto (Docker usa /app/, local usa src/backend/)
schema_path = '/app/schemas.py' if os.path.exists('/app/schemas.py') else 'src/backend/schemas.py'

# Leer el archivo
with open(schema_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Añadir import de ConfigDict si no existe
if 'from pydantic import' in content and 'ConfigDict' not in content:
    content = content.replace(
        'from pydantic import BaseModel, Field, field_validator, model_validator',
        'from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict'
    )

# Contar ocurrencias antes del reemplazo
before_count = content.count('class Config:')
print(f"✓ Found {before_count} instances of 'class Config:'")

# Patrón 1: use_enum_values
content = re.sub(
    r'(\s+)class Config:\n\s+use_enum_values = True  # Serialize enums as their values',
    r'\1model_config = ConfigDict(use_enum_values=True)  # Serialize enums as their values',
    content,
    flags=re.MULTILINE
)

# Patrón 2: from_attributes con comentario
content = re.sub(
    r'(\s+)class Config:\n\s+# Allow ORM models \(Supabase Row\) to be converted to Pydantic\n\s+from_attributes = True',
    r'\1model_config = ConfigDict(from_attributes=True)  # Allow ORM models (Supabase Row) to be converted to Pydantic',
    content,
    flags=re.MULTILINE
)

# Patrón 3: from_attributes solo
content = re.sub(
    r'(\s+)class Config:\n\s+from_attributes = True\s*\n',
    r'\1model_config = ConfigDict(from_attributes=True)\n',
    content,
    flags=re.MULTILINE
)

# Patrón 4: from_attributes + json_encoders
content = re.sub(
    r'(\s+)class Config:\n\s+from_attributes = True\n\s+# Serialize datetime as ISO 8601 strings\n\s+json_encoders = \{\n\s+datetime: lambda v: v\.isoformat\(\) if v else None\n\s+\}',
    r'\1model_config = ConfigDict(\n\1    from_attributes=True,\n\1    json_encoders={\n\1        datetime: lambda v: v.isoformat() if v else None\n\1    }\n\1)',
    content,
    flags=re.MULTILINE
)

# Patrón 5: json_schema_extra (complejo, multi-línea)
# Este requiere múltiples pasadas para capturar correctamente

lines = content.split('\n')
i = 0
result_lines = []

while i < len(lines):
    line = lines[i]
    
    # Detectar inicio de class Config con json_schema_extra
    if 'class Config:' in line:
        indent = len(line) - len(line.lstrip())
        indent_str = ' ' * indent
        
        # Buscar qué contiene esta Config
        j = i + 1
        config_block = []
        while j < len(lines) and (lines[j].strip() == '' or len(lines[j]) - len(lines[j].lstrip()) > indent):
            if lines[j].strip():
                config_block.append(lines[j])
            j += 1
        
        # Analizar el bloque
        has_from_attrs = any('from_attributes = True' in l for l in config_block)
        has_json_schema = any('json_schema_extra' in l for l in config_block)
        
        if has_json_schema:
            # Extraer json_schema_extra completo
            schema_start_idx = next((idx for idx, l in enumerate(config_block) if 'json_schema_extra' in l), None)
            if schema_start_idx is not None:
                # Capturar todo el dict
                json_schema_lines = []
                brace_count = 0
                for k in range(schema_start_idx, len(config_block)):
                    json_schema_lines.append(config_block[k].strip())
                    brace_count += config_block[k].count('{') - config_block[k].count('}')
                    if brace_count == 0 and '{' in config_block[k]:
                        break
                
                # Construir nuevo model_config
                if has_from_attrs:
                    result_lines.append(f'{indent_str}model_config = ConfigDict(')
                    result_lines.append(f'{indent_str}    from_attributes=True,')
                    result_lines.append(f'{indent_str}    json_schema_extra=' + json_schema_lines[0].replace('json_schema_extra = ', ''))
                    for schema_line in json_schema_lines[1:]:
                        result_lines.append(f'{indent_str}    {schema_line}')
                    result_lines.append(f'{indent_str})')
                else:
                    result_lines.append(f'{indent_str}model_config = ConfigDict(')
                    result_lines.append(f'{indent_str}    json_schema_extra=' + json_schema_lines[0].replace('json_schema_extra = ', ''))
                    for schema_line in json_schema_lines[1:]:
                        result_lines.append(f'{indent_str}    {schema_line}')
                    result_lines.append(f'{indent_str})')
                
                i = j  # Saltar las líneas procesadas
                continue
    
    result_lines.append(line)
    i += 1

content = '\n'.join(result_lines)

# Contar restantes
after_count = content.count('class Config:')
print(f"✓ Remaining 'class Config:': {after_count}")
print(f"✓ Successfully migrated: {before_count - after_count}")

# Escribir de vuelta
with open(schema_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Pydantic Config → ConfigDict migration complete!")
