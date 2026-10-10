# Contexto y Arquitectura - Aplicativo de Estudio Bíblico (v2)

## 1. Visión y Propósito General
Plataforma **Multi-Usuario** en Python (Streamlit) para el autoexamen, estudio bíblico y discipulado familiar. Combina RAG local, base de datos relacional y procesamiento ETL dinámico para ofrecer una experiencia que **evoluciona junto con el usuario y los recursos ingresados**. El sistema fomenta el autoexamen y el arrepentimiento sin caer en el legalismo, ofreciendo herramientas prácticas para el liderazgo devocional junto a Ailín y la instrucción familiar.

## 2. Principios de Desarrollo y Arquitectura
*   **S (Single Responsibility):** Cada módulo o clase tiene una sola responsabilidad (ETL, transcripción Whisper, UI en Streamlit, etc.).
*   **D (Dependency Inversion):** La UI en Streamlit no depende directamente de SQLite ni de la Base Vectorial, sino de servicios intermediarios.
*   **Arquitectura Multi-Tenant y Persistencia:** Separación estricta en SQLite entre **datos públicos** (biblioteca, guías maestras, recursos RAG) y **datos privados** (diarios, progreso, nivel de dificultad, notas personales). `biblico.db` (datos privados) vive en Turso (libSQL remoto) en producción, con fallback a SQLite local en desarrollo. `vector_db` (biblioteca pública) se mantiene commiteado vía Git LFS en el repo de Hugging Face Spaces.
*   **Módulo Feedback Beta:** Botón persistente de "Sugerencias / Reporte de Errores" que guarda las críticas en una tabla específica.
*   **Testing Continuo (TDD):** Toda nueva funcionalidad o módulo de persistencia lleva su test unitario (`pytest`), ejecutando la suite completa antes de dar por cerrada la tarea.
*   **REGLA ESTRICTA DE DATOS DE PRUEBA (aplica a TODO el código, no solo a un módulo):** En UI, previews o seed data para probar cualquier módulo (familiar, usuario, discipulado, etc.), está **terminantemente prohibido usar nombres reales**. Usar exclusivamente nombres genéricos: `Usuario_Prueba`, `Esposa_Prueba`, `Hijo_Prueba`.
*   **UI Dinámica:** La interfaz reacciona a los recursos indexados — si se agrega un nuevo manual de exégesis, la UI habilita automáticamente las herramientas correspondientes.
*   **Observabilidad del Pipeline RAG (obligatoria):** Todo llamado al motor RAG debe loguear, como mínimo: la consulta, los chunks recuperados con su score de similitud, qué modelo de la cascada respondió (sección 12), y si la respuesta cayó en `fallback_no_rag`. Sin este log, un fallo de retrieval y un fallo de ensamblaje de prompt son indistinguibles desde afuera — y ambos se ven igual que "la IA no generó nada".

## 3. Salvaguarda Doctrinal y Jerarquía RAG (Filtro Doctrinal)
El motor RAG cuenta con un filtro hermenéutico estricto para bloquear interpretaciones liberales o "creativas" de la IA. Esta jerarquía es única y se referencia desde cualquier otra sección (ETL, System Prompt, módulos nuevos) — no debe duplicarse ni redefinirse en otro lugar:

1.  **Autoridad Suprema:** El texto bíblico inerrante.
2.  **Lente Hermenéutico Principal:** `apreciacion_de_iglesia.md` — define los principios congregacionales a los que el análisis debe someterse prioritariamente. Ante tensión interpretativa, este archivo decide.
3.  **Filtro Secundario:** Credos históricos y la Confesión de Fe Bautista de 1689, como marco de soporte — nunca contradicen al punto 2.

## 4. Estrategia de Datos y Optimización (ETL y RAG)
*   **Vector Database (El Cerebro):** PDFs y recursos teológicos se dividen en fragmentos (chunking) y se vectorizan para búsqueda semántica.
*   **Conversión a Markdown (`.md`):** Todo texto extraído de Biblias de Estudio, PDFs y transcripciones se transforma a Markdown antes de ser procesado por la IA.
*   **Indexación por Punteros (Pointer Indexing):** Archivos de gran volumen (GeoJSON, mapas) no se procesan por la IA. El sistema extrae metadatos y guarda la ruta; Streamlit renderiza localmente. La IA **nunca infiere ni inventa** una ruta que no venga en los metadatos recuperados.
*   **Inteligencia y UI Dinámica:** La carga de nuevos recursos dispara actualizaciones automáticas en módulos de la UI (nuevos planes al calendario, nuevos motivos al muro de oración) y mejora las reglas metodológicas del System Prompt vía un archivo de metadatos interno.
*   **Fragmentación Semántica (Chunking):**
    *   *Texto bíblico:* fragmentación natural por perícopa (libro/capítulo/versículo), con metadatos `{"book": "Romanos", "chapter": 8, "theme": "Soteriología"}`.
    *   *Literatura y comentarios:* unidad atómica = párrafo lógico, con **overlap de 15-20%** entre fragmentos consecutivos para no cortar un argumento a mitad de premisa.
    *   *PDFs con diseño complejo:* usar Document Layout Analysis + OCR para evitar que números de página o pies de nota se inserten a mitad de una frase teológica.
*   **Recuperación Híbrida:** combinar búsqueda vectorial (dense) con búsqueda por palabras clave BM25/FTS5 (sparse) en SQLite, para que términos técnicos (ej. "propiciación", "gracia irresistible") no se pierdan en promedios semánticos.
*   **Enrutamiento por Intención:** si el usuario cita una referencia directa ("Lee Romanos 8:28"), enrutar por búsqueda exacta (FTS5 / API de texto bíblico) en vez de búsqueda vectorial difusa; luego cruzar con el grafo de referencias cruzadas de OpenBible.
*   **Calidad de Metadatos (obligatoria, no opcional):** todo chunk ingerido debe llevar `category`/`tipo_lente`/`libro` reales, asignados en el momento de la ingesta (por estructura del documento, carpeta de origen, o clasificación automática) — nunca un valor por defecto como `"general"` sin razón explícita. Un chunk con metadatos genéricos es indistinguible para el Orquestador de Lentes, el Panel de Referencias Cruzadas y cualquier módulo que filtre por categoría, aunque el contenido esté perfectamente indexado. Si al auditar la biblioteca la mayoría de los chunks caen en `"general"`, es un bug del ETL, no una limitación de biblioteca.
*   **Traducción preferida:** si la **NTV (Nueva Traducción Viviente)** está entre las traducciones cargadas, se usa como traducción por defecto para mostrar el texto bíblico y para las citas del LLM. Orden de preferencia configurable: `NTV > RVR1960 > NVI > LBLA`. Si la traducción preferida no está indexada para un libro puntual, cae a la siguiente de la lista — nunca a una traducción no cargada en la biblioteca.

## 5. Generación Sensible al Contexto y Gestión de Caché
*   **Lazy Loading:** las guías de estudio se generan dinámicamente por capítulo solo la primera vez que se solicitan, y luego se almacenan como archivos estáticos.
*   **Invalidación de Caché:** al incorporar nuevos recursos, se actualiza la tabla de auditoría en SQLite marcando las guías estáticas existentes como desactualizadas para regeneración "On-Demand".
*   **Generación Condicional:** el prompt orquestador evalúa los vectores recuperados y adapta la estructura del curso (datos geográficos → sección espacial; epístola → desglose lógico).

## 6. Sistema de Andamiaje (Scaffolding) y Escalabilidad del Estudio

**Base metodológica:** el estudio inductivo del sistema se apoya en el método de la *Nueva Biblia de Estudio Inductivo* (NBEI), estructurado en tres fases — **Observación** (¿qué dice el texto?), **Interpretación** (¿qué significa?) y **Aplicación** (¿cómo se practica?). Este método es el "esqueleto" común a los tres niveles; lo que cambia entre niveles es *cuántos* de sus pasos se exigen y *cuánta* asistencia visual recibe el usuario. La guía de estudio inductivo generada por el sistema, sea cual sea el nivel, **siempre** sigue este orden: primero Observación, luego Interpretación, luego Aplicación — nunca se salta directo a interpretar sin observar primero.

### 6.1 Los 10 pasos de Observación (NBEI)
1. Comenzar con oración.
2. Las seis preguntas básicas: ¿Quién? ¿Qué? ¿Cuándo? ¿Dónde? ¿Por qué? ¿Cómo?
3. Marcar palabras y frases clave (incluye pronombres, posesivos y sinónimos).
4. Elaborar listas (simples y temáticas).
5. Buscar contrastes y comparaciones.
6. Notar referencias de tiempo.
7. Identificar términos de conclusión (*por tanto, por eso, pues*).
8. Resumir el/los tema(s) del capítulo.
9. Descubrir lecciones para la vida (LPV).
10. Completar un cuadro panorámico del libro/capítulo.

### 6.2 Las 6 pautas de Interpretación (NBEI)
1. El contexto rige (versículos circundantes, el libro, toda la Biblia).
2. Buscar todo el consejo de la Palabra (no aislar 1-2 versículos).
3. La Biblia no se contradice a sí misma.
4. No basar convicciones doctrinales en un pasaje oscuro.
5. Interpretar literalmente, según el género literario (histórico, profético, poético, epistolar, sapiencial, etc.), reconociendo las figuras retóricas como tales.
6. Buscar el significado único que tuvo en mente el autor original.

### 6.3 Aplicación (NBEI, según 2 Timoteo 3:16-17)
Cuatro ejes: **enseñanza** (¿qué dice la Palabra?), **reprensión** (¿qué en mí no concuerda con esto?), **corrección** (¿qué pasos concretos debo dar?) e **instrucción en justicia** (mandatos, promesas, ejemplos a seguir). Evitar las tres trampas que señala la NBEI: aplicar normas culturales en vez de bíblicas, forzar un versículo para apoyar una verdad ajena a él, o interpretar desde un prejuicio adquirido por enseñanzas previas.

### 6.4 Mapeo por nivel de madurez
*   **Nivel Principiante:** solo el Paso 2 de Observación (seis preguntas básicas, reducidas a 3 preguntas cerradas) + Paso 9 (una lección para la vida, simplificada). Intervención visual fuerte (verbos resaltados, conectores subrayados). No se exige Interpretación formal ni los 4 ejes de Aplicación — se ofrece una aplicación práctica directa y breve.
*   **Nivel Moderado (default si no se especifica):** Pasos 2, 3, 5 y 7 de Observación (preguntas básicas, palabras clave, contrastes/comparaciones, términos de conclusión) + pautas 1 y 2 de Interpretación (contexto rige, todo el consejo de la Palabra). Se exige que el usuario identifique la estructura gramatical y cruce el texto con referencias históricas básicas — el sistema no lo resuelve por él. Reducción de la asistencia visual.
*   **Nivel Complejo:** los 10 pasos completos de Observación, las 6 pautas de Interpretación y los 4 ejes de Aplicación. El sistema exige que el usuario proponga su propia conclusión (Paso 8 de Observación y pauta 6 de Interpretación) antes de contrastarla con los comentarios bíblicos recuperados por RAG. Despliegue total del motor exegético: análisis de proposiciones, hermenéutica avanzada, teología sistemática.

### 6.5 Metodología específica por libro (herencia progresiva)
La NBEI es la base metodológica común, pero cada libro de la Biblia tiene su propia introducción y enfoque específico de estudio (contexto histórico, género literario, estructura, propósito del autor). Cuando el ETL ingiere el material introductorio de un libro específico (ej. la introducción a Romanos), este se guarda como una **capa adicional** de metodología en el archivo de metadatos interno (ver sección 4 y la Directiva de evolución del contexto, sección 9), y se inyecta en el RAG junto con la base NBEI cuando el usuario estudia ese libro puntual. La base NBEI nunca se reemplaza — solo se complementa.

## 7. Discipulado Familiar Integrado
Módulo que traslada el estudio personal a la mesa del hogar: traduce conceptos teológicos complejos a lenguaje cotidiano, con guías prácticas, preguntas de debate sencillas y motivos de oración para compartir en familia. Interfaz fluida, adaptada para lectura horizontal en tableta.

## 8. Prompt Base del Sistema (System Prompt)
*Todo modelo de lenguaje integrado en esta aplicación debe inicializarse con el siguiente contexto:*

```
Actúa como un asistente de estudio bíblico estrictamente alineado a la sana doctrina de la congregación local. Tu única fuente de verdad son los fragmentos de contexto recuperados por el sistema RAG en este turno. No usas conocimiento teológico general almacenado en tu entrenamiento salvo como respaldo gramatical/histórico neutro (fechas, idioma original, geografía), nunca como fuente doctrinal.

JERARQUÍA DOCTRINAL (en este orden de autoridad):
1. Texto bíblico (inerrante, autoridad suprema).
2. `apreciacion_de_iglesia.md` — lente hermenéutico principal. Ante cualquier tensión interpretativa, este archivo decide.
3. Confesiones y credos históricos recuperados (incl. Confesión de 1689) — marco de soporte secundario, nunca contradice al punto 2.

REGLA INQUEBRANTABLE DE PROFUNDIDAD Y CITAS:
Debes responder con máxima profundidad. Los devocionales familiares deben contener al menos 3 párrafos completos. Los estudios personales deben desglosar el texto versículo por versículo. Estás obligado a citar explícitamente al menos 3 fuentes de los metadatos entregados. Si no lo haces, serás penalizado. Tu única fuente de verdad es el texto bíblico, el documento apreciacion_de_iglesia.md y los credos provistos en el contexto.

REGLA DE CONTEXTO INSUFICIENTE (fallback educativo con transparencia total — aplica a TODOS los módulos, incluida interpretación doctrinal directa):
Si los fragmentos recuperados no alcanzan para fundamentar completamente la respuesta, no te niegues por completo: generá el contenido igual usando conocimiento teológico general ortodoxo/evangélico (nunca posturas liberales, heterodoxas ni "balances" entre posiciones en conflicto), pero:
1. Marcá `"fallback_no_rag": true` en la salida estructurada.
2. Completá `recommended_resources` con qué convendría indexar para fundamentar mejor esto en el futuro — sé específico (ej. "comentario expositivo de 2 Tesalonicenses", "material de escatología paulina"), no genérico ("más libros").
3. Si SÍ hay fragmentos reales recuperados (aunque sean parciales), tienen prioridad total sobre tu conocimiento general — nunca los contradigas ni los ignores para preferir tu propia formulación.
4. Esta es la única regla de contexto insuficiente del sistema — reemplaza cualquier distinción anterior entre nivel doctrinal y metodológico. El objetivo es que la necesidad de este fallback vaya desapareciendo a medida que la biblioteca crece, no bloquear al usuario mientras tanto.

FORMATO DE SALIDA ESTRUCTURADA (obligatorio para todos los módulos, no solo el fallback):
Responde siempre como JSON con esta forma:
{
  "content": "<el texto de la respuesta>",
  "sources_used": ["<ids o referencias de los fragmentos RAG efectivamente usados>"],
  "fallback_no_rag": <true|false>,
  "recommended_resources": ["<tema/tipo de recurso a indexar, solo si fallback_no_rag=true>"]
}
La capa de Streamlit es responsable de renderizar el banner de advertencia cuando `fallback_no_rag` sea true — el LLM no debe intentar dibujar la advertencia dentro de `content` como texto libre, solo debe setear el flag correctamente.

REGLA DE VERIFICACIÓN DE FUENTE (obligatoria):
Antes de citar un versículo, un credo o `apreciacion_de_iglesia.md`, confirma que ese fragmento específico está presente en el contexto entregado en este turno. Nunca cites de memoria. Si citas un versículo, indica siempre la referencia (libro capítulo:versículo).
El nombre del pasaje que el usuario pidió estudiar (ej. "2 Tesalonicenses 1") NO cuenta como fuente en `sources_used` — ese dato ya lo tenías antes de buscar nada. Para que `fallback_no_rag` sea `false`, `sources_used` debe contener al menos un fragmento de comentario, credo o `apreciacion_de_iglesia.md` efectivamente recuperado por el RAG. Si tu interpretación, explicación o analogía no se apoya en ninguno de esos fragmentos, aplicá la regla de contexto insuficiente (fallback educativo) — no marques `fallback_no_rag: false` solo porque el usuario mencionó el pasaje.

USO DEL CONTEXTO VITAL DEL USUARIO (perfil personal, sección 13.1):
- Se usa ÚNICAMENTE en la fase de Aplicación del modo `estudio_personal`, para el propio usuario, y como máximo un dato de contexto por respuesta.
- NUNCA se usa como fuente de analogías en modo `discipulado_familiar`. Ese modo habla de/para otras personas (cónyuge, hijos) — tu profesión, hobbies o rutina diaria son irrelevantes para explicarle algo a un niño. Si el modo es `discipulado_familiar` y existe un parámetro `audiencia` (edad/perfil de a quién va dirigido), las analogías se adaptan a esa audiencia, no al usuario principal. Si no hay `audiencia` declarada, usa un lenguaje simple y neutro, sin inventar un perfil.
- Nunca combines más de un dato de contexto en una misma analogía (evitar sumar trabajo + comida + lo que sea) — un solo anclaje relevante, o ninguno.

REGLA DE INFERENCIA VS. DOCTRINA EXPLÍCITA:
Si tu respuesta incluye una conclusión que no está dicha literalmente en las fuentes sino que es una inferencia razonable a partir de ellas, márcala con la frase "Esto se puede inferir de...". Nunca presentes una inferencia propia como si fuera doctrina explícita de la iglesia.

METODOLOGÍA DE ESTUDIO INDUCTIVO — NBEI (obligatoria cuando el modo activo sea Estudio Inductivo):
Sigue siempre el método de la Nueva Biblia de Estudio Inductivo (NBEI): Observación → Interpretación → Aplicación, en ese orden. Nunca interpretes un pasaje sin haber completado primero la observación correspondiente al nivel activo. Si el contexto recuperado incluye una introducción o metodología específica para el libro que se está estudiando, aplícala como capa adicional sin contradecir ni reemplazar la base NBEI.

NIVEL DE ESTUDIO (parámetro de entrada: principiante | moderado | complejo):
- Si no se especifica, usa "moderado" por defecto y acláralo en tu respuesta.
- Principiante: solo el Paso 2 de Observación NBEI (seis preguntas básicas, reducidas a 3 preguntas cerradas) + Paso 9 (una lección para la vida, simplificada). Apoyo visual fuerte. Sin Interpretación formal ni Aplicación en 4 ejes.
- Moderado: Pasos 2, 3, 5 y 7 de Observación NBEI (preguntas básicas, palabras clave, contrastes/comparaciones, términos de conclusión) + pautas 1 y 2 de Interpretación NBEI (contexto rige, todo el consejo de la Palabra). Exige que el usuario identifique la estructura gramatical y cruce el texto con referencias históricas básicas, sin resolverlo por él.
- Complejo: los 10 pasos de Observación NBEI, las 6 pautas de Interpretación NBEI y los 4 ejes de Aplicación NBEI (enseñanza, reprensión, corrección, instrucción en justicia). Exige que el usuario proponga su propia conclusión antes de contrastarla con comentarios.

MODO DE SALIDA (parámetro de entrada: estudio_personal | discipulado_familiar):
- estudio_personal: profundidad según nivel configurado.
- discipulado_familiar: si existe un análisis fundamentado previo (`estudio_personal` con fuentes reales), tradúcelo a lenguaje cotidiano. Si no existe, aplicá el fallback educativo (regla de contexto insuficiente) directamente en este modo, adaptando el lenguaje a la `audiencia` declarada y marcando `fallback_no_rag`. No mezcles ambos formatos en una sola respuesta.

RUTAS DE ARCHIVOS (mapas, GeoJSON, audio):
Solo devuelve un `file_path` si viene explícitamente en los metadatos del contexto recuperado. Nunca inventes ni infieras una ruta.

MÓDULO DE ANÁLISIS PROPOSICIONAL (cuando se invoque este modo):
Analiza el texto bíblico de forma proposicional: 1) Identifica la cláusula principal. 2) Separa las cláusulas subordinadas mediante saltos de línea e indentación. 3) Resalta en negrita los conectores lógicos (Porque, Por tanto, Pero, Y, Si). 4) No interpretes el texto, solo revela su estructura gramatical.

FORMATO Y ESTILO (obligatorio):
- Español rioplatense/neutro correcto. Evita explícitamente: "propositiones" (usa "proposiciones"), "asitencia" (usa "asistencia"), calcos del inglés como "aplicar para" (usa "postularse/solicitar"), "eventualmente" con sentido de "finalmente" en vez de "posiblemente".
- Antes de entregar la respuesta final, revisa mentalmente ortografía y que no haya anglicismos.
- Ante textos narrativos: enfoque en teología bíblica del relato.
- Ante epístolas: desglose lógico de proposiciones.

CERO CREATIVIDAD DOCTRINAL: nunca ofrezcas posturas liberales, nueva revelación, ni "balances" entre posturas teológicas en conflicto cuando `apreciacion_de_iglesia.md` ya tomó una posición.
```

### Changelog del prompt (por qué se agregó cada regla)

| Problema típico en bots RAG | Mitigación agregada |
|---|---|
| El modelo "rellena" cuando el RAG no trae nada relevante | Regla de **contexto insuficiente** con respuesta obligatoria estándar |
| Cita referencias que no vinieron en los fragmentos recuperados | Regla de **verificación de fuente** |
| El límite de palabras se ignora en la práctica | Instrucción dura de formato + auto-conteo |
| Anglicismos / errores ortográficos recurrentes | Lista negra concreta + autorrevisión final |
| Mezcla de niveles de estudio | Default explícito (Moderado) si no viene especificado |
| Confusión entre inferencia propia y doctrina explícita | Obliga a marcar "Esto se puede inferir de..." |
| Rutas de archivos geográficos inventadas | Solo devuelve `file_path` si viene en los metadatos |
| Mezcla de modo estudio personal / familiar | `modo_salida` como parámetro obligatorio de entrada |

## 9. Módulos Nuevos y Avanzados (Fase 6 — ver roadmap en sección 10)

**A. Buscador Temático (Topic Engine):** el usuario ingresa un tema (ej. "La Gracia", "Adoración Familiar"); el sistema recupera fragmentos de libros, predicaciones transcritas, diccionarios y comentarios, y la IA orquesta un estudio estructurado. **Obligatorio:** cada punto del estudio debe citar la fuente local recuperada (ver regla de verificación de fuente, sección 8).

**B. Análisis Proposicional:** desglose gramatical de epístolas. Ver instrucciones específicas ya integradas en el System Prompt (sección 8).

**C. Orquestador de Lentes (Multi-Lens Exegesis):** botonera en la UI para filtrar la recuperación RAG por tipo de recurso (Lente Inductivo, Lente Eclesiológico 9Marcas, Lente Histórico), ofreciendo distintas perspectivas del mismo pasaje. Reemplaza/absorbe lo que antes eran "Tabs Dinámicos" — es el mismo concepto de exponer distintas herramientas exegéticas, pero con selector explícito de lente en vez de pestañas fijas. **Nota de cobertura:** este módulo depende de tener contenido indexado y *etiquetado por tipo de lente y libro* — no alcanza con tener la Biblia y un comentario general (ver sección 8, regla de contexto insuficiente nivel metodológico, para el comportamiento cuando falta cobertura).

**D. Traductor "Seminario → Mesa Familiar":** botón que toma un análisis exegético complejo ya generado y lo reescribe con un prompt estricto para producir un devocional de ~10 minutos, con analogías sencillas para `Esposa_Prueba` o `Hijo_Prueba` (ver regla de datos de prueba, sección 2) y un motivo de oración.

**E. Generador de Roadmaps / Syllabus:** transforma un tema amplio (ej. "Paternidad Bíblica") en un plan secuencial de varias semanas con lecturas diarias de ~15 minutos. El progreso se guarda en SQLite y se integra visualmente con el Calendario y el Tracker de Gracia. **Componente de UI recomendado: `streamlit-calendar`** (basado en FullCalendar) — vistas mes/semana/lista, drag&drop para reprogramar lecturas, callbacks de click/selección, tema claro/oscuro nativo de Streamlit. Evitar armar un calendario custom desde cero; los eventos se arman como lista de dicts `{title, start, end}` a partir de las filas de SQLite.

**F. Panel de Referencias Cruzadas (Verse-Level):** al seleccionar un pasaje, mostrar automáticamente contexto histórico/cultural, comentarios locales, menciones en predicaciones transcritas y análisis de griego/hebreo — usando coincidencias exactas de metadatos (Libro, Capítulo, Versículo), no búsqueda difusa. **Fuente primaria obligatoria: la tabla de referencias cruzadas de OpenBible (sección 12.2), consultada por lookup exacto libro-capítulo-versículo.** La búsqueda vectorial genérica sobre la biblioteca (comentarios, libros indexados) es un complemento *después* de resolver las referencias cruzadas reales, nunca un sustituto — si el panel solo devuelve resultados de similitud semántica sin pasar por la tabla de OpenBible, el módulo está mal implementado, no es un caso de "biblioteca insuficiente".

**G. Simulador de Evangelismo (Roleplay Bot):** entorno de chat donde la IA actúa como un compañero no creyente (persona ficticia, nunca basada en una persona real). Evalúa las respuestas del usuario cruzándolas con los PDFs de evangelización/apologética de la biblioteca. Este módulo es conversacional y de práctica, no doctrinal en sí mismo — pero cualquier afirmación que la IA haga *como personaje* sobre teología cristiana sigue sujeta a la Jerarquía Doctrinal (sección 3).

**H. Gimnasio Hermenéutico (Práctica Activa):** módulo tipo quiz donde la IA oculta la respuesta y desafía al usuario a aplicar reglas de poesía hebrea o de epístolas (ej. identificar conectores lógicos, paralelismos), dando retroalimentación después de que el usuario responde — no antes.

**I. Alertas de Aplicación (Diario de la Vida Real):** muro de reflexión donde el usuario vuelca luchas personales (laborales, familiares); el RAG cruza la situación descrita con manuales de santidad/consejería bíblica indexados para devolver un mini-estudio focalizado.

**J. Auditoría Doctrinal por Lotes:** script automatizado que evalúa los nuevos archivos `.md` (extraídos de PDFs) contra la Confesión de 1689, buscando errores carismáticos/pentecostales. Clasifica los recursos en `[Alineado]`, `[Precaución]`, `[Descartar]` o `[Pendiente]`. Los recursos sugeridos entran por defecto como `[Pendiente]` hasta que se cargue y analice su PDF.

**K. Backlog Automático de Recursos:** la IA detecta proactivamente "vacíos" de información durante las consultas del usuario y registra estos faltantes (ej. "Falta biografía de Hudson Taylor") en SQLite (`temas_pendientes`). La UI expone este backlog para priorizar adquisiciones literarias.

**L. Panel de Administración Centralizado (`ui/admin_panel.py`):** módulo visual exclusivo para administradores (`ADMIN_USERS`). Centraliza herramientas de mantenimiento: Analizador de Discrepancias (PDF vs MD para detectar OCRs defectuosos), Limpiador de Huérfanos en SQLite, Verificador del Esquema de Base de Datos, Sincronización Incremental, Disparador de Reconstrucción Blue-Green en segundo plano, Auditoría Doctrinal por Lotes y Extracción Loteada del Grafo de Conocimiento.

**M. Grafo de Conocimiento Semántico (GraphRAG):** red de entidades teológicas (conceptos, personas, libros, doctrinas) y relaciones semánticas ("enseña sobre", "justifica", "escribió") persistidas en las tablas `graph_nodes` y `graph_edges`. Se extrae utilizando el modelo local gratuito de Ollama (`llama3.1`) para proteger la cuota de la API de Gemini. En tiempo de consulta, `RAGService.retrieve_subgraph()` extrae las relaciones asociadas a los términos clave y las prepende al prompt del LLM como contexto de máxima fidelidad.

**N. Reconstrucción Asíncrona Blue-Green (Zero-Downtime Rebuild):** mecanismo para re-indexar y limpiar por completo la base de datos relacional y vectorial (`biblico_blue.db` y `vector_db_blue`) en segundo plano sin bloquear ni degradar la experiencia de los usuarios activos. Al finalizar el procesamiento total, se realiza un intercambio atómico en caliente (Swap) reemplazando la base de datos previa por la nueva de forma transparente.

**Directiva de evolución del contexto:** al ingerir nuevos documentos (ej. una Biblia de Estudio Teológico o un manual de paternidad), el pipeline ETL extrae reglas/metodologías del libro y las guarda en el archivo de metadatos interno (sección 4). El System Prompt lee ese archivo dinámicamente, ampliando sus herramientas de estudio a medida que crece la biblioteca.

## 10. Fases del Proyecto y Estado

| Fase | Contenido | Estado |
|---|---|---|
| 1 | Entorno Multi-Usuario, Tracker de Gracia, Feedback Beta, diario espiritual | `[COMPLETADO]` |
| 2 | Pipeline ETL, Vector Database, motor "On-Demand", escalado de dificultad | `[COMPLETADO]` |
| 3 | Ecosistema Iglesia Local: transcripción Whisper con hash antiduplicado | `[COMPLETADO]` |
| 4 | Mapeo temático y referencias cruzadas automáticas | `[COMPLETADO]` |
| 5 | Indexación masiva de Biblias JSON + enriquecimiento OpenBible (cron semanal, rollback ante fallos) | `[COMPLETADO]` |
| 6 | Topic Engine, Análisis Proposicional, Orquestador de Lentes, Traductor Familiar, Roadmaps, Panel de Referencias Cruzadas, Simulador de Evangelismo, Gimnasio Hermenéutico, Alertas de Aplicación | `[COMPLETADO]` |
| 7 | Sistema de Consciencia y Notificaciones: integración con Discord/Telegram Webhooks para "Recordatorios de Gracia" basados en el estudio diario | `[COMPLETADO]` |
| 8 | Auditoría Doctrinal por Lotes (filtros de 1689) y Backlog Automático de Recursos | `[COMPLETADO]` |
| 9 | Reconstrucción Blue-Green Zero-Downtime, Panel de Administración UI y Grafo de Conocimiento Semántico (GraphRAG con Ollama local) | `[COMPLETADO]` |

## 11. Estrategia de Modelos IA y Fallbacks

**Diagnóstico previo:** Gemini 3.7 Flash muestra, según benchmarks independientes, una tasa de alucinación mayor que 3.6 Flash, y la propia ficha de modelo de Google reconoce "lentitud ocasional o problemas de timeout". Desde abril de 2026, Google exige topes de gasto obligatorios (`mandatory spend caps`) incluso en tier gratuito — antes de rediseñar la cascada, verificar que la key no esté pegando contra ese tope (se manifiesta como fallos intermitentes indistinguibles de un problema del modelo).

**Principio de diseño:** la cascada es **configuración, no código hardcodeado** — una lista ordenada en `.env`/config, para poder reordenar o sacar un proveedor sin redeploy cuando cambien límites (los free tiers de estos proveedores cambian sin aviso). Casi todos los proveedores de abajo son **compatibles con el SDK de OpenAI** (mismo `base_url` + `api_key` + nombre de modelo) — conviene una única clase cliente genérica en vez de un SDK distinto por proveedor.

**Principio de privacidad:** los tiers gratuitos de proveedores agregadores/terceros (OpenRouter, Eden AI, Z.AI) suelen entrenar sus modelos con los prompts que reciben salvo que se pague. Nunca enrutar por ahí contenido de la partición de **datos privados** (Contexto Vital, diario, Radar de Gracia — sección 2, Multi-Tenant); reservar esos casos para Google AI Studio (con billing propio) o el fallback local de Ollama.

### 11.1 Matriz de Modelos Gemini Gratuitos por Tiers (Nivel de Razonamiento y Especialización)

Se incorpora la suite completa de modelos Gemini gratuitos clasificados por Tiers jerárquicos según su nivel de razonamiento, capacidad analítica y caso de uso óptimo dentro de la aplicación:

| Modelo | Tier | Nivel de Razonamiento | Ventana de Contexto | Mejor Caso de Uso |
|---|---|---|---|---|
| **Gemini 3.8 Flash** | **S** | Muy Alto | 1M tokens | RAG profundo, agentes autónomos, arquitectura y código complejo. |
| **Gemini 2.5 Pro** | **S** | Muy Alto | 1M tokens | Deducciones lógicas profundas y auditorías detalladas (a menor RPM). |
| **Gemini 3.7 Flash** | **A** | Alto | 1M tokens | Flujos de código ágiles, multi-step execution y chat avanzado. |
| **Gemini 3.6 Flash** | **A** | Alto | 1M tokens | Fidelidad documental estricta, RAG sin desvíos y extracción. |
| **Gemini 3.5 Flash** | **B** | Medio-Alto | 1M tokens | Respuestas generales y consultas de mediana complejidad. |
| **Gemini 2.5 Flash** | **B** | Medio | 1M tokens | Tareas operativas rápidas y chats estándar. |
| **Gemini 3.5 / 3.1 Flash-Lite** | **C** | Rápido / Básico | 1M tokens | Clasificación de metadatos, resúmenes cortos y etiquetado masivo. |
| **Gemini 2.5 Flash-Lite** | **D** | Muy Básico | 1M tokens | Filtros sintácticos simples y operaciones de cuota ultrabaja. |

### 11.2 Cascada Multitier y Ruteo por Módulo

La orquestación se delega a `TierRouter` (`llm/tier_router.py`) y al proxy de telemetría LiteLLM (`litellm_config.yaml`), estructurando las llamadas según la exigencia analítica:

**Tier 1 — Contexto Grande y Razonamiento Crítico (Tiers S y A de Gemini)**
*Uso exclusivo para:* Generación de guías de estudio, Motor RAG de Precisión, Topic Engine, Orquestador de Lentes y Auditoría Doctrinal contra la Confesión Bautista de 1689.
1. `gemini-3.8-flash` (Tier S): Primer intento para RAG profundo, ensamble de perícopas amplias y síntesis teológica de máxima fidelidad.
2. `gemini-2.5-pro` (Tier S): Deducciones lógicas profundas, auditorías doctrinales automatizadas y dictámenes exegéticos de alta exigencia.
3. `gemini-3.7-flash` (Tier A): Fallback ágil para flujos interactivos complejos y multi-step execution.
4. `gemini-3.6-flash` (Tier A): Extracción exegética estricta y anclaje documental sin desvíos.
5. `eden-ai-gemma4` (Fallback secundario si hay saldo disponible).

**Tier 2 — Disponibilidad y Velocidad (Tier B de Gemini + Proveedores Cloud)**
*Uso para:* Turnos conversacionales cortos, Simulador de Evangelismo, Gimnasio Hermenéutico y respuestas rápidas.
1. `gemini-3.5-flash` (Tier B): Consultas de mediana complejidad y respuestas devocionales.
2. `gemini-2.5-flash` (Tier B): Chats operacionales rápidos y simuladores interactivos.
3. `groq-gpt-oss-120b` / `groq-qwen-27b`: Alternativas de ultra-baja latencia cuando se requiera respuesta instantánea.
4. `mistral` / `openrouter` / `zai`: Proveedores de respaldo para alta concurrencia.

**Tier 3 — Tareas Cortas, Clasificación y Metadatos (Tiers C y D de Gemini + Cerebras)**
*Uso para:* Extracción de metadatos en ETL, resúmenes de una línea, hashing de perícopas y saneamiento de texto.
1. `gemini-3.5-flash-lite` / `gemini-3.1-flash-lite` (Tier C): Clasificación documental y etiquetado masivo con 1M de tokens y consumo mínimo de cuota.
2. `gemini-2.5-flash-lite` (Tier D): Filtros sintácticos y operaciones ultrarrápidas de cuota casi nula.
3. `cerebras` (Llama 3.3 70B capado a 8K tokens): Inferencia acelerada por hardware para micro-tareas.

### 11.3 Escalón casi-gratis antes de caer a local
Si toda la cascada gratuita se agota el mismo día: **DeepSeek V4 Flash** (~$0.14 input / $0.28 output por 1M tokens) es lo suficientemente barato como para tratarlo como un "seguro" de bajo costo antes de forzar todo a Ollama local.

### 11.4 Ollama local (Tier 4 y Extracción Pesada de GraphRAG)
Ollama local (`llama3.1` corriendo en `http://localhost:11434`) cumple tres funciones estratégicas en la arquitectura:
1. **Tier 4 Local (Fallback definitivo y Análisis Proposicional):** Mapeado en `task_tier_map` (`propositional_format` y `propositional_analysis`), permitiendo formatear cláusulas bíblicas sin gastar cuota de API, y sirviendo de respaldo cuando no hay conexión a internet o fallan los proveedores cloud.
2. **Motor de Ingesta para GraphRAG:** Extracción masiva de entidades y relaciones semánticas (`services/graph_service.py`). Al ser un proceso intensivo que analiza miles de fragmentos, el uso de Ollama local evita drenar la cuota de la API de Gemini.
3. **Resumen de Documentos Masivos:** Libros de 2.000-3.000 páginas sin límites de rate artificiales.

Cada modelo de la cascada debe recibir el mismo System Prompt (sección 8) sin excepciones — las reglas de contexto insuficiente y verificación de fuente son especialmente importantes en los modelos más "creativos" ante contexto débil.

## 12. Fuentes de Datos RAG — Referencia Técnica (ETL)

### 12.1 APIs de texto bíblico

| Fuente | Auth | Formatos | Notas de implementación |
|---|---|---|---|
| **Bolls Life API** | Ninguna | JSON, HTML | 148+ versiones, incluye griego/hebreo y léxicos (BDB, Thayer, Strong). POST con array de versículos `[1,2,3]` para pericopas. **No** raspar versículo por versículo — descargar los paquetes JSON completos para uso intensivo. Ideal como fuente primaria offline. |
| **API.bible (American Bible Society)** | API Key | JSON, XML, HTML | Miles de versiones con licencia, SLA alto. Uso empresarial/institucional. |
| **Bible SuperSearch** | Ninguna (1000 req/día gratis) | REST, GraphQL | Búsquedas booleanas con exclusión (`-condemn`) y filtros de testamento. |
| **API RVR1960 (Samuel David de la Cruz / AWS)** | Ninguna | JSON | Solo RVR1960. Histórico de caídas por picos de tráfico — no usar como única fuente. |

### 12.2 Referencias cruzadas y grafo temático
*   **OpenBible.info:** ~340.000 referencias cruzadas (base Treasury of Scripture Knowledge). Descarga libre en CSV/ZIP. Permite recorrer un grafo en vez de depender solo de similitud vectorial — más fiel a la hermenéutica de "Escritura interpreta Escritura".
*   Existe una versión empaquetada como bóveda Obsidian (Markdown, ~32.500 notas atómicas por versículo/capítulo/libro/tópico) — útil para migrar directo a SQLite FTS5 o a un grafo tipo Neo4j.

### 12.3 Corpus teológico para vectorizar (por ministerio)

| Fuente | Enfoque | Formato típico |
|---|---|---|
| Coalición por el Evangelio (TGC) | Teología reformada general, vida cristiana práctica | eBooks, artículos |
| 9Marcas (9Marks) | Eclesiología: las 9 marcas de una iglesia sana | PDF (libros, revista, guías de estudio inductivo) |
| Desiring God (John Piper) | Teología afectiva, hedonismo cristiano | PDF/EPUB |
| Third Millennium Ministries (ThirdMill) | Teología sistemática, teología bíblica, escatología | Word/texto — preferible al PDF por retención de estructura en el chunking |
| Gracia a Vosotros (John MacArthur) | Exposición versículo por versículo | Transcripciones |
| Chapel Library | Literatura puritana/Reforma (dominio público) | PDF vía API (`?code=X&format=pdf`) |

### 12.4 Formatos propietarios para extracción masiva
*   **e-Sword** (`.bblx`, `.cmtx`, `.dctx`): internamente son bases **SQLite**. Se pueden consultar y exportar directamente con Python/Java sin necesidad de scraping.
*   **The SWORD Project (CrossWire):** módulos en XML (OSIS/ThML/TEI) comprimidos en ZIP, con morfología griega/hebrea y números Strong embebidos. Existen scripts en Python para convertirlos a datos legibles por máquina.

### 12.5 Audio
*   **Bible Brain / Faith Comes By Hearing:** API con key, 1700+ idiomas, streaming MP3 (64kbps) u Ogg Opus (16kbps) para bajo ancho de banda. Soporta "Live Verse Tracking" (resaltado sincronizado con audio).
*   Paquetes ZIP masivos (1-6 GB) de audio narrado en dominio público (vía OpenBible) — mejor servirlos como archivos estáticos propios (ej. S3) que depender de la API externa en cada request.

### 12.6 Motor de embeddings
*   Modelo recomendado: **Qwen3-Embedding-0.6B** cuantizado INT8 — corre local en CPU/ARM64, sin GPU.
*   Debe ser **multilingüe** y sensible al léxico teológico técnico ("expiación penal sustitutoria", "propiciación", "gracia irresistible") — los embeddings generalistas suelen perder esta sutileza semántica.

### 12.7 Enlaces de referencia (recursos en español, descarga manual)
- [Reflexiones - Sociedad Bíblica Argentina](https://www.biblia.sba.org.ar/reflexiones)
- [Recursos – Sociedad Bíblica Argentina](https://sba.org.ar/recursos/)
- [Cursos Coalición por el Evangelio](https://www.coalicionporelevangelio.org/cursos/)
- [Recursos Coalición por el Evangelio](https://www.coalicionporelevangelio.org/recursos/?cat=todos&sort=newest&downloadable=false)
- [Sana Doctrina: Temas Fundamentales](https://www.sanadoctrina.org/temasfundamentales.html)
- [Sana Doctrina: Tratados Doctrinales](https://www.sanadoctrina.org/tratadosdoctrinales.html)
- [Escuela Bíblica: Estudios Bíblicos](https://www.escuelabiblica.com/estudio-biblico.php?id=700)

## 13. Detalle de Fases Pendientes (Ecosistema de Discipulado)

### 13.1 Perfil de "Contexto Vital"
Pestaña en el perfil de `Usuario_Prueba` para ingresar su situación actual en texto plano (ej. "Trabajo remoto, preparándonos para la maternidad, lucho con la constancia"). Este contexto se inyecta en el System Prompt **únicamente** durante la fase de Aplicación del modo `estudio_personal` (sección 6.3/NBEI, sección 8) — nunca en `discipulado_familiar` (ver regla de uso del Contexto Vital, sección 8). **Dato personal — va en la partición de datos privados (sección 2, Multi-Tenant), nunca en la biblioteca pública.**

**Campo `audiencia` (nuevo, requerido para discipulado_familiar):** perfil de a quién va dirigido el devocional — ej. `{"relacion": "hijo", "edad_aprox": 6}` o `{"relacion": "conyuge"}`. Se usa para calibrar vocabulario y analogías (sección 8). Si no está completo, el sistema usa lenguaje simple y neutro por defecto, sin inventar un perfil ni tomar prestado el contexto del usuario principal.

### 13.2 Laboratorio Exegético (detalle de implementación del módulo C/H de la sección 9)
- **Lupa de Observación:** atajo para aplicar el Análisis Proposicional automáticamente sobre el pasaje activo.
- **Orquestador de Lentes:** ver módulo C, sección 9.
- **Gimnasio Hermenéutico:** ver módulo H, sección 9.
- **Diccionario RAG a un clic:** cruce de palabras clave con definiciones doctrinales locales (léxicos Strong/BDB/Thayer, sección 12.1).

### 13.3 Ecosistema de Discipulado Familiar
Detalle de implementación de los módulos D (Traductor Seminario→Mesa) y E (Roadmaps) de la sección 9, aplicados específicamente a paternidad/maternidad — sin agregar módulos nuevos, es la misma arquitectura con datos de ejemplo `Esposa_Prueba`/`Hijo_Prueba`.

### 13.4 Motor y Simulador de Evangelismo Intencional
- **Radar de Gracia:** tabla en SQLite para ingresar nombres de contactos — **dato privado del usuario**, nunca usar nombres reales en seed/testing (sección 2).
- **Simulador de Evangelismo:** ver módulo G, sección 9.

### 13.5 Auditoría de Crecimiento
- **Auditoría 9 Marcas en el Hogar:** autoevaluación semanal que alimenta una gráfica de radar en el dashboard, aplicando las 9 marcas eclesiológicas (sección 3, corpus 9Marcas) al hogar en vez de a la iglesia local.
- **Alertas de Aplicación:** ver módulo I, sección 9.

### 13.6 Procesamiento de Nuevos Recursos (PyMuPDF4LLM)
Conversión automática de PDFs nuevos (`/pdfs_nuevos/`) a Markdown (`/data_raw/`) mediante **PyMuPDF4LLM**, ejecutada en la Sincronización Incremental (ver Invalidación de Caché, sección 5). Los PDFs procesados con éxito se archivan en `/pdfs_procesados/`; los que fallan deben quedar logueados (ver Observabilidad del Pipeline RAG, sección 2) para revisión manual, no silenciosamente descartados.

### 13.7 Sistema de Consciencia y Notificaciones (Fase 7, Discord Webhooks)
- **Bot de Recordatorios de Gracia:** script (`cron_reminders.py`) que corre en segundo plano, conectado vía Webhooks de Discord (config en `.env`, nunca hardcodeado).
- **Mecánica:** consulta SQLite para saber qué capítulo se estudió ese día; el LLM genera un recordatorio exegético/aplicativo corto y lo envía como notificación. Este recordatorio, al ser generado por el LLM, está sujeto a las mismas reglas del System Prompt (sección 8) que cualquier otra salida — incluida la salida estructurada JSON y la regla de contexto insuficiente.

## 14. Pipeline de Extracción Web Automatizada (Web Harvester)

**Objetivo:** reducir la carga manual de descarga (200+ PDFs ya cargados a mano) automatizando la extracción de contenido bíblico gratuito publicado en sitios de ministerios (TGC, 9Marcas, Desiring God, ThirdMill, Gracia a Vosotros, Chapel Library, etc. — ver catálogo en sección 12.3), diferenciando por tipo de contenido.

### 14.1 Catálogo de fuentes
Archivo de configuración (`fuentes_web.yaml` o similar) con, por cada sitio: URL base, tipo de contenido dominante (articulo/curso/audio/word), y si tiene `sitemap.xml` disponible para descubrimiento de URLs. Empezar por los ministerios ya identificados en la sección 12.3 antes de sumar sitios nuevos.

### 14.2 Extractor por tipo de contenido (dispatcher)
Un único dispatcher decide qué extractor usar según el tipo de página:
- **Blogs / artículos / lecciones de curso (HTML):** usar `trafilatura` como extractor primario (elimina menús, ads y boilerplate mucho mejor que un `BeautifulSoup` genérico), con fallback a `readability-lxml` si `trafilatura` no logra extraer contenido limpio. Salida: Markdown. Un curso con varias lecciones se trata como una serie de "artículos" individuales, pero agrupados bajo un mismo `curso_id` en los metadatos para no perder la secuencia pedagógica.
- **Word (.docx):** descargar el archivo y parsear con `python-docx` o `mammoth` — mismo criterio que ya se aplica a los documentos Word de ThirdMill (sección 12.3): retienen mejor la jerarquía de encabezados que el PDF.
- **Audio (mp3):** descargar el archivo y **reutilizar el pipeline de transcripción Whisper ya existente (Fase 3)** en vez de crear una ruta nueva — así hereda automáticamente la validación de hash antiduplicado que ya tenés funcionando.
- **PDF encontrado en una página (no descarga manual):** reutilizar el pipeline PyMuPDF4LLM ya existente (sección 13.6), mismo criterio.

### 14.3 Descubrimiento de URLs
Si el sitio tiene `sitemap.xml`, usarlo. Si no, crawl acotado desde la página de índice/categoría, con una profundidad máxima configurable (evitar crawlear el sitio entero sin límite).

### 14.4 Respeto del sitio de origen (obligatorio)
- Revisar y respetar `robots.txt` de cada sitio antes de crawlear.
- Rate limiting: 1 request cada 2-3 segundos como mínimo, con un User-Agent identificable (no simular un navegador para evadir bloqueos).
- Cachear localmente la respuesta cruda (HTML/mp3/docx) antes de procesar, para poder reintentar el procesamiento sin volver a pegarle al servidor del ministerio si algo falla en la conversión.
- Esto no es solo cortesía técnica: varios de estos ministerios ya avisan explícitamente (ver Bolls Life API, sección 12.1) que no soportan bien el scraping agresivo — el mismo criterio aplica a sus sitios web.

### 14.5 Metadatos obligatorios (ver Calidad de Metadatos, sección 4)
Cada documento extraído debe llevar como mínimo: `source_url`, `ministerio`, `tipo_contenido` (articulo/curso/audio_transcrito/word), `fecha_extraccion`, y una `categoria`/`tema` real asignada en el momento de la extracción — nunca cae por defecto en `"general"`.

### 14.6 Idempotencia
Antes de reprocesar una URL, chequear la tabla de auditoría (misma lógica de Invalidación de Caché, sección 5) para no duplicar contenido si el harvester se corre de nuevo sobre el mismo sitio.

### 14.7 Salida unificada
Todo el contenido extraído (HTML, Word, audio transcrito) cae en `/data_raw/` como Markdown, exactamente igual que el pipeline PyMuPDF4LLM de PDFs — un solo camino downstream para chunking y embeddings, no pipelines paralelos por tipo de fuente.

## 15. Registro de Actualizaciones (Changelog)
*   **[2026-08-14]** Creación del contexto base, Jerarquía RAG, Arquitectura Multi-Tenant.
*   **[2026-08-15]** Reescritura del System Prompt con salvaguardas anti-error, NBEI como metodología base, y separación de la regla de contexto insuficiente en nivel doctrinal (estricto) vs. metodológico (fallback educativo con salida JSON estructurada y observabilidad del pipeline RAG).
*   **[2026-08-15]** Fusión de los módulos de Fase 6 en una sola lista (Topic Engine, Análisis Proposicional, Orquestador de Lentes, Traductor Familiar, Roadmaps, Panel de Referencias Cruzadas, Simulador de Evangelismo, Gimnasio Hermenéutico, Alertas de Aplicación) y de la Fase 7 (notificaciones vía Discord Webhooks); se agrega la sección 13 con el detalle de implementación de cada módulo del ecosistema de discipulado.
*   **[2026-08-15]** Bug detectado en producción: `discipulado_familiar` generó interpretación doctrinal sin fuente real (marcando `fallback_no_rag: false` con `sources_used` conteniendo solo el nombre del pasaje, no un fragmento real) y mezcló el Contexto Vital del usuario principal (profesión, hobbies) en analogías dirigidas a otras personas. Se endurece la regla de verificación de fuente (el nombre del pasaje no cuenta como fuente), se restringe el uso del Contexto Vital exclusivamente a la Aplicación del modo `estudio_personal`, se agrega el campo `audiencia` para calibrar analogías en `discipulado_familiar`, y se obliga a que ese modo traduzca un análisis ya fundamentado en vez de generar interpretación nueva.
*   **[2026-08-15]** Se reconsidera el bloqueo estricto anterior: se unifica en una sola regla de contexto insuficiente (fallback educativo con transparencia total) que aplica a todos los módulos, incluida interpretación doctrinal directa — prioriza avisar qué falta indexar sobre negarse a responder, mientras la biblioteca sigue creciendo. Se detecta que el Panel de Referencias Cruzadas devolvía documentos genéricos (`category: general`) en vez de usar las 340.000 referencias cruzadas de OpenBible; se sospecha un bug único de raíz en el ETL (falta de metadatos reales por chunk) que también explicaría fallos previos del Orquestador de Lentes. Se agrega principio de Calidad de Metadatos obligatoria (sección 4) y se exige que el Panel de Referencias Cruzadas use la tabla de OpenBible por lookup exacto antes que búsqueda semántica genérica.
*   **[2026-08-15]** Se agrega la sección 14: Pipeline de Extracción Web Automatizada (Web Harvester), para reducir la carga manual de descarga de recursos (200+ PDFs cargados a mano hasta ahora). Diferencia extractor por tipo de contenido (HTML vía `trafilatura`, Word vía `python-docx`/`mammoth`, audio reutilizando el pipeline Whisper existente), exige respeto de `robots.txt` y rate limiting, e integra la salida al mismo pipeline unificado en `/data_raw/` que ya usa PyMuPDF4LLM para PDFs.
*   **[2026-08-15]** Se fija NTV como traducción preferida (orden: NTV > RVR1960 > NVI > LBLA) cuando esté disponible. Se recomienda `streamlit-calendar` (FullCalendar) para el Roadmap/Tracker de Gracia en vez de un calendario custom. Se rediseña la cascada de modelos (sección 11) de 3 a 8 proveedores gratuitos investigados (Google AI Studio, Groq, Mistral, OpenRouter, Z.AI, Eden AI, Cerebras) más un escalón casi-gratis (DeepSeek) antes de Ollama local, con la cascada como configuración externa y no hardcodeada. Se documenta que Gemini 3.7 Flash tiene mayor tasa de alucinación reportada que 3.6 Flash y que Google exige spend caps obligatorios en tier gratuito desde abril 2026 — posible causa real de los fallos intermitentes reportados. Se agrega principio de privacidad: datos privados del usuario nunca se enrutan por proveedores agregadores de tier gratuito.
*   **[2026-08-15]** Se reorganiza la sección 11 en 3 tiers explícitos por tamaño de contexto y caso de uso (Contexto Grande / Disponibilidad y Velocidad / Tareas Cortas), con sugerencia de a qué módulo del sistema corresponde cada tier. Se crea prompt de implementación dedicado (`prompt_cascada_modelos.md`) para que el agente del IDE lo aplique de forma aislada del resto del roadmap.
*   **[2026-08-17]** Se implementa el sistema de selección y fallback de modelos LLM por tiers (sección 11). Se crea `data/models_config.yaml` con la configuración externa de 3 tiers + escalón casi-gratis, eliminando los 3 proveedores hardcodeados de `rag_service._call_llm()`. Se crea `llm/llm_client.py` (cliente unificado OpenAI-compatible + wrapper Gemini), `llm/tier_router.py` (selector de tier por módulo, filtrado de privacidad, estimación de tokens, fallback intra-tier). Se refactoriza `services/rag_service.py` para que cada método declare su `module` y `contains_private_data` explícitamente. Se eliminan `llm/strategies/gemini_strategy.py` y `groq_strategy.py` (absorbidas por el cliente unificado). Se agregan 5 tests en `tests/test_tier_router.py` (prompt largo nunca llega a Cerebras, datos privados nunca llegan a agregadores, fallback dentro del tier antes de escalar, mapeo módulo→tier, detección de módulos privados).
*   **[2026-08-17]** Se elimina GitHub Models de la arquitectura debido a que dejó de estar disponible en julio de 2026. Se añade la **Fase 8** al roadmap (sección 10) que incluye dos nuevos módulos (sección 9): la Auditoría Doctrinal por Lotes (filtro automático contra teología carismática/pentecostal usando la Confesión de 1689 para los PDFs ingresantes) y el Backlog Automático de Recursos (la IA registra silenciosamente en SQLite cuando falta información en el RAG para guiar futuras adquisiciones).
*   **[2026-08-17]** Corrección de fallos en el ruteo de la cascada LLM: 1) Se actualizó Groq de `llama-3.3-70b-versatile` (deprecado) a `openai/gpt-oss-120b` en la configuración. 2) Se implementó el wrapper de la API para Eden AI (dejado en deshabilitado por configuración hasta recargar créditos). 3) Se mejoró el manejo de excepciones de `google-genai` usando `traceback` para capturar mensajes de 503. 4) Se integró el Motor de Estudio Temático ("Teólogo Sistemático") con prohibición estricta de micro-exégesis y se implementó la Regla de Profundidad Inquebrantable.
*   **[2026-09-14]** **Implementación de Arquitectura Integral en 6 Fases:**
    - **Fase 0 (Gateway y Observabilidad):** Se implementó `litellm_config.yaml` centralizando modelos bajo `http://localhost:4000/v1` con callback de telemetría a Langfuse. Se creó `docker-compose.yml` para desplegar Langfuse (`langfuse/langfuse:latest`) en puerto 3000 con PostgreSQL dedicado.
    - **Fase 1 (Esquema Bíblico y Persistencia):** Se integraron en `database/connection.py` y `biblico.db` las tablas `document_audit`, `rag_interactions`, `feedback_beta` y `system_settings`.
    - **Fase 1 (Auditoría Doctrinal y Castigo Automático):** Se creó `scripts/doctrinal_audit.py` para clasificar documentos crudos contrastando contra la Confesión Bautista de 1689 antes de vectorizar (`[Alineado]` únicamente). Se implementó `services/feedback_analyzer.py` para auditar `feedback_beta` y degradar/purgar vectores de ChromaDB tras 3 fallos doctrinales reportados vía `delete_document_vectors`.
    - **Fase 1 (Motor RAG de Precisión):** Se implementó `services/retrieval_service.py` con recuperación de candidatos Top 50 del universo `[Alineado]` y re-ranking a Top 15 con Cross-Encoder (`sentence-transformers`). Se inyectó la regla inquebrantable de profundidad y citas en `services/prompt_builder.py`.
    - **Fase 2 (ML para Trading):** Se creó `scripts/optimize_strategy.py` con motor de backtesting técnico, optimización bayesiana de hiperparámetros (RSI, MACD, MA) en 100 trials con Optuna, telemetría en MLflow y persistencia de configuración óptima en `system_settings`.
    - **Fase 3 (Arbitraje P2P y Umbrales Dinámicos):** Se creó `core/dynamic_threshold.py` para leer `Planilla_Arbitraje_Alan.xlsx`, computar el régimen de volatilidad y spread reciente, silenciar alertas en mercados chatos y disparar webhooks inteligentes ante picos de volatilidad.
*   **[2026-09-14]** **Incorporación de la Suite de Modelos Gemini Gratuitos por Tiers:**
    - Se agregaron a la matriz doctrinal y arquitectónica los modelos: **Gemini 3.8 Flash** (Tier S - RAG profundo y orquestación), **Gemini 2.5 Pro** (Tier S - Deducciones lógicas y auditoría 1689), **Gemini 3.7 Flash** (Tier A - Flujos ágiles y multi-step), **Gemini 3.6 Flash** (Tier A - Fidelidad documental y extracción sin desvíos), **Gemini 3.5 Flash** (Tier B - Mediana complejidad), **Gemini 2.5 Flash** (Tier B - Chat estándar), **Gemini 3.5 / 3.1 Flash-Lite** (Tier C - Clasificación ETL y metadatos masivos) y **Gemini 2.5 Flash-Lite** (Tier D - Filtros sintácticos).
    - Se configuraron los nuevos endpoints en `litellm_config.yaml` y la cascada con fallback intra-tier en `data/models_config.yaml`.
*   **[2026-09-20]** **Consolidación Arquitectónica: Panel de Administración, Blue-Green Rebuild y GraphRAG:**
    - **Panel de Administración (`ui/admin_panel.py`):** Centralización de tareas de mantenimiento, eliminando scripts CLI aislados. Incorpora Analizador de Discrepancias (PDF vs MD), Limpiador de Huérfanos, Salud de BD, Sincronización Incremental, Auditoría Doctrinal y Monitoreo/Construcción de GraphRAG.
    - **Reconstrucción Blue-Green Zero-Downtime (`scripts/blue_green_rebuild.py`):** Soporte de variables `SQLITE_DB_PATH` y `CHROMA_DB_PATH` para reprocesamiento asíncrono en segundo plano sobre bases de datos temporales (`biblico_blue.db` y `vector_db_blue`), con swap atómico en caliente sin interrumpir a los usuarios.
    - **Grafo de Conocimiento Semántico (GraphRAG):** Creación de tablas `graph_nodes` y `graph_edges` e implementación de `services/graph_service.py` obligando al uso de Ollama local (`llama3.1`) para extracción de entidades y relaciones teológicas sin consumo de API. Desacoplado de la ingesta básica de embeddings para evitar cuellos de botella e integrado en la recuperación de `generate_study_guide`, `query_topic` y `chat_screen`.
    - **Refactorización Core:** Consolidación de singletons `core/embeddings.py` y `core/vector_db.py`, migración de `PropositionalService` a `TierRouter`, y homogeneización de tests unitarios con mocks herméticos.

---


## 16. Arquitectura de Fases Avanzadas (Fase 0 a Fase 3)

### 16.1 Gateway Unificado LiteLLM y Observabilidad Langfuse (Fase 0)
- **Archivo:** `litellm_config.yaml`
- **Proxy Local:** Expuesto en `http://localhost:4000/v1` unificando proveedores (Gemini 1.5/2.0, Groq LLaMA/Mixtral, OpenAI GPT-4o-mini).
- **Telemetría Centralizada:** `success_callback: ["langfuse"]` registra costos, latencias, prompts y completados.
- **Docker Compose:** `docker-compose.yml` orquesta Langfuse Server (puerto 3000) y PostgreSQL 16 con volúmenes persistentes y healthchecks.

### 16.2 Esquema Relacional de Auditoría y Trazabilidad (Fase 1)
- **`document_audit`:** Registro y filtro sanitario de cada recurso ingestable:
  - `id` (TEXT PK): Hash determinista del archivo.
  - `filename` (TEXT NOT NULL): Nombre del archivo `.md`.
  - `estado` (TEXT): `[Pendiente]`, `[Alineado]`, `[Precaución]`, `[Descartar]`.
  - `fallos_doctrinales_reportados` (INTEGER DEFAULT 0).
- **`rag_interactions`:** Trazabilidad de cada query servido:
  - `id` (TEXT PK), `timestamp`, `query`, `model_used`, `module`, `sources_used`.
- **`feedback_beta`:** Retroalimentación explícita del usuario:
  - `id` (INTEGER PK), `interaction_id` (FK `rag_interactions.id`), `rating` (1 o -1), `motivo`, `comentario_libre`.
- **`system_settings`:** Configuración dinámica del sistema y almacenamiento de modelos/hiperparámetros optimizados por ML.

### 16.3 Microservicio de Auditoría Doctrinal e Ingesta Condicional
- **Script:** `scripts/doctrinal_audit.py`
- **Regla Estricta:** Únicamente los documentos en estado `[Alineado]` se envían al pipeline de embeddings (`VectorService`).
- **Norma Hermenéutica:** Contraste obligatorio contra la *Confesión Bautista de Fe de Londres de 1689* (`data_raw/Credos y Confesiones/La Confesión Bautista de Fe de Londres de 1689.md`).

### 16.4 Proceso Asíncrono de Castigo Automático
- **Servicio:** `services/feedback_analyzer.py`
- **Mecánica:** Proceso en segundo plano que inspecciona `feedback_beta` donde `rating = -1` y `motivo = "Error Doctrinal"`.
- **Penalización:** Identifica los documentos en `sources_used` e incrementa `fallos_doctrinales_reportados`.
- **Purga de Vectores:** Al llegar a 3 fallos acumulados, degrada el estado a `[Precaución]` y purga de ChromaDB todos los fragmentos asociados a ese documento mediante `VectorService.delete_document_vectors(...)`.

### 16.5 Motor RAG de Precisión con Re-ranking Cross-Encoder
- **Servicio:** `services/retrieval_service.py`
- **Extracción de Candidatos (Top 50):** Consulta ChromaDB filtrando exclusivamente los documentos del universo `[Alineado]` (excluyendo descartados o en precaución).
- **Re-ordenamiento de Precisión (Top 15):** Un modelo `CrossEncoder` (`cross-encoder/ms-marco-MiniLM-L-6-v2`) evalúa los 50 pares `(query, fragmento)` asignando un score de relevancia semántica profunda. Devuelve únicamente los mejores 15 fragmentos al LLM.

### 16.6 Evaluación Continua de Calidad RAG y Auto-Backlog (Fase 1)
- **Servicio:** `services/rag_evaluator.py` (`RAGEvaluatorService`)
- **Evaluación Tripartita:**
  - *Fidelidad (`faithfulness`):* Verifica si las afirmaciones de la respuesta generada están respaldadas por las fuentes recuperadas.
  - *Relevancia del Contexto (`context_relevancy`):* Cuantifica si los chunks recuperados son pertinentes para responder al query.
  - *Relevancia de Respuesta (`answer_relevancy`):* Valora la coherencia y dirección de la respuesta frente a la pregunta original.
- **Auto-Backlog:** Si la fidelidad cae por debajo de 0.70 o la relevancia por debajo de 0.60, el sistema genera automáticamente un ticket en `temas_pendientes` con prioridad 'Alta', identificando vacíos documentales en el corpus sin requerir intervención humana.
- **Trazabilidad:** Persiste cada evaluación en la tabla `rag_evaluations` de SQLite.
- **Re-ranking Adaptativo (Bandit/Feedback Loop):** `services/retrieval_service.py` aplica bonificaciones (`+0.15`) o penalizaciones (`-0.10` por fallo reportado) sobre el puntaje del `CrossEncoder`, priorizando dinámicamente los recursos con historial positivo comprobado.

### 16.7 Motor de Machine Learning para Trading (Fase 2)
- **Script:** `scripts/optimize_strategy.py`
- **Backtesting Modular:** Simula estrategias técnicas basadas en RSI, MACD y Medias Móviles con cálculo de Retorno Neto (ROI), Win Rate y número de operaciones.
- **Optuna + MLflow:** Realiza 100 trials bayesianos maximizando el ROI y registrando métricas y parámetros en MLflow. Guarda la mejor configuración en la tabla `system_settings`.

### 16.8 Motor de Arbitraje P2P y Umbrales Dinámicos (Fase 3)
- **Módulo:** `core/dynamic_threshold.py`
- **Lectura Adaptativa:** Lee `Planilla_Arbitraje_Alan.xlsx` con Pandas (creando una plantilla inicial si el archivo no existe).
- **Régimen de Mercado:** Calcula el spread promedio y la volatilidad reciente.
  - *Mercado Chato:* Silencia alertas para evitar saturación y falsos positivos.
  - *Pico de Volatilidad:* Eleva o adapta el umbral dinámico y dispara notificaciones enriquecidas a webhooks de Discord o Telegram.

### 16.9 Grafo de Conocimiento Semántico (GraphRAG)
- **Servicio:** `services/graph_service.py` (`GraphService`)
- **Tablas Relacionales:**
  - `graph_nodes`: `id` (PK), `entity_name` (UNIQUE), `entity_type` (Concepto, Persona, Libro, Doctrina), `description`.
  - `graph_edges`: `id` (INTEGER PK), `source_entity`, `target_entity`, `relationship` (verbo o acción), `resource_id`, `chunk_id`.
- **Extracción de Costo Cero:** Utiliza exclusivamente el modelo local de Ollama (`llama3.1`) vía proxy LiteLLM local para procesar fragmentos sin consumir cuotas de API de Gemini.
- **Desacoplamiento Operativo:** La extracción de entidades está desacoplada del pipeline de embeddings principal (`VectorService`), procesándose en lotes progresivos desde el Panel de Administración o mediante scripts en background con barra de progreso.
- **Inyección en RAG:** Antes de que el LLM responda, `retrieve_subgraph(query)` localiza términos teológicos en la consulta del usuario, recupera las relaciones de 1 salto (1-hop) y las inyecta en el prompt como contexto relacional estructurado.

### 16.10 Reconstrucción Asíncrona Blue-Green (Zero-Downtime Rebuild)
- **Script:** `scripts/blue_green_rebuild.py`
- **Aislamiento por Entorno:** Configura `SQLITE_DB_PATH="biblico_blue.db"` y `CHROMA_DB_PATH="vector_db_blue"`.
- **Ejecución Asíncrona:** Se lanza como subproceso en background desde la UI (`subprocess.Popen(["python", "-m", "scripts.blue_green_rebuild"])`).
- **Swap en Caliente:** Al completarse la vectorización y la auditoría con éxito:
  1. `biblico.db` se renombra a `biblico_old.db` y `biblico_blue.db` se promueve a `biblico.db`.
  2. `vector_db` se renombra a `vector_db_old` y `vector_db_blue` se promueve a `vector_db`.
  3. Los usuarios activos continúan consultando la aplicación sin caídas ni bloqueos de lectura.

### 16.11 Panel de Administración Centralizado (UI)
- **Módulo:** `ui/admin_panel.py`
- **Control de Acceso:** Exclusivo para administradores configurados en `core/constants.py` (`ADMIN_USERS`).
- **Herramientas Integradas:**
  - *Analizador de Discrepancias:* Compara peso de PDFs procesados vs tamaño de `.md` generados para identificar OCRs vacíos o defectuosos y reciclarlos a `pdfs_nuevos/`.
  - *Limpiador de Huérfanos:* Detecta y purga de SQLite referencias a archivos físicos eliminados en `data_raw/`.
  - *Salud del Esquema:* Inspecciona columnas y tipos de todas las tablas activas en SQLite.
  - *Monitoreo y Construcción de GraphRAG:* Muestra métricas en tiempo real de nodos y relaciones con control deslizante para extraer lotes con Ollama local.
  - *Disparadores Operativos:* Sincronización incremental, reconstrucción Blue-Green, auditoría doctrinal por lotes y pruebas de recordatorios en Discord.

---

## 17. Guía de Despliegue y Ejecución del Sistema Multicomponente

A continuación se detalla cómo levantar y operar la plataforma con todos sus servicios y dependencias:

### 17.1 Requisitos Previos y Entorno
1. **Python:** 3.10+ (probado en 3.13 en Windows PowerShell).
2. **Docker Desktop:** Instalado y corriendo para la observabilidad con Langfuse.
3. **Variables de Entorno (`.env`):**
   ```env
   GEMINI_API_KEY=tu_api_key
   GROQ_API_KEY=tu_api_key
   OPENAI_API_KEY=tu_api_key
   DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
   TELEGRAM_BOT_TOKEN=tu_token_opcional
   TELEGRAM_CHAT_ID=tu_chat_id_opcional
   ```

### 17.2 Paso 1: Levantar Observabilidad con Langfuse (Docker)
En una terminal:
```powershell
docker compose up -d
```
- Dashboard disponible en: `http://localhost:3000`
- Primera vez: Crea tu cuenta local y genera las claves de proyecto para Langfuse si deseas sincronizarlas con LiteLLM.

### 17.3 Paso 2: Levantar el Gateway de LLMs (LiteLLM Proxy)
En una terminal dedicada:
```powershell
litellm --config litellm_config.yaml --port 4000
```
- Endpoint OpenAI-compatible activo en: `http://localhost:4000/v1`
- Todos los modelos y llamadas quedarán telemetrizados en Langfuse automáticamente.

### 17.4 Paso 3: Inicializar la Base de Datos Relacional
Para asegurar que todas las tablas canónicas y migraciones estén al día:
```powershell
python database/connection.py
```

### 17.5 Paso 4: Levantar la Aplicación Web (Streamlit)
En la terminal principal:
```powershell
streamlit run app.py
```
- Acceso local: `http://localhost:8501`

### 17.6 Paso 5: Ejecución de Tareas de Fondo y Microservicios Especializados
- **Auditoría Doctrinal e Ingesta:**
  ```powershell
  python scripts/doctrinal_audit.py
  ```
- **Monitoreo Asíncrono de Feedback y Castigo Doctrinal:**
  ```powershell
  python services/feedback_analyzer.py
  ```
- **Optimización de Estrategias de Trading con Optuna y MLflow:**
  ```powershell
  python scripts/optimize_strategy.py
  ```
  *(Opcional para ver dashboard de MLflow: `mlflow ui` en `http://localhost:5000`)*
- **Monitor de Umbrales Dinámicos de Arbitraje P2P:**
  ```powershell
  python core/dynamic_threshold.py
  ```
- **Reconstrucción Total de Biblioteca (Blue-Green Zero-Downtime):**
  ```powershell
  python -m scripts.blue_green_rebuild
  ```

### 17.7 Diagnóstico y Resoluciones Clave del Stack (Fase 0 y Fase 1)
1. **Carga Automática de Variables de Entorno (`.env`):**
   - Se configuró la carga automática vía `dotenv.load_dotenv()` en todos los módulos (`llm/llm_client.py`, `llm/tier_router.py`, `database/connection.py`, `scripts/doctrinal_audit.py`, `services/retrieval_service.py`, `services/rag_evaluator.py`).
   - El script maestro `start_full_stack.ps1` parsea y exporta dinámicamente `.env` al proceso PowerShell para que todos los binarios hijos (`docker`, `litellm`, `streamlit`) hereden las credenciales.
2. **Deduplicación Robusta e Ingesta SQLite (`md5_hash` y `filepath`):**
   - En `scripts/doctrinal_audit.py`, la vectorización verifica simultáneamente `md5_hash`, rutas relativas y absolutas, evitando violaciones de unicidad (`UNIQUE constraint failed: resources.md5_hash`) y normalizando las rutas.
3. **Compatibilidad LiteLLM y Langfuse:**
   - Se fijó la versión de Langfuse a `langfuse<3.0.0` (v2.60.10) para garantizar total compatibilidad con los callbacks de LiteLLM (`litellm.integrations.langfuse`).
4. **Detección Automática de Docker y Ollama en Windows:**
   - `start_full_stack.ps1` localiza el binario de Docker Desktop (`$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin`) y de Ollama, iniciando servicios locales en segundo plano cuando no están activos y permitiendo continuar sin bloquear si Docker no está inicializado.