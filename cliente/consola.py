import os
import shutil
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cliente.cliente_chat import (
    conectar, enviar, recibir, enviar_nickname, enviar_mensaje_publico,
    enviar_mensaje_privado, solicitar_lista, enviar_archivo,
    enviar_typing, guardar_archivo, cerrar, EMOJIS_COMUNES
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


def _asegurar_utf8():
    # Evita UnicodeEncodeError con los caracteres de caja/bloque si la
    # salida no está en una consola UTF-8 (p. ej. redirigida a un archivo).
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


_habilitar_colores_windows()
_asegurar_utf8()

LOCK_IMPRESION = threading.RLock()

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


PALETA_USUARIOS = ['\033[34m', '\033[32m', '\033[33m', '\033[35m', '\033[36m', '\033[31m']


def color_usuario(nickname):
    indice = sum(ord(c) for c in nickname) % len(PALETA_USUARIOS)
    return PALETA_USUARIOS[indice]


MASCOTA_ASCII = [
    "  █     █  ",
    "   █   █   ",
    "  ███████  ",
    " ██ ███ ██ ",
    "███████████",
    "█ ███████ █",
    "█ █     █ █",
    "   █   █   ",
]

ANCHO_BANNER = 60


def _margen_centrado():
    # Centra los recuadros según el ancho real de la terminal. Si no se
    # puede detectar (p. ej. salida redirigida a un archivo), usa 80
    # columnas por defecto en vez de fallar.
    ancho_terminal = shutil.get_terminal_size(fallback=(80, 24)).columns
    return ' ' * max((ancho_terminal - ANCHO_BANNER) // 2, 0)


def reproducir_beep():
    """Reproduce un sonido de notificación."""
    try:
        if sys.platform == 'win32':
            import winsound
            winsound.PlaySound(r'C:\Windows\Media\Windows Pop-up Blocked.wav',
                                winsound.SND_FILENAME | winsound.SND_ASYNC)
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


def imprimir_mascota():
    margen = _margen_centrado()
    print()
    for fila in MASCOTA_ASCII:
        print(margen + color(fila.center(ANCHO_BANNER), Color.VERDE))
    print()


def imprimir_banner():
    with LOCK_IMPRESION:
        margen = _margen_centrado()
        print()
        imprimir_mascota()
        print(margen + color('╔' + '═' * (ANCHO_BANNER - 2) + '╗', Color.AZUL))
        print(margen + color('║' + 'CHAT CON SOCKETS - CONSOLA'.center(ANCHO_BANNER - 2) + '║', Color.AZUL))
        print(margen + color('║' + 'Laboratorio de Sistemas Operativos'.center(ANCHO_BANNER - 2) + '║', Color.GRIS))
        print(margen + color('╟' + '─' * (ANCHO_BANNER - 2) + '╢', Color.AZUL))
        print(margen + color('║', Color.AZUL) + color(' ➤ Datos de conexión'.ljust(ANCHO_BANNER - 2), Color.FONDO_GRIS + Color.BOLD) + color('║', Color.AZUL))
        print(margen + color('╚' + '═' * (ANCHO_BANNER - 2) + '╝', Color.AZUL))
        print()


def imprimir_separador():
    print(_margen_centrado() + color('─' * ANCHO_BANNER, Color.GRIS))


def imprimir_ayuda():
    with LOCK_IMPRESION:
        margen = _margen_centrado()
        print()
        print(margen + color('┌' + '─' * (ANCHO_BANNER - 2) + '┐', Color.CIAN))
        print(margen + color('│' + 'COMANDOS DISPONIBLES'.center(ANCHO_BANNER - 2) + '│', Color.CIAN))
        print(margen + color('└' + '─' * (ANCHO_BANNER - 2) + '┘', Color.CIAN))
        print(f'{margen}  {color("/privado", Color.AMARILLO)} <usuario> <mensaje>  Enviar mensaje privado  ({color("/p", Color.AMARILLO)})')
        print(f'{margen}  {color("/usuarios", Color.AMARILLO)}                    Ver usuarios conectados  ({color("/u", Color.AMARILLO)})')
        print(f'{margen}  {color("/archivo", Color.AMARILLO)} <ruta> [usuario]    Enviar archivo             ({color("/a", Color.AMARILLO)})')
        print(f'{margen}  {color("/buscar", Color.AMARILLO)} <texto>              Buscar en el historial     ({color("/b", Color.AMARILLO)})')
        print(f'{margen}  {color("/emoji", Color.AMARILLO)} [número] [texto]      Enviar mensaje con emoji   ({color("/e", Color.AMARILLO)})')
        print(f'{margen}  {color("/limpiar", Color.AMARILLO)}                     Limpiar pantalla           ({color("/clear", Color.AMARILLO)})')
        print(f'{margen}  {color("/reconectar", Color.AMARILLO)}                  Intentar reconectar        ({color("/r", Color.AMARILLO)})')
        print(f'{margen}  {color("/salir", Color.AMARILLO)}                       Desconectarse              ({color("/s", Color.AMARILLO)})')
        print(f'{margen}  {color("/ayuda", Color.AMARILLO)}                       Mostrar esta ayuda         ({color("/h", Color.AMARILLO)})')
        imprimir_separador()
        print(
            f'{margen}  {color("●", Color.AMARILLO)} comando  '
            f'{color("●", Color.VERDE)} servidor  '
            f'{color("●", Color.AMARILLO)} privado  '
            f'{color("●", Color.MAGENTA)} archivo  '
            f'{color("●", Color.GRIS)} historial'
        )
        print()


def imprimir_menu_emojis():
    with LOCK_IMPRESION:
        margen = _margen_centrado()
        print()
        print(margen + color('┌' + '─' * (ANCHO_BANNER - 2) + '┐', Color.CIAN))
        print(margen + color('│' + 'ELEGÍ UN EMOJI'.center(ANCHO_BANNER - 2) + '│', Color.CIAN))
        print(margen + color('└' + '─' * (ANCHO_BANNER - 2) + '┘', Color.CIAN))
        por_fila = 10
        for i in range(0, len(EMOJIS_COMUNES), por_fila):
            fila = EMOJIS_COMUNES[i:i + por_fila]
            numeros = '  '.join(f'{color(str(i + j + 1), Color.AMARILLO)}:{e}' for j, e in enumerate(fila))
            print(f'{margen}  {numeros}')
        print()



class ClienteConsola:
    def __init__(self):
        self.sock = None
        self.nickname = ''
        self.conectado = False
        self.hilo_escucha = None
        self.historial = []
        self.historial_mostrado = False
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
        print(color(f'✓ Conectado como {nickname} a {ip}:{puerto}', Color.VERDE))

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
        with LOCK_IMPRESION:
            margen = _margen_centrado()
            print()
            print(margen + color('╔' + '═' * (ANCHO_BANNER - 2) + '╗', Color.VERDE))
            print(margen + color('║' + '¡Gracias por usar el chat!'.center(ANCHO_BANNER - 2) + '║', Color.VERDE))
            print(margen + color('║' + 'Desconectado del servidor'.center(ANCHO_BANNER - 2) + '║', Color.GRIS))
            print(margen + color('╚' + '═' * (ANCHO_BANNER - 2) + '╝', Color.VERDE))
            print()

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
                linea = color(f' {color("[Tú]", Color.BOLD + Color.BLANCO)} {hora}: {contenido} ', Color.FONDO_AZUL)
            else:
                nombre = color(emisor, Color.BOLD + color_usuario(emisor))
                linea = f'{nombre} {color(hora, Color.GRIS)}: {contenido}'
                reproducir_beep()

        elif tipo == 'priv':
            emisor = mensaje.get('emisor')
            contenido = mensaje.get('contenido')
            if emisor == self.nickname:
                destinatario = mensaje.get('destinatario')
                linea = f'🔒 {color("[PRIVADO para", Color.AMARILLO)} {color(destinatario, Color.BOLD)}{color("]", Color.AMARILLO)} {color(hora, Color.GRIS)}: {color(contenido, Color.AMARILLO)}'
            else:
                linea = f'🔒 {color("[PRIVADO", Color.AMARILLO)} {color("de", Color.AMARILLO)} {color(emisor, Color.BOLD)}{color("]", Color.AMARILLO)} {color(hora, Color.GRIS)}: {color(contenido, Color.AMARILLO)}'
                reproducir_beep()

        elif tipo == 'server':
            linea = f'ℹ️  {color("[SERVIDOR]", Color.VERDE)} {mensaje.get("contenido")}'

        elif tipo == 'usuarios':
            usuarios = mensaje.get('contenido', [])
            lista = ', '.join(usuarios) or '(ninguno)'
            linea = f'👥 {color("[USUARIOS]", Color.CIAN)} {lista}'

        elif tipo == 'historial':
            if not self.historial_mostrado:
                with LOCK_IMPRESION:
                    print()
                    print(_margen_centrado() + color('──── Historial anterior ────', Color.GRIS))
                self.historial_mostrado = True
            linea = f'🕘 {color("[HISTORIAL]", Color.GRIS)} {mensaje.get("contenido")}'

        elif tipo == 'file':
            emisor = mensaje.get('emisor')
            nombre = mensaje.get('nombre_archivo')
            tipo_archivo = 'IMAGEN' if es_imagen(nombre) else 'ARCHIVO'
            if emisor == self.nickname:
                linea = f'📎 {color(f"[{tipo_archivo} enviado]", Color.MAGENTA)} {nombre} → {mensaje.get("destinatario", "todos")}'
            else:
                ruta = guardar_archivo(emisor, nombre, mensaje.get('datos'))
                linea = f'📎 {color(f"[{tipo_archivo} de", Color.MAGENTA)} {color(emisor, Color.BOLD)}{color("]", Color.MAGENTA)} {nombre}\n    Guardado en: {ruta}'
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
            with LOCK_IMPRESION:
                print(f'\n{linea}')
                self._mostrar_sign()

    def _mostrar_server(self, texto):
        linea = f'ℹ️  {color("[SERVIDOR]", Color.VERDE)} {texto}'
        self.historial.append(linea)
        with LOCK_IMPRESION:
            print(linea)

    def _mostrar_typing(self, emisor):
        with LOCK_IMPRESION:
            print(f'\r{color(f"{emisor} está escribiendo...", Color.GRIS)}', end='', flush=True)
        threading.Timer(3.0, self._mostrar_sign).start()

    def _mostrar_sign(self):
        if self.conectado:
            with LOCK_IMPRESION:
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

        elif entrada in ('/emoji', '/e'):
            self._enviar_con_emoji()

        elif entrada.startswith('/emoji ') or entrada.startswith('/e '):
            partes = entrada.split(' ', 2)
            try:
                indice = int(partes[1]) - 1
                emoji = EMOJIS_COMUNES[indice]
            except (ValueError, IndexError):
                print(color(f'Uso: /emoji <número> [texto]  (número del 1 al {len(EMOJIS_COMUNES)} — usá /emoji para ver la lista)', Color.ROJO))
                return
            texto = partes[2] if len(partes) == 3 else ''
            mensaje = f'{emoji} {texto}'.strip() if texto else emoji
            enviar_mensaje_publico(self.sock, mensaje)

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

    def _enviar_con_emoji(self):
        imprimir_menu_emojis()
        eleccion = input(color('Elegí un número (Enter para cancelar): ', Color.BOLD)).strip()
        if not eleccion:
            return
        try:
            indice = int(eleccion) - 1
            emoji = EMOJIS_COMUNES[indice]
        except (ValueError, IndexError):
            print(color('Número inválido.', Color.ROJO))
            return

        texto = input(color(f'Mensaje con {emoji} (Enter para mandar solo el emoji): ', Color.BOLD)).strip()
        mensaje = f'{emoji} {texto}'.strip() if texto else emoji
        enviar_mensaje_publico(self.sock, mensaje)

    def _buscar(self, texto):
        coincidencias = [linea for linea in self.historial if texto.lower() in linea.lower()]
        with LOCK_IMPRESION:
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

        ip = input(color('  IP del servidor', Color.BOLD) + ' (127.0.0.1): ').strip() or '127.0.0.1'
        puerto_str = input(color('  Puerto', Color.BOLD) + ' (5000): ').strip() or '5000'
        try:
            self.puerto = int(puerto_str)
        except ValueError:
            print(color('Puerto inválido.', Color.ROJO))
            return

        self.nickname = input(color('  Nickname', Color.BOLD) + ': ').strip()
        if not self.nickname:
            print(color('El nickname no puede estar vacío.', Color.ROJO))
            return
        imprimir_separador()

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
