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
- [ ] Implementar `control.py` (ancla + mapeo por posición relativa) con
  su test.
- [ ] Implementar `midi_io.py` (captura con `mido`).
- [ ] Integrar `matchmaker` en `diff.py` — probar con un MIDI real
  (usar algo de `~/Music/BoosterMusicBooks4/` como primer caso de prueba).
- [ ] `report.py`: reporte de texto con las 3 dimensiones (timing, pitch,
  dinámica) separadas.
- [ ] Decidir rango exacto del Keystation 61es (verificar con hardware
  real qué nota MIDI es la más grave/aguda que reporta — no asumir).
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
