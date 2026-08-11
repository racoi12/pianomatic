# Bitácora de progreso

Formato: fecha, qué se hizo, qué decisiones se tomaron y por qué, qué sigue.
Para que cualquiera (humano o IA) retome el proyecto sin tener que releer
todo el historial de conversación que lo originó.

## 2026-08-11 — Arranque del proyecto

**Contexto de origen**: nace de armar una MacBook Air 2015 (Ubuntu 24.04)
como "companion" dedicado de un teclado MIDI (M-Audio Keystation 61es) para
uso familiar. Al dejar ese setup funcionando (fluidsynth + PianoBooster +
soundfonts + autostart systemd), surgió la pregunta de qué sería el
"estado del arte" de aprender piano con IA/MIDI/Linux en 2026 — no existía
nada maduro que combinara los 4 pilares (repertorio, lectura, oído,
técnica) con feedback real (no gamificación vacía), así que se decidió
construirlo.

**Investigación hecha** (6 sub-agentes, ver enlaces citados en
ARCHITECTURE.md): pedagogía del piano, neurociencia del aprendizaje motor,
psicología de la motivación/gamificación, librerías MIDI/DTW existentes,
herramientas de lectura a primera vista/oído, renderizado de notación +
IMSLP + OMR + datasets de repertorio graduado.

**Decisiones tomadas**:
- Stack: Python (latencia no es problema real — el audio en tiempo real ya
  lo maneja fluidsynth en C, este proyecto solo analiza timestamps MIDI
  en batch/post-hoc).
- Motor de alineación: `matchmaker`, no DTW propio.
- Curriculum: ancla en syllabus ABRSM/RCM (grado 5-6 como meta), no un
  sistema de niveles inventado desde cero.
- Contenido clásico: Piano Syllabus Dataset (Zenodo) — ya viene graduado
  por dificultad, evita curación manual.
- Contenido popular: manual, canción por canción — pared legal real.
- Licencia: MIT.
- Control manos-libres: ancla en extremos del teclado (nota más grave +
  más aguda sostenidas) + comandos por posición relativa de teclas
  intermedias — evita interactuar con mouse/teclado durante la práctica.

**Hecho en esta sesión**:
- Repo creado en GitHub (`racoi12/pianomatic`, público, MIT).
- `docs/ARCHITECTURE.md` con el diseño completo de los 4 pilares.
- Scaffold inicial: `src/pianomatic/{control,midi_io,diff,report,cli}.py`.

**Pendiente / siguiente sesión**:
- [x] Implementar `control.py` (ancla + mapeo por posición relativa) con
  su test — hecho al arranque de esta sesión, 6 tests (ver commit
  inicial), este checkbox había quedado sin marcar por error.
- [x] Implementar `midi_io.py` — `translate()` puro (testeado) + `MidiSession`
  (I/O real, necesita hardware, no testeado). Usa `mido.ports.MultiPort`
  con `yield_ports=True` para fusionar varios puertos de entrada.
- [x] `diff.py`: `align()` implementado, envuelve `Matchmaker.run()`.
  **Verificado manualmente** (no en el pytest suite — el motor real jala
  todo el stack de ML y tarda segundos por corrida, no vale la pena en
  cada `pytest`) con self-comparison contra
  `~/Music/BoosterMusicBooks4/Beginner Course/01-StartWithMiddleC.mid`:
  138 posiciones, progresión monótona correcta. Comando exacto para
  re-verificar:
  ```
  .venv/bin/python3 -c "
  import sys; sys.path.insert(0, 'src')
  from pianomatic.diff import align
  r = align('SCORE.mid', 'SCORE.mid')
  print(r.path.shape, r.path[:3])
  "
  ```
- [x] **Bug encontrado en pymatchmaker**: el docstring de `Matchmaker.run()`
  dice que el alignment path tiene shape `(2, N)` — en la práctica es
  `(N, 2)` (verificado, shape real `(138, 2)`). También: el path de
  retorno de `run()` (un generador) solo se obtiene vía
  `StopIteration.value`, no agotando el generador con `list()` — eso
  descarta silenciosamente el path si no se maneja bien.
- [x] Diff por nota (timing + pitch) en `diff.py`: `match_notes()`
  implementado y con 7 tests unitarios (datos sintéticos, rápidos — no
  dependen del stack de ML). Algoritmo: nearest-neighbor greedy por pitch
  dentro de una ventana de tolerancia (0.5s default), cada nota tocada se
  usa como máximo una vez. **No es un assignment globalmente óptimo** —
  suficiente para v1, revisar si falla en tocadas reales con notas
  repetidas muy cerca entre sí.
- [x] `compare()` end-to-end verificado manualmente contra un archivo real
  (self-comparison): 8/8 notas de referencia emparejadas, desviación de
  timing ~0ms (ruido de punto flotante). **Hallazgo real**: el archivo de
  prueba (`~/Music/BoosterMusicBooks4/.../01-StartWithMiddleC.mid`, de
  PianoBooster) trae banda completa — batería, bajo, acompañamiento — 196
  eventos NOTE_ON en 4 canales MIDI contra solo 8 notas de la melodía de
  piano. `extract_performed_notes()` ahora acepta `channel: int | None`
  para filtrar, aunque en este archivo específico ni eso alcanza (la
  melodía está doblada en varios canales). **No afecta el uso real**: la
  captura en vivo (`midi_io.MidiSession` desde el teclado físico) nunca
  tiene este problema — solo captura lo que el usuario realmente toca.
  Para pruebas futuras, usar un MIDI de referencia limpio (solo piano,
  ej. algo del dataset PSyllabus) en vez de un archivo de banda completa.
- [ ] Dimensión de dinámica (velocity): `match_notes()` ya guarda la
  velocity tocada por nota emparejada, pero **no compara contra una
  referencia** — un MIDI simple no trae marcas de dinámica confiables.
  Necesita una fuente de referencia con dinámica real antes de que esta
  comparación tenga sentido.
- [x] `report.py`: implementado, inglés (ver nota abajo sobre
  localización), 8 tests unitarios (datos sintéticos). Solo lista
  desviaciones de timing por encima del umbral JND (default 50ms) —
  nunca reporta ruido sub-perceptual como error, y separa timing/notas
  perdidas/extra en secciones distintas (nunca un solo score).
- [x] `cli.py`: `pianomatic compare SCORE.mid PERFORMANCE.mid` funciona
  end-to-end, verificado con el comando real instalado (`pip install -e`).
- [x] **v1 del pilar Repertorio queda cerrado**: captura → alineación →
  diff por nota → reporte, cada pieza implementada y probada (26 tests).
  Falta solo dinámica (bloqueada por necesitar una fuente de referencia
  con marcas de expresión reales) y localización del reporte (ver abajo).

## Pendiente: localización del reporte

`report.py` genera el texto en inglés (consistente con "todo en inglés" a
partir de esta sesión). Pero el/los usuario(s) reales de esta herramienta
(Akira, Chayo, familia) hablan español — un reporte de coaching en inglés
no es la experiencia final que se quiere. No se resolvió aquí porque:
- v1 es una herramienta de desarrollador (CLI, texto plano) para probar
  que el motor funciona, no la experiencia de coaching pulida.
- El reporte real de cara al usuario será generado por el LLM local
  (fase de "coach" pendiente, ver ARCHITECTURE.md) — ahí es donde
  naturalmente se resuelve el idioma (prompt en español), no en el
  `report.py` de texto plano de v1.
Cuando se llegue a esa fase, decidir: ¿`report.py` se vuelve internal-only
(datos estructurados que el LLM consume) y el texto en inglés deja de
mostrarse directamente al usuario? Probablemente sí — no diseñar
i18n genérico para un texto que va a dejar de ser user-facing.
- [x] Rango real del Keystation 61es **verificado con hardware físico**
  (aseqdump contra el puerto MIDI real, no supuesto): nota más grave = 36
  (C2), más aguda = 96 (C7) — 60 semitonos, 61 teclas, coincide con la
  especificación de 5 octavas. Ahora expuesto como
  `control.KEYSTATION_61ES_LOW`/`KEYSTATION_61ES_HIGH`, reutilizado por
  los tests en vez de duplicar los literales.
- [ ] Módulos de lectura a primera vista y oído: aún no empezados,
  ver ARCHITECTURE.md para qué reutilizar.
- [ ] Sustain pedal (CC64) support in `midi_io.py` + diff engine, and
  multi-port MIDI merging (see docs/ARCHITECTURE.md, "Sustain pedal") —
  verify with real hardware whether the Keystation 61es reports half-pedal
  (continuous) or on/off only.
- [ ] **Traducir todo a inglés** (docs, comentarios, mensajes de commit).
  README/ARCHITECTURE/STATUS/CONTRIBUTING y `control.py`/tests quedaron en
  español de la sesión de arranque — no es prioridad inmediata, pero todo
  código/doc nuevo a partir de ahora se escribe en inglés directamente.
