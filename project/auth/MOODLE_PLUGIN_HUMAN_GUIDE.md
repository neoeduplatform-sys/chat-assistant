# Guía humana: implementar el plugin de Moodle para el chat (JWT)

Esta guía explica **en qué orden** y **por qué** haces cada cosa. La referencia técnica exacta (tabla de claims, nombres de archivos mínimos) está en `MOODLE_PLUGIN_STEP_BY_STEP.md`.

---

## 1. Qué estás construyendo (en una frase)

Un pequeño **plugin local** de Moodle que, cuando alguien entra a un curso, genera en el **servidor** un token firmado (JWT) y deja en la página unas variables JavaScript (`CHATBOT_TOKEN`, etc.) para que el archivo `chat-widget.js` pueda llamar a tu API con la cabecera `Authorization: Bearer`.

El secreto para firmar **nunca** sale del servidor Moodle; el navegador solo recibe el token ya emitido.

---

## 2. Antes de tocar Moodle

Comprueba lo siguiente:

1. **Tu API del chat** ya tiene configurado `JWT_SECRET` (y `JWT_ISSUER` solo si decidiste usar emisor obligatorio).
2. En el backend ya existe **configuración del curso** para el ID de negocio que usarás como `course_id` (tabla tipo `course_configurations`). Si ese ID no existe en la API, obtendrás error aunque el JWT sea válido.
3. Decides **cómo vas a llamar cada curso en la API**: por `idnumber` de Moodle, por `shortname`, por el número interno del curso o por una tabla de equivalencias. Esa decisión es lo más importante para no tener que rehacer el plugin.

---

## 3. Cómo encaja todo (flujo mental)

1. El usuario abre una página de curso en Moodle.
2. Moodle ejecuta **PHP**: conoce al usuario y al curso.
3. Tu plugin arma un objeto con `sub` (usuario), `course_id` (curso en la nomenclatura del API), fechas (`iat`, `exp`) y opcionalmente `iss`.
4. Firma ese objeto con **HS256** y la misma clave que usa la API.
5. Moodle imprime en HTML algo como “`window.CHATBOT_TOKEN = '...'`” y luego carga la URL donde hospedas `chat-widget.js`.
6. El widget hace peticiones a `/api/chat` con el token; la API **no confía** en los IDs que vengan en el JSON del body para identificar usuario/curso: usa lo que trae el JWT.

Por eso el token debe generarse donde hay contexto real de Moodle (PHP), no en JavaScript libre en el navegador.

---

## 4. Fase A — Esqueleto del plugin en el código

### Paso A1 — Carpeta y nombre

Crea una carpeta bajo la instalación de Moodle:

`local/chatassistant/`

El nombre técnico del componente será `local_chatassistant`: conviene mantener nombre de carpeta y prefijos coherentes para no equivocarte en rutas.

### Paso A2 — Registrar el plugin (`version.php`)

Este archivo dice a Moodle “aquí hay un plugin local”. Sin él, Moodle no reconoce la carpeta. Tras cualquier cambio importante de código, sueles **subir el número de versión** para que Moodle detecte actualizaciones.

### Paso A3 — Textos visibles (`lang/en/local_chatassistant.php`)

Aquí van las cadenas que verá el administrador en pantalla (nombre del plugin, etiquetas de los campos de configuración). Moodle exige inglés como mínimo en `en`; puedes añadir después `lang/es/` si quieres interfaz en español.

### Paso A4 — Pantalla de configuración (`settings.php`)

Aquí defines lo que el administrador del campus rellena **sin editar código**:

- Secreto compartido con la API (`JWT_SECRET`).
- Tiempo de vida del token (TTL): cuántos segundos será válido el JWT.
- Opcional: valor de emisor (`iss`) si tu API tiene `JWT_ISSUER`.
- URL del endpoint de chat (la que espera `chat-widget.js`, típicamente …`/api/chat`).
- URL donde está alojado `chat-widget.js` (CDN o tu propio servidor).

Piensa que el mismo plugin puede pasar de desarrollo a producción cambiando solo estas URLs y el secreto en la interfaz.

---

## 5. Fase B — Lógica que tú programas

### Paso B1 — De curso Moodle a `course_id` del API

Implementa una función clara (por ejemplo en `classes/local/course_mapper.php`) que reciba el objeto curso de Moodle y devuelva **un string**. Ese string es el que debe coincidir con lo que tu equipo dio de alta en la API como identificador del curso.

Si no coinciden, el usuario verá errores del tipo “curso no encontrado” en la API aunque el JWT sea correcto.

### Paso B2 — Firmar el JWT (`jwt_helper`)

Aquí lees la configuración guardada (`get_config`), montas el array del payload según las reglas del backend (`sub`, `course_id`, `exp`, etc.) y llamas a la librería JWT que use tu Moodle (habitualmente `\Firebase\JWT\JWT::encode` con algoritmo **HS256**).

Si falta el secreto en la configuración, lo sensato es **no imprimir token** y opcionalmente registrar un mensaje en los logs del servidor para que el administrador lo vea.

---

## 6. Fase C — Mostrar el widget en la página

El usuario final no debe pegar código a mano: el plugin debe **inyectar** dos cosas:

1. Un `<script>` que define `window.CHATBOT_TOKEN`, `window.CHATBOT_API_URL`, `window.CHATBOT_HISTORY_URL` si la necesitas explícita, y `window.CHATBOT_COURSE_ID` (el mismo valor conceptual que `course_id` del token).
2. Un segundo `<script src="...">` que carga `chat-widget.js` desde la URL configurada.

**Dónde** enganchar eso depende de tu versión de Moodle y de tu comodidad:

- **Hooks modernos** (según documentación de tu rama): suelen ser la forma limpia de añadir HTML antes del cierre del body.
- **Observer del evento** de visualización de curso: útil si conoces bien el ciclo de vida de la página; a veces hay que probar en la vista de curso concreta.
- **Plugin bloque**: si tu equipo prefiere algo muy visible y controlado, puedes crear un bloque que solo “imprime” esos scripts cuando el profesor añade el bloque al curso.

Elige una vía, prueba en `course/view.php`, y no hagas que el script se cargue en **todas** las páginas del sitio si no es necesario.

---

## 7. Fase D — Instalación en el servidor Moodle

1. Copias la carpeta del plugin al árbol correcto (`local/chatassistant`).
2. Entras como administrador en Moodle y vas a **Administración del sitio → Notificaciones** para que ejecute el script de actualización de base de datos del plugin.
3. Abres la configuración del plugin (ruta típica: **Plugins → Plugins locales → …**) y pegas URLs, TTL y secreto **idéntico** al de la API.

Hasta que el secreto no coincida byte a byte, la API responderá con error de autenticación.

---

## 8. Fase E — Cómo probar sin volverte loco

1. **Sin Moodle:** usa en el repo del backend `scripts/generate_token.py` para generar un token de prueba y llama con Postman o curl a `POST /api/chat` con cabecera Bearer. Así aislas problemas de Moodle.
2. **Con Moodle:** abre el curso, usa “Inspeccionar” en el navegador y comprueba que existen las variables globales del widget y que la pestaña Red muestra `Authorization: Bearer` en las llamadas al chat y al historial.
3. Si algo falla, anota el **código HTTP** (401 = token o issuer; 404 = curso no configurado en la API; 500 = configuración del servidor).

---

## 9. Errores frecuentes (lectura rápida)

| Síntoma | Causa probable |
|---------|----------------|
| 401 “Invalid authentication” | Secreto distinto, token caducado, falta `iss` cuando la API lo exige, o claim `course_id` vacío |
| 404 curso no encontrado | El `course_id` del JWT no existe en la configuración del API |
| El widget no aparece | Variables globales no definidas o script bloqueado por CSP; orden incorrecto (token antes que `chat-widget.js`) |
| Funciona en un curso y no en otro | Mapeo curso Moodle → `course_id` inconsistente |

---

## 10. Documentos relacionados en este proyecto

| Archivo | Para qué sirve |
|---------|----------------|
| `project/auth/MOODLE_PLUGIN_STEP_BY_STEP.md` | Especificación compacta (claims, checklist, opciones de inyección) pensada también para automatización |
| `app/auth.py` | Comportamiento exacto de validación en el servidor |
| `frontend/chat-widget.js` | Variables globales que el plugin debe definir |

Cuando termines la primera versión del plugin, vale la pena documentar internamente **qué campo de Moodle** usaste como `course_id` para que soporte y contenidos hablen el mismo idioma que la API.
