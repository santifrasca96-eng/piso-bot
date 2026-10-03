# Buscador de piso / habitación en Barcelona (GitHub Actions)

GitHub ejecuta el bot cada ~10 minutos, gratis. En cada pasada atiende tus botones de Telegram,
revisa los portales y te avisa de lo nuevo con **✅ Preparar contacto** / **❌ Descartar**.
Al aprobar, te da el mensaje redactado para que lo pegues tú en el anuncio (no envía nada solo).

## Puesta en marcha (todo desde el navegador, sin instalar nada)

### 1. Telegram
1. Habla con **@BotFather** → `/newbot` → guarda el **token** (no lo compartas con nadie).
2. Escribe un mensaje cualquiera a tu bot nuevo ("hola").
3. Para sacar tu **chat id**, abre en el navegador (sustituye TOKEN por el tuyo):
   `https://api.telegram.org/botTOKEN/getUpdates`
   y busca `"chat":{"id":` seguido de un número (ej. `123456789`). Ese número es tu chat id.

### 2. Repositorio en GitHub
1. Crea cuenta en github.com (gratis, sin tarjeta) y pulsa **New repository**.
   Nombre `piso-bot`, **Public** (necesario: en repositorios públicos los minutos de Actions son gratuitos).
2. Descomprime el zip. En el repositorio: **Add file → Upload files** y arrastra el CONTENIDO de la carpeta
   (no la carpeta en sí). Pulsa **Commit changes**.
3. Si no se subió la carpeta oculta `.github`: **Add file → Create new file**, escribe como nombre
   `.github/workflows/piso-bot.yml` (al teclear `/` se crean las carpetas), pega dentro el contenido
   del archivo `workflow-para-github.yml` del zip y haz commit.

### 3. Secretos (aquí van tus datos, que no se ven en el repositorio público)
En el repositorio: **Settings → Secrets and variables → Actions → New repository secret**. Crea tres:

| Nombre | Valor |
|---|---|
| `TELEGRAM_TOKEN` | el token de BotFather |
| `TELEGRAM_CHAT_ID` | tu chat id |
| `PROFILE_YAML` | tu perfil (ver abajo) |

Ejemplo de `PROFILE_YAML` (cámbialo por tus datos; borra las líneas que no sean ciertas):
```
name: "Santiago"
age: 30
job: "ingeniero de pista en el campeonato del mundo y el europeo de motociclismo"
move_in: "enero de 2027"
phone: "+34 600 000 000"
extra_room_lines:
  - "Soy una persona tranquila, no fumadora y sin mascotas."
```

### 4. Probar (pestaña **Actions**)
Si GitHub pide confirmar, pulsa "I understand my workflows, go ahead and enable them".
Entra en **piso-bot → Run workflow** y lanza, por orden:
1. **check-urls** → en el log verás qué búsquedas funcionan desde GitHub (OK / VACÍO / FALLO).
2. **dry-run** → muestra qué aceptaría y rechazaría, sin avisar.
3. **tick** → pasada real: te llegan los primeros avisos a Telegram (máx. 5 por búsqueda).

Desde ahí corre solo cada ~10 minutos. Las pasadas programadas solo se ejecutan desde la rama principal (`main`).

## Cómo interpretar los resultados de check-urls
- `FALLO … 404` → la URL está mal: ábrela en tu navegador y copia la correcta en `config.yaml`.
- `FALLO … 403/429` → el portal bloquea las IPs de GitHub (son de datacenter). Alternativa: alertas por email del portal.
- `VACÍO` → la página carga pero no se reconocen anuncios: hay que ajustar `LINK_PATTERNS` en `piso_bot/parsers.py`.

## Limitaciones (importante)
- **Retraso:** GitHub puede retrasar las pasadas programadas varios minutos en horas de carga; el intervalo mínimo
  permitido es de 5 min. Tus botones se atienden en la siguiente pasada (el círculo del botón puede tardar en
  dejar de girar; el borrador llega igualmente).
- **Se desactiva a los 60 días:** GitHub desactiva las tareas programadas de repositorios públicos sin actividad
  en 60 días. Cada vez que edites un archivo en el repositorio (por ejemplo `config.yaml`) el contador se reinicia.
  Pon un recordatorio para editar algo cada ~50 días. Además, el bot manda **un mensaje silencioso al día**
  ("🟢 Buscador activo"): si deja de llegar, algo se ha parado (reactívalo en Actions → piso-bot → Enable workflow).
- **Estado:** los anuncios ya vistos se guardan en la caché de Actions (se borra tras 7 días sin uso; con pasadas
  cada 10 min no ocurre). Si se perdiera, volvería a avisarte de algunos anuncios repetidos (máx. 5 por búsqueda).
- **Privacidad:** el repositorio y los logs son públicos (se ven búsquedas, zonas y presupuesto). No se ven el token,
  el chat id ni tu perfil. El token se oculta además en los logs.

## Personalizar
Edita `config.yaml` desde GitHub (icono del lápiz → Commit): presupuestos, zonas, búsquedas, palabras que descartan
o suman puntos. Se aplica en la siguiente pasada.

## Alternativa: servidor propio o tu PC
`python -m piso_bot run` deja el bot corriendo de forma continua (con botones instantáneos). Necesita un `.env`
(ver `.env.example`) y Python 3.10+. En `deploy/` hay un servicio systemd de ejemplo.

## Importante
- **Subarriendo**: para alquilar habitaciones de un piso necesitas autorización escrita del propietario
  (art. 8 LAU). El mensaje de pisos ya lo pregunta. No es asesoramiento legal.
- **Estafas**: nunca pagues señal ni reserves sin visitar (o videollamada + contrato verificable). El bot marca 🚨
  los anuncios con señales típicas, pero no sustituye a tu criterio.
