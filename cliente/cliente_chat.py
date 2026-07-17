import base64
import hashlib
import json
import os
import re
import socket
import threading
import uuid

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:
    Fernet = None
    InvalidToken = Exception


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CARPETA_DESCARGAS = os.path.join(BASE_DIR, 'descargas')
ARCHIVO_CLAVE = os.environ.get(
    'CHAT_CLAVE_ARCHIVO',
    os.path.join(BASE_DIR, 'clave_chat.key')
)
MAX_TRAMA_BYTES = 80 * 1024 * 1024

EMOJIS_COMUNES = [
    '😀', '😂', '😅', '😉', '😊', '😍', '😘', '😎', '🤔', '😴',
    '😭', '😡', '🥳', '😱', '🤯', '🙄', '😇', '🤗', '🤝', '👍',
    '👎', '👏', '🙏', '💪', '✌️', '👀', '❤️', '💔', '🔥', '⭐',
    '🎉', '✅', '❌', '⚠️', '💬', '☕', '🍕', '🎮', '💻', '📎',
]

EMOJI_SHORTCODES = {
    ':smile:': '😄',
    ':laugh:': '😂',
    ':heart:': '❤️',
    ':fire:': '🔥',
    ':thumbsup:': '👍',
    ':sad:': '😢',
    ':angry:': '😡',
    ':party:': '🥳',
    ':eyes:': '👀',
    ':check:': '✅',
    ':warning:': '⚠️',
    ':computer:': '💻',
    ':game:': '🎮',
    ':coffee:': '☕',
    ':pizza:': '🍕',
}

_LOCK_ENVIO = threading.Lock()
_FERNET = None
_CLAVE = None


def es_mencionado(nickname, contenido):
    if not nickname or not contenido:
        return False
    return re.search(r'@' + re.escape(nickname) + r'\b', contenido) is not None


def convertir_emojis(texto):
    if not texto:
        return texto
    for codigo, emoji in EMOJI_SHORTCODES.items():
        texto = texto.replace(codigo, emoji)
    return texto


def _obtener_clave():
    global _CLAVE

    if _CLAVE is not None:
        return _CLAVE

    if Fernet is None:
        raise RuntimeError(
            'Falta la librería cryptography. Instálala con: pip install cryptography'
        )

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
        print(
            f'[Seguridad] Se generó {ARCHIVO_CLAVE}. '
            'Copia este mismo archivo a los demás clientes.'
        )

    try:
        Fernet(clave)
    except Exception as exc:
        raise RuntimeError(
            'La clave Fernet no es válida. Usa una clave generada por Fernet.generate_key().'
        ) from exc

    _CLAVE = clave
    return clave


def _obtener_fernet():
    global _FERNET
    if _FERNET is None:
        _FERNET = Fernet(_obtener_clave())
    return _FERNET


def obtener_huella_clave():
    return hashlib.sha256(_obtener_clave()).hexdigest()[:16]


def cifrar_texto(texto):
    texto = convertir_emojis(texto)
    return _obtener_fernet().encrypt(texto.encode('utf-8')).decode('ascii')


def descifrar_texto(token):
    if token is None:
        return ''
    try:
        return _obtener_fernet().decrypt(token.encode('ascii')).decode('utf-8')
    except (InvalidToken, UnicodeDecodeError, ValueError) as exc:
        raise ValueError(
            'No se pudo descifrar el mensaje. Verifica que todos usen la misma clave.'
        ) from exc


def interpretar_contenido(mensaje):
    contenido = mensaje.get('contenido', '')
    if mensaje.get('cifrado'):
        return descifrar_texto(contenido)
    return contenido


def generar_id_mensaje():
    return uuid.uuid4().hex


def conectar(ip, puerto):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((ip, puerto))
    return sock


def enviar(socket_cliente, mensaje):
    data = json.dumps(mensaje, ensure_ascii=False).encode('utf-8')
    longitud = len(data)
    if longitud > MAX_TRAMA_BYTES:
        raise ValueError('El mensaje supera el tamaño máximo permitido.')
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
    if longitud <= 0 or longitud > MAX_TRAMA_BYTES:
        raise ValueError('El servidor envió una trama con longitud inválida.')

    data = b''
    while len(data) < longitud:
        paquete = socket_cliente.recv(longitud - len(data))
        if not paquete:
            return None
        data += paquete
    return json.loads(data.decode('utf-8'))


def enviar_nickname(socket_cliente, nickname, avatar='circulo', color=None):
    enviar(socket_cliente, {
        'tipo': 'nick',
        'contenido': nickname,
        'avatar': avatar,
        'color': color,
        'huella_clave': obtener_huella_clave(),
        'version_protocolo': 2,
    })


def _mensaje_cifrado(tipo, mensaje, **campos):
    id_mensaje = campos.pop('id_mensaje', None) or generar_id_mensaje()
    paquete = {
        'tipo': tipo,
        'id': id_mensaje,
        'contenido': cifrar_texto(mensaje),
        'cifrado': True,
    }
    paquete.update(campos)
    return id_mensaje, paquete


def enviar_mensaje_publico(socket_cliente, mensaje, id_mensaje=None):
    id_mensaje, paquete = _mensaje_cifrado(
        'msg', mensaje, id_mensaje=id_mensaje
    )
    enviar(socket_cliente, paquete)
    return id_mensaje


def enviar_mensaje_privado(
    socket_cliente, destinatario, mensaje, id_mensaje=None
):
    id_mensaje, paquete = _mensaje_cifrado(
        'priv',
        mensaje,
        id_mensaje=id_mensaje,
        destinatario=destinatario,
    )
    enviar(socket_cliente, paquete)
    return id_mensaje


def solicitar_lista(socket_cliente):
    enviar(socket_cliente, {'tipo': 'list'})


def solicitar_salas(socket_cliente):
    enviar(socket_cliente, {'tipo': 'sala_listar'})


def crear_sala(socket_cliente, nombre):
    enviar(socket_cliente, {'tipo': 'sala_crear', 'nombre': nombre})


def unirse_sala(socket_cliente, nombre):
    enviar(socket_cliente, {'tipo': 'sala_unirse', 'nombre': nombre})


def salir_sala(socket_cliente):
    enviar(socket_cliente, {'tipo': 'sala_salir'})


def enviar_typing(socket_cliente, destinatario='todos'):
    enviar(
        socket_cliente,
        {'tipo': 'typing', 'destinatario': destinatario}
    )


def confirmar_entrega(socket_cliente, id_mensaje):
    if id_mensaje:
        enviar(
            socket_cliente,
            {'tipo': 'delivered', 'id_mensaje': id_mensaje}
        )


def confirmar_lectura(socket_cliente, id_mensaje):
    if id_mensaje:
        enviar(
            socket_cliente,
            {'tipo': 'read', 'id_mensaje': id_mensaje}
        )


def enviar_reaccion(socket_cliente, id_mensaje, emoji):
    enviar(socket_cliente, {
        'tipo': 'reaccion',
        'id_mensaje': id_mensaje,
        'emoji': emoji,
    })


def crear_grupo(socket_cliente, nombre, miembros, avatar='gente'):
    enviar(socket_cliente, {
        'tipo': 'grupo_crear',
        'nombre': nombre,
        'miembros': miembros,
        'avatar': avatar,
    })


def invitar_a_grupo(socket_cliente, grupo, miembros):
    enviar(socket_cliente, {
        'tipo': 'grupo_invitar',
        'grupo': grupo,
        'miembros': miembros,
    })


def enviar_mensaje_grupo(
    socket_cliente, grupo, mensaje, id_mensaje=None
):
    id_mensaje, paquete = _mensaje_cifrado(
        'grupo_msg',
        mensaje,
        id_mensaje=id_mensaje,
        grupo=grupo,
    )
    enviar(socket_cliente, paquete)
    return id_mensaje


def salir_grupo(socket_cliente, grupo):
    enviar(socket_cliente, {'tipo': 'grupo_salir', 'grupo': grupo})


def enviar_archivo(socket_cliente, ruta, destinatario='todos'):
    nombre = os.path.basename(ruta)
    with open(ruta, 'rb') as archivo:
        contenido = base64.b64encode(archivo.read()).decode('utf-8')
    enviar(socket_cliente, {
        'tipo': 'file',
        'destinatario': destinatario,
        'nombre_archivo': nombre,
        'datos': contenido,
    })


def _nombre_seguro(texto):
    texto = os.path.basename(str(texto))
    return re.sub(r'[^A-Za-z0-9._ -]', '_', texto)


def guardar_archivo(emisor, nombre_archivo, datos_base64):
    os.makedirs(CARPETA_DESCARGAS, exist_ok=True)
    emisor_seguro = _nombre_seguro(emisor)
    archivo_seguro = _nombre_seguro(nombre_archivo)
    ruta = os.path.join(
        CARPETA_DESCARGAS,
        f'{emisor_seguro}_{archivo_seguro}'
    )

    base, extension = os.path.splitext(ruta)
    contador = 1
    while os.path.exists(ruta):
        ruta = f'{base}_{contador}{extension}'
        contador += 1

    with open(ruta, 'wb') as archivo:
        archivo.write(base64.b64decode(datos_base64, validate=True))
    return ruta


def cerrar(socket_cliente):
    try:
        enviar(socket_cliente, {'tipo': 'exit'})
    except Exception:
        pass
    try:
        socket_cliente.shutdown(socket.SHUT_RDWR)
    except Exception:
        pass
    try:
        socket_cliente.close()
    except Exception:
        pass
