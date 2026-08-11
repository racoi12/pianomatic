# Contribuir a pianomatic

Bienvenidos PRs de humanos y de agentes de IA por igual.

## Antes de escribir código

1. Lee `docs/ARCHITECTURE.md` completo — la mayoría de decisiones ya
   tienen un porqué documentado con fuente de investigación. Si vas a
   contradecir una decisión ahí, dilo explícitamente en el PR y por qué.
2. Revisa `docs/STATUS.md` para saber qué está en progreso — evita
   duplicar trabajo.
3. Antes de escribir un módulo nuevo, revisa si ya existe una librería
   open-source madura que resuelva el problema (ver la tabla de
   ARCHITECTURE.md). Este proyecto prioriza *integrar* sobre *reinventar*.

## Estilo

- Sin comentarios que expliquen QUÉ hace el código (nombres claros ya lo
  dicen) — solo comentarios que expliquen un PORQUÉ no obvio (una
  restricción oculta, un workaround de un bug específico).
- Toda lógica no trivial (una rama, un loop, un parser) lleva un test
  mínimo que falle si la lógica se rompe — no hace falta framework de
  fixtures elaborado, un `test_*.py` simple con `assert` basta.
- Diffs cortos y enfocados. Un PR, un cambio lógico.

## Al terminar un cambio significativo

Actualiza `docs/STATUS.md` con una entrada nueva (fecha, qué se hizo, qué
sigue) — es lo que le permite a la siguiente persona (o sesión de IA)
retomar sin releer todo el historial.
