# pianomatic

Coach de piano con IA, 100% local y open-source. Corre en Linux con un
teclado MIDI real. No es una app de gamificación — el objetivo es
proficiencia musical real (partitura, oído, memoria), no rachas ni puntos.

**Estado actual**: v1 en desarrollo — motor de diff MIDI (pilar
"repertorio") + capa de control manos-libres. Ver [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
para el diseño completo de los 4 pilares y el porqué de cada decisión
técnica (con fuentes de investigación citadas).

## Por qué existe

Las apps comerciales (Simply Piano, Yousician, Flowkey) optimizan retención
de la app, no maestría del instrumento — alta racha de uso, baja
competencia real transferible al piano físico sin la app. `pianomatic`
existe para hacer lo contrario: feedback multidimensional real (no un
score único), con foco explícito en poder algún día tocar sin depender
del software.

## Empezando (para retomar el proyecto)

1. Lee [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) completo primero — tiene
   el mapa de los 4 pilares, qué está hecho, qué falta, y qué librería
   externa reutilizar en cada caso (no reinventar lo que ya existe bien
   hecho en el ecosistema open-source).
2. Lee [docs/STATUS.md](docs/STATUS.md) — qué se hizo en cada sesión de
   trabajo, qué sigue, decisiones pendientes.
3. Requisitos: Python 3.11+, un teclado MIDI conectado (o `mido`'s virtual
   port para desarrollar sin hardware).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest  # corre los self-checks
```

## Estructura

```
src/pianomatic/
  control.py    — capa de control manos-libres (ancla + comandos MIDI)
  midi_io.py    — captura de eventos MIDI con timestamps
  diff.py       — alineación (matchmaker) + diff multidimensional
  report.py     — reporte de texto del diff
  cli.py        — punto de entrada
docs/
  ARCHITECTURE.md — diseño completo, decisiones y porqués
  STATUS.md       — bitácora de progreso entre sesiones
tests/           — un self-check por cada módulo con lógica no trivial
```

## Contribuir

Ver [CONTRIBUTING.md](CONTRIBUTING.md). Issues y PRs bienvenidos —
humanos o agentes de IA por igual, siempre que el PR explique el *por qué*
del cambio, no solo el qué (el código ya dice el qué).

## Licencia

MIT — ver [LICENSE](LICENSE). Dependencias externas mantienen sus propias
licencias (ver ARCHITECTURE.md).
