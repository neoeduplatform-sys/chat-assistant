# Moodle local plugin → widget JWT (guía IA / implementación)

Documento único para **implementar** o **validar** un plugin Moodle que alimenta `frontend/chat-widget.js`. Objetivo: token **solo en servidor**, firma **HS256**, mismo secreto que el backend.

---

## 1. Contrato con el backend (no negociable)

Origen de verdad del código: `app/auth.py`.

| Campo | Obligatoriedad | Regla |
|--------|----------------|-------|
| Algoritmo | sí | **HS256** únicamente |
| `JWT_SECRET` (PHP config) | sí | Byte-identical al env del API |
| `JWT_ISSUER` (API) | opcional | Si el API tiene `JWT_ISSUER`, el JWT **debe** llevar `iss` con ese valor exacto |
| `sub` | sí | Identificador de usuario (string estable; suele ser ID Moodle o prefijo + ID) |
| `course_id` | sí | String que **existe** en la config del API (p. ej. `course_configurations.course_id`) |
| `exp` | sí | Unix time futuro |
| `iat` | recomendado | Unix time actual |

**Prioridad ID:** El API usa `sub` y `course_id` del JWT; ignora suplantación vía body JSON (`app/main.py`). El widget puede enviar `course_id` en JSON; debe coincidir con el token para evitar confusiones en UI.

**Endpoints protegidos:** `POST /api/chat`, `GET /api/chat/history` → cabecera `Authorization: Bearer <jwt>`.

---

## 2. Contrato con el frontend

Variables globales que el plugin debe definir **antes** de cargar `chat-widget.js`:

| Variable | Obligatoria | Notas |
|-----------|-------------|--------|
| `window.CHATBOT_TOKEN` | sí | JWT |
| `window.CHATBOT_API_URL` | opcional si default OK | Default del widget: `http://localhost:8080/api/chat` |
| `window.CHATBOT_HISTORY_URL` | opcional | Si falta: se deduce sustituyendo sufijo del API por `/api/chat/history` |
| `window.CHATBOT_COURSE_ID` | sí * | Widget lo exige hoy; debe ser el **mismo string** que `course_id` del JWT |

\*Coherencia token/UI; el API autoriza solo con el JWT.

---

## 3. Árbol mínimo del plugin

Nombre ejemplo: **`local_chatassistant`** → carpeta `moodle/local/chatassistant/`.

**Implementación de referencia en este repo:** `integrations/moodle/local/chatassistant/` (copiar a `{moodle}/local/chatassistant/`).

```text
local/chatassistant/
  version.php                    # obligatorio
  lang/en/local_chatassistant.php
  settings.php                   # jwt_secret, ttl, jwt_issuer, api_url, widget_url
  classes/local/jwt_helper.php   # firma JWT
  classes/local/course_mapper.php # Moodle course → string course_id del API (opción A/B/C)
  lib.php                        # o hooks/observers según opción §5
```

Opcional según mecanismo de inyección: `db/hooks.php`, `db/events.php`, `classes/hook_callbacks.php`.

---

## 4. Secuencia de implementación

1. Crear carpeta + `version.php` (`$plugin->component = 'local_chatassistant'`).
2. Añadir strings en `lang/en/local_chatassistant.php`.
3. Implementar `settings.php`: al menos `jwt_secret`, TTL (segundos), `jwt_issuer` (texto vacío permitido si el API no usa issuer), `api_url`, `widget_url`. Leer con `get_config('local_chatassistant', …)`.
4. Implementar `course_mapper`: entrada `$course` (objeto Moodle), salida **string** = claim `course_id`.
5. Implementar `jwt_helper::encode(...)`: payload tabla §1; `Firebase\JWT\JWT::encode(..., $secret, 'HS256')`. Sin secreto configurado → no emitir token (o log + abortar inyección).
6. Inyectar en contexto **curso + usuario autenticado**: scripts §2 + `<script src="widget_url">`. URLs desde config, no hardcode salvo ejemplos.
7. Subir `version`, **Site administration → Notifications**, instalar strings, rellenar settings.
8. Verificar red: `Authorization: Bearer` en POST chat y GET history; 401 si exp/TTL o `iss` incorrecto.

---

## 5. Dónde inyectar JS (elige una)

| Mecanismo | Cuándo usarlo |
|-----------|----------------|
| **Hook** `before_footer_html` / equivalente en tu rama (p. ej. Moodle 4.4+ `db/hooks.php`) | Control fino; consulta nombre exacto del hook en docs de tu versión |
| **Observer** `\core\event\course_viewed` + `$PAGE->requires->js_init_code` + `js()` | Compatible con muchas versiones; validar que la página permite `requires` |
| **Block** `block_chatassistant` | Menos automático; el usuario añade el bloque al curso; `get_content()` imprime scripts |

Condición común: ejecutar solo si hay curso válido y usuario logueado; obtener `$course` del contexto de la página.

---

## 6. Mapeo `course_id`

El string del claim debe existir en el backend (config de curso).

| Estrategia | Origen |
|------------|--------|
| A | `$course->idnumber` o `$course->shortname` (si ya son los IDs de negocio del API) |
| B | Tabla propia `moodle_course_id → api_course_id` |
| C | `(string) $course->id` solo si el API registró ese mismo valor |

---

## 7. Fragmento HTML objetivo

Sustituir valores por PHP/escape correcto (`json_encode` para el JWT en JS si contiene caracteres especiales).

```html
<script>
window.CHATBOT_TOKEN = "<JWT>";
window.CHATBOT_API_URL = "<api_url desde config>";
window.CHATBOT_HISTORY_URL = "<derivado o setting explícito>";
window.CHATBOT_COURSE_ID = "<mismo que claim course_id>";
</script>
<script src="<widget_url desde config>"></script>
```

---

## 8. Seguridad (checklist corto)

- Secreto solo servidor Moodle + env API; nunca cliente ni repo público.
- HTTPS cliente↔Moodle y cliente↔API.
- TTL corto (p. ej. 1–4 h); nuevo token por carga de página.

---

## 9. Referencias repo

| Artefacto | Ruta |
|-----------|------|
| Validación JWT | `app/auth.py` |
| Overrides desde token | `app/main.py` (`get_current_user`) |
| Payload de prueba | `scripts/generate_token.py` |
| Variables globales widget | `frontend/chat-widget.js` (cabecera del archivo) |

---

## 10. Ejemplos PHP (referencia rápida)

### `version.php`

```php
<?php
defined('MOODLE_INTERNAL') || die();
$plugin->component = 'local_chatassistant';
$plugin->version   = 2026042100;
$plugin->requires  = 2023100900; // ajustar a tu Moodle
```

### Payload JWT (debe cumplir §1)

```php
$payload = [
    'sub' => (string) $USER->id,
    'course_id' => $coursemapper->api_course_id($course),
    'iat' => time(),
    'exp' => time() + $ttlseconds,
];
if ($issuer !== '') {
    $payload['iss'] = $issuer;
}
$jwt = \Firebase\JWT\JWT::encode($payload, $secret, 'HS256');
```

---

**Fin.** Cualquier implementación debe satisfacer §1–§2 y la secuencia §4; el resto es detalle Moodle por versión.
