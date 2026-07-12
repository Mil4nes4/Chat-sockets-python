import socket
import json
import base64
import os
import re

CARPETA_DESCARGAS = 'descargas'

EMOJIS_COMUNES = [
    '😀', '😂', '😅', '😉', '😊', '😍', '😘', '😎', '🤔', '😴',
    '😭', '😡', '🥳', '😱', '🤯', '🙄', '😇', '🤗', '🤝', '👍',
    '👎', '👏', '🙏', '💪', '✌️', '👀', '❤️', '💔', '🔥', '⭐',
    '🎉', '✅', '❌', '⚠️', '💬', '☕', '🍕', '🎮', '💻', '📎',
]


def es_mencionado(nickname, contenido):
    # Antes se usaba "f'@{nickname}' in contenido", que da falso positivo
    # cuando un nick es prefijo de otro (ej. "Ana" matchea "@Anabel"). Se
    # exige que el nick termine en un límite de palabra real.
    if not nickname or not contenido:
        return False
    return re.search(r'@' + re.escape(nickname) + r'\b', contenido) is not None


def conectar(ip, puerto):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((ip, puerto))
    return sock


def enviar(socket_cliente, mensaje):
    data = json.dumps(mensaje).encode('utf-8')
    longitud = len(data)
    socket_cliente.sendall(longitud.to_bytes(4, byteorder='big'))
    socket_cliente.sendall(data)


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


def enviar_nickname(socket_cliente, nickname, avatar='circulo', color=None):
    enviar(socket_cliente, {'tipo': 'nick', 'contenido': nickname, 'avatar': avatar, 'color': color})


def enviar_mensaje_publico(socket_cliente, mensaje):
    enviar(socket_cliente, {'tipo': 'msg', 'contenido': mensaje})


def enviar_mensaje_privado(socket_cliente, destinatario, mensaje):
    enviar(socket_cliente, {
        'tipo': 'priv',
        'destinatario': destinatario,
        'contenido': mensaje
    })


def solicitar_lista(socket_cliente):
    enviar(socket_cliente, {'tipo': 'list'})


def enviar_typing(socket_cliente, destinatario='todos'):
    enviar(socket_cliente, {'tipo': 'typing', 'destinatario': destinatario})


def enviar_reaccion(socket_cliente, id_mensaje, emoji):
    enviar(socket_cliente, {'tipo': 'reaccion', 'id_mensaje': id_mensaje, 'emoji': emoji})


def crear_grupo(socket_cliente, nombre, miembros, avatar='gente'):
    enviar(socket_cliente, {'tipo': 'grupo_crear', 'nombre': nombre, 'miembros': miembros, 'avatar': avatar})


def invitar_a_grupo(socket_cliente, grupo, miembros):
    enviar(socket_cliente, {'tipo': 'grupo_invitar', 'grupo': grupo, 'miembros': miembros})


def enviar_mensaje_grupo(socket_cliente, grupo, mensaje):
    enviar(socket_cliente, {'tipo': 'grupo_msg', 'grupo': grupo, 'contenido': mensaje})


def salir_grupo(socket_cliente, grupo):
    enviar(socket_cliente, {'tipo': 'grupo_salir', 'grupo': grupo})


def enviar_archivo(socket_cliente, ruta, destinatario='todos'):
    nombre = os.path.basename(ruta)
    with open(ruta, 'rb') as f:
        contenido = base64.b64encode(f.read()).decode('utf-8')
    enviar(socket_cliente, {
        'tipo': 'file',
        'destinatario': destinatario,
        'nombre_archivo': nombre,
        'datos': contenido
    })


def guardar_archivo(emisor, nombre_archivo, datos_base64):
    os.makedirs(CARPETA_DESCARGAS, exist_ok=True)
    ruta = os.path.join(CARPETA_DESCARGAS, f'{emisor}_{nombre_archivo}')
    with open(ruta, 'wb') as f:
        f.write(base64.b64decode(datos_base64))
    return ruta


def cerrar(socket_cliente):
    try:
        enviar(socket_cliente, {'tipo': 'exit'})
    except Exception:
        pass
    try:
        socket_cliente.close()
    except Exception:
        pass
