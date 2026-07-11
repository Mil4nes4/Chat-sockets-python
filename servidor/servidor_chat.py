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
lock = threading.Lock()
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
    broadcast({'tipo': 'usuarios', 'contenido': usuarios})


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
        broadcast(mensaje, excluir=emisor)
    else:
        enviar_privado(destinatario, mensaje)
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

        with lock:
            if not nickname or nickname in clientes:
                enviar(socket_cliente, {
                    'tipo': 'server',
                    'contenido': 'NICK_INVALIDO'
                })
                return
            clientes[nickname] = socket_cliente

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
                enviar_privado(destinatario, {
                    'tipo': 'priv',
                    'id': nuevo_id_mensaje(),
                    'emisor': nickname,
                    'destinatario': destinatario,
                    'contenido': contenido,
                    'hora': hora
                })

            elif tipo == 'list':
                with lock:
                    usuarios = list(clientes.keys())
                enviar(socket_cliente, {'tipo': 'usuarios', 'contenido': usuarios})

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

            elif tipo == 'exit':
                break

    except Exception as e:
        print(f'[Error con {direccion}] {e}')
    finally:
        if nickname:
            with lock:
                if nickname in clientes:
                    del clientes[nickname]
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
