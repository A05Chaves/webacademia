# Plan futuro: avatar, monedas y rachas de Galeras BJJ

Estado: concepto aprobado para implementación posterior. Este documento no implica que las funciones estén programadas.

## Identidad visual

- La mascota digital será un cuy luchador de jiujitsu, inspirado en la identidad de Galeras y reconocible para niños y adultos.
- La moneda será completamente original, con el rostro o silueta del cuy, una `G` y colores azul, verde, negro y dorado.
- No se copiarán gráficos, sonidos ni animaciones de videojuegos comerciales.
- Boceto guardado en `docs/assets/concepto-avatar-moneda-galeras.png`.
- El avatar tendrá piezas intercambiables: kimono, rashguard, camiseta, cinturón decorativo, peinado, expresiones, fondos, marcos e insignias.
- El grado o cinturón real no se podrá comprar: se tomará del registro académico.

## Billetera virtual

- Las monedas son puntos virtuales, no COP ni USD, no se retiran y no se mezclan con la contabilidad o la tienda real.
- Todo cambio se registra en un libro de movimientos; nunca se modifica el saldo sin trazabilidad.
- Ejemplos: asistencia `+10`, pago oportuno `+30`, meta semanal `+20`, artículo de avatar `-50`, conducta `-5` y reversión administrativa.
- Cada origen tendrá una clave única para impedir recompensas duplicadas.
- Una anulación genera un movimiento contrario y conserva el movimiento original.

## Recompensas por asistencia

- Una asistencia válida con mensualidad activa entrega una cantidad configurable; propuesta inicial: `+10`.
- Una asistencia solo entrega monedas una vez.
- Cortesías no generan monedas hasta que la persona se convierta en estudiante.
- Becas activas se consideran al día.
- Profesores tendrán reglas separadas.
- Un estudiante vencido con permiso administrativo puede confirmar clase, pero no obtiene monedas ni progreso de racha.
- No se entregarán retroactivamente monedas por clases tomadas mientras la mensualidad estaba vencida.
- Un estudiante suspendido no puede confirmar clase.

## Recompensa por pago oportuno

- Propuesta inicial: `+30` por renovar antes o el día del vencimiento.
- Se entrega únicamente cuando el pago sea aprobado.
- La elegibilidad usa la fecha de reporte o transacción, no el día en que el administrador revisó el pago.
- Solo se entrega un bono por periodo renovado.
- Pagos duplicados, rechazados, anulados o devueltos no generan recompensa; si ya se otorgó, se revierte.
- El premio es fijo y no depende del precio del plan.

## Rachas

- La racha principal será semanal por cumplimiento de meta, no por asistencia diaria.
- La meta se adapta al plan: por ejemplo, un plan de ocho clases mensuales puede tener meta de dos clases semanales.
- Cumplir la meta conserva la racha; incumplirla la reinicia.
- Incapacidades, suspensión justificada o cierre de academia podrán congelar la semana.
- Se mostrarán racha actual, récord y progreso semanal.
- La mensualidad vencida impide avanzar la racha aunque la asistencia haya sido permitida.
- Se podrán entregar premios en hitos configurables, por ejemplo 4, 8 y 12 semanas.

## Conducta infantil

- Los profesores podrán registrar reconocimientos o descuentos desde la asistencia de la clase.
- Motivos y valores serán configurados por la administración; no se permitirá escribir una cantidad arbitraria.
- Propuestas: interrupción reiterada `-2`, falta de respeto `-5`, conducta peligrosa `-10` y reconocimiento positivo entre `+2` y `+5`.
- Habrá límites máximos por clase y día; nunca se permitirá saldo negativo.
- Solo el profesor asignado o presente podrá registrar la novedad.
- Cada movimiento conserva estudiante, profesor, clase, fecha, motivo y observación.
- Medidas altas requieren aprobación administrativa.
- Un administrador puede reversar errores sin borrar el historial.
- No habrá clasificaciones públicas ni exposición de sanciones.
- Se podrá notificar al acudiente en casos relevantes.
- Los descuentos no eliminan logros, asistencias ni rachas históricas.
- Las monedas no se recuperan pagando dinero real.

## Experiencia al confirmar clase

- Mostrar primero la confirmación visual de la clase.
- Si obtiene recompensa, emerge una moneda original, gira, muestra `+10`, reproduce un sonido breve propio y se desplaza hacia el contador.
- Mostrar el nuevo saldo y el progreso semanal.
- Si la mensualidad está vencida, confirmar la clase sin moneda ni sonido y explicar que no generó recompensa.
- Una deducción utiliza una animación discreta y diferente, sin efectos humillantes.
- El usuario podrá silenciar sonidos y se respetarán preferencias de accesibilidad.

## Configuración administrativa

- Monedas por asistencia.
- Bono por pago oportuno.
- Bono por meta semanal e hitos de racha.
- Metas según el plan.
- Reglas para asistencias con mensualidad vencida.
- Motivos y límites de reconocimientos y descuentos.
- Notificación al acudiente.
- Catálogo, precio, requisitos, público, vigencia y estado de artículos del avatar.

## Orden recomendado de implementación

1. Billetera y libro de movimientos.
2. Recompensas idempotentes por asistencia y pago oportuno.
3. Metas semanales, rachas y congelaciones.
4. Controles de conducta infantil y auditoría.
5. Animación y sonido original de la moneda.
6. Avatar base, inventario virtual y personalización.
7. Catálogo de artículos, insignias y campañas temporales.

