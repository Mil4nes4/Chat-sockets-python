import os
import sys
import threading

# Asegura que el módulo cliente_chat se pueda importar desde cualquier ubicación
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cliente.cliente_chat import (
    conectar, enviar, recibir, enviar_nickname, enviar_mensaje_publico,
    enviar_mensaje_privado, solicitar_lista, enviar_archivo, guardar_archivo, cerrar
)


def imprimir_ayuda():
    print('\nComandos disponibles:')
    print('  /privado <usuario> <mensaje>   Enviar mensaje privado')
    print('  /usuarios                      Ver usuarios conectados')
    print('  /archivo <ruta> [usuario]      Enviar archivo (a todos o privado)')
    print('  /salir                         Desconectarse del chat')
    print('  /ayuda                         Mostrar esta ayuda\n')


def escuchar_mensajes(sock, conectado):
    """Hilo que escucha continuamente los mensajes del servidor."""
    while conectado[0]:
        try:
            mensaje = recibir(sock)
            if not mensaje:
                print('\n[Desconectado del servidor]')
                conectado[0] = False
                break

            tipo = mensaje.get('tipo')
            hora = mensaje.get('hora', '')

            if tipo == 'msg':
                print(f'\n[{hora}] {mensaje["emisor"]}: {mensaje["contenido"]}')
            elif tipo == 'priv':
                print(f'\n[{hora}] [PRIVADO de {mensaje["emisor"]}]: {mensaje["contenido"]}')
            elif tipo == 'server':
                print(f'\n[SERVIDOR] {mensaje["contenido"]}')
            elif tipo == 'usuarios':
                lista = ', '.join(mensaje.get('contenido', [])) or '(ninguno)'
                print(f'\n[USUARIOS CONECTADOS] {lista}')
            elif tipo == 'historial':
                print(f'\n[HISTORIAL] {mensaje["contenido"]}')
            elif tipo == 'file':
                ruta = guardar_archivo(
                    mensaje.get('emisor'),
                    mensaje.get('nombre_archivo'),
                    mensaje.get('datos')
                )
                print(f'\n[ARCHIVO de {mensaje["emisor"]}] Guardado en: {ruta}')

            print('> ', end='', flush=True)
        except Exception as e:
            print(f'\n[Error de recepción] {e}')
            conectado[0] = False
            break


def main():
    print('--- Cliente de Chat (Consola) ---')
    ip = input('IP del servidor (127.0.0.1): ').strip() or '127.0.0.1'
    puerto_str = input('Puerto (5000): ').strip() or '5000'
    try:
        puerto = int(puerto_str)
    except ValueError:
        print('Puerto inválido.')
        return

    nickname = input('Nickname: ').strip()
    if not nickname:
        print('El nickname no puede estar vacío.')
        return

    try:
        sock = conectar(ip, puerto)
    except Exception as e:
        print(f'No se pudo conectar al servidor: {e}')
        return

    enviar_nickname(sock, nickname)
    respuesta = recibir(sock)

    if respuesta and respuesta.get('contenido') == 'NICK_INVALIDO':
        print('El nickname ya está en uso o es inválido.')
        sock.close()
        return

    if respuesta:
        print(f'[SERVIDOR] {respuesta.get("contenido")}')

    conectado = [True]
    hilo = threading.Thread(target=escuchar_mensajes, args=(sock, conectado), daemon=True)
    hilo.start()

    imprimir_ayuda()

    while conectado[0]:
        try:
            entrada = input('> ')
        except EOFError:
            break
        except KeyboardInterrupt:
            break

        if not entrada:
            continue

        if entrada.startswith('/privado '):
            partes = entrada.split(' ', 2)
            if len(partes) < 3:
                print('Uso: /privado <usuario> <mensaje>')
                continue
            enviar_mensaje_privado(sock, partes[1], partes[2])

        elif entrada == '/usuarios':
            solicitar_lista(sock)

        elif entrada.startswith('/archivo '):
            partes = entrada.split(' ', 2)
            if len(partes) < 2:
                print('Uso: /archivo <ruta> [usuario]')
                continue
            ruta = partes[1]
            destinatario = partes[2] if len(partes) == 3 else 'todos'
            if not os.path.exists(ruta):
                print('El archivo no existe.')
                continue
            try:
                enviar_archivo(sock, ruta, destinatario)
                print(f'Archivo enviado a {destinatario}.')
            except Exception as e:
                print(f'Error al enviar archivo: {e}')

        elif entrada == '/salir':
            break

        elif entrada == '/ayuda':
            imprimir_ayuda()

        else:
            enviar_mensaje_publico(sock, entrada)

    cerrar(sock)
    print('Desconectado.')


if __name__ == '__main__':
    main()
