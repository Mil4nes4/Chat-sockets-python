import socket
import threading
import json
import os
import base64
from datetime import datetime

HOST = '0.0.0.0'
PUERTO = int(os.environ.get('CHAT_PUERTO', 5000))
MAX_ARCHIVO_MB = 50

# Rutas relativas a la ubicación de este archivo
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_HISTORIAL = os.path.join(BASE_DIR, 'historial_chat.txt')
CARPETA_ARCHIVOS = os.path.join(BASE_DIR, 'archivos_recibidos')

# Diccionario global de clientes conectados: nickname -> socket
clientes = {}
# Diccionario global de avatares elegidos: nickname -> patron_key
avatares = {}
# Diccionario global de colores de perfil elegidos: nickname -> hex
colores = {}
# Diccionario global de grupos: nombre -> {'miembros': set(nicknames), 'creador': nickname, 'avatar': patron_key}
grupos = {}
lock = threading.Lock()
# Protege el envío por socket: sin esto, dos hilos pueden mandarle datos al
# mismo cliente al mismo tiempo (ej. dos "fulano se unió" casi simultáneos) y
# sus bytes se intercalan, rompiendo el framing de longitud del protocolo --
# el cliente afectado queda "sordo" (deja de recibir todo) sin ningún error
# visible. Reproducido con varias conexiones simultáneas antes de este fix.
lock_envio = threading.Lock()
siguiente_id_mensaje = 0


def nuevo_id_mensaje():
    global siguiente_id_mensaje
    with lock:
        siguiente_id_mensaje += 1
        return siguiente_id_mensaje


def obtener_ip_local():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


def enviar(socket_cliente, mensaje):
    try:
        data = json.dumps(mensaje).encode('utf-8')
        longitud = len(data)
        with lock_envio:
            socket_cliente.sendall(longitud.to_bytes(4, byteorder='big'))
            socket_cliente.sendall(data)
    except Exception:
        pass


def recibir(socket_cliente):
    longitud_bytes = b''
    while len(longitud_bytes) < 4:
        chunk = socket_cliente.recv(4 - len(longitud_bytes))
        if not chunk:
            return None
        longitud_bytes += chunk
    longitud = int.from_bytes(longitud_bytes, byteorder='big')
    data = b''
    while len(data) < longitud:
        paquete = socket_cliente.recv(longitud - len(data))
        if not paquete:
            return None
        data += paquete
    return json.loads(data.decode('utf-8'))


def broadcast(mensaje, excluir=None):
    with lock:
        copia = list(clientes.items())
    for nick, sock in copia:
        if excluir and nick == excluir:
            continue
        enviar(sock, mensaje)


def enviar_privado(destinatario, mensaje):
    with lock:
        sock = clientes.get(destinatario)
    if sock:
        enviar(sock, mensaje)


def enviar_lista_usuarios():
    with lock:
        usuarios = list(clientes.keys())
        copia_avatares = dict(avatares)
        copia_colores = dict(colores)
    broadcast({'tipo': 'usuarios', 'contenido': usuarios, 'avatares': copia_avatares, 'colores': copia_colores})


def enviar_grupo(nombre_grupo, mensaje):
    with lock:
        miembros = list(grupos.get(nombre_grupo, {}).get('miembros', []))
        socks = [clientes[m] for m in miembros if m in clientes]
    for sock in socks:
        enviar(sock, mensaje)


def sincronizar_grupo(nombre_grupo):
    with lock:
        info = grupos.get(nombre_grupo)
        if not info:
            return
        miembros = list(info['miembros'])
        mensaje = {
            'tipo': 'grupo_actualizado', 'nombre': nombre_grupo,
            'miembros': miembros, 'creador': info['creador'], 'avatar': info['avatar']
        }
    enviar_grupo(nombre_grupo, mensaje)


def _salir_de_grupo(nickname, nombre_grupo):
    with lock:
        info = grupos.get(nombre_grupo)
        if not info or nickname not in info['miembros']:
            return
        info['miembros'].discard(nickname)
        vacio = not info['miembros']
        if vacio:
            del grupos[nombre_grupo]
    if not vacio:
        sincronizar_grupo(nombre_grupo)


def guardar_historial(linea):
    with open(ARCHIVO_HISTORIAL, 'a', encoding='utf-8') as f:
        f.write(linea + '\n')


def enviar_historial(socket_cliente):
    if os.path.exists(ARCHIVO_HISTORIAL):
        with open(ARCHIVO_HISTORIAL, 'r', encoding='utf-8') as f:
            for linea in f:
                linea = linea.strip()
                if linea:
                    enviar(socket_cliente, {'tipo': 'historial', 'contenido': linea})


def manejar_archivo(emisor, destinatario, nombre_archivo, datos_base64):
    if len(datos_base64) > MAX_ARCHIVO_MB * 1024 * 1024 * 4 // 3 + 4:
        with lock:
            sock = clientes.get(emisor)
        if sock:
            enviar(sock, {'tipo': 'server', 'contenido': f'Archivo rechazado: supera el límite de {MAX_ARCHIVO_MB} MB.'})
        return

    os.makedirs(CARPETA_ARCHIVOS, exist_ok=True)
    ruta = os.path.join(CARPETA_ARCHIVOS, f'{emisor}_{nombre_archivo}')
    try:
        with open(ruta, 'wb') as f:
            f.write(base64.b64decode(datos_base64))
    except Exception as e:
        print(f'[Error al guardar archivo] {e}')
        return

    mensaje = {
        'tipo': 'file',
        'id': nuevo_id_mensaje(),
        'emisor': emisor,
        'destinatario': destinatario,
        'nombre_archivo': nombre_archivo,
        'datos': datos_base64,
        'hora': obtener_hora()
    }

    if destinatario == 'todos':
        # Sin excluir al emisor: mismo patrón que los mensajes públicos, así
        # el emisor ve su propio archivo con el mismo id que todos (antes
        # quedaba afuera del broadcast y el cliente tenía que compensar con
        # un eco local propio, que además duplicaba con el eco de abajo).
        broadcast(mensaje)
    else:
        enviar_privado(destinatario, mensaje)
        if destinatario != emisor:
            with lock:
                sock = clientes.get(emisor)
            if sock:
                enviar(sock, mensaje)


def obtener_hora():
    return datetime.now().strftime('%H:%M:%S')


def activar_keepalive(socket_cliente):
    # Sin esto, si un cliente se va sin cerrar el socket bien (crash,
    # se corta la red, el túnel/VM lo tira) el hilo del servidor se queda
    # bloqueado para siempre en recv() y el usuario queda "fantasma"
    # conectado. Con keepalive, el sistema operativo manda pings al
    # cliente y si no responde, recv() falla solo y el finally de
    # manejar_cliente limpia el usuario como en cualquier desconexión.
    socket_cliente.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    try:
        socket_cliente.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)
        socket_cliente.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
        socket_cliente.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
    except (AttributeError, OSError):
        # TCP_KEEPIDLE/INTVL/CNT no existen en todos los sistemas
        # (p. ej. Windows viejo); SO_KEEPALIVE ya quedó activado igual.
        pass


def manejar_cliente(socket_cliente, direccion):
    nickname = None
    try:
        # Primer mensaje: nickname
        mensaje = recibir(socket_cliente)
        if not mensaje or mensaje.get('tipo') != 'nick':
            return

        nickname = mensaje.get('contenido', '').strip()
        avatar = mensaje.get('avatar', 'circulo')
        color = mensaje.get('color')

        with lock:
            if not nickname or nickname in clientes:
                enviar(socket_cliente, {
                    'tipo': 'server',
                    'contenido': 'NICK_INVALIDO'
                })
                return
            clientes[nickname] = socket_cliente
            avatares[nickname] = avatar
            if color:
                colores[nickname] = color

        print(f'[Conectado] {nickname} desde {direccion}')

        enviar(socket_cliente, {
            'tipo': 'server',
            'contenido': f'Bienvenido al chat, {nickname}.'
        })
        broadcast({
            'tipo': 'server',
            'contenido': f'{nickname} se ha unido al chat.'
        }, excluir=nickname)
        enviar_historial(socket_cliente)
        enviar_lista_usuarios()

        while True:
            mensaje = recibir(socket_cliente)
            if not mensaje:
                break

            tipo = mensaje.get('tipo')

            if tipo == 'msg':
                contenido = mensaje.get('contenido', '')
                hora = obtener_hora()
                texto_historial = f'[{hora}] {nickname}: {contenido}'
                guardar_historial(texto_historial)
                broadcast({
                    'tipo': 'msg',
                    'id': nuevo_id_mensaje(),
                    'emisor': nickname,
                    'contenido': contenido,
                    'hora': hora
                })

            elif tipo == 'priv':
                destinatario = mensaje.get('destinatario')
                contenido = mensaje.get('contenido', '')
                hora = obtener_hora()
                mensaje_priv = {
                    'tipo': 'priv',
                    'id': nuevo_id_mensaje(),
                    'emisor': nickname,
                    'destinatario': destinatario,
                    'contenido': contenido,
                    'hora': hora
                }
                enviar_privado(destinatario, mensaje_priv)
                if destinatario != nickname:
                    enviar(socket_cliente, mensaje_priv)

            elif tipo == 'list':
                with lock:
                    usuarios = list(clientes.keys())
                    copia_avatares = dict(avatares)
                    copia_colores = dict(colores)
                enviar(socket_cliente, {
                    'tipo': 'usuarios', 'contenido': usuarios,
                    'avatares': copia_avatares, 'colores': copia_colores
                })

            elif tipo == 'file':
                destinatario = mensaje.get('destinatario', 'todos')
                nombre_archivo = mensaje.get('nombre_archivo', 'archivo')
                datos = mensaje.get('datos', '')
                manejar_archivo(nickname, destinatario, nombre_archivo, datos)

            elif tipo == 'typing':
                destinatario = mensaje.get('destinatario', 'todos')
                notificacion = {
                    'tipo': 'typing',
                    'emisor': nickname,
                    'destinatario': destinatario
                }
                if destinatario == 'todos':
                    broadcast(notificacion, excluir=nickname)
                else:
                    enviar_privado(destinatario, notificacion)

            elif tipo == 'reaccion':
                id_mensaje = mensaje.get('id_mensaje')
                emoji = mensaje.get('emoji')
                if id_mensaje is not None and emoji:
                    broadcast({
                        'tipo': 'reaccion',
                        'id_mensaje': id_mensaje,
                        'emisor': nickname,
                        'emoji': emoji
                    })

            elif tipo == 'grupo_crear':
                nombre_grupo = (mensaje.get('nombre') or '').strip()
                miembros_pedidos = mensaje.get('miembros', [])
                avatar_grupo = mensaje.get('avatar', 'gente')

                with lock:
                    miembros_validos = {m for m in miembros_pedidos if m in clientes and m != nickname}
                    if not nombre_grupo:
                        error = 'el nombre no puede estar vacío'
                    elif nombre_grupo in ('crear', 'invitar', 'salir'):
                        # Esas palabras son subcomandos de "/grupo <subcomando>
                        # ..." en el cliente de consola -- un grupo con ese
                        # nombre nunca podría recibir mensajes desde ahí.
                        error = f'"{nombre_grupo}" es una palabra reservada, elegí otro nombre'
                    elif nombre_grupo in grupos or nombre_grupo in clientes:
                        error = 'ya existe un grupo o usuario con ese nombre'
                    elif not miembros_validos:
                        error = 'elegí al menos un miembro conectado'
                    else:
                        error = None
                        grupos[nombre_grupo] = {
                            'miembros': {nickname, *miembros_validos},
                            'creador': nickname,
                            'avatar': avatar_grupo
                        }

                if error:
                    enviar(socket_cliente, {'tipo': 'server', 'contenido': f'GRUPO_INVALIDO: {error}'})
                else:
                    sincronizar_grupo(nombre_grupo)

            elif tipo == 'grupo_invitar':
                nombre_grupo = mensaje.get('grupo')
                miembros_pedidos = mensaje.get('miembros', [])

                with lock:
                    info = grupos.get(nombre_grupo)
                    if not info or nickname not in info['miembros']:
                        error = 'no sos miembro de ese grupo'
                    else:
                        error = None
                        nuevos = {m for m in miembros_pedidos if m in clientes and m not in info['miembros']}
                        info['miembros'].update(nuevos)

                if error:
                    enviar(socket_cliente, {'tipo': 'server', 'contenido': f'GRUPO_INVALIDO: {error}'})
                else:
                    sincronizar_grupo(nombre_grupo)

            elif tipo == 'grupo_msg':
                nombre_grupo = mensaje.get('grupo')
                contenido = mensaje.get('contenido', '')

                with lock:
                    es_miembro = nickname in grupos.get(nombre_grupo, {}).get('miembros', set())

                if es_miembro:
                    enviar_grupo(nombre_grupo, {
                        'tipo': 'grupo_msg',
                        'id': nuevo_id_mensaje(),
                        'grupo': nombre_grupo,
                        'emisor': nickname,
                        'contenido': contenido,
                        'hora': obtener_hora()
                    })

            elif tipo == 'grupo_salir':
                nombre_grupo = mensaje.get('grupo')
                _salir_de_grupo(nickname, nombre_grupo)
                enviar(socket_cliente, {'tipo': 'grupo_eliminado', 'nombre': nombre_grupo})

            elif tipo == 'exit':
                break

    except Exception as e:
        print(f'[Error con {direccion}] {e}')
    finally:
        if nickname:
            with lock:
                if nickname in clientes:
                    del clientes[nickname]
                avatares.pop(nickname, None)
                colores.pop(nickname, None)
                grupos_del_usuario = [n for n, info in grupos.items() if nickname in info['miembros']]
            for nombre_grupo in grupos_del_usuario:
                _salir_de_grupo(nickname, nombre_grupo)
            print(f'[Desconectado] {nickname}')
            broadcast({
                'tipo': 'server',
                'contenido': f'{nickname} ha abandonado el chat.'
            })
            enviar_lista_usuarios()
        socket_cliente.close()


def main():
    os.makedirs(CARPETA_ARCHIVOS, exist_ok=True)

    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servidor.bind((HOST, PUERTO))
    servidor.listen()

    print('=' * 50)
    print('Servidor de chat iniciado')
    print(f'Escuchando en {HOST}:{PUERTO}')
    print(f'IP local del servidor: {obtener_ip_local()}')
    print('Presiona Ctrl+C para detener')
    print('=' * 50)

    try:
        while True:
            socket_cliente, direccion = servidor.accept()
            activar_keepalive(socket_cliente)
            hilo = threading.Thread(
                target=manejar_cliente,
                args=(socket_cliente, direccion),
                daemon=True
            )
            hilo.start()
    except KeyboardInterrupt:
        print('\n[Apagando servidor...]')
    finally:
        servidor.close()


if __name__ == '__main__':
    main()
