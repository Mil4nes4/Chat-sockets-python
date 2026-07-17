# Chat con Sockets TCP en Python

Proyecto de laboratorio de Sistemas Operativos que implementa un chat cliente-servidor mediante sockets TCP en Python. Permite conectar varios usuarios simultáneamente desde una interfaz de consola o una interfaz gráfica.

## 1. Funciones principales

El sistema incluye:

* Mensajes públicos por salas.
* Mensajes privados.
* Grupos de usuarios.
* Envío de archivos.
* Historial de mensajes públicos.
* Lista de usuarios conectados.
* Indicador de “escribiendo”.
* Búsqueda de mensajes.
* Reacciones con emojis.
* Conversión de códigos como `:smile:` o `:fire:`.
* Reconexión desde la consola.
* Notificaciones sonoras.
* Cifrado de mensajes de texto con Fernet.
* Estados de envío, entrega y lectura.
* Interfaz de consola.
* Interfaz gráfica con CustomTkinter.

---

## 2. Arquitectura

El proyecto utiliza una arquitectura cliente-servidor:

* **Servidor:** acepta las conexiones, administra usuarios, salas y grupos, y reenvía los mensajes.
* **Cliente:** envía y recibe información mediante sockets TCP.
* **Cliente de consola:** permite utilizar el chat desde una terminal.
* **Cliente gráfico:** ofrece una interfaz visual con salas, grupos, usuarios, emojis y archivos.

El servidor crea un hilo para cada cliente conectado. Los clientes utilizan un hilo adicional para escuchar los mensajes mientras el usuario continúa utilizando la interfaz.

La comunicación entre clientes siempre pasa por el servidor.

---

## 3. Salas y grupos

Las salas y los grupos tienen funciones diferentes.

### Salas

Cada usuario pertenece a una sola sala pública.

Los mensajes públicos únicamente son recibidos por los usuarios que están en la misma sala.

La sala predeterminada es:

```text
General
```

Los usuarios pueden crear nuevas salas y cambiarse entre ellas.

### Grupos

Los grupos son conversaciones privadas entre varios usuarios seleccionados.

Un grupo funciona independientemente de la sala actual de sus miembros. Por ejemplo, dos usuarios pueden estar en salas distintas y continuar conversando dentro del mismo grupo.

---

## 4. Estructura del proyecto

```text
chat_sockets/
├── servidor/
│   ├── servidor_chat.py
│   ├── historial_chat.txt
│   └── archivos_recibidos/
├── cliente/
│   ├── __init__.py
│   ├── cliente_chat.py
│   ├── consola.py
│   ├── gui.py
│   ├── clave_chat.key
│   └── descargas/
├── scripts/
│   └── setup_ngrok.ps1
├── requirements.txt
└── README.md
```

Los archivos `historial_chat.txt`, `clave_chat.key` y las carpetas de archivos se generan automáticamente cuando son necesarios.

---

## 5. Requisitos

* Python 3.8 o superior.
* Tkinter.
* CustomTkinter.
* Cryptography.
* Pillow para mostrar miniaturas de imágenes.

Instala las dependencias desde la carpeta principal:

```bash
pip install -r requirements.txt
```

También pueden instalarse manualmente:

```bash
pip install customtkinter cryptography Pillow
```

---

## 6. Clave de cifrado

Los mensajes públicos, privados y grupales se cifran con Fernet antes de enviarse al servidor.

La primera vez que se ejecuta un cliente se genera el archivo:

```text
cliente/clave_chat.key
```

Todos los clientes deben utilizar exactamente la misma clave. Para conectar clientes desde diferentes computadoras:

1. Ejecuta primero uno de los clientes.
2. Copia el archivo `clave_chat.key`.
3. Colócalo dentro de la carpeta `cliente/` de las demás computadoras.

El servidor no necesita este archivo. Solamente recibe y reenvía el contenido cifrado.

También puede definirse la clave mediante la variable de entorno:

```text
CHAT_FERNET_KEY
```

El cifrado se aplica a los mensajes de texto. Los archivos se transfieren codificados en Base64, pero no están cifrados con Fernet.

---

## 7. Cómo ejecutar

### Servidor

Desde la carpeta principal:

```bash
python servidor/servidor_chat.py
```

El servidor utiliza por defecto:

```text
IP: 0.0.0.0
Puerto: 5000
```

La dirección `0.0.0.0` permite aceptar conexiones desde las interfaces de red de la computadora.

Para cambiar el puerto puede utilizarse la variable de entorno `CHAT_PUERTO`.

En PowerShell:

```powershell
$env:CHAT_PUERTO = "6000"
python servidor/servidor_chat.py
```

### Cliente de consola

```bash
python cliente/consola.py
```

El programa solicitará:

* Dirección IP o dominio del servidor.
* Puerto.
* Nickname.

Para conectarse desde la misma computadora se puede utilizar:

```text
127.0.0.1
```

### Cliente gráfico

```bash
python cliente/gui.py
```

La pantalla de inicio permite elegir:

* IP o dominio del servidor.
* Puerto.
* Nickname.
* Avatar.
* Color de perfil.

La interfaz principal permite cambiar de sala, seleccionar destinatarios, crear grupos, enviar archivos, insertar emojis, reaccionar y buscar mensajes.

---

## 8. Comandos de consola

| Comando                           | Descripción                                |
| --------------------------------- | ------------------------------------------ |
| Escribir normalmente              | Envía un mensaje público a la sala actual. |
| `/privado <usuario> <mensaje>`    | Envía un mensaje privado.                  |
| `/p <usuario> <mensaje>`          | Alias de mensaje privado.                  |
| `/usuarios`                       | Muestra los usuarios conectados.           |
| `/salas`                          | Muestra las salas disponibles.             |
| `/crear <nombre>`                 | Crea una sala y entra en ella.             |
| `/unirse <nombre>`                | Cambia a otra sala.                        |
| `/salirSala`                      | Regresa a la sala General.                 |
| `/grupo crear <nombre> <u1,u2>`   | Crea un grupo.                             |
| `/grupo invitar <nombre> <u1,u2>` | Invita usuarios a un grupo.                |
| `/grupo salir <nombre>`           | Sale de un grupo.                          |
| `/grupo <nombre> <mensaje>`       | Envía un mensaje al grupo.                 |
| `/grupos`                         | Muestra los grupos del usuario.            |
| `/archivo <ruta> [usuario]`       | Envía un archivo a todos o a un usuario.   |
| `/emoji`                          | Muestra el selector de emojis.             |
| `/buscar <texto>`                 | Busca mensajes de la sesión.               |
| `/limpiar`                        | Limpia la consola.                         |
| `/reconectar`                     | Intenta conectarse nuevamente.             |
| `/ayuda`                          | Muestra los comandos disponibles.          |
| `/salir`                          | Cierra la conexión.                        |

---

## 9. Emojis

Los emojis pueden insertarse directamente desde el selector de la consola o desde el botón de la interfaz gráfica.

También se pueden utilizar códigos dentro del mensaje:

```text
Hola :smile:
Excelente trabajo :fire:
Me gusta :thumbsup:
```

El cliente los convierte antes de cifrar y enviar el mensaje.

Algunos códigos disponibles son:

```text
:smile:      😄
:laugh:      😂
:heart:      ❤️
:fire:       🔥
:thumbsup:   👍
:sad:        😢
:angry:      😡
:party:      🥳
:eyes:       👀
:check:      ✅
```

---

## 10. Estados de mensajes

Cada mensaje de texto tiene un identificador único.

La interfaz puede mostrar los siguientes estados:

| Estado     | Significado                                                |
| ---------- | ---------------------------------------------------------- |
| `…`        | El mensaje está pendiente de confirmación.                 |
| `✓`        | El servidor recibió el mensaje.                            |
| `✓✓`       | El mensaje fue entregado a los destinatarios conectados.   |
| `✓✓ Leído` | Los destinatarios mostraron el mensaje en la vista activa. |
| `✗`        | El mensaje no pudo enviarse correctamente.                 |

El estado de lectura no significa que el usuario haya comprendido el mensaje, sino que el cliente lo mostró dentro de la conversación correspondiente.

---

## 11. Protocolo de comunicación

La comunicación ya no utiliza cadenas con prefijos como `MSG:` o `PRIV:`.

Los datos se envían como objetos JSON. Antes de cada JSON se envían 4 bytes que indican el tamaño de la trama.

Ejemplo conceptual:

```json
{
  "tipo": "msg",
  "id": "identificador-unico",
  "contenido": "contenido-cifrado",
  "cifrado": true
}
```

Los principales tipos de mensajes son:

```text
nick
msg
priv
file
list
typing
reaccion
grupo_crear
grupo_invitar
grupo_msg
grupo_salir
sala_listar
sala_crear
sala_unirse
sala_salir
ack
delivered
read
exit
```

El encabezado de longitud evita que varios mensajes TCP recibidos juntos o divididos en diferentes paquetes dañen la lectura del protocolo.

---

## 12. Conexión en red local

Cuando todos los equipos se encuentran en la misma red WiFi o Ethernet:

1. Ejecuta el servidor.
2. Obtén la IP local de la computadora servidor.

En Windows:

```bash
ipconfig
```

3. Busca una dirección similar a:

```text
192.168.1.10
```

4. Utiliza esa dirección en los clientes.
5. Verifica que el firewall permita conexiones al puerto `5000`.

Todos los clientes deben tener la misma copia de `clave_chat.key`.

---

## 13. Conexión mediante ngrok

Ngrok permite conectar clientes que están en redes diferentes sin configurar el router.

Primero ejecuta el servidor:

```bash
python servidor/servidor_chat.py
```

Después, en PowerShell, configura el token y ejecuta el script:

```powershell
$env:NGROK_TOKEN = "tu_token_aqui"
.\scripts\setup_ngrok.ps1
```

Ngrok mostrará una dirección similar a:

```text
0.tcp.sa.ngrok.io:27660
```

En el cliente se deben ingresar los datos por separado:

```text
IP o dominio: 0.tcp.sa.ngrok.io
Puerto: 27660
```

El puerto público de ngrok no tiene que ser `5000`, porque ngrok lo redirige hacia el puerto local del servidor.

En el plan gratuito, la dirección y el puerto pueden cambiar cada vez que se reinicia el túnel. Por ello, debe compartirse la dirección nueva con los usuarios.

Los clientes conectados mediante ngrok también deben utilizar el mismo archivo `clave_chat.key`.

---

## 14. Historial y archivos

* El servidor guarda el historial de mensajes públicos separado por sala.
* Los mensajes se almacenan cifrados.
* Los mensajes privados y grupales no se guardan en el historial público.
* Los archivos recibidos por el servidor se guardan en:

```text
servidor/archivos_recibidos/
```

* Los archivos recibidos por cada cliente se guardan en:

```text
cliente/descargas/
```

* Los nombres de los archivos son validados antes de guardarse.
* El tamaño máximo permitido por el servidor es de 50 MB.

---

## 15. Notas importantes

* Cada nickname debe ser único.
* Todos los clientes deben usar la misma clave de cifrado.
* Las salas públicas y los grupos son funciones diferentes.
* Los mensajes públicos solo llegan a la sala actual.
* El servidor continúa funcionando aunque un cliente se desconecte.
* Para detener el servidor se utiliza `Ctrl + C`.
* La interfaz de consola utiliza colores ANSI.
* Pillow es necesario únicamente para mostrar miniaturas de imágenes.
* El servidor no puede leer los mensajes de texto cifrados, pero sí puede observar información necesaria para el funcionamiento, como emisor, destinatario, sala, grupo, hora y tipo de mensaje.
