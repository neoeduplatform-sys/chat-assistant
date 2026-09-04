# Plan de Implementación: Autenticación JWT para Widget de Chat (Opción A)

**Versión:** 1.0
**Estado:** Propuesta de Arquitectura
**Objetivo:** Permitir que el chat funcione como una burbuja flotante en Moodle, manteniendo la seguridad mediante tokens JWT firmados en el servidor, eliminando la necesidad de flujos LTI de pantalla completa o cookies de terceros.

---

## 1. Resumen de la Arquitectura

1.  **Moodle (Lado Servidor):** Cuando un usuario carga un curso, un plugin o bloque de Moodle genera un token JWT firmado con una clave secreta compartida (`JWT_SECRET`).
2.  **Frontend (Navegador):** El script `chat-widget.js` recibe este token y lo incluye en la cabecera `Authorization: Bearer <TOKEN>` de todas las peticiones al backend.
3.  **Backend (FastAPI):** Valida la firma del JWT, extrae de forma segura el `user_id` y `course_id`, y procesa la petición.

---

## 2. Cambios en el Backend (FastAPI)

### 2.1 Dependencias
Añadir `PyJWT` al proyecto para el manejo de tokens.

### 2.2 Nuevo Módulo: `app/auth.py`
Crear un módulo dedicado a la validación de tokens que:
- Lea `JWT_SECRET` de las variables de entorno.
- Implemente una función `verify_jwt_token(token: str)` que valide:
    - Firma (HS256).
    - Fecha de expiración (`exp`).
    - Emisor (`iss`) - opcional pero recomendado.
- Exponga una dependencia de FastAPI `get_current_user` para ser usada en los endpoints.

### 2.3 Modificaciones en `app/main.py`
- Importar la dependencia de seguridad.
- Aplicar la protección a los endpoints:
    - `POST /api/chat`
    - `GET /api/chat/history`
- **Importante:** Priorizar los IDs extraídos del token sobre los enviados en el cuerpo del JSON para evitar suplantación.

---

## 3. Cambios en el Frontend (`chat-widget.js`)

- Modificar la inicialización para aceptar un parámetro `token`.
- Actualizar las llamadas `fetch` para incluir la cabecera:
  ```javascript
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${window.CHATBOT_TOKEN}`
  }
  ```

---

## 4. Requerimientos para el Plugin de Moodle

El administrador de Moodle o desarrollador PHP debe implementar lo siguiente:

### 4.1 Generación del Token (PHP)
Usar la librería `Firebase\JWT\JWT` (estándar en Moodle).
```php
$secret_key = 'TU_CLAVE_SECRETA_COMPARTIDA';
$payload = [
    'iss' => 'moodle-instance-name',
    'sub' => $USER->id, // ID del usuario en Moodle
    'course_id' => $COURSE->id, // ID del curso
    'iat' => time(),
    'exp' => time() + (60 * 60 * 2), // Expiración en 2 horas
];
$jwt = JWT::encode($payload, $secret_key, 'HS256');
```

### 4.2 Inyección del Widget
El plugin debe imprimir el script en el footer del curso:
```html
<script>
    window.CHATBOT_TOKEN = "<?php echo $jwt; ?>";
    window.CHATBOT_COURSE_ID = "<?php echo $COURSE->id; ?>";
</script>
<script src="https://tu-backend.com/static/chat-widget.js"></script>
```

---

## 5. Guía de Testing con Postman

### 5.1 Generación de Token de Prueba (Python)
Crear un script `scripts/generate_token.py`:
```python
import jwt
import datetime

SECRET = "tu-secreto-de-desarrollo"
payload = {
    "sub": "user_test_123",
    "course_id": "default",
    "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
}
token = jwt.encode(payload, SECRET, algorithm="HS256")
print(f"Token: {token}")
```

### 5.2 Configuración en Postman
1. Ir a la pestaña **Authorization**.
2. Seleccionar **Type: Bearer Token**.
3. Pegar el token generado.
4. Enviar la petición a `POST /api/chat`.

---

## 6. Instrucciones para el Agente IA (Implementación)

Para llevar a cabo esta implementación, sigue estos pasos:

1.  **Instalación:** Añade `PyJWT==2.10.1` a `requirements.txt`.
2.  **Seguridad:** Crea `app/auth.py`. Define una clave `JWT_SECRET` (usa `os.getenv`). La función de validación debe lanzar `HTTPException(401)` si el token es inválido o ha expirado.
3.  **Modelos:** En `app/models.py`, asegúrate de que `user_id` y `course_id` en `ChatRequest` puedan ser opcionales si se proporcionan vía token.
4.  **Integración:** En `app/main.py`, usa `Depends(get_current_user)` en los endpoints de chat. Extrae el `user_id` y `course_id` del token y úsalos para la lógica de RAG y memoria.
5.  **Frontend:** Actualiza `frontend/chat-widget.js` para que lea `window.CHATBOT_TOKEN` y lo envíe en cada request.
6.  **Validación:** Crea un test básico en `tests/test_auth.py` que verifique que un token válido permite el acceso y uno inválido devuelve 401.
