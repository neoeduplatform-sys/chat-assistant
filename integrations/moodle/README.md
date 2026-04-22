# Integración Moodle → chat JWT

## Instalación

1. Copia todo el contenido de **`local/chatassistant/`** (esta carpeta) a tu Moodle:

   ```text
   {moodle_root}/local/chatassistant/
   ```

2. Como administrador: **Administración del sitio → Notificaciones** y ejecuta la actualización.

3. **Administración del sitio → Plugins → Plugins locales → Chat assistant (Kumu)** y configura:

   | Campo | Descripción |
   |-------|-------------|
   | JWT shared secret | Igual que `JWT_SECRET` del backend (`app/auth.py`). |
   | Token lifetime | Segundos hasta `exp` (p. ej. `7200`). |
   | JWT issuer | Solo si el API tiene `JWT_ISSUER`; mismo texto exacto. |
   | Course ID claim source | Cómo mapear el curso Moodle al `course_id` del API. |
   | Chat API URL | Ej. `https://tu-api.com/api/chat`. |
   | Widget script URL | Ej. `https://tu-api.com/static/chat-widget.js`. |
   | History API URL | Opcional; si está vacío se deduce como en `chat-widget.js`. |

4. Entra a un curso con un usuario **no invitado**: el widget debe cargar y las peticiones deben llevar `Authorization: Bearer`.

## Requisitos

- **Moodle 4.4+** (hook `before_footer_html_generation`).
- PHP con la clase `\Firebase\JWT\JWT` (incluida en el núcleo de Moodle reciente).

## Documentación

- Guía humana: `project/auth/MOODLE_PLUGIN_HUMAN_GUIDE.md`
- Contrato técnico / IA: `project/auth/MOODLE_PLUGIN_STEP_BY_STEP.md`

## Alcance del plugin

Inyecta el widget en páginas donde Moodle expone `$PAGE->course` con un id de curso válido (no página de portada del sitio). Si necesitas más contextos (solo ciertas actividades), habría que ampliar `classes/hook_callbacks.php`.
