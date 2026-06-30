import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cliente.cliente_chat import (
    conectar, enviar, recibir, enviar_nickname, enviar_mensaje_publico,
    enviar_mensaje_privado, solicitar_lista, enviar_archivo,
    enviar_typing, guardar_archivo, cerrar
)


def _habilitar_colores_windows():
    #Habilita los códigos ANSI en cmd y PowerShell de Windows.
    if sys.platform == 'win32':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass


_habilitar_colores_windows()


class Color:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    AZUL = '\033[94m'
    VERDE = '\033[92m'
    AMARILLO = '\033[93m'
    ROJO = '\033[91m'
    MAGENTA = '\033[95m'
    CIAN = '\033[96m'
    GRIS = '\033[90m'
    BLANCO = '\033[97m'
    FONDO_AZUL = '\033[44m'
    FONDO_GRIS = '\033[100m'


def color(texto, codigo):
    return f'{codigo}{texto}{Color.RESET}'


def reproducir_beep():
    """Reproduce un sonido de notificación."""
    try:
        if sys.platform == 'win32':
            import winsound
            winsound.MessageBeep()
        else:
            print('\a', end='')
    except Exception:
        pass


def es_imagen(nombre_archivo):
    extensiones = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')
    return nombre_archivo.lower().endswith(extensiones)


def limpiar_pantalla_mensajes():
    """Limpia la pantalla de la terminal."""
    if sys.platform == 'win32':
        os.system('cls')
    else:
        os.system('clear')


def imprimir_banner():
    print()
    print(color('╔══════════════════════════════════════════╗', Color.AZUL))
    print(color('║        CHAT CON SOCKETS - CONSOLA        ║', Color.AZUL))
    print(color('╚══════════════════════════════════════════╝', Color.AZUL))
    print()


def imprimir_ayuda():
    print(color('\nComandos disponibles:', Color.BOLD))
    print(f'  {color("/privado", Color.AMARILLO)} <usuario> <mensaje>  Enviar mensaje privado  ({color("/p", Color.AMARILLO)})')
    print(f'  {color("/usuarios", Color.AMARILLO)}                    Ver usuarios conectados  ({color("/u", Color.AMARILLO)})')
    print(f'  {color("/archivo", Color.AMARILLO)} <ruta> [usuario]    Enviar archivo             ({color("/a", Color.AMARILLO)})')
    print(f'  {color("/buscar", Color.AMARILLO)} <texto>              Buscar en el historial     ({color("/b", Color.AMARILLO)})')
    print(f'  {color("/limpiar", Color.AMARILLO)}                     Limpiar pantalla           ({color("/clear", Color.AMARILLO)})')
    print(f'  {color("/reconectar", Color.AMARILLO)}                  Intentar reconectar        ({color("/r", Color.AMARILLO)})')
    print(f'  {color("/salir", Color.AMARILLO)}                       Desconectarse              ({color("/s", Color.AMARILLO)})')
    print(f'  {color("/ayuda", Color.AMARILLO)}                       Mostrar esta ayuda         ({color("/h", Color.AMARILLO)})\n')



class ClienteConsola:
    def __init__(self):
        self.sock = None
        self.nickname = ''
        self.conectado = False
        self.hilo_escucha = None
        self.historial = []
        self.ultimo_typing = 0
        self.ip = '127.0.0.1'
        self.puerto = 5000

    def conectar(self, ip, puerto, nickname):
        self.ip = ip
        self.puerto = puerto
        self.nickname = nickname

        try:
            self.sock = conectar(ip, puerto)
        except Exception as e:
            print(color(f'No se pudo conectar al servidor: {e}', Color.ROJO))
            return False

        enviar_nickname(self.sock, nickname)
        respuesta = recibir(self.sock)

        if respuesta and respuesta.get('contenido') == 'NICK_INVALIDO':
            print(color('El nickname ya está en uso o es inválido.', Color.ROJO))
            self.sock.close()
            self.sock = None
            return False

        self.conectado = True

        if respuesta:
            self._mostrar_server(respuesta.get('contenido'))

        self.hilo_escucha = threading.Thread(target=self._escuchar, daemon=True)
        self.hilo_escucha.start()

        return True

    def desconectar(self):
        self.conectado = False
        if self.sock:
            cerrar(self.sock)
            self.sock = None
        print(color('\nDesconectado.', Color.VERDE))

    def reconectar(self):
        self.desconectar()
        if self.hilo_escucha and self.hilo_escucha.is_alive():
            self.hilo_escucha.join(timeout=2.0)
        print(color('\nIntentando reconectar...', Color.AMARILLO))
        time.sleep(1)
        return self.conectar(self.ip, self.puerto, self.nickname)

    def _escuchar(self):
        while self.conectado:
            try:
                mensaje = recibir(self.sock)
                if not mensaje:
                    print(color('\n[Desconectado del servidor]', Color.ROJO))
                    self.conectado = False
                    break
                self._manejar_mensaje(mensaje)
            except Exception as e:
                if self.conectado:
                    print(color(f'\n[Error de recepción] {e}', Color.ROJO))
                    self.conectado = False
                break

    def _manejar_mensaje(self, mensaje):
        tipo = mensaje.get('tipo')
        hora = mensaje.get('hora', '')
        linea = ''

        if tipo == 'msg':
            emisor = mensaje.get('emisor')
            contenido = mensaje.get('contenido')
            if emisor == self.nickname:
                linea = f'{color("[Tú]", Color.AZUL)} {color(hora, Color.GRIS)}: {color(contenido, Color.AZUL)}'
            else:
                linea = f'{color(emisor, Color.BOLD)} {color(hora, Color.GRIS)}: {contenido}'
                reproducir_beep()

        elif tipo == 'priv':
            emisor = mensaje.get('emisor')
            contenido = mensaje.get('contenido')
            linea = f'{color("[PRIVADO", Color.AMARILLO)} {color("de", Color.AMARILLO)} {color(emisor, Color.BOLD)}{color("]", Color.AMARILLO)} {color(hora, Color.GRIS)}: {color(contenido, Color.AMARILLO)}'
            if emisor != self.nickname:
                reproducir_beep()

        elif tipo == 'server':
            linea = f'{color("[SERVIDOR]", Color.VERDE)} {mensaje.get("contenido")}'

        elif tipo == 'usuarios':
            usuarios = mensaje.get('contenido', [])
            lista = ', '.join(usuarios) or '(ninguno)'
            linea = f'{color("[USUARIOS]", Color.CIAN)} {lista}'

        elif tipo == 'historial':
            linea = f'{color("[HISTORIAL]", Color.GRIS)} {mensaje.get("contenido")}'

        elif tipo == 'file':
            emisor = mensaje.get('emisor')
            nombre = mensaje.get('nombre_archivo')
            tipo_archivo = 'IMAGEN' if es_imagen(nombre) else 'ARCHIVO'
            if emisor == self.nickname:
                linea = f'{color(f"[{tipo_archivo} enviado]", Color.MAGENTA)} {nombre} → {mensaje.get("destinatario", "todos")}'
            else:
                ruta = guardar_archivo(emisor, nombre, mensaje.get('datos'))
                linea = f'{color(f"[{tipo_archivo} de", Color.MAGENTA)} {color(emisor, Color.BOLD)}{color("]", Color.MAGENTA)} {nombre}\n    Guardado en: {ruta}'
                reproducir_beep()

        elif tipo == 'typing':
            emisor = mensaje.get('emisor')
            destinatario = mensaje.get('destinatario')
            if emisor != self.nickname:
                if destinatario == 'todos' or destinatario == self.nickname:
                    self._mostrar_typing(emisor)
            return

        if linea:
            self.historial.append(linea)
            print(f'\n{linea}')
            self._mostrar_sign()

    def _mostrar_server(self, texto):
        linea = f'{color("[SERVIDOR]", Color.VERDE)} {texto}'
        self.historial.append(linea)
        print(linea)

    def _mostrar_typing(self, emisor):
        print(f'\r{color(f"{emisor} está escribiendo...", Color.GRIS)}', end='', flush=True)
        threading.Timer(3.0, self._mostrar_sign).start()

    def _mostrar_sign(self):
        if self.conectado:
            print('\r> ', end='', flush=True)

    def _on_typing(self):
        if not self.conectado or not self.sock:
            return
        ahora = time.time()
        if ahora - self.ultimo_typing > 2:
            self.ultimo_typing = ahora
            try:
                enviar_typing(self.sock, 'todos')
            except Exception:
                pass

    def enviar_mensaje(self, entrada):
        if entrada.startswith('/privado ') or entrada.startswith('/p '):
            partes = entrada.split(' ', 2)
            if len(partes) < 3:
                print(color('Uso: /privado <usuario> <mensaje>', Color.ROJO))
                return
            enviar_mensaje_privado(self.sock, partes[1], partes[2])
            linea = f'{color("[PRIVADO para", Color.AMARILLO)} {color(partes[1], Color.BOLD)}{color("]", Color.AMARILLO)} {color(time.strftime("%H:%M:%S"), Color.GRIS)}: {color(partes[2], Color.AMARILLO)}'
            self.historial.append(linea)
            print(linea)

        elif entrada in ('/usuarios', '/u'):
            solicitar_lista(self.sock)

        elif entrada.startswith('/archivo ') or entrada.startswith('/a '):
            partes = entrada.split(' ', 2)
            if len(partes) < 2:
                print(color('Uso: /archivo <ruta> [usuario]', Color.ROJO))
                return
            ruta = partes[1]
            destinatario = partes[2] if len(partes) == 3 else 'todos'
            if not os.path.exists(ruta):
                print(color('El archivo no existe.', Color.ROJO))
                return
            try:
                enviar_archivo(self.sock, ruta, destinatario)
                nombre = os.path.basename(ruta)
                tipo_archivo = 'IMAGEN' if es_imagen(nombre) else 'ARCHIVO'
                print(color(f'{tipo_archivo} enviado a {destinatario}: {nombre}', Color.MAGENTA))
            except Exception as e:
                print(color(f'Error al enviar archivo: {e}', Color.ROJO))

        elif entrada in ('/buscar', '/b'):
            print(color('Uso: /buscar <texto>', Color.ROJO))

        elif entrada.startswith('/buscar ') or entrada.startswith('/b '):
            partes = entrada.split(' ', 1)
            if len(partes) < 2:
                print(color('Uso: /buscar <texto>', Color.ROJO))
                return
            self._buscar(partes[1])

        elif entrada in ('/limpiar', '/clear'):
            self._limpiar()

        elif entrada in ('/reconectar', '/r'):
            self.reconectar()

        elif entrada in ('/salir', '/s'):
            return False

        elif entrada in ('/ayuda', '/h'):
            imprimir_ayuda()

        else:
            enviar_mensaje_publico(self.sock, entrada)

        return True

    def _buscar(self, texto):
        coincidencias = [linea for linea in self.historial if texto.lower() in linea.lower()]
        print(color(f'\n[BUSCAR] {len(coincidencias)} coincidencias para "{texto}":', Color.CIAN))
        for linea in coincidencias:
            resaltada = linea.replace(
                texto, color(texto, Color.AMARILLO)
            ).replace(
                texto.capitalize(), color(texto.capitalize(), Color.AMARILLO)
            )
            print(f'  {resaltada}')
        if not coincidencias:
            print(color('  No se encontraron coincidencias.', Color.GRIS))

    def _limpiar(self):
        limpiar_pantalla_mensajes()
        imprimir_banner()
        print(color('Pantalla limpiada. Mensajes anteriores eliminados de la vista.', Color.GRIS))

    def run(self):
        imprimir_banner()

        ip = input(color('IP del servidor', Color.BOLD) + ' (127.0.0.1): ').strip() or '127.0.0.1'
        puerto_str = input(color('Puerto', Color.BOLD) + ' (5000): ').strip() or '5000'
        try:
            self.puerto = int(puerto_str)
        except ValueError:
            print(color('Puerto inválido.', Color.ROJO))
            return

        self.nickname = input(color('Nickname', Color.BOLD) + ': ').strip()
        if not self.nickname:
            print(color('El nickname no puede estar vacío.', Color.ROJO))
            return

        if not self.conectar(ip, self.puerto, self.nickname):
            return

        imprimir_ayuda()

        while self.conectado:
            try:
                entrada = input('> ')
            except EOFError:
                break
            except KeyboardInterrupt:
                break

            if not entrada:
                continue

            continuar = self.enviar_mensaje(entrada)
            if continuar is False:
                break

        self.desconectar()


def main():
    cliente = ClienteConsola()
    cliente.run()


if __name__ == '__main__':
    main()
