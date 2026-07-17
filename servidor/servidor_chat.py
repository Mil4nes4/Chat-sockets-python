import socket
import ssl
import threading
import json
import os
import base64
import time
from datetime import datetime

HOST = '0.0.0.0'
PUERTO = int(os.environ.get('CHAT_PUERTO', 5000))
MAX_ARCHIVO_MB = 50

# Rutas relativas a la ubicación de este archivo
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_HISTORIAL = os.path.join(BASE_DIR, 'historial_chat.txt')
CARPETA_ARCHIVOS = os.path.join(BASE_DIR, 'archivos_recibidos')
ARCHIVO_LOG_CONEXIONES = os.path.join(BASE_DIR, 'conexiones_log.txt')
RUTA_CERT_TLS = os.path.join(BASE_DIR, 'certs', 'servidor_cert.pem')
RUTA_KEY_TLS = os.path.join(BASE_DIR, 'certs', 'servidor_key.pem')

# Diccionario global de clientes conectados: nickname -> socket
clientes = {}
# Diccionario global de avatares elegidos: nickname -> patron_key
avatares = {}
# Diccionario global de colores de perfil elegidos: nickname -> hex
colores = {}
# Diccionario global de grupos: nombre -> {'miembros': set(nicknames), 'creador': nickname, 'avatar': patron_key}
grupos = {}
# nickname -> fecha/hora de conexión (para /whois)
horas_conexion = {}
# nickname -> timestamps de sus últimos mensajes (para el límite anti-flood)
mensajes_recientes = {}
# id_mensaje -> datos del mensaje, para validar dueño/ventana de tiempo al editar o eliminar.
mensajes_registro = {}
lock = threading.Lock()
# Fallback si un socket llega sin su lock propio (no debería pasar); el lock real es por socket, ver enviar().
lock_envio = threading.Lock()
lock_historial = threading.Lock()
lock_log_conexiones = threading.Lock()
siguiente_id_mensaje = 0

LIMITE_MENSAJES_ANTIFLOOD = 8
VENTANA_ANTIFLOOD_SEGUNDOS = 5
VENTANA_EDICION_SEGUNDOS = 120
# Timeout para el caso patológico de un cliente con el buffer lleno que no lee: sin esto broadcast() se cuelga.
TIMEOUT_ENVIO_SEGUNDOS = 4

mensajes_totales = 0
hora_inicio_servidor = time.time()


def nuevo_id_mensaje():
    global siguiente_id_mensaje
    with lock:
        siguiente_id_mensaje += 1
        return siguiente_id_mensaje


def excede_limite_envio(nickname):
    ahora = time.time()
    with lock:
        registros = mensajes_recientes.setdefault(nickname, [])
        registros[:] = [t for t in registros if ahora - t < VENTANA_ANTIFLOOD_SEGUNDOS]
        if len(registros) >= LIMITE_MENSAJES_ANTIFLOOD:
            return True
        registros.append(ahora)
        return False


def registrar_mensaje_enviado():
    global mensajes_totales
    with lock:
        mensajes_totales += 1


def registrar_mensaje_editable(id_mensaje, emisor, tipo, destinatario=None, grupo=None):
    with lock:
        mensajes_registro[id_mensaje] = {
            'emisor': emisor, 'ts': time.time(), 'tipo': tipo,
            'destinatario': destinatario, 'grupo': grupo
        }


def validar_edicion(nickname, id_mensaje):
    # Devuelve (info, None) si se puede editar/eliminar, o (None, error) si no.
    with lock:
        info = mensajes_registro.get(id_mensaje)
        if not info or info['emisor'] != nickname:
            return None, 'Ese mensaje no existe o no te pertenece.'
        if time.time() - info['ts'] > VENTANA_EDICION_SEGUNDOS:
            return None, 'Ya pasaron más de 2 minutos: no se puede editar ni eliminar.'
        return dict(info), None


def registrar_log_conexion(texto):
    # Lock dedicado (no el general): escribir a disco no debe bloquear broadcasts ni altas de usuarios.
    linea = f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] {texto}'
    with lock_log_conexiones:
        with open(ARCHIVO_LOG_CONEXIONES, 'a', encoding='utf-8') as f:
            f.write(linea + '\n')


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


# Máximo que dura un recv() antes de soltar el lock del socket para dejar escribir a otro hilo.
INTERVALO_POLL_LECTURA = 0.2


def _io_con_lock(socket_cliente, operacion, timeout):
    # Un socket TLS no admite lectura/escritura concurrentes: el lock por socket las serializa, con sondeo corto.
    lock_propio = getattr(socket_cliente, '_lock_io', None) or lock_envio
    with lock_propio:
        socket_cliente.settimeout(timeout)
        return operacion()


def enviar(socket_cliente, mensaje):
    try:
        data = json.dumps(mensaje).encode('utf-8')
        longitud = len(data)

        def _enviar():
            socket_cliente.sendall(longitud.to_bytes(4, byteorder='big'))
            socket_cliente.sendall(data)

        _io_con_lock(socket_cliente, _enviar, TIMEOUT_ENVIO_SEGUNDOS)
    except Exception:
        pass


def recibir(socket_cliente):
    def _leer(n):
        # Un timeout acá (cliente inactivo) es normal, no una desconexión: se reintenta en silencio.
        while True:
            try:
                return _io_con_lock(socket_cliente, lambda: socket_cliente.recv(n), INTERVALO_POLL_LECTURA)
            except socket.timeout:
                continue

    longitud_bytes = b''
    while len(longitud_bytes) < 4:
        chunk = _leer(4 - len(longitud_bytes))
        if not chunk:
            return None
        longitud_bytes += chunk
    longitud = int.from_bytes(longitud_bytes, byteorder='big')
    data = b''
    while len(data) < longitud:
        paquete = _leer(longitud - len(data))
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
    # Lock dedicado para que dos hilos no escriban a la vez este archivo (antes no tenía y era un bug).
    with lock_historial:
        with open(ARCHIVO_HISTORIAL, 'a', encoding='utf-8') as f:
            f.write(linea + '\n')


MAX_LINEAS_HISTORIAL_REENVIADO = 200


def enviar_historial(socket_cliente):
    # Un mensaje de red por línea: se limita a las últimas N para acotar la demora con historiales grandes.
    if os.path.exists(ARCHIVO_HISTORIAL):
        with open(ARCHIVO_HISTORIAL, 'r', encoding='utf-8') as f:
            lineas = [linea.strip() for linea in f if linea.strip()]
        for linea in lineas[-MAX_LINEAS_HISTORIAL_REENVIADO:]:
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
    registrar_mensaje_enviado()

    if destinatario == 'todos':
        # Sin excluir al emisor: ve su propio archivo con el mismo id que todos, sin eco local que duplique.
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
    # Sin keepalive, un cliente que se va sin cerrar bien deja el hilo colgado en recv() y un usuario "fantasma".
    socket_cliente.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    try:
        socket_cliente.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)
        socket_cliente.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
        socket_cliente.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
    except (AttributeError, OSError):
        # TCP_KEEPIDLE/INTVL/CNT no existen en todos los sistemas; SO_KEEPALIVE ya quedó activado igual.
        pass


def manejar_cliente(socket_cliente, direccion, contexto_tls):
    nickname = None
    try:
        # El wrap TLS se hace acá (no en main()) para que un handshake fallido corte solo a este hilo.
        socket_cliente = contexto_tls.wrap_socket(socket_cliente, server_side=True)
        # Lock de lectura+escritura propio de este socket (ver _io_con_lock()).
        socket_cliente._lock_io = threading.Lock()
    except (ssl.SSLError, OSError) as e:
        print(f'[TLS] Handshake fallido con {direccion}: {e}')
        socket_cliente.close()
        return

    try:
        # Primer mensaje: nickname
        mensaje = recibir(socket_cliente)
        if not mensaje or mensaje.get('tipo') != 'nick':
            return

        nickname = mensaje.get('contenido', '').strip()
        avatar = mensaje.get('avatar', 'circulo')
        color = mensaje.get('color')

        # Solo se decide el resultado bajo lock; el enviar() de rechazo va afuera para no bloquear con un sendall().
        with lock:
            nick_valido = bool(nickname) and nickname not in clientes
            if nick_valido:
                clientes[nickname] = socket_cliente
                avatares[nickname] = avatar
                if color:
                    colores[nickname] = color
                horas_conexion[nickname] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if not nick_valido:
            enviar(socket_cliente, {'tipo': 'server', 'contenido': 'NICK_INVALIDO'})
            return

        print(f'[Conectado] {nickname} desde {direccion}')
        registrar_log_conexion(f'CONEXION {nickname} desde {direccion[0]}:{direccion[1]}')

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
                if excede_limite_envio(nickname):
                    enviar(socket_cliente, {
                        'tipo': 'server',
                        'contenido': 'Estás enviando mensajes muy rápido. Esperá unos segundos.'
                    })
                    continue
                contenido = mensaje.get('contenido', '')
                hora = obtener_hora()
                id_msg = nuevo_id_mensaje()
                registrar_mensaje_editable(id_msg, nickname, 'msg')
                registrar_mensaje_enviado()
                texto_historial = f'[{hora}] {nickname}: {contenido}'
                guardar_historial(texto_historial)
                broadcast({
                    'tipo': 'msg',
                    'id': id_msg,
                    'emisor': nickname,
                    'contenido': contenido,
                    'hora': hora
                })

            elif tipo == 'priv':
                if excede_limite_envio(nickname):
                    enviar(socket_cliente, {
                        'tipo': 'server',
                        'contenido': 'Estás enviando mensajes muy rápido. Esperá unos segundos.'
                    })
                    continue
                destinatario = mensaje.get('destinatario')
                contenido = mensaje.get('contenido', '')
                hora = obtener_hora()
                id_msg = nuevo_id_mensaje()
                registrar_mensaje_editable(id_msg, nickname, 'priv', destinatario=destinatario)
                registrar_mensaje_enviado()
                mensaje_priv = {
                    'tipo': 'priv',
                    'id': id_msg,
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
                        # Son subcomandos de "/grupo ..." en consola: un grupo con ese nombre no recibiría mensajes.
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
                if excede_limite_envio(nickname):
                    enviar(socket_cliente, {
                        'tipo': 'server',
                        'contenido': 'Estás enviando mensajes muy rápido. Esperá unos segundos.'
                    })
                    continue
                nombre_grupo = mensaje.get('grupo')
                contenido = mensaje.get('contenido', '')

                with lock:
                    es_miembro = nickname in grupos.get(nombre_grupo, {}).get('miembros', set())

                if es_miembro:
                    id_msg = nuevo_id_mensaje()
                    registrar_mensaje_editable(id_msg, nickname, 'grupo_msg', grupo=nombre_grupo)
                    registrar_mensaje_enviado()
                    enviar_grupo(nombre_grupo, {
                        'tipo': 'grupo_msg',
                        'id': id_msg,
                        'grupo': nombre_grupo,
                        'emisor': nickname,
                        'contenido': contenido,
                        'hora': obtener_hora()
                    })

            elif tipo == 'grupo_salir':
                nombre_grupo = mensaje.get('grupo')
                _salir_de_grupo(nickname, nombre_grupo)
                enviar(socket_cliente, {'tipo': 'grupo_eliminado', 'nombre': nombre_grupo})

            elif tipo == 'ping':
                enviar(socket_cliente, {
                    'tipo': 'pong',
                    'ts_cliente': mensaje.get('ts_cliente'),
                    'hora': obtener_hora()
                })

            elif tipo == 'stats_solicitar':
                with lock:
                    usuarios_conectados = len(clientes)
                    total_mensajes = mensajes_totales
                enviar(socket_cliente, {
                    'tipo': 'stats',
                    'usuarios_conectados': usuarios_conectados,
                    'mensajes_totales': total_mensajes,
                    'uptime_segundos': int(time.time() - hora_inicio_servidor)
                })

            elif tipo == 'whois':
                usuario = mensaje.get('usuario', '')
                with lock:
                    existe = usuario in clientes
                    avatar_u = avatares.get(usuario)
                    color_u = colores.get(usuario)
                    desde = horas_conexion.get(usuario)
                enviar(socket_cliente, {
                    'tipo': 'whois_resultado', 'usuario': usuario, 'existe': existe,
                    'avatar': avatar_u, 'color': color_u, 'conectado_desde': desde
                })

            elif tipo == 'msg_editar':
                id_mensaje = mensaje.get('id_mensaje')
                nuevo_contenido = mensaje.get('contenido', '')
                info, error = validar_edicion(nickname, id_mensaje)
                if error:
                    enviar(socket_cliente, {'tipo': 'server', 'contenido': error})
                else:
                    evento = {'tipo': 'msg_editado', 'id_mensaje': id_mensaje, 'contenido': nuevo_contenido}
                    if info['tipo'] == 'msg':
                        broadcast(evento)
                    elif info['tipo'] == 'priv':
                        enviar_privado(info['destinatario'], evento)
                        if info['destinatario'] != nickname:
                            enviar(socket_cliente, evento)
                    elif info['tipo'] == 'grupo_msg':
                        enviar_grupo(info['grupo'], evento)

            elif tipo == 'msg_eliminar':
                id_mensaje = mensaje.get('id_mensaje')
                info, error = validar_edicion(nickname, id_mensaje)
                if error:
                    enviar(socket_cliente, {'tipo': 'server', 'contenido': error})
                else:
                    evento = {'tipo': 'msg_eliminado', 'id_mensaje': id_mensaje}
                    if info['tipo'] == 'msg':
                        broadcast(evento)
                    elif info['tipo'] == 'priv':
                        enviar_privado(info['destinatario'], evento)
                        if info['destinatario'] != nickname:
                            enviar(socket_cliente, evento)
                    elif info['tipo'] == 'grupo_msg':
                        enviar_grupo(info['grupo'], evento)
                    with lock:
                        mensajes_registro.pop(id_mensaje, None)

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
                horas_conexion.pop(nickname, None)
                mensajes_recientes.pop(nickname, None)
                grupos_del_usuario = [n for n, info in grupos.items() if nickname in info['miembros']]
            for nombre_grupo in grupos_del_usuario:
                _salir_de_grupo(nickname, nombre_grupo)
            registrar_log_conexion(f'DESCONEXION {nickname}')
            print(f'[Desconectado] {nickname}')
            broadcast({
                'tipo': 'server',
                'contenido': f'{nickname} ha abandonado el chat.'
            })
            enviar_lista_usuarios()
        socket_cliente.close()


def main():
    os.makedirs(CARPETA_ARCHIVOS, exist_ok=True)

    contexto_tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    contexto_tls.load_cert_chain(certfile=RUTA_CERT_TLS, keyfile=RUTA_KEY_TLS)

    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servidor.bind((HOST, PUERTO))
    servidor.listen()

    print('=' * 50)
    print('Servidor de chat iniciado')
    print(f'Escuchando en {HOST}:{PUERTO}')
    print(f'IP local del servidor: {obtener_ip_local()}')
    print('Cifrado: TLS habilitado (certificado autofirmado)')
    print('Presiona Ctrl+C para detener')
    print('=' * 50)

    try:
        while True:
            socket_cliente, direccion = servidor.accept()
            activar_keepalive(socket_cliente)
            hilo = threading.Thread(
                target=manejar_cliente,
                args=(socket_cliente, direccion, contexto_tls),
                daemon=True
            )
            hilo.start()
    except KeyboardInterrupt:
        print('\n[Apagando servidor...]')
    finally:
        servidor.close()


if __name__ == '__main__':
    main()
