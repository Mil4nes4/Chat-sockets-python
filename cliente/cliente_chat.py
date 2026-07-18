import socket
import ssl
import json
import base64
import os
import re
import time
import threading
import hashlib

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:
    Fernet = None
    InvalidToken = Exception

# Serializa los envíos: la consola ahora manda acuses desde el hilo de escucha además del principal.
_LOCK_ENVIO = threading.Lock()

CARPETA_DESCARGAS = 'descargas'

# Clave Fernet compartida entre clientes (E2E del contenido, además del TLS del canal).
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_CLAVE = os.environ.get('CHAT_CLAVE_ARCHIVO', os.path.join(BASE_DIR, 'clave_chat.key'))
_FERNET = None
_CLAVE = None

EMOJIS_COMUNES = [
    '😀', '😂', '😅', '😉', '😊', '😍', '😘', '😎', '🤔', '😴',
    '😭', '😡', '🥳', '😱', '🤯', '🙄', '😇', '🤗', '🤝', '👍',
    '👎', '👏', '🙏', '💪', '✌️', '👀', '❤️', '💔', '🔥', '⭐',
    '🎉', '✅', '❌', '⚠️', '💬', '☕', '🍕', '🎮', '💻', '📎',
]


def es_mencionado(nickname, contenido):
    # Límite de palabra para no dar falso positivo cuando un nick es prefijo de otro (Ana / @Anabel).
    if not nickname or not contenido:
        return False
    return re.search(r'@' + re.escape(nickname) + r'\b', contenido) is not None


def _obtener_clave():
    # Toma la clave de CHAT_FERNET_KEY, o del archivo clave_chat.key, o la genera la primera vez.
    global _CLAVE
    if _CLAVE is not None:
        return _CLAVE
    if Fernet is None:
        raise RuntimeError('Falta la librería cryptography. Instalala con: pip install cryptography')
    clave_entorno = os.environ.get('CHAT_FERNET_KEY', '').strip()
    if clave_entorno:
        clave = clave_entorno.encode('ascii')
    elif os.path.exists(ARCHIVO_CLAVE):
        with open(ARCHIVO_CLAVE, 'rb') as archivo:
            clave = archivo.read().strip()
    else:
        clave = Fernet.generate_key()
        os.makedirs(os.path.dirname(ARCHIVO_CLAVE) or '.', exist_ok=True)
        with open(ARCHIVO_CLAVE, 'wb') as archivo:
            archivo.write(clave)
        print(f'[Seguridad] Se generó {ARCHIVO_CLAVE}. Copiá ese mismo archivo a los demás clientes.')
    try:
        Fernet(clave)
    except Exception as exc:
        raise RuntimeError('La clave Fernet no es válida (usá una generada por Fernet.generate_key()).') from exc
    _CLAVE = clave
    return clave


def _obtener_fernet():
    global _FERNET
    if _FERNET is None:
        _FERNET = Fernet(_obtener_clave())
    return _FERNET


def obtener_huella_clave():
    # Huella pública de la clave: permite al servidor detectar claves distintas sin conocer la clave.
    return hashlib.sha256(_obtener_clave()).hexdigest()[:16]


def cifrar_texto(texto):
    return _obtener_fernet().encrypt(texto.encode('utf-8')).decode('ascii')


def descifrar_texto(token):
    if token is None:
        return ''
    try:
        return _obtener_fernet().decrypt(token.encode('ascii')).decode('utf-8')
    except (InvalidToken, UnicodeDecodeError, ValueError) as exc:
        raise ValueError('No se pudo descifrar el mensaje. Verificá que todos usen la misma clave.') from exc


def interpretar_contenido(mensaje):
    # Devuelve el texto en claro de un mensaje: lo descifra si viene con cifrado=True.
    contenido = mensaje.get('contenido', '')
    if mensaje.get('cifrado'):
        return descifrar_texto(contenido)
    return contenido


def conectar(ip, puerto):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((ip, puerto))
    # Certificado autofirmado: TLS solo para cifrar el canal, no se valida hostname/CA.
    contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    contexto.check_hostname = False
    contexto.verify_mode = ssl.CERT_NONE
    return contexto.wrap_socket(sock, server_hostname=ip)


def enviar(socket_cliente, mensaje):
    data = json.dumps(mensaje).encode('utf-8')
    longitud = len(data)
    with _LOCK_ENVIO:
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
    enviar(socket_cliente, {
        'tipo': 'nick', 'contenido': nickname, 'avatar': avatar, 'color': color,
        'huella_clave': obtener_huella_clave()
    })


def enviar_mensaje_publico(socket_cliente, mensaje):
    enviar(socket_cliente, {'tipo': 'msg', 'contenido': cifrar_texto(mensaje), 'cifrado': True})


def enviar_mensaje_privado(socket_cliente, destinatario, mensaje):
    enviar(socket_cliente, {
        'tipo': 'priv',
        'destinatario': destinatario,
        'contenido': cifrar_texto(mensaje),
        'cifrado': True
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
    enviar(socket_cliente, {'tipo': 'grupo_msg', 'grupo': grupo, 'contenido': cifrar_texto(mensaje), 'cifrado': True})


def salir_grupo(socket_cliente, grupo):
    enviar(socket_cliente, {'tipo': 'grupo_salir', 'grupo': grupo})


def enviar_ping(socket_cliente):
    # Se manda el timestamp propio; el servidor lo devuelve en el pong y el RTT se calcula con el reloj local.
    enviar(socket_cliente, {'tipo': 'ping', 'ts_cliente': time.time()})


def solicitar_stats(socket_cliente):
    enviar(socket_cliente, {'tipo': 'stats_solicitar'})


def solicitar_whois(socket_cliente, usuario):
    enviar(socket_cliente, {'tipo': 'whois', 'usuario': usuario})


def editar_mensaje(socket_cliente, id_mensaje, contenido):
    enviar(socket_cliente, {
        'tipo': 'msg_editar', 'id_mensaje': id_mensaje,
        'contenido': cifrar_texto(contenido), 'cifrado': True
    })


def eliminar_mensaje(socket_cliente, id_mensaje):
    enviar(socket_cliente, {'tipo': 'msg_eliminar', 'id_mensaje': id_mensaje})


def crear_sala(socket_cliente, nombre):
    enviar(socket_cliente, {'tipo': 'sala_crear', 'nombre': nombre})


def unirse_sala(socket_cliente, nombre):
    enviar(socket_cliente, {'tipo': 'sala_unirse', 'nombre': nombre})


def salir_sala(socket_cliente):
    # Vuelve a la sala 'General'.
    enviar(socket_cliente, {'tipo': 'sala_salir'})


def listar_salas(socket_cliente):
    enviar(socket_cliente, {'tipo': 'sala_listar'})


def confirmar_entrega(socket_cliente, id_mensaje):
    # Acuse "entregado" (llegó al cliente) que se manda al recibir un mensaje ajeno.
    enviar(socket_cliente, {'tipo': 'delivered', 'id_mensaje': id_mensaje})


def confirmar_lectura(socket_cliente, id_mensaje):
    # Acuse "leído" (el usuario lo vio) que se manda al mostrar el mensaje.
    enviar(socket_cliente, {'tipo': 'read', 'id_mensaje': id_mensaje})


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
