# identity — criterios de aceptación

Usuarios, magic link y sesiones. Es el único dominio que sabe qué es un email;
los demás solo ven un `UserId`.

## Pedir el enlace

- **IDENTITY-01** — pedir un magic link para un email nuevo crea el usuario y responde 202.
- **IDENTITY-02** — pedir un magic link para un email que ya existe responde exactamente igual: la respuesta no revela si la cuenta existe.
- **IDENTITY-03** — el email se normaliza (minúsculas, sin espacios al borde): `  Persona@Ejemplo.CL ` y `persona@ejemplo.cl` son el mismo usuario.
- **IDENTITY-04** — un email con formato inválido devuelve 422 sin crear usuario ni enviar correo.
- **IDENTITY-05** — el correo enviado contiene un enlace a `public_url` con el token.
- **IDENTITY-06** — el token no se guarda en claro: en la base solo existe su hash.
- **IDENTITY-07** — pedir un segundo enlace invalida el primero que seguía pendiente.
- **IDENTITY-08** — superar el límite de solicitudes por email devuelve 429.
- **IDENTITY-09** — superar el límite de solicitudes por IP devuelve 429, aunque cada intento use un email distinto.

## Canjear el enlace

- **IDENTITY-10** — verificar un token válido crea una sesión y devuelve la cookie.
- **IDENTITY-11** — un token usado dos veces devuelve 401 y no crea una segunda sesión.
- **IDENTITY-12** — un token expirado devuelve 401 con un código propio, para poder decirle al usuario que pida otro.
- **IDENTITY-13** — un token inexistente o falsificado devuelve 401.
- **IDENTITY-14** — la cookie de sesión es `httponly` y `samesite=lax`.

## Usar la sesión

- **IDENTITY-15** — `GET /auth/me` sin cookie devuelve 401.
- **IDENTITY-16** — `GET /auth/me` con cookie válida devuelve el email del usuario.
- **IDENTITY-17** — `POST /auth/logout` revoca la sesión: la misma cookie deja de servir.
- **IDENTITY-18** — una sesión expirada no autentica.
- **IDENTITY-19** — una cookie falsificada no autentica.

## Secretos

- **IDENTITY-20** — ni el token del enlace ni la cookie de sesión aparecen nunca en los logs.
- **IDENTITY-21** — el email completo no aparece en los logs; solo su versión enmascarada.

## Abrir el enlace

- **IDENTITY-22** — el enlace del correo se puede abrir: apunta a una página que responde a `GET`, no a un endpoint que solo acepta `POST`.
- **IDENTITY-23** — abrir el enlace no inicia sesión por sí solo: canjear el token sigue siendo un `POST`, para que ningún `GET` cambie estado y un escáner de enlaces no queme el token.

## Acceso por la red de Tailscale

Con `PORTADA_ACCESO=tailnet` no hay pantalla de entrar: quien llega por la red de
Tailscale ya pasó por la puerta de Tailscale, y entra como el usuario de la
instancia (`PORTADA_ACCESO_COMO`). La puerta de la app pasa a ser de dónde viene
la petición, no qué cookie trae.

- **IDENTITY-24** — con el acceso por tailnet, una petición desde una IP de Tailscale entra como el usuario configurado, sin cookie ni enlace.
- **IDENTITY-25** — con el acceso por tailnet, una petición que no viene de Tailscale ni del propio equipo recibe 403: escuchar en la red local no abre la app a quien esté en el mismo wifi.
- **IDENTITY-26** — si el usuario configurado no existe todavía, se crea al primer acceso: una instancia nueva arranca sin pasos.
- **IDENTITY-27** — con el acceso por tailnet no se manda ningún enlace: pedirlo responde 404.
