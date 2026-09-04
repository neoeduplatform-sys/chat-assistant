# Integración del Chatbot en un proyecto Laravel (guía backend)

Esta guía está pensada para un **desarrollador backend con poca experiencia** que necesita integrar este chatbot (servicio FastAPI externo) en una app **Laravel**.

El chatbot expone un API HTTP y **no emite tokens**: solo **valida JWT** firmados por tu backend.

---

### Arquitectura de integración (2 opciones)

- **Opción A (recomendada, “widget directo”)**: tu Laravel **genera el JWT** y lo inyecta al HTML (Blade). El navegador carga `chat-widget.js` y el widget llama al chatbot.
- **Opción B (“proxy API”)**: tu Laravel expone un endpoint propio (ej. `/api/chatbot/ask`) y tu backend **llama server-to-server** al chatbot. El front habla solo con Laravel.

---

### Contrato del chatbot (lo mínimo que debes respetar)

#### Endpoint de chat

- **URL**: `POST {CHATBOT_BASE_URL}/api/chat`
- **Auth**: `Authorization: Bearer <JWT>`
- **Body JSON**:

```json
{
  "question": "¿Qué es el mantenimiento preventivo?",
  "course_id": "mantenimiento-mecanico",
  "user_id": "123"
}
```

Notas importantes:
- `course_id` y `user_id` en el body son **opcionales**: el backend del chatbot **prioriza** lo que venga en el JWT (anti-suplantación).
- Si usas el **widget**, normalmente enviarás `question` y `course_id`. El `user_id` es opcional.

#### Respuesta

```json
{
  "answer": "…",
  "sources": ["…"],
  "course_id": "mantenimiento-mecanico",
  "user_id": "123"
}
```

#### JWT requerido (firmado por Laravel)

El chatbot valida tokens **HS256** con un secreto compartido.

Claims esperados:

- **`sub`** (obligatorio): id del usuario (string)
- **`course_id`** (obligatorio): id del curso (string)
- **`exp`** (obligatorio): expiración (Unix timestamp en segundos)
- **`iat`** (opcional, recomendado): emisión (Unix timestamp)
- **`iss`** (solo si el chatbot tiene `JWT_ISSUER` configurado): debe coincidir exactamente

Referencia del repo: `project/auth/CLIENT_JWT_TOKEN_GUIDE.md` y validación en `app/auth.py`.

---

### Paso 0. Variables de entorno en Laravel

Agrega estas variables en tu `.env` (Laravel):

```env
CHATBOT_BASE_URL="https://tu-chatbot.ejemplo.com"
CHATBOT_JWT_SECRET="***secreto_compartido***"
CHATBOT_JWT_ISSUER="" # opcional (déjalo vacío si el chatbot no lo exige)
CHATBOT_TOKEN_TTL_SECONDS=3600
```

Notas:
- **Nunca** pongas `CHATBOT_JWT_SECRET` en JavaScript público.
- El secreto lo debe proveer el operador del chatbot (es el mismo valor configurado como `JWT_SECRET` en el servidor FastAPI).

---

### Paso 1. Instalar dependencias (PHP JWT + HTTP client)

En tu proyecto Laravel:

```bash
composer require firebase/php-jwt guzzlehttp/guzzle
```

---

### Paso 2. Servicio para firmar el JWT (Laravel)

Crea `app/Services/ChatbotTokenService.php`:

```php
<?php

namespace App\Services;

use Firebase\JWT\JWT;

class ChatbotTokenService
{
    public function makeToken(string $userId, string $courseId): string
    {
        $secret = config('services.chatbot.jwt_secret');
        $issuer = config('services.chatbot.jwt_issuer');
        $ttl = (int) config('services.chatbot.token_ttl_seconds', 3600);

        $now = time();
        $payload = [
            'sub' => (string) $userId,
            'course_id' => (string) $courseId,
            'iat' => $now,
            'exp' => $now + $ttl,
        ];

        if (is_string($issuer) && strlen(trim($issuer)) > 0) {
            $payload['iss'] = $issuer;
        }

        return JWT::encode($payload, $secret, 'HS256');
    }
}
```

Luego registra la config en `config/services.php`:

```php
// config/services.php
return [
    // ...
    'chatbot' => [
        'base_url' => env('CHATBOT_BASE_URL'),
        'jwt_secret' => env('CHATBOT_JWT_SECRET'),
        'jwt_issuer' => env('CHATBOT_JWT_ISSUER', ''),
        'token_ttl_seconds' => env('CHATBOT_TOKEN_TTL_SECONDS', 3600),
    ],
];
```

---

### Opción A (recomendada). Integrar el widget en una vista Blade

#### A.1 Decidir cómo servir el widget JS

El chatbot (FastAPI) monta `frontend/` como estáticos en `/static`, así que normalmente tendrás:
- Widget: `{CHATBOT_BASE_URL}/static/chat-widget.js`
- Marked ESM: `{CHATBOT_BASE_URL}/static/marked.esm.js`

Si prefieres, puedes copiar el archivo y servirlo desde tu app Laravel, pero **no es obligatorio**.

#### A.2 Inyectar variables globales en la vista

En tu controlador Laravel que renderiza la vista (ej. `CourseController@show`), genera el token:

```php
use App\Services\ChatbotTokenService;

public function show(string $courseId, ChatbotTokenService $tokens)
{
    $userId = (string) auth()->id(); // ajusta a tu auth
    $jwt = $tokens->makeToken($userId, $courseId);

    return view('courses.show', [
        'courseId' => $courseId,
        'chatbotJwt' => $jwt,
        'chatbotBaseUrl' => config('services.chatbot.base_url'),
    ]);
}
```

En tu Blade (ej. `resources/views/courses/show.blade.php`):

```html
<script>
  window.CHATBOT_COURSE_ID = @json($courseId);
  window.CHATBOT_TOKEN = @json($chatbotJwt);

  // Recomendado si el chatbot está en otro dominio:
  window.CHATBOT_API_URL = @json(rtrim($chatbotBaseUrl, '/'));

  // Opcionales:
  window.CHATBOT_TITLE = 'Asistente del Curso';
  window.CHATBOT_SUBTITLE = 'Pregúntame sobre el contenido';
</script>

<script src="{{ rtrim($chatbotBaseUrl, '/') }}/static/chat-widget.js"></script>
```

Checklist de seguridad:
- **El token va sin el prefijo** `"Bearer "` (el widget lo agrega en el header).
- El JWT debe ser **por usuario y por curso** (claim `course_id`).
- TTL razonable (ej. 1 hora) y renovar en cada carga de página.

#### A.3 CORS (solo si tu Laravel y el chatbot están en dominios distintos)

El navegador hará `fetch()` hacia `{CHATBOT_BASE_URL}/api/chat` y `{CHATBOT_BASE_URL}/api/chat/history`.
El servidor del chatbot debe permitir tu dominio vía `CORS_ORIGINS` (config del chatbot).

---

### Opción B. Laravel como proxy (server-to-server)

Usa esta opción si:
- no quieres exponer el JWT al navegador, o
- quieres agregar rate limiting / auditoría / caching en tu backend.

#### B.1 Endpoint Laravel: `/api/chatbot/ask`

Ejemplo de controlador `app/Http/Controllers/ChatbotController.php`:

```php
<?php

namespace App\Http\Controllers;

use App\Services\ChatbotTokenService;
use GuzzleHttp\Client;
use Illuminate\Http\Request;

class ChatbotController extends Controller
{
    public function ask(Request $request, ChatbotTokenService $tokens)
    {
        $data = $request->validate([
            'question' => ['required', 'string', 'min:1', 'max:5000'],
            'course_id' => ['required', 'string', 'max:255'],
        ]);

        $userId = (string) $request->user()->id;
        $jwt = $tokens->makeToken($userId, $data['course_id']);

        $client = new Client([
            'base_uri' => rtrim(config('services.chatbot.base_url'), '/') . '/',
            'timeout' => 30,
        ]);

        $resp = $client->post('api/chat', [
            'headers' => [
                'Authorization' => 'Bearer ' . $jwt,
                'Accept' => 'application/json',
            ],
            'json' => [
                'question' => $data['question'],
                'course_id' => $data['course_id'],
            ],
        ]);

        return response()->json(json_decode((string) $resp->getBody(), true));
    }
}
```

Ruta (ejemplo) en `routes/api.php`:

```php
use App\Http\Controllers\ChatbotController;

Route::middleware('auth:sanctum')->post('/chatbot/ask', [ChatbotController::class, 'ask']);
```

---

### Errores típicos (y qué revisar)

- **401 `Missing authentication token.`**
  - No se envió `Authorization: Bearer ...` (o el token llegó vacío).
- **401 `Invalid authentication token.`**
  - Secreto distinto (`CHATBOT_JWT_SECRET` incorrecto) o algoritmo distinto a **HS256**.
- **401 `Token has expired.`**
  - `exp` en el pasado. Ajusta TTL/reloj del servidor.
- **401 `Token is missing required claim: course_id.`**
  - No incluiste `course_id` en el payload del JWT.
- **401 `Invalid token issuer.`**
  - El chatbot exige `JWT_ISSUER` y tu JWT no trae `iss` o no coincide.
- **404 `Course 'X' not found or inactive.`**
  - `course_id` no existe (o está inactivo) en la configuración multi-curso del chatbot.

---

### Prueba rápida (sin widget, desde Laravel / Postman)

1) Genera un token con `sub`, `course_id`, `exp`.
2) Llama:

- `POST {CHATBOT_BASE_URL}/api/chat`
- Header: `Authorization: Bearer <JWT>`
- JSON: `{ "question": "Hola", "course_id": "..." }`

Si recibes `answer`, la integración base está lista.

