import base64
import json
import os
import re
import socket
import threading
from datetime import datetime


HOST = '0.0.0.0'
PUERTO = int(os.environ.get('CHAT_PUERTO', 5000))
MAX_ARCHIVO_MB = 50
MAX_TRAMA_BYTES = 80 * 1024 * 1024

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_HISTORIAL = os.path.join(BASE_DIR, 'historial_chat.txt')
CARPETA_ARCHIVOS = os.path.join(BASE_DIR, 'archivos_recibidos')

# nickname -> socket
clientes = {}
avatares = {}
colores = {}

# nombre -> {'miembros': set, 'creador': str, 'avatar': str}
grupos = {}

# Cada usuario pertenece exactamente a una sala pública.
salas = {'General': set()}
sala_por_usuario = {}

# id -> información necesaria para ACK, entrega, lectura y reacciones.
estados_mensajes = {}
rutas_mensajes = {}

lock = threading.RLock()
lock_envio = threading.Lock()
siguiente_id_mensaje = 0
huella_sesion = None


def nuevo_id_mensaje():
    global siguiente_id_mensaje
    with lock:
        siguiente_id_mensaje += 1
        return f'srv{siguiente_id_mensaje}'


def obtener_hora():
    return datetime.now().strftime('%H:%M:%S')


def obtener_ip_local():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(('8.8.8.8', 80))
        ip = sock.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        sock.close()
    return ip


def activar_keepalive(socket_cliente):
    socket_cliente.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    try:
        socket_cliente.setsockopt(
            socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30
        )
        socket_cliente.setsockopt(
            socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10
        )
        socket_cliente.setsockopt(
            socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3
        )
    except (AttributeError, OSError):
        pass


def enviar(socket_cliente, mensaje):
    try:
        data = json.dumps(mensaje, ensure_ascii=False).encode('utf-8')
        longitud = len(data)
        if longitud > MAX_TRAMA_BYTES:
            return
        with lock_envio:
            socket_cliente.sendall(
                longitud.to_bytes(4, byteorder='big')
            )
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
    if longitud <= 0 or longitud > MAX_TRAMA_BYTES:
        raise ValueError('Longitud de trama inválida.')

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
    for nickname, sock in copia:
        if excluir and nickname == excluir:
            continue
        enviar(sock, mensaje)


def _sockets_de_nicks(nicknames):
    with lock:
        return [
            (nickname, clientes[nickname])
            for nickname in nicknames
            if nickname in clientes
        ]


def enviar_a_nicks(nicknames, mensaje, excluir=None):
    for nickname, sock in _sockets_de_nicks(nicknames):
        if excluir and nickname == excluir:
            continue
        enviar(sock, mensaje)


def enviar_privado(destinatario, mensaje):
    with lock:
        sock = clientes.get(destinatario)
    if sock:
        enviar(sock, mensaje)
        return True
    return False


def miembros_sala(nombre_sala):
    with lock:
        return set(salas.get(nombre_sala, set()))


def broadcast_sala(nombre_sala, mensaje, excluir=None):
    enviar_a_nicks(
        miembros_sala(nombre_sala),
        mensaje,
        excluir=excluir
    )


def enviar_grupo(nombre_grupo, mensaje):
    with lock:
        miembros = set(
            grupos.get(nombre_grupo, {}).get('miembros', set())
        )
    enviar_a_nicks(miembros, mensaje)


def enviar_lista_usuarios():
    with lock:
        usuarios = list(clientes.keys())
        copia_avatares = dict(avatares)
        copia_colores = dict(colores)
        copia_salas = dict(sala_por_usuario)
    broadcast({
        'tipo': 'usuarios',
        'contenido': usuarios,
        'avatares': copia_avatares,
        'colores': copia_colores,
        'salas_usuarios': copia_salas,
    })


def _mensaje_salas_para(nickname):
    with lock:
        contenido = [
            {'nombre': nombre, 'usuarios': len(miembros)}
            for nombre, miembros in salas.items()
        ]
        contenido.sort(
            key=lambda item: (
                item['nombre'] != 'General',
                item['nombre'].lower()
            )
        )
        sala_actual = sala_por_usuario.get(nickname, 'General')
    return {
        'tipo': 'salas',
        'contenido': contenido,
        'sala_actual': sala_actual,
    }


def enviar_lista_salas(destinatario=None):
    if destinatario:
        with lock:
            sock = clientes.get(destinatario)
        if sock:
            enviar(sock, _mensaje_salas_para(destinatario))
        return

    with lock:
        copia = list(clientes.items())
    for nickname, sock in copia:
        enviar(sock, _mensaje_salas_para(nickname))


def _nombre_valido(nombre):
    if not nombre or len(nombre) > 30:
        return False
    return re.fullmatch(r'[\wáéíóúÁÉÍÓÚñÑ .-]+', nombre) is not None


def mover_usuario_a_sala(nickname, nueva_sala):
    with lock:
        if nickname not in clientes or nueva_sala not in salas:
            return False

        sala_anterior = sala_por_usuario.get(nickname, 'General')
        if sala_anterior == nueva_sala:
            sock = clientes.get(nickname)
        else:
            salas.setdefault(sala_anterior, set()).discard(nickname)
            salas[nueva_sala].add(nickname)
            sala_por_usuario[nickname] = nueva_sala
            sock = clientes.get(nickname)

    if sala_anterior != nueva_sala:
        broadcast_sala(
            sala_anterior,
            {
                'tipo': 'server',
                'contenido': f'{nickname} salió de la sala.',
                'sala': sala_anterior,
            },
        )
        broadcast_sala(
            nueva_sala,
            {
                'tipo': 'server',
                'contenido': f'{nickname} entró a la sala.',
                'sala': nueva_sala,
            },
            excluir=nickname,
        )

    if sock:
        enviar(sock, {
            'tipo': 'sala_actualizada',
            'nombre': nueva_sala,
        })
        enviar_historial(sock, nueva_sala)

    enviar_lista_salas()
    enviar_lista_usuarios()
    return True


def sincronizar_grupo(nombre_grupo):
    with lock:
        info = grupos.get(nombre_grupo)
        if not info:
            return
        mensaje = {
            'tipo': 'grupo_actualizado',
            'nombre': nombre_grupo,
            'miembros': list(info['miembros']),
            'creador': info['creador'],
            'avatar': info['avatar'],
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


def guardar_historial(evento):
    try:
        with open(ARCHIVO_HISTORIAL, 'a', encoding='utf-8') as archivo:
            archivo.write(
                json.dumps(evento, ensure_ascii=False) + '\n'
            )
    except Exception as exc:
        print(f'[Error de historial] {exc}')


def enviar_historial(socket_cliente, nombre_sala):
    if not os.path.exists(ARCHIVO_HISTORIAL):
        return

    try:
        with open(
            ARCHIVO_HISTORIAL, 'r', encoding='utf-8'
        ) as archivo:
            for linea in archivo:
                linea = linea.strip()
                if not linea:
                    continue
                try:
                    evento = json.loads(linea)
                except json.JSONDecodeError:
                    if nombre_sala == 'General':
                        enviar(socket_cliente, {
                            'tipo': 'historial',
                            'contenido': linea,
                        })
                    continue

                if not isinstance(evento, dict):
                    continue
                if evento.get('sala', 'General') != nombre_sala:
                    continue

                historial = dict(evento)
                historial['tipo'] = 'historial_msg'
                enviar(socket_cliente, historial)
    except Exception as exc:
        print(f'[Error al enviar historial] {exc}')


def registrar_mensaje(
    id_mensaje, emisor, destinatarios, participantes, contexto
):
    destinatarios = set(destinatarios)
    participantes = set(participantes)
    with lock:
        estados_mensajes[id_mensaje] = {
            'emisor': emisor,
            'destinatarios': destinatarios,
            'entregados': set(),
            'leidos': set(),
        }
        rutas_mensajes[id_mensaje] = {
            'participantes': participantes,
            'contexto': contexto,
        }


def enviar_ack(emisor, id_mensaje):
    with lock:
        estado = estados_mensajes.get(id_mensaje, {})
        total = len(estado.get('destinatarios', set()))
    enviar_privado(emisor, {
        'tipo': 'ack',
        'id_mensaje': id_mensaje,
        'total_destinatarios': total,
    })


def procesar_estado(nickname, id_mensaje, estado_nuevo):
    with lock:
        estado = estados_mensajes.get(id_mensaje)
        if not estado:
            return

        destinatarios = estado['destinatarios']
        if nickname not in destinatarios:
            return

        if estado_nuevo == 'delivered':
            estado['entregados'].add(nickname)
        elif estado_nuevo == 'read':
            estado['entregados'].add(nickname)
            estado['leidos'].add(nickname)
        else:
            return

        total = len(destinatarios)
        entregados = len(estado['entregados'])
        leidos = len(estado['leidos'])
        emisor = estado['emisor']

        if total > 0 and leidos >= total:
            estado_agregado = 'read'
        elif total > 0 and entregados >= total:
            estado_agregado = 'delivered'
        else:
            estado_agregado = 'ack'

    enviar_privado(emisor, {
        'tipo': 'estado',
        'id_mensaje': id_mensaje,
        'estado': estado_agregado,
        'entregados': entregados,
        'leidos': leidos,
        'total_destinatarios': total,
    })


def manejar_reaccion(nickname, id_mensaje, emoji):
    if id_mensaje is None or not emoji:
        return

    with lock:
        ruta = rutas_mensajes.get(id_mensaje)
        if not ruta:
            return
        participantes = set(ruta['participantes'])

    if nickname not in participantes:
        return

    enviar_a_nicks(participantes, {
        'tipo': 'reaccion',
        'id_mensaje': id_mensaje,
        'emisor': nickname,
        'emoji': emoji,
    })


def manejar_archivo(
    emisor, destinatario, nombre_archivo, datos_base64
):
    limite_base64 = MAX_ARCHIVO_MB * 1024 * 1024 * 4 // 3 + 4
    if len(datos_base64) > limite_base64:
        enviar_privado(emisor, {
            'tipo': 'server',
            'contenido': (
                f'Archivo rechazado: supera el límite de '
                f'{MAX_ARCHIVO_MB} MB.'
            ),
        })
        return

    nombre_archivo = os.path.basename(nombre_archivo)
    os.makedirs(CARPETA_ARCHIVOS, exist_ok=True)
    ruta = os.path.join(
        CARPETA_ARCHIVOS,
        f'{re.sub(r"[^A-Za-z0-9._ -]", "_", emisor)}_'
        f'{re.sub(r"[^A-Za-z0-9._ -]", "_", nombre_archivo)}'
    )

    try:
        datos = base64.b64decode(datos_base64, validate=True)
        if len(datos) > MAX_ARCHIVO_MB * 1024 * 1024:
            raise ValueError('archivo demasiado grande')
        with open(ruta, 'wb') as archivo:
            archivo.write(datos)
    except Exception as exc:
        print(f'[Error al guardar archivo] {exc}')
        enviar_privado(emisor, {
            'tipo': 'server',
            'contenido': 'No se pudo procesar el archivo enviado.',
        })
        return

    id_mensaje = nuevo_id_mensaje()
    hora = obtener_hora()
    mensaje = {
        'tipo': 'file',
        'id': id_mensaje,
        'emisor': emisor,
        'destinatario': destinatario,
        'nombre_archivo': nombre_archivo,
        'datos': datos_base64,
        'hora': hora,
    }

    if destinatario == 'todos':
        with lock:
            nombre_sala = sala_por_usuario.get(emisor, 'General')
            participantes = set(salas.get(nombre_sala, set()))
        mensaje['sala'] = nombre_sala
        enviar_a_nicks(participantes, mensaje)
        with lock:
            rutas_mensajes[id_mensaje] = {
                'participantes': participantes,
                'contexto': {'tipo': 'sala', 'nombre': nombre_sala},
            }
    else:
        with lock:
            existe = destinatario in clientes
        if not existe:
            enviar_privado(emisor, {
                'tipo': 'server',
                'contenido': (
                    f'No se pudo enviar el archivo: '
                    f'{destinatario} no está conectado.'
                ),
            })
            return

        participantes = {emisor, destinatario}
        enviar_a_nicks(participantes, mensaje)
        with lock:
            rutas_mensajes[id_mensaje] = {
                'participantes': participantes,
                'contexto': {
                    'tipo': 'privado',
                    'destinatario': destinatario,
                },
            }


def _id_recibido(mensaje):
    return str(mensaje.get('id') or nuevo_id_mensaje())


def _contenido_cifrado_valido(mensaje):
    contenido = mensaje.get('contenido')
    return (
        isinstance(contenido, str)
        and bool(contenido)
        and mensaje.get('cifrado') is True
    )


def manejar_cliente(socket_cliente, direccion):
    global huella_sesion

    nickname = None
    try:
        mensaje = recibir(socket_cliente)
        if not mensaje or mensaje.get('tipo') != 'nick':
            return

        nickname = str(mensaje.get('contenido', '')).strip()
        avatar = mensaje.get('avatar', 'circulo')
        color = mensaje.get('color')
        huella = str(mensaje.get('huella_clave', '')).strip()

        with lock:
            if not nickname or nickname in clientes:
                error = 'NICK_INVALIDO'
            elif not huella:
                error = 'CLAVE_REQUERIDA'
            elif huella_sesion and huella_sesion != huella:
                error = 'CLAVE_INCOMPATIBLE'
            else:
                error = None
                if huella_sesion is None:
                    huella_sesion = huella
                clientes[nickname] = socket_cliente
                avatares[nickname] = avatar
                if color:
                    colores[nickname] = color
                salas.setdefault('General', set()).add(nickname)
                sala_por_usuario[nickname] = 'General'

        if error:
            enviar(socket_cliente, {
                'tipo': 'server',
                'contenido': error,
            })
            return

        print(f'[Conectado] {nickname} desde {direccion}')

        enviar(socket_cliente, {
            'tipo': 'server',
            'contenido': f'Bienvenido al chat, {nickname}.',
        })
        enviar(socket_cliente, {
            'tipo': 'sala_actualizada',
            'nombre': 'General',
        })

        broadcast_sala('General', {
            'tipo': 'server',
            'contenido': f'{nickname} se ha unido al chat.',
            'sala': 'General',
        }, excluir=nickname)

        enviar_historial(socket_cliente, 'General')
        enviar_lista_usuarios()
        enviar_lista_salas()

        while True:
            mensaje = recibir(socket_cliente)
            if not mensaje:
                break

            tipo = mensaje.get('tipo')

            if tipo == 'msg':
                if not _contenido_cifrado_valido(mensaje):
                    enviar(socket_cliente, {
                        'tipo': 'server',
                        'contenido': 'MENSAJE_NO_CIFRADO',
                    })
                    continue

                id_mensaje = _id_recibido(mensaje)
                contenido = mensaje['contenido']
                hora = obtener_hora()

                with lock:
                    nombre_sala = sala_por_usuario.get(
                        nickname, 'General'
                    )
                    participantes = set(
                        salas.get(nombre_sala, set())
                    )
                destinatarios = participantes - {nickname}

                salida = {
                    'tipo': 'msg',
                    'id': id_mensaje,
                    'emisor': nickname,
                    'contenido': contenido,
                    'cifrado': True,
                    'hora': hora,
                    'sala': nombre_sala,
                }

                registrar_mensaje(
                    id_mensaje,
                    nickname,
                    destinatarios,
                    participantes,
                    {'tipo': 'sala', 'nombre': nombre_sala},
                )
                enviar_a_nicks(participantes, salida)
                enviar_ack(nickname, id_mensaje)
                guardar_historial(salida)

            elif tipo == 'priv':
                if not _contenido_cifrado_valido(mensaje):
                    enviar(socket_cliente, {
                        'tipo': 'server',
                        'contenido': 'MENSAJE_NO_CIFRADO',
                    })
                    continue

                destinatario = str(
                    mensaje.get('destinatario', '')
                ).strip()
                id_mensaje = _id_recibido(mensaje)

                with lock:
                    existe = destinatario in clientes
                if not existe:
                    enviar(socket_cliente, {
                        'tipo': 'error_envio',
                        'id_mensaje': id_mensaje,
                        'contenido': (
                            f'{destinatario} no está conectado.'
                        ),
                    })
                    continue

                participantes = {nickname, destinatario}
                destinatarios = (
                    {destinatario}
                    if destinatario != nickname
                    else set()
                )
                salida = {
                    'tipo': 'priv',
                    'id': id_mensaje,
                    'emisor': nickname,
                    'destinatario': destinatario,
                    'contenido': mensaje['contenido'],
                    'cifrado': True,
                    'hora': obtener_hora(),
                }

                registrar_mensaje(
                    id_mensaje,
                    nickname,
                    destinatarios,
                    participantes,
                    {
                        'tipo': 'privado',
                        'destinatario': destinatario,
                    },
                )
                enviar_a_nicks(participantes, salida)
                enviar_ack(nickname, id_mensaje)

            elif tipo == 'list':
                with lock:
                    usuarios = list(clientes.keys())
                    copia_avatares = dict(avatares)
                    copia_colores = dict(colores)
                    copia_salas = dict(sala_por_usuario)
                enviar(socket_cliente, {
                    'tipo': 'usuarios',
                    'contenido': usuarios,
                    'avatares': copia_avatares,
                    'colores': copia_colores,
                    'salas_usuarios': copia_salas,
                })

            elif tipo == 'sala_listar':
                enviar_lista_salas(nickname)

            elif tipo == 'sala_crear':
                nombre_sala = str(
                    mensaje.get('nombre', '')
                ).strip()
                with lock:
                    if not _nombre_valido(nombre_sala):
                        error = (
                            'El nombre debe tener entre 1 y 30 '
                            'caracteres válidos.'
                        )
                    elif nombre_sala in salas:
                        error = 'Ya existe una sala con ese nombre.'
                    elif nombre_sala in grupos:
                        error = (
                            'Ya existe un grupo con ese nombre.'
                        )
                    else:
                        error = None
                        salas[nombre_sala] = set()

                if error:
                    enviar(socket_cliente, {
                        'tipo': 'server',
                        'contenido': f'SALA_INVALIDA: {error}',
                    })
                else:
                    mover_usuario_a_sala(
                        nickname, nombre_sala
                    )

            elif tipo == 'sala_unirse':
                nombre_sala = str(
                    mensaje.get('nombre', '')
                ).strip()
                with lock:
                    existe = nombre_sala in salas
                if not existe:
                    enviar(socket_cliente, {
                        'tipo': 'server',
                        'contenido': (
                            'SALA_INVALIDA: La sala no existe.'
                        ),
                    })
                else:
                    mover_usuario_a_sala(
                        nickname, nombre_sala
                    )

            elif tipo == 'sala_salir':
                mover_usuario_a_sala(nickname, 'General')

            elif tipo == 'file':
                manejar_archivo(
                    nickname,
                    mensaje.get('destinatario', 'todos'),
                    mensaje.get('nombre_archivo', 'archivo'),
                    mensaje.get('datos', ''),
                )

            elif tipo == 'typing':
                destinatario = mensaje.get(
                    'destinatario', 'todos'
                )
                notificacion = {
                    'tipo': 'typing',
                    'emisor': nickname,
                    'destinatario': destinatario,
                }

                if destinatario == 'todos':
                    with lock:
                        nombre_sala = sala_por_usuario.get(
                            nickname, 'General'
                        )
                    notificacion['sala'] = nombre_sala
                    broadcast_sala(
                        nombre_sala,
                        notificacion,
                        excluir=nickname,
                    )
                else:
                    enviar_privado(
                        destinatario, notificacion
                    )

            elif tipo == 'delivered':
                procesar_estado(
                    nickname,
                    mensaje.get('id_mensaje'),
                    'delivered',
                )

            elif tipo == 'read':
                procesar_estado(
                    nickname,
                    mensaje.get('id_mensaje'),
                    'read',
                )

            elif tipo == 'reaccion':
                manejar_reaccion(
                    nickname,
                    mensaje.get('id_mensaje'),
                    mensaje.get('emoji'),
                )

            elif tipo == 'grupo_crear':
                nombre_grupo = str(
                    mensaje.get('nombre', '')
                ).strip()
                miembros_pedidos = mensaje.get('miembros', [])
                avatar_grupo = mensaje.get('avatar', 'gente')

                with lock:
                    miembros_validos = {
                        miembro
                        for miembro in miembros_pedidos
                        if miembro in clientes
                        and miembro != nickname
                    }

                    if not _nombre_valido(nombre_grupo):
                        error = 'el nombre no es válido'
                    elif nombre_grupo.lower() in {
                        'crear', 'invitar', 'salir'
                    }:
                        error = (
                            f'"{nombre_grupo}" es una palabra '
                            'reservada'
                        )
                    elif (
                        nombre_grupo in grupos
                        or nombre_grupo in clientes
                        or nombre_grupo in salas
                    ):
                        error = (
                            'ya existe un grupo, sala o usuario '
                            'con ese nombre'
                        )
                    elif not miembros_validos:
                        error = (
                            'elegí al menos un miembro conectado'
                        )
                    else:
                        error = None
                        grupos[nombre_grupo] = {
                            'miembros': {
                                nickname, *miembros_validos
                            },
                            'creador': nickname,
                            'avatar': avatar_grupo,
                        }

                if error:
                    enviar(socket_cliente, {
                        'tipo': 'server',
                        'contenido': (
                            f'GRUPO_INVALIDO: {error}'
                        ),
                    })
                else:
                    sincronizar_grupo(nombre_grupo)

            elif tipo == 'grupo_invitar':
                nombre_grupo = mensaje.get('grupo')
                miembros_pedidos = mensaje.get(
                    'miembros', []
                )

                with lock:
                    info = grupos.get(nombre_grupo)
                    if (
                        not info
                        or nickname not in info['miembros']
                    ):
                        error = (
                            'no sos miembro de ese grupo'
                        )
                    else:
                        error = None
                        nuevos = {
                            miembro
                            for miembro in miembros_pedidos
                            if miembro in clientes
                            and miembro not in info['miembros']
                        }
                        info['miembros'].update(nuevos)

                if error:
                    enviar(socket_cliente, {
                        'tipo': 'server',
                        'contenido': (
                            f'GRUPO_INVALIDO: {error}'
                        ),
                    })
                else:
                    sincronizar_grupo(nombre_grupo)

            elif tipo == 'grupo_msg':
                if not _contenido_cifrado_valido(mensaje):
                    enviar(socket_cliente, {
                        'tipo': 'server',
                        'contenido': 'MENSAJE_NO_CIFRADO',
                    })
                    continue

                nombre_grupo = mensaje.get('grupo')
                with lock:
                    miembros = set(
                        grupos.get(
                            nombre_grupo, {}
                        ).get('miembros', set())
                    )
                    es_miembro = nickname in miembros
                    conectados = {
                        miembro
                        for miembro in miembros
                        if miembro in clientes
                    }

                if not es_miembro:
                    enviar(socket_cliente, {
                        'tipo': 'server',
                        'contenido': (
                            'GRUPO_INVALIDO: no sos miembro '
                            'de ese grupo'
                        ),
                    })
                    continue

                id_mensaje = _id_recibido(mensaje)
                destinatarios = conectados - {nickname}
                salida = {
                    'tipo': 'grupo_msg',
                    'id': id_mensaje,
                    'grupo': nombre_grupo,
                    'emisor': nickname,
                    'contenido': mensaje['contenido'],
                    'cifrado': True,
                    'hora': obtener_hora(),
                }

                registrar_mensaje(
                    id_mensaje,
                    nickname,
                    destinatarios,
                    conectados,
                    {
                        'tipo': 'grupo',
                        'nombre': nombre_grupo,
                    },
                )
                enviar_a_nicks(conectados, salida)
                enviar_ack(nickname, id_mensaje)

            elif tipo == 'grupo_salir':
                nombre_grupo = mensaje.get('grupo')
                _salir_de_grupo(
                    nickname, nombre_grupo
                )
                enviar(socket_cliente, {
                    'tipo': 'grupo_eliminado',
                    'nombre': nombre_grupo,
                })

            elif tipo == 'exit':
                break

    except Exception as exc:
        print(f'[Error con {direccion}] {exc}')
    finally:
        if nickname:
            with lock:
                estaba_conectado = nickname in clientes
                clientes.pop(nickname, None)
                avatares.pop(nickname, None)
                colores.pop(nickname, None)

                nombre_sala = sala_por_usuario.pop(
                    nickname, 'General'
                )
                salas.setdefault(
                    nombre_sala, set()
                ).discard(nickname)

                grupos_usuario = [
                    nombre
                    for nombre, info in grupos.items()
                    if nickname in info['miembros']
                ]

            for nombre_grupo in grupos_usuario:
                _salir_de_grupo(
                    nickname, nombre_grupo
                )

            if estaba_conectado:
                print(f'[Desconectado] {nickname}')
                broadcast_sala(nombre_sala, {
                    'tipo': 'server',
                    'contenido': (
                        f'{nickname} ha abandonado el chat.'
                    ),
                    'sala': nombre_sala,
                })
                enviar_lista_usuarios()
                enviar_lista_salas()

            with lock:
                if not clientes:
                    huella_sesion = None
                    estados_mensajes.clear()
                    rutas_mensajes.clear()

        try:
            socket_cliente.close()
        except Exception:
            pass


def main():
    os.makedirs(CARPETA_ARCHIVOS, exist_ok=True)

    servidor = socket.socket(
        socket.AF_INET, socket.SOCK_STREAM
    )
    servidor.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1,
    )
    servidor.bind((HOST, PUERTO))
    servidor.listen()

    print('=' * 58)
    print('Servidor de chat iniciado')
    print(f'Escuchando en {HOST}:{PUERTO}')
    print(f'IP local del servidor: {obtener_ip_local()}')
    print('Los mensajes de texto viajan cifrados entre clientes.')
    print('Presiona Ctrl+C para detener')
    print('=' * 58)

    try:
        while True:
            socket_cliente, direccion = servidor.accept()
            activar_keepalive(socket_cliente)
            hilo = threading.Thread(
                target=manejar_cliente,
                args=(socket_cliente, direccion),
                daemon=True,
            )
            hilo.start()
    except KeyboardInterrupt:
        print('\n[Apagando servidor...]')
    finally:
        servidor.close()


if __name__ == '__main__':
    main()
