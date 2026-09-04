# Memoria en el chat educativo — guía sencilla
 
## 1. El problema que queremos resolver


En cursos técnicos (mantenimiento, electricidad, etc.) las respuestas suelen ser **largas** y el alumno hace **muchas preguntas seguidas** sobre el mismo tema. Sin memoria, el asistente repite cosas o contradice lo que ya explicó.

**Lo que queremos:** que el asistente recuerde **lo suficiente** de **esta** conversación con **este** alumno en **este** curso, para que las respuestas encajen entre sí.

---

## 2. Tres tipos de “memoria” (una metáfora)

Imaginá que el asistente tiene tres cuadernos:

### Cuaderno A — Lo que se dijo recién (historial)

- Es como **la última página** de la charla: las últimas frases del alumno y del asistente, en orden.
- Sirve para cosas como: “como te decía recién…”, “sigamos con el ejemplo del motor”.
- **No** puede ser infinito: si la charla es muy larga, no cabe todo en la cabeza del sistema de un solo golpe. Por eso se usa un **límite** (similar a “no leer más de X líneas de chat”).

### Cuaderno B — Resumen de lo que ya pasó (memoria resumida)

- Cuando la conversación ya es larga, **no** se puede leer todo el chat palabra por palabra.
- Entonces el sistema mantiene un **resumen corto** del estilo: “Ya vimos X, acordamos Y, el alumno preguntó por Z”.
- Ese resumen se va **actualizando** de vez en cuando, no en cada mensaje (para no hacer todo más lento y caro).

### Cuaderno C — El material del curso (libros y apuntes)

- Esto **no** es la conversación: son los **documentos del curso** (PDFs, temas, etc.) que el sistema busca para fundamentar respuestas.
- Es lo que hace que la respuesta sea **correcta según el contenido oficial**, no inventada.

**Idea clave:** los cuadernos **A** y **B** son “qué charlamos vos y yo”. El cuaderno **C** es “qué dice el material del curso”. Los tres se combinan, pero **no son lo mismo**.

---

## 3. Por qué hace falta combinarlos

- Solo **A** (historial) → el asistente se pierde al cabo de muchos mensajes largos.
- Solo **B** (resumen) → pierde matices recientes (“el ejemplo que acabamos de usar”).
- Solo **C** (material del curso) → responde bien sobre el tema, pero **no** siente el hilo de conversación.

Por eso la propuesta es usar **los tres a la vez**.

---

## 4. Cómo se relaciona con “usuario” y “curso”

Para que la memoria no se mezcle entre personas ni entre materias:

- **Usuario** = quién está hablando (un identificador, como un ID de alumno).
- **Curso** = en qué materia está (mantenimiento industrial, mecánico, etc.).

Así, lo que se guarda en **A** y **B** queda **atado a ese par**: “este alumno, en este curso”. Si el mismo alumno cambia de curso, no se arrastra el resumen de la otra materia (salvo que el producto lo permita a propósito).

---

## 5. Qué cambia para el alumno (en la práctica)

- El alumno puede hacer preguntas **en cadena** sin repetir todo el contexto cada vez.
- El asistente puede **retomar** lo ya explicado cuando el resumen lo cubre.
- Las respuestas siguen **apoyadas en el material del curso** (cuaderno C), no solo en la charla.

---

## 6. Límites honestos (importante)

- **No es memoria humana.** A veces el resumen omite un detalle.
- **Hay límites de tamaño.** Por eso existe un “techo” de cuánto historial se puede enviar cada vez.
- **Privacidad:** guardar conversaciones implica decidir **cuánto tiempo** se conservan y **quién** puede verlas. Eso es un tema de política del producto, no solo técnico.

---

## 7. Si querés el detalle técnico

La implementación concreta (tablas, pasos del servidor, variables de configuración) está en  
**`CONVERSATION_MEMORY_MODEL.md`**.

Este archivo **`CONVERSATION_MEMORY_PARA_HUMANOS.md`** es solo la versión **clara y corta** para entender la idea.

---

## 8. Resumen en una frase

**Guardamos un poco de conversación reciente, un resumen cuando la charla crece, y seguimos usando el material del curso para que las respuestas sean coherentes entre sí y fieles al contenido.**
