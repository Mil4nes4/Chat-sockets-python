# Chat con Sockets en Python

Proyecto de laboratorio de Sistemas Operativos: implementación de un chat cliente-servidor mediante sockets TCP en Python, con soporte para múltiples clientes simultáneos, mensajes públicos y privados, envío de archivos, historial de mensajes y dos interfaces de cliente: consola y gráfica (tkinter).

---

## 1. Arquitectura

El sistema sigue un modelo **cliente-servidor** basado en sockets TCP:

- **Servidor (`servidor_chat.py`)**: centraliza las conexiones, administra los usuarios conectados, reenvía mensajes, gestiona mensajes privados, archivos y guarda el historial.
- **Cliente de consola (`consola.py`)**: interfaz textual para conectarse al chat.
- **Cliente gráfico (`gui.py`)**: interfaz visual con `tkinter`, estilo simple tipo Discord.
- **Módulo compartido (`cliente_chat.py`)**: funciones de red usadas por ambos clientes.

Cada cliente mantiene dos hilos:

1. Un hilo para **escuchar mensajes** del servidor.
2. Un hilo para **leer/enviar** la entrada del usuario.

El servidor crea un hilo por cada cliente conectado para atenderlo de forma concurrente.

---

## 2. Estructura del proyecto

```
chat_sockets/
├── servidor/
│   ├── servidor_chat.py          # Servidor principal
│   ├── historial_chat.txt        # Generado automáticamente por el servidor
│   └── archivos_recibidos/       # Copia de archivos enviados
├── cliente/
│   ├── cliente_chat.py           # Lógica de red compartida
│   ├── consola.py                # Cliente de terminal
│   └── gui.py                    # Cliente gráfico con tkinter
└── README.md                     # Este archivo
```

---

## 3. Requisitos

- Python 3.8 o superior.
- Librerías estándar utilizadas: `socket`, `threading`, `tkinter`, `os`, `datetime`, `json`, `base64`.
- El cliente de consola usa **códigos ANSI** para colores. Funciona en Windows 10/11 (cmd y PowerShell), Linux y macOS.
- El cliente gráfico usa `tkinter`.
- **Opcional**: instalar `Pillow` si se desea ver miniaturas de imágenes en la GUI:
  ```bash
  pip install Pillow
  ```
  Si no está instalado, la GUI igual indica que se recibió una imagen pero no muestra la miniatura.

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

Si deseas cambiar el puerto, edita la constante al inicio de `servidor_chat.py`:

```python
PUERTO = 5000
```

Al iniciarse mostrará la IP local del servidor y quedará esperando conexiones.

### 4.2. Cliente de consola

En otra terminal ejecuta:

```bash
python cliente/consola.py
```

Te pedirá:

1. La IP del servidor (usa `127.0.0.1` si estás en la misma máquina, o la IP de la máquina servidor).
2. El puerto (presiona Enter para usar el `5000` por defecto).
3. Tu nickname (debe ser único).

Una vez dentro, escribe mensajes y presiona Enter para enviarlos a todos.

La consola muestra mensajes con **colores** según su tipo: azul para los propios, amarillo para privados, verde para mensajes del servidor, etc. También emite un sonido al recibir mensajes o archivos de otros usuarios.

### 4.3. Cliente gráfico

Ejecuta:

```bash
python cliente/gui.py
```

Aparecerá una pantalla de login donde ingresas:

- IP del servidor.
- Puerto.
- Nickname.

Luego presiona **Conectar**. El chat principal incluye:

- Burbujas de mensajes con colores tipo Discord.
- Lista de usuarios conectados con indicador en línea.
- Doble clic en un usuario para enviarle un mensaje privado.
- Indicador de "escribiendo...".
- Envío de archivos con botón de clip (📎).
- Preview de imágenes (si tienes Pillow instalado).
- Búsqueda en el historial.
- Cambio entre tema oscuro y claro.
- Notificación sonora al recibir mensajes.

---

## 5. Comandos disponibles

### Consola

| Función | Comando | Alias | Descripción |
|---|---|---|---|
| Mensaje público | Escribir normalmente | - | Llega a todos los usuarios conectados. |
| Mensaje privado | `/privado <usuario> <mensaje>` | `/p` | Envía un mensaje solo al usuario indicado. |
| Lista de usuarios | `/usuarios` | `/u` | Muestra los nicknames conectados. |
| Enviar archivo | `/archivo <ruta> [usuario]` | `/a` | Envía un archivo a todos o a un usuario. |
| Buscar en historial | `/buscar <texto>` | `/b` | Busca coincidencias en los mensajes de la sesión. |
| Limpiar pantalla | `/limpiar` | `/clear` | Limpia los mensajes anteriores de la consola. |
| Reconectar | `/reconectar` | `/r` | Intenta reconectar al servidor. |
| Salir | `/salir` | `/s` | Desconecta al cliente del servidor. |
| Ayuda | `/ayuda` | `/h` | Muestra la lista de comandos. |

### Interfaz gráfica

- Selecciona el destinatario en el menú desplegable (`Todos` o un usuario específico).
- Presiona **Enviar** o la tecla `Enter` para enviar mensajes.
- Presiona **📎 Adjuntar archivo** para enviar archivos.
- Haz doble clic en un usuario de la lista para seleccionarlo como destinatario privado.
- Presiona **Buscar** para buscar en el historial.
- Presiona **Tema claro/oscuro** para cambiar el tema.

Atajos de teclado en la GUI:

- `Enter`: enviar mensaje.
- `Escape`: desconectar / salir.
- `Ctrl + T`: cambiar tema.
- `Ctrl + L`: limpiar el área de chat.

---

## 6. Protocolo de mensajes

El servidor y los clientes se comunican mediante mensajes con prefijos:

| Prefijo | Uso |
|---|---|
| `NICK:<nombre>` | Registro del nickname al conectarse. |
| `MSG:<mensaje>` | Mensaje público. |
| `PRIV:<usuario>:<mensaje>` | Mensaje privado. |
| `LIST` | Solicitud de lista de usuarios. |
| `FILE:<destinatario>:<nombre>:<bytes>` | Envío de archivo. |
| `TYPING:<destinatario>` | Indicador de que el usuario está escribiendo. |
| `EXIT` | Desconexión ordenada. |

El servidor responde con:

| Prefijo | Uso |
|---|---|
| `SERVER:<mensaje>` | Mensajes del sistema (bienvenida, errores, notificaciones). |
| `LIST:<u1,u2,u3>` | Lista de usuarios conectados. |
| `PRIV:<emisor>:<mensaje>` | Mensaje privado recibido. |
| `FILE:<emisor>:<nombre>:<bytes>` | Archivo recibido. |
| `TYPING:<emisor>:<destinatario>` | Notificación de que un usuario está escribiendo. |
| `HIST:<linea>` | Línea del historial enviada al cliente que se conecta. |

---

## 7. Pruebas en red real (diferentes computadoras)

Para probar el chat entre computadoras distintas:

1. En la máquina que hará de servidor, obtén su dirección IP:
   - **Windows**: abre `cmd` y ejecuta `ipconfig`.
   - **Linux/macOS**: abre una terminal y ejecuta `hostname -I` o `ifconfig`.

2. Asegúrate de que el servidor esté escuchando en `0.0.0.0` (valor por defecto).

3. En el cliente, usa la **IP local del servidor** si ambas computadoras están en la misma red WiFi/Ethernet (por ejemplo, `192.168.1.10`).

4. Si las computadoras están en redes diferentes (por ejemplo, cada uno en su casa):
   - Necesitas la **IP pública** del servidor.
   - En el router del servidor debes configurar **redirección de puertos** (port forwarding) del puerto `5000` hacia la IP local del servidor.
   - También puedes usar una VPN como Tailscale o Hamachi si no quieres configurar el router.

5. Verifica que el firewall del servidor permita conexiones entrantes por el puerto `5000`.

---

## 8. Notas importantes

- Los nicknames deben ser únicos. Si un usuario intenta usar uno repetido, el servidor le pedirá que elija otro.
- Los archivos recibidos por los clientes se guardan automáticamente en la carpeta `descargas/` (relativa al directorio desde donde se ejecute el cliente).
- El servidor guarda una copia de los archivos enviados en `chat_sockets/servidor/archivos_recibidos/`.
- El historial de mensajes públicos se guarda en `chat_sockets/servidor/historial_chat.txt`.
- Los mensajes privados y archivos privados **no** se guardan en el historial público.
- El servidor sigue funcionando aunque los clientes se desconecten; solo se cierra con `Ctrl + C`.
- Si la consola no muestra colores en Windows, asegúrate de usar **cmd** o **PowerShell** moderno (Windows 10 o superior).

---

## 9. Ejemplo de flujo de uso

1. Máquina A ejecuta el servidor.
2. Máquina B ejecuta `gui.py` y se conecta a la IP de A.
3. Máquina C ejecuta `consola.py` y se conecta a la IP de A.
4. Los tres usuarios pueden chatear, enviarse mensajes privados y compartir archivos.

