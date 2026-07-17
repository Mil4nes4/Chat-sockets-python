# Chat con Sockets en Python

Proyecto de laboratorio de Sistemas Operativos: un chat cliente-servidor sobre **sockets TCP** en Python, con múltiples clientes simultáneos, **tráfico cifrado con TLS**, mensajes públicos y privados, **salas** públicas, **grupos**, envío de archivos, historial, confirmaciones de **entregado/leído**, reacciones, menciones y dos interfaces de cliente: consola (ANSI) y gráfica (CustomTkinter).

---

## 1. Arquitectura

Modelo **cliente-servidor** basado en sockets TCP, con todo el tráfico envuelto en **TLS**:

- **Servidor (`servidor_chat.py`)**: centraliza las conexiones, administra usuarios, salas y grupos, reenvía mensajes, gestiona privados y archivos, guarda el historial y rastrea el estado entregado/leído de cada mensaje. Crea **un hilo por cliente** conectado.
- **Cliente de consola (`consola.py`)**: interfaz de terminal con colores ANSI.
- **Cliente gráfico (`gui.py`)**: interfaz visual con **CustomTkinter** (burbujas, avatares, temas claro/oscuro).
- **Módulo compartido (`cliente_chat.py`)**: lógica de red (framing, TLS, helpers de protocolo) usada por ambos clientes.

Cada cliente mantiene dos hilos: uno para **escuchar** mensajes del servidor y otro para **enviar** la entrada del usuario. Los envíos se serializan con un lock para que ambos hilos puedan escribir en el mismo socket sin corromper el framing.

**Framing:** cada mensaje es un objeto JSON precedido por su longitud en 4 bytes (big-endian). El TLS cifra el canal completo.

---

## 2. Estructura del proyecto

```
chat_sockets/
├── servidor/
│   ├── servidor_chat.py          # Servidor principal
│   ├── certs/                    # Certificado y clave TLS (necesarios para arrancar)
│   │   ├── servidor_cert.pem
│   │   └── servidor_key.pem
│   ├── historial_chat.txt        # Generado automáticamente por el servidor
│   └── archivos_recibidos/       # Copia de archivos enviados
├── cliente/
│   ├── cliente_chat.py           # Lógica de red compartida (TLS, framing, protocolo)
│   ├── consola.py                # Cliente de terminal
│   └── gui.py                    # Cliente gráfico con CustomTkinter
└── README.md                     # Este archivo
```

---

## 3. Requisitos

- **Python 3.8 o superior.**
- Librerías estándar: `socket`, `ssl`, `threading`, `tkinter`, `os`, `datetime`, `json`, `base64`.
- **CustomTkinter (requerido para el cliente gráfico):**
  ```bash
  pip install customtkinter
  ```
- **Opcionales:**
  - `Pillow` — miniaturas de imágenes en la GUI. Sin él, la GUI avisa que llegó una imagen pero no la previsualiza.
    ```bash
    pip install Pillow
    ```
  - `tkinterdnd2` — arrastrar y soltar archivos en la GUI. Sin él, se envían igual con el botón 📎.
    ```bash
    pip install tkinterdnd2
    ```
- El cliente de consola usa **códigos ANSI** para colores (funciona en Windows 10/11 con cmd y PowerShell, Linux y macOS).
- **Certificados TLS:** el servidor exige TLS y no arranca sin `servidor/certs/servidor_cert.pem` y `servidor/certs/servidor_key.pem`. Ya vienen incluidos en el proyecto (autofirmados). El cliente cifra pero no valida la CA (por ser autofirmado), así que funciona con cualquier IP.

---

## 4. Cómo ejecutar

### 4.1. Servidor

Abre una terminal en la carpeta del proyecto y ejecuta:

```bash
python servidor/servidor_chat.py
```

Por defecto el servidor escucha en:

- IP: `0.0.0.0` (acepta conexiones de cualquier dirección)
- Puerto: `5000`

El puerto se controla con la variable de entorno **`CHAT_PUERTO`** (no editando el código):

```bash
# Linux/macOS
CHAT_PUERTO=443 python servidor/servidor_chat.py
# Windows (PowerShell)
$env:CHAT_PUERTO = "443"; python servidor/servidor_chat.py
```

Al iniciarse muestra la IP local y queda esperando conexiones cifradas.

### 4.2. Cliente de consola

En otra terminal:

```bash
python cliente/consola.py
```

Te pedirá la **IP del servidor** (`127.0.0.1` si es la misma máquina), el **puerto** (Enter usa `5000`) y tu **nickname** (único). Una vez dentro, escribe y presiona Enter para enviar a tu sala actual. Los mensajes se muestran con colores según su tipo y suena una notificación al recibir mensajes/archivos ajenos.

### 4.3. Cliente gráfico

```bash
python cliente/gui.py
```

En el login ingresas IP, puerto, nickname, y podés elegir **avatar** y **color de perfil**. Luego **Conectar**.

---

## 5. Funciones

- **TLS**: todo el tráfico va cifrado.
- **Mensajes públicos y privados**, con historial reenviado al conectarse.
- **Salas públicas**: cada usuario está en **una sola sala a la vez** (por defecto `General`). El chat público y el historial se acotan a la sala; al entrar a otra sala recibís su historial. Sirven como canales temáticos.
- **Grupos**: conversaciones con un subconjunto invitado de usuarios; podés estar en varios a la vez y se superponen al chat general.
- **Entregado / leído**: cada mensaje propio muestra su estado — **✓ enviado → ✓✓ entregado → ✓✓ Leído**. En la GUI, "leído" se marca cuando la otra persona tiene la ventana en foco.
- **Reacciones** con emojis (clic derecho sobre un mensaje, en la GUI).
- **Menciones** `@usuario` (resaltado + sonido distinto).
- **Editar y eliminar** el último mensaje propio (ventana de 2 minutos).
- **Envío de archivos** (a todos, a un usuario o a un grupo), con **arrastrar y soltar** y preview de imágenes.
- **Indicador de "escribiendo…"**, **búsqueda en el historial**, **links clicables**.
- **Personalización (GUI)**: temas claro/oscuro, avatares y colores de perfil, selector de emojis y color de acento.
- **Utilidades**: `/ping` (latencia), `/stats`, `/whois`, `/silenciar`.
- **Anti-flood**: límite de mensajes por segundo para evitar spam.

---

## 6. Comandos de consola

| Función | Comando | Alias |
|---|---|---|
| Mensaje público (a tu sala) | Escribir normalmente | — |
| Mensaje privado | `/privado <usuario> <mensaje>` | `/p` |
| Lista de usuarios | `/usuarios` | `/u` |
| Enviar archivo | `/archivo <ruta> [usuario]` | `/a` |
| Buscar en historial | `/buscar <texto>` | `/b` |
| Insertar emoji | `/emoji` o `/emoji <n> [texto]` | `/e` |
| **Ver salas y en cuál estás** | `/salas` | — |
| **Crear una sala y entrar** | `/crear <sala>` | — |
| **Cambiarte de sala** | `/unirse <sala>` (usa `General` para volver) | — |
| Crear grupo | `/grupo crear <nombre> <u1,u2,...>` | — |
| Invitar a grupo | `/grupo invitar <nombre> <u1,u2,...>` | — |
| Salir de grupo | `/grupo salir <nombre>` | — |
| Mensaje a grupo | `/grupo <nombre> <mensaje>` | — |
| Ver tus grupos | `/grupos` | — |
| Editar último mensaje | `/editar <texto>` | — |
| Eliminar último mensaje | `/eliminar` | — |
| Latencia (RTT) | `/ping` | — |
| Estadísticas del servidor | `/stats` | — |
| Info de un usuario | `/whois <usuario>` | — |
| Silenciar/mostrar a alguien | `/silenciar <usuario>` | — |
| Ver historial paginado | `/historial` | `/hist` |
| Limpiar pantalla | `/limpiar` | `/clear` |
| Reconectar | `/reconectar` | `/r` |
| Salir | `/salir` | `/s` |
| Ayuda | `/ayuda` | `/h` |

### Interfaz gráfica

- Elegí el destinatario en el desplegable (`Todos`, un usuario o un grupo).
- Cambiá de **sala** con el selector "SALA" de la barra lateral; el botón **＋** crea una sala nueva.
- **Enviar** o `Enter` para mandar; **📎** o arrastrar un archivo para enviarlo.
- **Clic derecho** sobre un mensaje: reaccionar, o editar/eliminar los propios.
- Clic en un usuario de la lista para mencionarlo con `@`.

Atajos: `Enter` enviar · `Escape` desconectar/salir · `Ctrl + L` limpiar el chat.

---

## 7. Protocolo de mensajes

Los mensajes son objetos **JSON** con un campo `tipo`, enviados con framing de longitud (4 bytes) sobre TLS. Tipos principales:

| Tipo (cliente → servidor) | Uso |
|---|---|
| `nick` | Registro del nickname (con avatar y color) al conectar. |
| `msg` / `priv` | Mensaje público (a la sala) / privado. |
| `list` | Solicitud de lista de usuarios. |
| `file` | Envío de archivo. |
| `typing` | Indicador de "escribiendo…". |
| `reaccion` | Reacción con emoji a un mensaje. |
| `grupo_crear` / `grupo_invitar` / `grupo_msg` / `grupo_salir` | Gestión de grupos. |
| `sala_crear` / `sala_unirse` / `sala_salir` / `sala_listar` | Gestión de salas. |
| `msg_editar` / `msg_eliminar` | Editar o eliminar un mensaje propio. |
| `delivered` / `read` | Acuse de entregado / leído. |
| `ping` / `stats_solicitar` / `whois` | Utilidades. |
| `exit` | Desconexión ordenada. |

| Tipo (servidor → cliente) | Uso |
|---|---|
| `server` | Mensajes del sistema (bienvenida, errores, avisos). |
| `usuarios` | Lista de conectados (con avatares y colores). |
| `msg` / `priv` / `file` | Mensaje o archivo recibido. |
| `historial` | Línea del historial (de la sala) al conectarse o cambiar de sala. |
| `salas` / `sala_actual` | Estado de salas y sala activa del usuario. |
| `reaccion` / `msg_editado` / `msg_eliminado` | Cambios sobre mensajes existentes. |
| `estado` | Estado agregado entregado/leído de un mensaje propio. |
| `pong` / `stats` / `whois_resultado` | Respuestas de utilidades. |

---

## 8. Pruebas en red real (diferentes computadoras)

Para probar el chat entre computadoras distintas:

1. En la máquina que hará de servidor, obtén su dirección IP:
   - **Windows**: abre `cmd` y ejecuta `ipconfig`.
   - **Linux/macOS**: abre una terminal y ejecuta `hostname -I` o `ifconfig`.

2. Asegúrate de que el servidor esté escuchando en `0.0.0.0` (valor por defecto).

3. En el cliente, usa la **IP local del servidor** si ambas computadoras están en la misma red WiFi/Ethernet (por ejemplo, `192.168.1.10`).

4. Si las computadoras están en redes diferentes, hay varias formas. Las dos que se usaron para probar este proyecto:

   **Opción A — Túnel con ngrok** (no requiere que quien se conecta instale nada):
   ```bash
   $env:NGROK_TOKEN = "tu_token_aqui"
   .\scripts\setup_ngrok.ps1
   ```
   Levanta un túnel TCP hacia el puerto local y muestra una dirección pública (ej. `0.tcp.sa.ngrok.io:27660`) que cambia cada vez que se reinicia el túnel.

   **Opción B — Servidor en una VM de la nube (Google Cloud, tier gratuito)**: se despliega el mismo `servidor_chat.py` en una instancia `e2-micro` con IP pública fija, corriendo dentro de una sesión de `tmux` para que quede persistente. Ventaja sobre ngrok: la IP no cambia entre reinicios.

   También es válido el **port forwarding** en el router, o una VPN de malla como Tailscale/Hamachi.

5. Verifica que el firewall del servidor (y el de red, en el caso de la nube) permita conexiones entrantes por el puerto usado.

6. **Redes restrictivas (universitarias/corporativas):** algunas bloquean puertos de salida no estándar. Si la conexión falla solo en ese tipo de redes, el plan B es correr el servidor en el puerto `443` (`CHAT_PUERTO=443`) en la VM de la nube — la mayoría de firewalls permiten salida por ese puerto al ser el de HTTPS. Requiere dar permiso a Python para usar puertos privilegiados: `sudo setcap 'cap_net_bind_service=+ep' $(which python3)`.

---

## 9. Notas importantes

- Los nicknames deben ser únicos; el servidor rechaza los repetidos.
- El servidor **exige TLS**: un cliente sin cifrado no conecta. Los certificados van incluidos en `servidor/certs/`.
- Al conectarte entrás a la sala `General`. El chat público solo llega a quienes están en tu **misma sala**.
- Los archivos recibidos se guardan en la carpeta `descargas/` (relativa al directorio del cliente); el servidor guarda copia en `servidor/archivos_recibidos/`.
- El historial de mensajes públicos se guarda en `servidor/historial_chat.txt` (etiquetado por sala). Los privados y archivos privados **no** se guardan en el historial público.
- El servidor sigue funcionando aunque los clientes se desconecten; se cierra con `Ctrl + C`.
- Si la consola no muestra colores en Windows, usa **cmd** o **PowerShell** moderno (Windows 10 o superior).

---

## 10. Ejemplo de flujo de uso

1. Máquina A ejecuta el servidor.
2. Máquina B ejecuta `gui.py` y se conecta a la IP de A.
3. Máquina C ejecuta `consola.py` y se conecta a la IP de A.
4. Los tres chatean en la sala `General`; pueden crear salas, mandarse privados, formar grupos y compartir archivos, viendo el estado entregado/leído de sus mensajes.
