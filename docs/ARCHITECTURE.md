# Arquitectura de pianomatic

Coach de piano local, 100% open-source. Objetivo: llevar a alguien de cero a
tocar piano con soltura real (partitura, oído, memoria) para disfrute
familiar — no formar concertistas. Ancla de progreso: syllabus ABRSM/RCM,
meta de graduación grado 5-6.

Cuatro pilares de la habilidad musical, cuatro módulos de software. Solo uno
(repertorio) tiene motor propio; el resto se apoya en el ecosistema
open-source existente en vez de reinventarse.

## 1. Repertorio (v1, el único implementado por ahora)

Comparar tu ejecución MIDI de una pieza contra una referencia.

- **Captura**: `mido` + `python-rtmidi` — timestamps de NOTE_ON/NOTE_OFF.
- **Alineación**: [`matchmaker`](https://github.com/pymatchmaker/matchmaker)
  (ISMIR 2025) — score-following ya resuelto y evaluado en datasets reales
  (ASAP), no se reimplementa DTW a mano.
- **Diff**: por dimensión separada — timing, pitch, dinámica/velocity — nunca
  un solo score (la crítica pedagógica a apps comerciales es unánime en esto).
  Umbral de sensibilidad: >20-50ms de desviación (JND humano medido en
  investigación de percepción de ritmo).
- **Reporte**: texto plano en v1. Feedback en dos capas más adelante:
  inmediato simple en vivo + reflexivo vía LLM local (Ollama) al día
  siguiente — el research de neurociencia muestra que ambos tiempos sirven
  a objetivos distintos (precisión temprana vs retención).

## 2. Lectura a primera vista (pendiente)

No usa la referencia fija del pilar 1 — necesita material NUEVO cada vez.

- Generación procedural: [Open Sheet Music Education](https://opensheetmusiceducation.org/)
  (BSD-3) o adaptar [`ftrain/sightreading`](https://github.com/ftrain/sightreading)
  (LGPL-3.0, ya tiene entrada MIDI en vivo y 23 niveles).
- Render: **OpenSheetMusicDisplay (OSMD)** — Cursor API resalta la nota
  actual en tiempo real sincronizado con MIDI, exactamente nuestro caso de
  uso. BSD-3.

## 3. Oído (pendiente)

Único pilar sin alternativa OSS viva y mantenida — GNU Solfege es GUI-only
y su última versión estable es de 2016, sin API. Se construye chico y propio
(quiz de intervalos/acordes, un par de cientos de líneas).

## 4. Técnica (pendiente)

Reutiliza el mismo motor de diff del pilar 1, pero contra patrones
(escalas/arpegios) en vez de piezas completas.

## Contenido / catálogo de canciones

- **Clásico**: [Piano Syllabus Dataset](https://zenodo.org/records/14794592)
  (CC) — 7,901 grabaciones ya anotadas por nivel ABRSM/RCM/Trinity, MIDI
  incluido. Resuelve la curación de repertorio graduado sin trabajo manual.
  Fuente secundaria de MusicXML: [OpenScore corpus](https://github.com/eduardomourar/music-scores-musicxml).
  IMSLP NO es la fuente primaria — es mayormente PDF escaneado, no MusicXML.
- **Popular**: curación manual, canción por canción. Pared legal real
  (copyright), no hay atajo honesto ni pipeline automático.
- **OMR (plan C)**: solo si falta una pieza en ninguna fuente digitalizada.
  `oemer` (Python, pip-instalable) preferido sobre Audiveris (Java, AGPL —
  si se usa, invocar por subprocess, nunca linkear, para no heredar la
  licencia).

## Control manos-libres

Problema real: coordinar mouse/teclado/piano rompe el flow state a media
práctica. Solución: reservar las teclas extremas del Keystation 61es
(rango real C2–C7, zonas que el repertorio hasta grado 5-6 casi nunca toca)
como modificador.

- **Ancla**: nota más grave + nota más aguda sostenidas a la vez (un
  meñique en cada extremo).
- **Comando**: mientras el ancla está sostenida, cada tecla intermedia
  tocada dispara una acción — mapeada por **posición relativa** desde el
  ancla grave (1ra tecla blanca = comando 1, 2da = comando 2...), no por
  nota fija — memorizable por distancia física sin mirar.
- **Cancelar**: soltar el ancla sin tocar nada intermedio = no-op.
- **Alcance**: activo solo dentro de la sesión de `pianomatic`, nunca a
  nivel sistema — fuera de la app el teclado es 100% piano normal.

Implementación: `pianomatic.control` — capa que intercepta el stream MIDI
crudo ANTES de pasarlo al motor de diff/síntesis.

## Usuario y progreso

SQLite. Progreso trackeado **por pilar por separado**, nunca un solo número
(anti-patrón de "vanity metrics" — alta retención con Duolingo/Yousician no
implica maestría real). Metas ad-hoc del usuario conviven con la ruta
estructurada por grado ABRSM.

## Licencia

MIT para el código propio de pianomatic. Dependencias externas mantienen
sus propias licencias (LGPL/BSD/AGPL según el componente arriba) — se
invocan como librerías/subprocess, no se vendorizan modificadas.
