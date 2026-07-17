import math
import os
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog

import customtkinter as ctk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cliente.cliente_chat import (
    conectar, recibir, enviar_nickname, enviar_mensaje_publico,
    enviar_mensaje_privado, solicitar_lista, enviar_archivo,
    enviar_typing, guardar_archivo, cerrar, EMOJIS_COMUNES, enviar_reaccion,
    crear_grupo, invitar_a_grupo, enviar_mensaje_grupo, salir_grupo,
    es_mencionado, interpretar_contenido, confirmar_entrega,
    confirmar_lectura, solicitar_salas, crear_sala, unirse_sala,
    salir_sala
)

REACCIONES_RAPIDAS = ['👍', '❤️', '😂', '😮', '😢', '🙏']

try:
    from PIL import Image, ImageTk
    PIL_DISPONIBLE = True
except ImportError:
    PIL_DISPONIBLE = False

TEMA_OSCURO = {
    'nombre': 'oscuro',
    'fondo': '#313338',
    'panel': '#2b2d31',
    'entrada': '#1e1f22',
    'borde': '#4e5058',
    'texto': '#f2f3f5',
    'texto_secundario': '#c2c5cb',
    'acento': '#5865f2',
    'acento_hover': '#4752c4',
    'propio': '#c7d2ff',
    'propio_fondo': '#393d5c',
    'otros_fondo': '#40444b',
    'privado': '#ffb454',
    'privado_fondo': '#4f442b',
    'server': '#3ddc84',
    'server_fondo': '#2f4f3f',
    'historial': '#9a9fa6',
    'archivo': '#ff6b6e',
    'archivo_fondo': '#4a2c2e',
    'online': '#3ddc84',
    'busqueda': '#fee75c',
    'mencion': '#ffe066',
    'mencion_fondo': '#4a3f14',
    'grupo': '#6fd7a8',
    'grupo_fondo': '#223b30'
}

TEMA_CLARO = {
    'nombre': 'claro',
    'fondo': '#ffffff',
    'panel': '#f2f3f5',
    'entrada': '#e3e5e8',
    'borde': '#d4d7dc',
    'texto': '#060607',
    'texto_secundario': '#5c5e66',
    'acento': '#5865f2',
    'acento_hover': '#4752c4',
    'propio': '#4147c4',
    'propio_fondo': '#e3e5fd',
    'otros_fondo': '#f2f3f5',
    'privado': '#a85700',
    'privado_fondo': '#fdecd8',
    'server': '#1a8754',
    'server_fondo': '#e3f9ee',
    'historial': '#6d7075',
    'archivo': '#c62828',
    'archivo_fondo': '#fbe4e4',
    'online': '#23a55a',
    'busqueda': '#fee75c',
    'mencion': '#8a6d00',
    'mencion_fondo': '#fff3c4',
    'grupo': '#2f6f4f',
    'grupo_fondo': '#e1f3e8'
}

# Ordenada por matiz (rueda de color: rojo -> naranja -> amarillo -> verde ->
# celeste -> azul -> violeta -> rosa) para que el selector de color del login
# se vea como un degradé prolijo en vez de una mezcla al azar.
PALETA_USUARIOS = [
    '#ff6b6b', '#ff922b', '#ffa94d', '#ffd43b',
    '#a9e34b', '#69db7c', '#63e6be', '#3bc9db',
    '#4dabf7', '#74c0fc', '#748ffc', '#9775fa',
    '#da77f2', '#f783ac'
]


def color_usuario(nickname):
    indice = sum(ord(c) for c in nickname) % len(PALETA_USUARIOS)
    return PALETA_USUARIOS[indice]

AVATARES_DISPONIBLES = [
    'circulo', 'anillo', 'diamante', 'rayas', 'estrella', 'triangulo',
    'cruz', 'luna', 'corazon', 'reloj_arena',
    'ojo', 'trebol', 'sol', 'flecha', 'rayo', 'equis', 'gota', 'reloj'
]

AVATARES_GRUPO_DISPONIBLES = ['gente', 'casa', 'bandera', 'engranaje', 'nube', 'escudo']


def _es_pixel_avatar(patron, dx, dy, radio):
    dist = math.sqrt(dx * dx + dy * dy)
    if patron == 'anillo':
        return radio - 3 <= dist <= radio
    if patron == 'diamante':
        return abs(dx) + abs(dy) <= radio
    if patron == 'rayas':
        return dist <= radio and (dy // 2) % 2 == 0
    if patron == 'estrella':
        if dx == 0 and dy == 0:
            return True
        angulo = math.atan2(dy, dx)
        radio_estrella = radio * (0.35 + 0.65 * abs(math.cos(2 * angulo)))
        return dist <= radio_estrella
    if patron == 'triangulo':
        return -radio <= dy <= radio and abs(dx) <= (dy + radio) / 2
    if patron == 'cruz':
        grosor = radio / 2.6
        return dist <= radio and (abs(dx) <= grosor or abs(dy) <= grosor)
    if patron == 'luna':
        offset = radio * 0.45
        radio2 = radio * 0.88
        return dist <= radio and math.sqrt((dx - offset) ** 2 + dy * dy) > radio2
    if patron == 'corazon':
        lobe_r, lobe_cx, lobe_cy = radio * 0.4, radio * 0.46, -radio * 0.4
        dist_izq = math.sqrt((dx + lobe_cx) ** 2 + (dy - lobe_cy) ** 2)
        dist_der = math.sqrt((dx - lobe_cx) ** 2 + (dy - lobe_cy) ** 2)
        en_lobulos = dist_izq <= lobe_r or dist_der <= lobe_r
        en_triangulo = lobe_cy <= dy <= radio and abs(dx) <= radio * (radio - dy) / (radio - lobe_cy)
        return en_lobulos or en_triangulo
    if patron == 'reloj_arena':
        return abs(dx) <= abs(dy) and dist <= radio * 1.5
    if patron == 'ojo':
        cy = radio * 0.9
        r = radio * 1.3
        return math.sqrt(dx * dx + (dy + cy) ** 2) <= r and math.sqrt(dx * dx + (dy - cy) ** 2) <= r
    if patron == 'trebol':
        offset = radio * 0.62
        r = radio * 0.42
        centros = [(0, -offset), (offset * 0.87, offset * 0.5), (-offset * 0.87, offset * 0.5)]
        return any(math.sqrt((dx - cx) ** 2 + (dy - cy) ** 2) <= r for cx, cy in centros)
    if patron == 'sol':
        nucleo = dist <= radio * 0.4
        angulo = math.atan2(dy, dx) if (dx, dy) != (0, 0) else 0
        cerca_rayo = min(abs((angulo - k * math.pi / 4 + math.pi) % (2 * math.pi) - math.pi) for k in range(8)) < 0.18
        return nucleo or (cerca_rayo and dist <= radio)
    if patron == 'flecha':
        base_ancho = radio * 0.75
        if dy > radio * 0.1:
            return abs(dx) <= radio * 0.28 and dy <= radio
        return abs(dx) <= base_ancho * (dy + radio) / (radio + radio * 0.1)
    if patron == 'rayo':
        if dy <= -radio * 0.1:
            t = (dy + radio) / (radio - radio * 0.1)
            centro_rayo = radio * 0.6 + t * (-radio * 0.5 - radio * 0.6)
        elif dy <= radio * 0.1:
            t = (dy + radio * 0.1) / (radio * 0.2)
            centro_rayo = -radio * 0.5 + t * (radio * 0.25 - (-radio * 0.5))
        else:
            t = (dy - radio * 0.1) / (radio - radio * 0.1)
            centro_rayo = radio * 0.25 + t * (-radio * 0.65 - radio * 0.25)
        return abs(dx - centro_rayo) <= radio * 0.16 and dist <= radio * 1.25
    if patron == 'equis':
        grosor = radio * 0.32
        return (abs(dx - dy) <= grosor or abs(dx + dy) <= grosor) and dist <= radio
    if patron == 'gota':
        cy0 = radio * 0.3
        r0 = radio * 0.62
        y_punta = cy0 - r0 * 0.75
        ancho_base_punta = math.sqrt(max(r0 * r0 - (y_punta - cy0) ** 2, 0))
        if dy < y_punta:
            t = max((dy - (-radio)) / (y_punta - (-radio)), 0)
            return abs(dx) <= t * ancho_base_punta and dy >= -radio
        return math.sqrt(dx * dx + (dy - cy0) ** 2) <= r0
    if patron == 'reloj':
        anillo_reloj = radio - 1.5 <= dist <= radio
        aguja_min = abs(dx) <= 0.6 and -radio * 0.55 <= dy <= 0
        aguja_hor = abs(dy) <= 0.6 and 0 <= dx <= radio * 0.4
        return anillo_reloj or aguja_min or aguja_hor
    if patron == 'gente':
        rp = radio * 0.5
        offset = radio * 0.62
        return math.sqrt((dx + offset) ** 2 + dy * dy) <= rp or math.sqrt((dx - offset) ** 2 + dy * dy) <= rp
    if patron == 'casa':
        base_ancho = radio * 0.75
        if dy > 0:
            return abs(dx) <= base_ancho and dy <= radio
        return abs(dx) <= base_ancho * (dy + radio) / radio
    if patron == 'bandera':
        polex = -radio * 0.55
        pole = abs(dx - polex) <= radio * 0.14 and -radio <= dy <= radio
        flag = (-radio <= dy <= -radio * 0.1) and (dx >= polex) and (dx <= polex + radio * 1.1)
        return pole or flag
    if patron == 'engranaje':
        r0 = radio * 0.55
        angulo = math.atan2(dy, dx) if (dx, dy) != (0, 0) else 0
        diente = 1.0 if math.cos(8 * angulo) > 0.2 else 0.0
        radio_borde = r0 + (radio - r0) * diente
        return dist <= radio_borde
    if patron == 'nube':
        c1 = math.sqrt((dx + radio * 0.5) ** 2 + (dy + radio * 0.05) ** 2) <= radio * 0.5
        c2 = math.sqrt(dx * dx + (dy - radio * 0.25) ** 2) <= radio * 0.62
        c3 = math.sqrt((dx - radio * 0.5) ** 2 + (dy + radio * 0.05) ** 2) <= radio * 0.5
        base = abs(dx) <= radio * 0.8 and 0 <= dy <= radio * 0.35
        return (c1 or c2 or c3 or base) and dy <= radio * 0.4
    if patron == 'escudo':
        if dy <= 0:
            return dist <= radio
        return abs(dx) <= radio * (radio - dy) / radio and dy <= radio
    return dist <= radio  # 'circulo' y cualquier valor desconocido caen al círculo relleno


def generar_avatar(patron, color_figura, color_fondo, tamano_px=32):
    resolucion = 12
    centro = (resolucion - 1) / 2
    radio = resolucion / 2 - 1

    img = tk.PhotoImage(width=resolucion, height=resolucion)
    img.put(color_fondo, to=(0, 0, resolucion, resolucion))
    for y in range(resolucion):
        for x in range(resolucion):
            if _es_pixel_avatar(patron, x - centro, y - centro, radio):
                img.put(color_figura, to=(x, y, x + 1, y + 1))

    escala = max(1, round(tamano_px / resolucion))
    return img.zoom(escala, escala)

MASCOTA_ASCII = (
    "  █     █  \n"
    "   █   █   \n"
    "  ███████  \n"
    " ██ ███ ██ \n"
    "███████████\n"
    "█ ███████ █\n"
    "█ █     █ █\n"
    "   █   █   "
)


def reproducir_beep(mencion=False):
    try:
        if sys.platform == 'win32':
            import winsound
            if mencion:
                winsound.PlaySound(r'C:\Windows\Media\Windows Notify Messaging.wav',
                                    winsound.SND_FILENAME | winsound.SND_ASYNC)
            else:
                winsound.PlaySound(r'C:\Windows\Media\Windows Pop-up Blocked.wav',
                                    winsound.SND_FILENAME | winsound.SND_ASYNC)
    except Exception:
        pass


def es_imagen(nombre_archivo):
    extensiones = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')
    return nombre_archivo.lower().endswith(extensiones)


def obtener_iniciales(nombre):
    palabras = nombre.split()
    if len(palabras) > 1:
        return (palabras[0][0] + palabras[-1][0]).upper()
    return nombre[:2].upper()


def crear_icono_mascota(tema, escala=3):
    patron = [
        "  X     X  ",
        "   X   X   ",
        "  XXXXXXX  ",
        " XX XXX XX ",
        "XXXXXXXXXXX",
        "X XXXXXXX X",
        "X X     X X",
        "   X   X   ",
    ]
    filas, columnas = len(patron), len(patron[0])
    img = tk.PhotoImage(width=columnas, height=filas)
    img.put(tema['panel'], to=(0, 0, columnas, filas))
    for y, fila in enumerate(patron):
        for x, caracter in enumerate(fila):
            if caracter == 'X':
                img.put(tema['server'], to=(x, y, x + 1, y + 1))
    return img.zoom(escala, escala)




# PANTALLA DE LOGIN
class LoginFrame(ctk.CTkFrame):
    def __init__(self, master, tema, on_conectar, on_cambiar_tema=None, **kwargs):
        super().__init__(master, fg_color=tema['fondo'], corner_radius=0, **kwargs)
        self.tema = tema
        self.on_conectar = on_conectar
        self.on_cambiar_tema = on_cambiar_tema
        self.labels_secundarios = []
        self.avatar_elegido = 'circulo'
        self.botones_avatar = {}
        self.imagenes_selector = {}
        self.color_elegido = None
        self.botones_color = {}
        self._construir()

    def _construir(self):
        self.scroll = ctk.CTkScrollableFrame(
            self, fg_color=self.tema['fondo'], corner_radius=0,
            scrollbar_button_color=self.tema['borde'], scrollbar_button_hover_color=self.tema['acento']
        )
        self.scroll.pack(fill=tk.BOTH, expand=True)

        self.frame_tarjeta = ctk.CTkFrame(self.scroll, fg_color=self.tema['fondo'], corner_radius=0)
        self.frame_tarjeta.pack(pady=30)

        self.linea_acento = tk.Frame(self.frame_tarjeta, bg=self.tema['acento'], height=4)
        self.linea_acento.pack(fill=tk.X)

        self.frame_central = ctk.CTkFrame(self.frame_tarjeta, fg_color=self.tema['panel'], corner_radius=16)
        self.frame_central.pack(ipadx=40, ipady=32)

        self.switch_tema = ctk.CTkSwitch(
            self.frame_central, text='Tema claro', command=self._on_switch_tema,
            text_color=self.tema['texto_secundario'], font=('Segoe UI', 11),
            progress_color=self.tema['acento']
        )
        self.switch_tema.pack(anchor='e')
        if self.tema['nombre'] == 'claro':
            self.switch_tema.select()

        self.label_mascota = ctk.CTkLabel(
            self.frame_central, text=MASCOTA_ASCII, fg_color='transparent',
            text_color=self.tema['server'],
            font=('Lucida Console', 11, 'bold'), justify=tk.CENTER
        )
        self.label_mascota.pack(pady=(26, 16))

        self.label_titulo_login = ctk.CTkLabel(
            self.frame_central, text='Chat con Sockets', fg_color='transparent',
            text_color=self.tema['texto'], font=('Segoe UI', 26, 'bold')
        )
        self.label_titulo_login.pack(pady=(0, 24))

        campos = [
            ('IP del servidor', '127.0.0.1', 'entry_ip'),
            ('Puerto', '5000', 'entry_puerto'),
            ('Nickname', '', 'entry_nick')
        ]

        self.entries = {}
        for label, default, attr in campos:
            label_campo = ctk.CTkLabel(
                self.frame_central, text=label, fg_color='transparent',
                text_color=self.tema['texto_secundario'],
                font=('Segoe UI', 13), anchor='w'
            )
            label_campo.pack(fill=tk.X, pady=(12, 3))
            self.labels_secundarios.append(label_campo)
            entry = ctk.CTkEntry(
                self.frame_central, width=300, height=40,
                fg_color=self.tema['entrada'], text_color=self.tema['texto'],
                border_color=self.tema['borde'], border_width=1,
                corner_radius=8, font=('Segoe UI', 14)
            )
            entry.insert(0, default)
            entry.pack(fill=tk.X, pady=(0, 5))
            self.entries[attr] = entry

        self.entries['entry_nick'].focus()

        self.boton_conectar = ctk.CTkButton(
            self.frame_central, text='Conectar al chat', command=self._intentar_conectar,
            fg_color=self.tema['acento'], hover_color=self.tema['acento_hover'],
            text_color='white', width=300, height=48, corner_radius=12,
            font=('Segoe UI', 14, 'bold')
        )
        self.boton_conectar.pack(pady=(20, 0))

        self.label_error = ctk.CTkLabel(
            self.frame_central, text='', text_color='#ed4245',
            fg_color='transparent', font=('Segoe UI', 12)
        )
        self.label_error.pack(pady=(10, 0))

        self.label_avatar = ctk.CTkLabel(
            self.frame_central, text='Foto de perfil', fg_color='transparent',
            text_color=self.tema['texto_secundario'],
            font=('Segoe UI', 13), anchor='w'
        )
        self.label_avatar.pack(fill=tk.X, pady=(12, 6))
        self.labels_secundarios.append(self.label_avatar)

        self.frame_avatares = ctk.CTkFrame(self.frame_central, fg_color='transparent')
        self.frame_avatares.pack()

        columnas_avatar = 6
        for indice, patron in enumerate(AVATARES_DISPONIBLES):
            imagen = generar_avatar(
                patron, self.tema['texto_secundario'], self.tema['entrada'], tamano_px=36
            )
            self.imagenes_selector[patron] = imagen
            boton = ctk.CTkButton(
                self.frame_avatares, text='', image=imagen, width=44, height=44,
                corner_radius=22, fg_color=self.tema['entrada'], hover_color=self.tema['borde'],
                border_width=0, border_color=self.tema['acento'],
                command=lambda p=patron: self._elegir_avatar(p)
            )
            fila, columna = divmod(indice, columnas_avatar)
            boton.grid(row=fila, column=columna, padx=3, pady=3)
            self.botones_avatar[patron] = boton

        self._elegir_avatar(self.avatar_elegido)

        self.label_color = ctk.CTkLabel(
            self.frame_central, text='Color de perfil', fg_color='transparent',
            text_color=self.tema['texto_secundario'],
            font=('Segoe UI', 13), anchor='w'
        )
        self.label_color.pack(fill=tk.X, pady=(12, 6))
        self.labels_secundarios.append(self.label_color)

        # Fila única con scroll horizontal -- a diferencia de la grilla de
        # avatares, acá no queremos que los colores salten a una segunda
        # fila por más que se agreguen más adelante.
        self.frame_colores = ctk.CTkScrollableFrame(
            self.frame_central, orientation='horizontal', fg_color='transparent',
            height=48, width=300,
            scrollbar_button_color=self.tema['borde'], scrollbar_button_hover_color=self.tema['acento']
        )
        self.frame_colores.pack(fill=tk.X)

        for color_hex in PALETA_USUARIOS:
            boton = ctk.CTkButton(
                self.frame_colores, text='', width=32, height=32,
                corner_radius=16, fg_color=color_hex, hover_color=color_hex,
                border_width=0, border_color=self.tema['texto'],
                command=lambda c=color_hex: self._elegir_color(c)
            )
            boton.pack(side=tk.LEFT, padx=3, pady=3)
            self.botones_color[color_hex] = boton

        self.label_pie = ctk.CTkLabel(
            self.frame_central, text='Sockets TCP · Sistemas Operativos',
            fg_color='transparent', text_color=self.tema['texto_secundario'],
            font=('Segoe UI', 11)
        )
        self.label_pie.pack(pady=(18, 0))
        self.labels_secundarios.append(self.label_pie)

        self.entries['entry_puerto'].bind('<Return>', lambda e: self._intentar_conectar())
        self.entries['entry_nick'].bind('<Return>', lambda e: self._intentar_conectar())

    def _on_switch_tema(self):
        if self.on_cambiar_tema:
            self.on_cambiar_tema()

    def _elegir_avatar(self, patron):
        self.avatar_elegido = patron
        for p, boton in self.botones_avatar.items():
            if p == patron:
                boton.configure(border_width=3)
            else:
                boton.configure(border_width=0)

    def _elegir_color(self, color_hex):
        self.color_elegido = color_hex
        for c, boton in self.botones_color.items():
            boton.configure(border_width=3 if c == color_hex else 0)

    def _aplicar_tema(self, tema):
        self.tema = tema
        self.configure(fg_color=tema['fondo'])
        self.scroll.configure(
            fg_color=tema['fondo'], scrollbar_button_color=tema['borde'],
            scrollbar_button_hover_color=tema['acento']
        )
        self.frame_tarjeta.configure(fg_color=tema['fondo'])
        self.linea_acento.configure(bg=tema['acento'])
        self.frame_central.configure(fg_color=tema['panel'])
        self.switch_tema.configure(text_color=tema['texto_secundario'], progress_color=tema['acento'])
        self.label_mascota.configure(text_color=tema['server'])
        self.label_titulo_login.configure(text_color=tema['texto'])
        for label_campo in self.labels_secundarios:
            label_campo.configure(text_color=tema['texto_secundario'])
        for entry in self.entries.values():
            entry.configure(fg_color=tema['entrada'], text_color=tema['texto'], border_color=tema['borde'])
        for patron, boton in self.botones_avatar.items():
            imagen = generar_avatar(patron, tema['texto_secundario'], tema['entrada'], tamano_px=36)
            self.imagenes_selector[patron] = imagen
            boton.configure(image=imagen, fg_color=tema['entrada'], hover_color=tema['borde'],
                             border_color=tema['acento'])
        # CTkScrollableFrame.configure() solo recalcula su color de fondo
        # cuando el kwarg 'fg_color' está presente en la llamada (aunque el
        # valor no cambie) -- un cascade genérico de bg_color desde el padre
        # (que sí sirve para CTkFrame/CTkLabel normales) no le hace nada,
        # por eso quedaba con el color del tema viejo al cambiar de modo.
        self.frame_colores.configure(
            fg_color='transparent',
            scrollbar_button_color=tema['borde'], scrollbar_button_hover_color=tema['acento']
        )
        for boton in self.botones_color.values():
            boton.configure(border_color=tema['texto'])
        self.boton_conectar.configure(fg_color=tema['acento'], hover_color=tema['acento_hover'])
        ctk.set_appearance_mode('light' if tema['nombre'] == 'claro' else 'dark')

    def _intentar_conectar(self):
        ip = self.entries['entry_ip'].get().strip() or '127.0.0.1'
        puerto_str = self.entries['entry_puerto'].get().strip() or '5000'
        nickname = self.entries['entry_nick'].get().strip()

        try:
            puerto = int(puerto_str)
        except ValueError:
            self.label_error.configure(text='El puerto debe ser un número.')
            return

        if not nickname:
            self.label_error.configure(text='El nickname no puede estar vacío.')
            return

        color = self.color_elegido or color_usuario(nickname)
        self.on_conectar(ip, puerto, nickname, self.avatar_elegido, color)

    def mostrar_error(self, mensaje):
        self.label_error.configure(text=mensaje)


# PANTALLA DE CHAT
class ChatFrame(ctk.CTkFrame):
    def __init__(self, master, tema, on_desconectar, on_cambiar_tema=None, ip='', puerto=None, **kwargs):
        super().__init__(master, fg_color=tema['fondo'], corner_radius=0, **kwargs)
        self.tema = tema
        self.on_desconectar = on_desconectar
        self.on_cambiar_tema = on_cambiar_tema
        self.ip = ip
        self.puerto = puerto
        self.nickname = ''
        self.conectado = False
        self.sock = None
        self.cola_mensajes = queue.Queue()
        self.hilo_escucha = None
        self.ultimo_typing = 0
        self.imagenes = []  # Referencias para evitar que se borren
        self.avatares_usuarios = {}  # nickname -> patron de avatar elegido
        self.colores_usuarios = {}  # nickname -> color de perfil elegido (hex)
        self.cache_avatares = {}  # (nickname, patron, tamano) -> PhotoImage generado
        self.usuarios_actuales = []  # últimos nicknames conectados recibidos
        self.grupos = {}  # nombre -> {'miembros': [...], 'creador': .., 'avatar': ..}
        self.sala_actual = 'General'
        self.salas = {'General': 0}
        self.estados_mensajes = {}  # id -> pending/ack/delivered/read/error
        self.ids_mensajes_vistos = set()
        self.lecturas_pendientes = {}  # id -> contexto del mensaje
        self.eventos_chat = []  # registro de cada burbuja mostrada, para poder re-dibujar el chat completo
        self.reacciones_por_mensaje = {}  # id_mensaje -> {emoji: set(nicknames)}
        self._marca_agua_presente = False
        self._historial_mostrado = False

        self._construir()
        self._procesar_cola()

    def _construir(self):
        # Barra superior
        self.frame_superior = tk.Frame(self, bg=self.tema['panel'], height=50)
        self.frame_superior.pack(fill=tk.X)
        self.frame_superior.pack_propagate(False)

        self.label_titulo = ctk.CTkLabel(
            self.frame_superior, text='👾 Chat con Sockets', fg_color='transparent',
            text_color=self.tema['texto'], font=('Segoe UI', 16, 'bold')
        )
        self.label_titulo.pack(side=tk.LEFT, padx=15, pady=10)

        self.boton_buscar = ctk.CTkButton(
            self.frame_superior, text='🔍 Buscar', command=self._mostrar_busqueda,
            fg_color=self.tema['entrada'], hover_color=self.tema['borde'],
            text_color=self.tema['texto'], width=120, height=36,
            corner_radius=12, font=('Segoe UI', 14)
        )
        self.boton_buscar.pack(side=tk.RIGHT, padx=5, pady=6)

        self.switch_tema = ctk.CTkSwitch(
            self.frame_superior, text='Claro', command=self._on_switch_tema,
            text_color=self.tema['texto_secundario'], font=('Segoe UI', 11),
            progress_color=self.tema['acento']
        )
        self.switch_tema.pack(side=tk.RIGHT, padx=5, pady=6)
        if self.tema['nombre'] == 'claro':
            self.switch_tema.select()

        self.boton_desconectar = ctk.CTkButton(
            self.frame_superior, text='Desconectar', command=self.on_desconectar,
            fg_color='#ed4245', hover_color='#c93537', text_color='white',
            width=130, height=36, corner_radius=12, font=('Segoe UI', 14, 'bold')
        )
        self.boton_desconectar.pack(side=tk.RIGHT, padx=15, pady=6)

        # Línea de acento decorativa bajo la barra superior
        self.linea_acento_superior = tk.Frame(self, bg=self.tema['acento'], height=2)
        self.linea_acento_superior.pack(fill=tk.X)

        # Panel de búsqueda (oculto inicialmente)
        self.frame_busqueda = tk.Frame(self, bg=self.tema['fondo'])
        self.entry_busqueda = ctk.CTkEntry(
            self.frame_busqueda, fg_color=self.tema['entrada'], text_color=self.tema['texto'],
            border_color=self.tema['borde'], border_width=1,
            corner_radius=8, font=('Segoe UI', 13)
        )
        self.entry_busqueda.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        self.entry_busqueda.bind('<KeyRelease>', lambda e: self._buscar())
        ctk.CTkButton(
            self.frame_busqueda, text='Cerrar', command=self._ocultar_busqueda,
            fg_color=self.tema['entrada'], hover_color=self.tema['borde'],
            text_color=self.tema['texto'], width=80, height=28,
            corner_radius=8, font=('Segoe UI', 13)
        ).pack(side=tk.RIGHT, padx=5)

        # Área central: chat + usuarios
        # Nota: el pack() de este frame se hace al final de _construir(),
        # después de empaquetar toda la barra inferior/estado/typing.
        # Así esos elementos de tamaño fijo reservan su espacio primero y
        # solo el área de chat se encoge si la ventana queda chica
        # (si no, el pack de Tk reparte el espacio en orden de llamada y
        # el frame con expand=True se queda con todo, empujando la barra
        # de envío fuera de la ventana visible).
        self.frame_central = tk.Frame(self, bg=self.tema['fondo'])

        # Panel de usuarios (se crea antes que el área de chat para que Tk
        # no corrompa el primer carácter del título al dibujarlo después
        # del widget Text con scrollbar)
        self.frame_usuarios = tk.Frame(self.frame_central, bg=self.tema['panel'], width=340)
        self.frame_usuarios.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=10)
        self.frame_usuarios.pack_propagate(False)

        self.frame_salas_header = ctk.CTkFrame(
            self.frame_usuarios, fg_color='transparent'
        )
        self.frame_salas_header.pack(
            fill=tk.X, padx=12, pady=(15, 4)
        )

        self.label_salas = ctk.CTkLabel(
            self.frame_salas_header, text='SALAS',
            fg_color='transparent',
            text_color=self.tema['texto_secundario'],
            font=('Segoe UI', 13, 'bold')
        )
        self.label_salas.pack(side=tk.LEFT)

        self.boton_crear_sala = ctk.CTkButton(
            self.frame_salas_header, text='＋ Crear',
            width=60, height=22,
            fg_color='transparent',
            hover_color=self.tema['borde'],
            text_color=self.tema['acento'],
            font=('Segoe UI', 12, 'bold'),
            corner_radius=6,
            command=self._mostrar_crear_sala
        )
        self.boton_crear_sala.pack(side=tk.RIGHT)

        self.combo_salas = ctk.CTkComboBox(
            self.frame_usuarios,
            values=['General'],
            state='readonly',
            fg_color=self.tema['entrada'],
            text_color=self.tema['texto'],
            border_color=self.tema['borde'],
            button_color=self.tema['borde'],
            button_hover_color=self.tema['acento'],
            dropdown_fg_color=self.tema['entrada'],
            dropdown_text_color=self.tema['texto'],
            font=('Segoe UI', 13),
            command=self._seleccionar_sala
        )
        self.combo_salas.set('General')
        self.combo_salas.pack(
            fill=tk.X, padx=12, pady=(0, 5)
        )

        self.boton_chat_general = ctk.CTkButton(
            self.frame_usuarios, text='↩ Volver a General',
            anchor='w',
            fg_color=self.tema['entrada'],
            hover_color=self.tema['borde'],
            text_color=self.tema['texto'],
            font=('Segoe UI', 13),
            corner_radius=8, height=30,
            command=self._ir_a_chat_general
        )
        self.boton_chat_general.pack(
            fill=tk.X, padx=12, pady=(0, 5)
        )

        self.label_usuarios = ctk.CTkLabel(
            self.frame_usuarios, text='USUARIOS EN LÍNEA', fg_color='transparent',
            text_color=self.tema['texto_secundario'], font=('Segoe UI', 13, 'bold')
        )
        self.label_usuarios.pack(anchor='w', padx=12, pady=(12, 5))

        self.lista_usuarios = ctk.CTkScrollableFrame(
            self.frame_usuarios, fg_color=self.tema['panel'], corner_radius=0
        )
        self.lista_usuarios.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.frame_grupos_header = ctk.CTkFrame(self.frame_usuarios, fg_color='transparent')
        self.frame_grupos_header.pack(fill=tk.X, padx=12, pady=(10, 0))
        self.label_grupos = ctk.CTkLabel(
            self.frame_grupos_header, text='GRUPOS', fg_color='transparent',
            text_color=self.tema['texto_secundario'], font=('Segoe UI', 13, 'bold')
        )
        self.label_grupos.pack(side=tk.LEFT)
        self.boton_crear_grupo = ctk.CTkButton(
            self.frame_grupos_header, text='＋ Crear', width=60, height=22,
            fg_color='transparent', hover_color=self.tema['borde'],
            text_color=self.tema['acento'], font=('Segoe UI', 12, 'bold'),
            corner_radius=6, command=self._mostrar_crear_grupo
        )
        self.boton_crear_grupo.pack(side=tk.RIGHT)

        self.lista_grupos = ctk.CTkScrollableFrame(
            self.frame_usuarios, fg_color=self.tema['panel'], corner_radius=0
        )
        self.lista_grupos.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Área de chat
        self.frame_chat = tk.Frame(self.frame_central, bg=self.tema['fondo'])
        self.frame_chat.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.area_chat = ctk.CTkTextbox(
            self.frame_chat, wrap=tk.WORD, state=tk.DISABLED,
            fg_color=self.tema['fondo'], text_color=self.tema['texto'],
            font=('Segoe UI', 14), padx=10, pady=10,
            spacing1=2, spacing3=2,
            corner_radius=8, border_width=1, border_color=self.tema['borde']
        )
        self.area_chat.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # El label de "escribiendo..." se crea aquí (para tener la
        # referencia disponible) pero se empaqueta más abajo, después de
        # toda la barra inferior, para que quede pegado justo encima de
        # ella en la pila de widgets "bottom" (ver comentario junto al
        # pack final de frame_central).
        self.label_typing = ctk.CTkLabel(
            self, text='', fg_color='transparent', text_color=self.tema['texto_secundario'],
            font=('Segoe UI', 13, 'italic'), anchor='w'
        )

        # Barra de estado de conexión
        self.frame_estado = tk.Frame(self, bg=self.tema['panel'])
        self.frame_estado.pack(fill=tk.X, side=tk.BOTTOM)

        texto_estado = f'● Conectado a {self.ip}:{self.puerto}' if self.ip else ''
        self.label_estado = ctk.CTkLabel(
            self.frame_estado, text=texto_estado, fg_color='transparent',
            text_color=self.tema['online'], font=('Segoe UI', 12), anchor='w'
        )
        self.label_estado.pack(side=tk.LEFT, padx=12, ipady=3)

        self.label_creditos = ctk.CTkLabel(
            self.frame_estado, text='Sockets TCP · Sistemas Operativos', fg_color='transparent',
            text_color=self.tema['texto_secundario'], font=('Segoe UI', 12), anchor='e'
        )
        self.label_creditos.pack(side=tk.RIGHT, padx=12, ipady=3)

        self.label_tip_reaccion = ctk.CTkLabel(
            self.frame_estado, text='💡 Click derecho en un mensaje para reaccionar',
            fg_color='transparent', text_color=self.tema['texto_secundario'],
            font=('Segoe UI', 11, 'italic')
        )
        self.label_tip_reaccion.pack(side=tk.LEFT, expand=True, ipady=3)

        # Barra inferior de entrada
        self.frame_inferior = tk.Frame(self, bg=self.tema['panel'], padx=10, pady=10)
        self.frame_inferior.pack(fill=tk.X, side=tk.BOTTOM)

        # Línea de acento decorativa sobre la barra de envío (simétrica a la de arriba)
        self.linea_acento_inferior = tk.Frame(self, bg=self.tema['acento'], height=2)
        self.linea_acento_inferior.pack(fill=tk.X, side=tk.BOTTOM)

        self.entry_mensaje = ctk.CTkEntry(
            self.frame_inferior, fg_color=self.tema['entrada'], text_color=self.tema['texto'],
            border_color=self.tema['borde'], border_width=1,
            corner_radius=8, font=('Segoe UI', 15), height=40
        )
        self.entry_mensaje.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.entry_mensaje.bind('<Return>', lambda e: self._enviar_mensaje())
        self.entry_mensaje.bind('<KeyRelease>', self._on_typing)

        self.label_para = ctk.CTkLabel(
            self.frame_inferior, text='Para:', fg_color='transparent',
            text_color=self.tema['texto_secundario'], font=('Segoe UI', 14)
        )
        self.label_para.pack(side=tk.LEFT)

        self.combo_destinatario = ctk.CTkComboBox(
            self.frame_inferior, values=['Todos'], state='readonly', width=140,
            fg_color=self.tema['entrada'], text_color=self.tema['texto'],
            border_color=self.tema['borde'], button_color=self.tema['borde'],
            button_hover_color=self.tema['acento'],
            dropdown_fg_color=self.tema['entrada'], dropdown_text_color=self.tema['texto'],
            font=('Segoe UI', 14), command=self._cambiar_vista
        )
        self.combo_destinatario.set('Todos')
        self.combo_destinatario.pack(side=tk.LEFT, padx=5)

        self.boton_archivo = ctk.CTkButton(
            self.frame_inferior, text='📎', command=self._enviar_archivo,
            fg_color=self.tema['entrada'], hover_color=self.tema['borde'],
            text_color=self.tema['texto'], width=44, height=40,
            corner_radius=10, font=('Segoe UI', 17)
        )
        self.boton_archivo.pack(side=tk.LEFT, padx=5)

        self.boton_emoji = ctk.CTkButton(
            self.frame_inferior, text='😊', command=self._mostrar_selector_emoji,
            fg_color=self.tema['entrada'], hover_color=self.tema['borde'],
            text_color=self.tema['texto'], width=44, height=40,
            corner_radius=10, font=('Segoe UI', 17)
        )
        self.boton_emoji.pack(side=tk.LEFT, padx=5)

        self.boton_enviar = ctk.CTkButton(
            self.frame_inferior, text='Enviar', command=self._enviar_mensaje,
            fg_color=self.tema['acento'], hover_color=self.tema['acento_hover'],
            text_color='white', width=100, height=40,
            corner_radius=12, font=('Segoe UI', 14, 'bold')
        )
        self.boton_enviar.pack(side=tk.LEFT, padx=5)

        # El typing se empaqueta ahora, como último elemento del lado
        # "bottom", para que quede justo encima de la barra inferior.
        self.label_typing.pack(fill=tk.X, padx=15, side=tk.BOTTOM)

        # Recién ahora se empaqueta el área central (chat + usuarios), al
        # final de todo, para que la barra inferior y el resto del
        # "chrome" fijo ya tengan su espacio reservado en la ventana. Si
        # se empaqueta antes (como estaba originalmente), Tk le da su
        # tamaño natural de una vez y los widgets empaquetados después
        # pueden quedarse sin espacio y no mostrarse cuando la ventana es
        # más chica que el tamaño "ideal" (ver bug de los botones
        # inferiores invisibles).
        self.frame_central.pack(fill=tk.BOTH, expand=True)

        self._configurar_tags()
        self._mostrar_marca_agua()

    def _on_switch_tema(self):
        if self.on_cambiar_tema:
            self.on_cambiar_tema()

    def _aplicar_tema(self, tema):
        self.tema = tema
        self.configure(fg_color=tema['fondo'])
        self.frame_superior.configure(bg=tema['panel'])
        self.label_titulo.configure(text_color=tema['texto'])
        self.boton_buscar.configure(fg_color=tema['entrada'], hover_color=tema['borde'], text_color=tema['texto'])
        self.switch_tema.configure(text_color=tema['texto_secundario'], progress_color=tema['acento'])
        self.linea_acento_superior.configure(bg=tema['acento'])
        self.linea_acento_inferior.configure(bg=tema['acento'])
        self.frame_busqueda.configure(bg=tema['fondo'])
        self.entry_busqueda.configure(fg_color=tema['entrada'], text_color=tema['texto'], border_color=tema['borde'])
        self.frame_central.configure(bg=tema['fondo'])
        self.frame_usuarios.configure(bg=tema['panel'])
        self.frame_salas_header.configure(bg_color=tema['panel'])
        self.label_salas.configure(
            bg_color=tema['panel'],
            text_color=tema['texto_secundario']
        )
        self.boton_crear_sala.configure(
            bg_color=tema['panel'],
            hover_color=tema['borde'],
            text_color=tema['acento']
        )
        self.combo_salas.configure(
            fg_color=tema['entrada'],
            text_color=tema['texto'],
            border_color=tema['borde'],
            button_color=tema['borde'],
            button_hover_color=tema['acento'],
            dropdown_fg_color=tema['entrada'],
            dropdown_text_color=tema['texto']
        )
        self.boton_chat_general.configure(
            fg_color=tema['entrada'],
            hover_color=tema['borde'],
            text_color=tema['texto']
        )
        # label_usuarios y frame_grupos_header tienen fg_color='transparent', lo que
        # internamente los pinta con su propio bg_color en vez de ser realmente
        # invisibles. Como su padre (frame_usuarios) es un tk.Frame común y no un
        # widget CTk, el mecanismo automático de CTk que propaga bg_color desde el
        # padre solo engancha si se llama a master.config() -- acá se usa .configure()
        # en todos lados, así que nunca se dispara y quedan con el color del tema
        # viejo. Hay que fijarles el bg_color a mano en cada cambio de tema.
        self.label_usuarios.configure(bg_color=tema['panel'], text_color=tema['texto_secundario'])
        self.lista_usuarios.configure(fg_color=tema['panel'])
        self.frame_grupos_header.configure(bg_color=tema['panel'])
        self.label_grupos.configure(bg_color=tema['panel'], text_color=tema['texto_secundario'])
        self.boton_crear_grupo.configure(bg_color=tema['panel'], hover_color=tema['borde'], text_color=tema['acento'])
        self.lista_grupos.configure(fg_color=tema['panel'])
        self.frame_chat.configure(bg=tema['fondo'])
        self.area_chat.configure(fg_color=tema['fondo'], text_color=tema['texto'], border_color=tema['borde'])
        self.label_typing.configure(text_color=tema['texto_secundario'])
        self.frame_estado.configure(bg=tema['panel'])
        self.label_estado.configure(text_color=tema['online'])
        self.label_creditos.configure(text_color=tema['texto_secundario'])
        self.label_tip_reaccion.configure(text_color=tema['texto_secundario'])
        self.frame_inferior.configure(bg=tema['panel'])
        self.entry_mensaje.configure(fg_color=tema['entrada'], text_color=tema['texto'], border_color=tema['borde'])
        self.label_para.configure(text_color=tema['texto_secundario'])
        self.combo_destinatario.configure(
            fg_color=tema['entrada'], text_color=tema['texto'],
            border_color=tema['borde'], button_color=tema['borde'],
            button_hover_color=tema['acento'],
            dropdown_fg_color=tema['entrada'], dropdown_text_color=tema['texto']
        )
        self.boton_archivo.configure(fg_color=tema['entrada'], hover_color=tema['borde'], text_color=tema['texto'])
        self.boton_emoji.configure(fg_color=tema['entrada'], hover_color=tema['borde'], text_color=tema['texto'])
        self.boton_enviar.configure(fg_color=tema['acento'], hover_color=tema['acento_hover'])

        self._configurar_tags()
        self.cache_avatares.clear()
        self._actualizar_usuarios(self.usuarios_actuales)
        self._actualizar_grupos()
        # Las burbujas ya insertadas en el chat tienen imágenes de avatar
        # embebidas (image_create) que apuntan a los PhotoImage que se
        # acaban de limpiar de cache_avatares -- sin este redibujado,
        # esas referencias quedan colgando (se recolectan como basura) y
        # las fotos de perfil ya mostradas en el chat desaparecen.
        self._redibujar_chat()

        ctk.set_appearance_mode('light' if tema['nombre'] == 'claro' else 'dark')

    def _configurar_tags(self):
        t = self.tema
        # CTkTextbox.tag_config() prohíbe el kwarg 'font' (lo bloquea por
        # incompatibilidad con su escalado de UI). Para poder seguir fijando
        # fuente por tag como antes, se usa el tkinter.Text real que
        # CTkTextbox envuelve internamente en self._textbox.
        tags = self.area_chat._textbox

        # Texto genérico
        tags.tag_config('hora', foreground=t['texto_secundario'], font=('Segoe UI', 13))
        tags.tag_config('historial_texto', foreground=t['historial'], font=('Segoe UI', 14, 'italic'))
        tags.tag_config('busqueda', background=t['busqueda'], foreground='black')
        tags.tag_config(
            'divisor', foreground=t['texto_secundario'], font=('Segoe UI', 13, 'italic'),
            justify=tk.CENTER
        )
        tags.tag_config(
            'marca_agua', foreground=t['historial'], font=('Lucida Console', 13),
            justify=tk.CENTER
        )
        tags.tag_config(
            'marca_agua_texto', foreground=t['texto_secundario'], font=('Segoe UI', 14, 'italic'),
            justify=tk.CENTER
        )
        tags.tag_config(
            'server_texto', foreground=t['server'], background=t['server_fondo'],
            font=('Segoe UI', 15), justify=tk.CENTER
        )

        # Burbujas: nombre / texto / hora por tipo de mensaje, con fondo propio
        fondos = {
            'propio': t['propio_fondo'], 'otro': t['otros_fondo'],
            'privado': t['privado_fondo'], 'archivo': t['archivo_fondo'],
            'mencion': t['mencion_fondo'], 'grupo': t['grupo_fondo']
        }
        colores_nombre = {
            'propio': t['propio'], 'otro': t['texto'],
            'privado': t['texto'], 'archivo': t['texto'],
            'mencion': t['mencion'], 'grupo': t['grupo']
        }
        colores_texto = {
            'propio': t['propio'], 'otro': t['texto'],
            'privado': t['privado'], 'archivo': t['archivo'],
            'mencion': t['mencion'], 'grupo': t['grupo']
        }
        for clave, fondo in fondos.items():
            tags.tag_config(
                f'nombre_{clave}', foreground=colores_nombre[clave], background=fondo,
                font=('Segoe UI', 15, 'bold')
            )
            tags.tag_config(
                f'{clave}_texto', foreground=colores_texto[clave], background=fondo,
                font=('Segoe UI', 15)
            )
            tags.tag_config(
                f'hora_{clave}', foreground=t['texto_secundario'], background=fondo,
                font=('Segoe UI', 13)
            )

        # Mensajes propios alineados a la derecha
        tags.tag_config('derecha', justify=tk.RIGHT)

    def _obtener_avatar(self, nickname, tamano):
        patron = self.avatares_usuarios.get(nickname, 'circulo')
        color = self.colores_usuarios.get(nickname) or color_usuario(nickname)
        clave = (nickname, patron, tamano, color)
        if clave not in self.cache_avatares:
            self.cache_avatares[clave] = generar_avatar(
                patron, color, self.tema['panel'], tamano_px=tamano
            )
        return self.cache_avatares[clave]

    def _obtener_avatar_grupo(self, nombre_grupo, tamano):
        patron = self.grupos.get(nombre_grupo, {}).get('avatar', 'gente')
        clave = (nombre_grupo, patron, tamano)
        if clave not in self.cache_avatares:
            self.cache_avatares[clave] = generar_avatar(
                patron, color_usuario(nombre_grupo), self.tema['panel'], tamano_px=tamano
            )
        return self.cache_avatares[clave]

    def _mostrar_marca_agua(self):
        self.area_chat.configure(state=tk.NORMAL)
        self.area_chat.delete('1.0', tk.END)
        self.area_chat.insert(tk.END, '\n' * 3)
        for fila in MASCOTA_ASCII.split('\n'):
            self.area_chat.insert(tk.END, fila + '\n', 'marca_agua')
        self.area_chat.insert(tk.END, '\n')
        self.area_chat.insert(tk.END, 'Aún no hay mensajes en este chat\n', 'marca_agua_texto')
        self.area_chat.configure(state=tk.DISABLED)
        self._marca_agua_presente = True

    def _limpiar_marca_agua(self):
        if self._marca_agua_presente:
            self.area_chat.delete('1.0', tk.END)
            self._marca_agua_presente = False

    def _mostrar_busqueda(self):
        self.frame_busqueda.pack(fill=tk.X, before=self.frame_central)
        self.entry_busqueda.focus()

    def _ocultar_busqueda(self):
        self.frame_busqueda.pack_forget()
        self.entry_busqueda.delete(0, tk.END)
        self._quitar_resaltado_busqueda()

    def _mostrar_selector_emoji(self):
        ventana = ctk.CTkToplevel(self)
        ventana.title('Emojis')
        ventana.geometry('280x220')
        ventana.resizable(False, False)
        ventana.configure(fg_color=self.tema['panel'])
        ventana.transient(self.winfo_toplevel())

        columnas = 8
        for i, emoji in enumerate(EMOJIS_COMUNES):
            fila, columna = divmod(i, columnas)
            ctk.CTkButton(
                ventana, text=emoji, width=30, height=30, corner_radius=6,
                fg_color='transparent', hover_color=self.tema['borde'],
                text_color=self.tema['texto'], font=('Segoe UI', 14),
                command=lambda e=emoji, v=ventana: self._insertar_emoji(e, v)
            ).grid(row=fila, column=columna, padx=2, pady=2)

    def _insertar_emoji(self, emoji, ventana):
        self.entry_mensaje.insert(tk.INSERT, emoji)
        ventana.destroy()
        self.entry_mensaje.focus()

    def _mostrar_crear_sala(self):
        ventana = ctk.CTkToplevel(self)
        ventana.title('Crear sala')
        ventana.resizable(False, False)
        ventana.configure(fg_color=self.tema['panel'])
        ventana.transient(self.winfo_toplevel())

        ctk.CTkLabel(
            ventana,
            text='Nombre de la nueva sala',
            text_color=self.tema['texto_secundario'],
            font=('Segoe UI', 12),
            anchor='w'
        ).pack(fill=tk.X, padx=16, pady=(16, 4))

        entry_nombre = ctk.CTkEntry(
            ventana,
            width=300,
            fg_color=self.tema['entrada'],
            text_color=self.tema['texto'],
            border_color=self.tema['borde'],
            border_width=1,
            corner_radius=8,
            font=('Segoe UI', 14)
        )
        entry_nombre.pack(fill=tk.X, padx=16)
        entry_nombre.focus()

        label_error = ctk.CTkLabel(
            ventana,
            text='',
            text_color='#ed4245',
            font=('Segoe UI', 11)
        )
        label_error.pack(pady=(6, 0))

        def confirmar():
            nombre = entry_nombre.get().strip()
            if not nombre:
                label_error.configure(
                    text='Escribe un nombre para la sala.'
                )
                return
            crear_sala(self.sock, nombre)
            ventana.destroy()

        ctk.CTkButton(
            ventana,
            text='Crear y entrar',
            command=confirmar,
            fg_color=self.tema['acento'],
            hover_color=self.tema['acento_hover'],
            text_color='white',
            height=36,
            corner_radius=8,
            font=('Segoe UI', 13, 'bold')
        ).pack(fill=tk.X, padx=16, pady=(10, 16))

        entry_nombre.bind(
            '<Return>', lambda _evento: confirmar()
        )

    def _seleccionar_sala(self, nombre_sala):
        if (
            not self.conectado
            or not nombre_sala
            or nombre_sala == self.sala_actual
        ):
            return
        unirse_sala(self.sock, nombre_sala)

    def _actualizar_salas(self, elementos, sala_actual=None):
        self.salas = {
            item.get('nombre'): item.get('usuarios', 0)
            for item in elementos
            if item.get('nombre')
        }
        if not self.salas:
            self.salas = {'General': 0}

        valores = list(self.salas.keys())
        self.combo_salas.configure(values=valores)

        if sala_actual:
            self.sala_actual = sala_actual
        if self.sala_actual not in self.salas:
            self.sala_actual = 'General'
        self.combo_salas.set(self.sala_actual)
        self._actualizar_titulo_vista()

    def _mostrar_crear_grupo(self):
        if not any(u != self.nickname for u in self.usuarios_actuales):
            messagebox.showinfo('Crear grupo', 'No hay otros usuarios conectados para invitar.')
            return

        ventana = ctk.CTkToplevel(self)
        ventana.title('Crear grupo')
        ventana.resizable(False, False)
        ventana.configure(fg_color=self.tema['panel'])
        ventana.transient(self.winfo_toplevel())

        ctk.CTkLabel(
            ventana, text='Nombre del grupo', text_color=self.tema['texto_secundario'],
            font=('Segoe UI', 12), anchor='w'
        ).pack(fill=tk.X, padx=16, pady=(14, 2))
        entry_nombre = ctk.CTkEntry(
            ventana, width=300, fg_color=self.tema['entrada'], text_color=self.tema['texto'],
            border_color=self.tema['borde'], border_width=1, corner_radius=8, font=('Segoe UI', 14)
        )
        entry_nombre.pack(fill=tk.X, padx=16)
        entry_nombre.focus()

        ctk.CTkLabel(
            ventana, text='Ícono', text_color=self.tema['texto_secundario'],
            font=('Segoe UI', 12), anchor='w'
        ).pack(fill=tk.X, padx=16, pady=(12, 2))
        frame_iconos = ctk.CTkFrame(ventana, fg_color='transparent')
        frame_iconos.pack(padx=16)

        estado = {'avatar': AVATARES_GRUPO_DISPONIBLES[0]}
        botones_icono = {}

        def elegir_icono(patron):
            estado['avatar'] = patron
            for p, b in botones_icono.items():
                b.configure(border_width=3 if p == patron else 0)

        for i, patron in enumerate(AVATARES_GRUPO_DISPONIBLES):
            img = generar_avatar(patron, self.tema['texto_secundario'], self.tema['entrada'], tamano_px=32)
            boton = ctk.CTkButton(
                frame_iconos, text='', image=img, width=38, height=38, corner_radius=19,
                fg_color=self.tema['entrada'], hover_color=self.tema['borde'],
                border_width=0, border_color=self.tema['acento'],
                command=lambda p=patron: elegir_icono(p)
            )
            boton.grid(row=0, column=i, padx=3)
            botones_icono[patron] = boton
        elegir_icono(estado['avatar'])

        ctk.CTkLabel(
            ventana, text='Invitar a', text_color=self.tema['texto_secundario'],
            font=('Segoe UI', 12), anchor='w'
        ).pack(fill=tk.X, padx=16, pady=(12, 2))
        frame_checks = ctk.CTkScrollableFrame(ventana, width=300, fg_color=self.tema['entrada'], height=130)
        frame_checks.pack(fill=tk.X, padx=16)

        checks = {}
        for u in self.usuarios_actuales:
            if u == self.nickname:
                continue
            var = tk.BooleanVar(value=False)
            ctk.CTkCheckBox(
                frame_checks, text=u, variable=var, text_color=self.tema['texto'],
                fg_color=self.tema['acento'], font=('Segoe UI', 13)
            ).pack(anchor='w', pady=2)
            checks[u] = var

        label_error = ctk.CTkLabel(ventana, text='', text_color='#ed4245', font=('Segoe UI', 11))
        label_error.pack(pady=(6, 0))

        def confirmar():
            nombre = entry_nombre.get().strip()
            miembros = [u for u, var in checks.items() if var.get()]
            if not nombre:
                label_error.configure(text='Poné un nombre para el grupo.')
                return
            if not miembros:
                label_error.configure(text='Elegí al menos un miembro.')
                return
            crear_grupo(self.sock, nombre, miembros, estado['avatar'])
            ventana.destroy()

        ctk.CTkButton(
            ventana, text='Crear', command=confirmar,
            fg_color=self.tema['acento'], hover_color=self.tema['acento_hover'],
            text_color='white', height=36, corner_radius=8, font=('Segoe UI', 13, 'bold')
        ).pack(fill=tk.X, padx=16, pady=(10, 16))

    def _mostrar_invitar_grupo(self, nombre_grupo):
        info = self.grupos.get(nombre_grupo)
        if not info:
            return
        candidatos = [
            u for u in self.usuarios_actuales
            if u != self.nickname and u not in info['miembros']
        ]
        if not candidatos:
            messagebox.showinfo('Invitar', 'No hay usuarios conectados para invitar a este grupo.')
            return

        ventana = ctk.CTkToplevel(self)
        ventana.title(f'Invitar a {nombre_grupo}')
        ventana.resizable(False, False)
        ventana.configure(fg_color=self.tema['panel'])
        ventana.transient(self.winfo_toplevel())

        ctk.CTkLabel(
            ventana, text=f'Invitar a "{nombre_grupo}"', text_color=self.tema['texto'],
            font=('Segoe UI', 14, 'bold')
        ).pack(padx=16, pady=(16, 8))

        frame_checks = ctk.CTkScrollableFrame(ventana, width=260, fg_color=self.tema['entrada'], height=170)
        frame_checks.pack(fill=tk.X, padx=16)

        checks = {}
        for u in candidatos:
            var = tk.BooleanVar(value=False)
            ctk.CTkCheckBox(
                frame_checks, text=u, variable=var, text_color=self.tema['texto'],
                fg_color=self.tema['acento'], font=('Segoe UI', 13)
            ).pack(anchor='w', pady=2)
            checks[u] = var

        label_error = ctk.CTkLabel(ventana, text='', text_color='#ed4245', font=('Segoe UI', 11))
        label_error.pack(pady=(6, 0))

        def confirmar():
            miembros = [u for u, var in checks.items() if var.get()]
            if not miembros:
                label_error.configure(text='Elegí al menos un usuario.')
                return
            invitar_a_grupo(self.sock, nombre_grupo, miembros)
            ventana.destroy()

        ctk.CTkButton(
            ventana, text='Invitar', command=confirmar,
            fg_color=self.tema['acento'], hover_color=self.tema['acento_hover'],
            text_color='white', height=36, corner_radius=8, font=('Segoe UI', 13, 'bold')
        ).pack(fill=tk.X, padx=16, pady=(10, 16))

    def _mostrar_selector_reaccion(self, event, id_mensaje):
        if not self.conectado:
            return
        ventana = ctk.CTkToplevel(self)
        ventana.title('Reaccionar')
        ventana.resizable(False, False)
        ventana.configure(fg_color=self.tema['panel'])
        ventana.geometry(f'+{event.x_root}+{event.y_root}')
        ventana.transient(self.winfo_toplevel())

        for i, emoji in enumerate(REACCIONES_RAPIDAS):
            ctk.CTkButton(
                ventana, text=emoji, width=32, height=32, corner_radius=6,
                fg_color='transparent', hover_color=self.tema['borde'],
                text_color=self.tema['texto'], font=('Segoe UI', 14),
                command=lambda e=emoji, v=ventana: self._enviar_reaccion(id_mensaje, e, v)
            ).grid(row=0, column=i, padx=2, pady=2)

    def _enviar_reaccion(self, id_mensaje, emoji, ventana):
        ventana.destroy()
        try:
            enviar_reaccion(self.sock, id_mensaje, emoji)
        except Exception:
            pass

    def _buscar(self):
        self._quitar_resaltado_busqueda()
        texto = self.entry_busqueda.get().strip().lower()
        if not texto:
            return
        self.area_chat.configure(state=tk.NORMAL)
        inicio = '1.0'
        while True:
            pos = self.area_chat.search(texto, inicio, tk.END, nocase=1)
            if not pos:
                break
            fin = f'{pos}+{len(texto)}c'
            self.area_chat.tag_add('busqueda', pos, fin)
            inicio = fin
        self.area_chat.configure(state=tk.DISABLED)

    def _quitar_resaltado_busqueda(self):
        self.area_chat.tag_remove('busqueda', '1.0', tk.END)

    def _seleccionar_usuario(self, usuario):
        if usuario == self.nickname:
            return
        self.combo_destinatario.set('Todos')
        self._cambiar_vista()
        texto_actual = self.entry_mensaje.get()
        if texto_actual and not texto_actual.endswith(' '):
            texto_actual += ' '
        self.entry_mensaje.delete(0, tk.END)
        self.entry_mensaje.insert(0, f'{texto_actual}@{usuario} ')
        self.entry_mensaje.focus()
        self.entry_mensaje.icursor(tk.END)

    def _on_typing(self, event):
        if not self.conectado:
            return
        ahora = time.time()
        if ahora - self.ultimo_typing > 2:
            self.ultimo_typing = ahora
            destinatario = self._destinatario_protocolo()
            if destinatario.startswith('Grupo: '):
                return  # el servidor no soporta "escribiendo..." para grupos todavía
            try:
                enviar_typing(self.sock, destinatario)
            except Exception:
                pass

    def _evento_visible(self, evento, vista):
        if evento['tipo'] == 'grupo':
            return vista == f'Grupo: {evento["grupo"]}'

        if vista.startswith('Grupo: '):
            return False

        if evento.get('sala'):
            return evento['sala'] == self.sala_actual

        return True

    def _texto_estado(self, id_mensaje):
        estado = self.estados_mensajes.get(
            id_mensaje, 'pending'
        )
        return {
            'pending': 'Enviando…',
            'ack': '✓ Recibido por el servidor',
            'delivered': '✓✓ Entregado',
            'read': '✓✓ Leído',
            'error': '✗ No enviado',
        }.get(estado, '')

    def _agregar_burbuja(
        self, emisor, contenido, hora, tipo='msg',
        alinear='izquierda', extra='', id_mensaje=None,
        grupo=None, sala=None, historico=False,
        destinatario=None
    ):
        evento = {
            'emisor': emisor,
            'contenido': contenido,
            'hora': hora,
            'tipo': tipo,
            'extra': extra,
            'id_mensaje': id_mensaje,
            'grupo': grupo,
            'sala': sala,
            'historico': historico,
            'destinatario': destinatario,
        }
        self.eventos_chat.append(evento)

        if not self._evento_visible(
            evento, self.combo_destinatario.get()
        ):
            return False

        reacciones_texto = ''
        if id_mensaje is not None:
            reacciones = self.reacciones_por_mensaje.get(
                id_mensaje
            )
            if reacciones:
                reacciones_texto = '  '.join(
                    f'{emoji} {len(nicks)}'
                    for emoji, nicks in reacciones.items()
                )

        self.area_chat.configure(state=tk.NORMAL)
        self._limpiar_marca_agua()

        if historico and not self._historial_mostrado:
            self.area_chat.insert(tk.END, '\n')
            self.area_chat.insert(
                tk.END,
                f'──── Historial de {sala or self.sala_actual} ────\n',
                'divisor'
            )
            self._historial_mostrado = True

        if tipo == 'server':
            self.area_chat.insert(tk.END, '\n')
            self.area_chat.insert(
                tk.END, f'{contenido}\n', 'server_texto'
            )
        elif tipo == 'historial':
            if not self._historial_mostrado:
                self.area_chat.insert(tk.END, '\n')
                self.area_chat.insert(
                    tk.END,
                    '──── Historial anterior ────\n',
                    'divisor'
                )
                self._historial_mostrado = True
            self.area_chat.insert(
                tk.END, f'{hora} ', 'hora'
            )
            self.area_chat.insert(
                tk.END,
                f'{contenido}\n',
                'historial_texto'
            )
        else:
            es_propio = emisor == self.nickname
            mencionado = (
                tipo in ('msg', 'grupo')
                and not es_propio
                and es_mencionado(
                    self.nickname, contenido
                )
            )
            inicio = self.area_chat.index(tk.END)
            self.area_chat.insert(tk.END, '\n')

            prefijo_grupo = (
                f'[{grupo}] ' if tipo == 'grupo' else ''
            )

            if tipo == 'priv':
                tag_nombre = 'nombre_privado'
                tag_texto = 'privado_texto'
                tag_hora = 'hora_privado'
                prefijo = (
                    '[Privado] Tú'
                    if es_propio
                    else f'[Privado] {emisor}'
                )
            elif tipo == 'archivo':
                tag_nombre = 'nombre_archivo'
                tag_texto = 'archivo_texto'
                tag_hora = 'hora_archivo'
                prefijo = 'Tú' if es_propio else emisor
            elif es_propio:
                tag_nombre = 'nombre_propio'
                tag_texto = 'propio_texto'
                tag_hora = 'hora_propio'
                prefijo = f'{prefijo_grupo}Tú'
            elif mencionado:
                tag_nombre = 'nombre_mencion'
                tag_texto = 'mencion_texto'
                tag_hora = 'hora_mencion'
                prefijo = f'{prefijo_grupo}{emisor}'
            elif tipo == 'grupo':
                tag_nombre = 'nombre_grupo'
                tag_texto = 'grupo_texto'
                tag_hora = 'hora_grupo'
                prefijo = f'{prefijo_grupo}{emisor}'
            else:
                tag_nombre = 'nombre_otro'
                tag_texto = 'otro_texto'
                tag_hora = 'hora_otro'
                prefijo = emisor

            self.area_chat.insert(
                tk.END, '┃ ', tag_texto
            )
            if (
                tipo in ('msg', 'grupo')
                and not es_propio
            ):
                avatar_img = self._obtener_avatar(
                    emisor, 18
                )
                self.area_chat._textbox.image_create(
                    tk.END, image=avatar_img
                )
                self.area_chat.insert(
                    tk.END, ' ', tag_nombre
                )
                self.area_chat.insert(
                    tk.END,
                    f'{prefijo}  ',
                    tag_nombre
                )
            else:
                self.area_chat.insert(
                    tk.END,
                    f'{prefijo}  ',
                    tag_nombre
                )

            self.area_chat.insert(
                tk.END, f'{hora}\n', tag_hora
            )
            self.area_chat.insert(
                tk.END, '┃ ', tag_texto
            )
            self.area_chat.insert(
                tk.END, f'{contenido}\n', tag_texto
            )

            if extra:
                self.area_chat.insert(
                    tk.END, f'{extra}\n', tag_hora
                )

            if reacciones_texto:
                self.area_chat.insert(
                    tk.END,
                    f'{reacciones_texto}\n',
                    tag_hora
                )

            if es_propio and id_mensaje is not None:
                estado_texto = self._texto_estado(
                    id_mensaje
                )
                if estado_texto:
                    self.area_chat.insert(
                        tk.END,
                        f'{estado_texto}\n',
                        tag_hora
                    )

            fin = self.area_chat.index(tk.END)

            if id_mensaje is not None:
                tag_mensaje = f'msg_{id_mensaje}'
                self.area_chat.tag_add(
                    tag_mensaje, inicio, fin
                )
                self.area_chat._textbox.tag_bind(
                    tag_mensaje,
                    '<Button-3>',
                    lambda evento, identificador=id_mensaje:
                    self._mostrar_selector_reaccion(
                        evento, identificador
                    )
                )

            if es_propio:
                self.area_chat.tag_add(
                    'derecha', inicio, fin
                )

        self.area_chat.see(tk.END)
        self.area_chat.configure(state=tk.DISABLED)
        return True


    def _mostrar_preview_imagen(self, ruta, emisor):
        if not PIL_DISPONIBLE:
            return False
        try:
            img = Image.open(ruta)
            img.thumbnail((200, 200))
            photo = ImageTk.PhotoImage(img)
            self.imagenes.append(photo)

            self.area_chat.configure(state=tk.NORMAL)
            self.area_chat.insert(tk.END, f'[Imagen de {emisor}]\n', 'hora')
            # CTkTextbox.image_create() está deshabilitado a propósito (por
            # la misma razón que 'font' en tag_config); se usa el
            # tkinter.Text real vía self._textbox, igual que en _configurar_tags.
            self.area_chat._textbox.image_create(tk.END, image=photo)
            self.area_chat.insert(tk.END, '\n\n')
            self.area_chat.see(tk.END)
            self.area_chat.configure(state=tk.DISABLED)
            return True
        except Exception:
            return False

    def _contenido_legible(self, mensaje):
        try:
            return interpretar_contenido(mensaje)
        except ValueError:
            return (
                '[No se pudo descifrar. Verifica que todos '
                'usen el mismo archivo clave_chat.key.]'
            )

    def _registrar_confirmacion_entrante(
        self, mensaje, visible
    ):
        id_mensaje = mensaje.get('id')
        emisor = mensaje.get('emisor')
        if (
            not id_mensaje
            or not emisor
            or emisor == self.nickname
        ):
            return

        try:
            confirmar_entrega(self.sock, id_mensaje)
        except Exception:
            pass

        if visible:
            try:
                confirmar_lectura(
                    self.sock, id_mensaje
                )
            except Exception:
                pass
        else:
            self.lecturas_pendientes[id_mensaje] = {
                'tipo': mensaje.get('tipo'),
                'grupo': mensaje.get('grupo'),
                'sala': mensaje.get('sala'),
            }

    def _confirmar_lecturas_visibles(self):
        vista = self.combo_destinatario.get()
        confirmados = []

        for id_mensaje, contexto in (
            self.lecturas_pendientes.items()
        ):
            tipo = contexto.get('tipo')
            if tipo == 'grupo_msg':
                visible = (
                    vista
                    == f'Grupo: {contexto.get("grupo")}'
                )
            elif tipo == 'msg':
                visible = (
                    not vista.startswith('Grupo: ')
                    and contexto.get('sala')
                    == self.sala_actual
                )
            else:
                visible = not vista.startswith('Grupo: ')

            if visible:
                try:
                    confirmar_lectura(
                        self.sock, id_mensaje
                    )
                    confirmados.append(id_mensaje)
                except Exception:
                    pass

        for id_mensaje in confirmados:
            self.lecturas_pendientes.pop(
                id_mensaje, None
            )

    def _manejar_mensaje(self, mensaje):
        tipo = mensaje.get('tipo')
        hora = mensaje.get('hora', '')
        id_mensaje = mensaje.get('id')

        if tipo in (
            'msg', 'priv', 'grupo_msg',
            'historial_msg', 'file'
        ):
            if (
                id_mensaje
                and id_mensaje in self.ids_mensajes_vistos
            ):
                return
            if id_mensaje:
                self.ids_mensajes_vistos.add(
                    id_mensaje
                )

        if tipo == 'msg':
            emisor = mensaje.get('emisor')
            contenido = self._contenido_legible(
                mensaje
            )
            visible = self._agregar_burbuja(
                emisor,
                contenido,
                hora,
                'msg',
                id_mensaje=id_mensaje,
                sala=mensaje.get(
                    'sala', self.sala_actual
                )
            )
            if emisor != self.nickname:
                mencionado = es_mencionado(
                    self.nickname, contenido
                )
                reproducir_beep(
                    mencion=mencionado
                )
                self._registrar_confirmacion_entrante(
                    mensaje, visible
                )

        elif tipo == 'priv':
            emisor = mensaje.get('emisor')
            contenido = self._contenido_legible(
                mensaje
            )
            visible = self._agregar_burbuja(
                emisor,
                contenido,
                hora,
                'priv',
                id_mensaje=id_mensaje,
                destinatario=mensaje.get(
                    'destinatario'
                )
            )
            if emisor != self.nickname:
                reproducir_beep()
                self._registrar_confirmacion_entrante(
                    mensaje, visible
                )

        elif tipo == 'server':
            contenido = mensaje.get('contenido', '')
            if contenido.startswith(
                'GRUPO_INVALIDO: '
            ):
                texto_error = contenido[
                    len('GRUPO_INVALIDO: '):
                ]
                messagebox.showerror(
                    'Grupo',
                    texto_error.capitalize()
                )
            elif contenido.startswith(
                'SALA_INVALIDA: '
            ):
                texto_error = contenido[
                    len('SALA_INVALIDA: '):
                ]
                messagebox.showerror(
                    'Sala', texto_error
                )
                self.combo_salas.set(
                    self.sala_actual
                )
            elif contenido == 'MENSAJE_NO_CIFRADO':
                messagebox.showerror(
                    'Seguridad',
                    'El servidor rechazó un mensaje '
                    'sin cifrado.'
                )
            self._agregar_burbuja(
                '',
                contenido,
                '',
                'server',
                sala=mensaje.get('sala')
            )

        elif tipo == 'usuarios':
            self.avatares_usuarios.update(
                mensaje.get('avatares', {})
            )
            self.colores_usuarios.update(
                mensaje.get('colores', {})
            )
            self._actualizar_usuarios(
                mensaje.get('contenido', [])
            )

        elif tipo == 'salas':
            self._actualizar_salas(
                mensaje.get('contenido', []),
                mensaje.get('sala_actual')
            )

        elif tipo == 'sala_actualizada':
            self.sala_actual = mensaje.get(
                'nombre', 'General'
            )
            self.combo_salas.set(
                self.sala_actual
            )
            self.combo_destinatario.set('Todos')
            self._historial_mostrado = False
            self._redibujar_chat()
            self._actualizar_titulo_vista()
            self._confirmar_lecturas_visibles()
            self._agregar_burbuja(
                '',
                f'Entraste a la sala '
                f'"{self.sala_actual}".',
                '',
                'server',
                sala=self.sala_actual
            )

        elif tipo == 'grupo_actualizado':
            nombre = mensaje.get('nombre')
            es_nuevo = nombre not in self.grupos
            self.grupos[nombre] = {
                'miembros': mensaje.get(
                    'miembros', []
                ),
                'creador': mensaje.get(
                    'creador'
                ),
                'avatar': mensaje.get(
                    'avatar', 'gente'
                )
            }
            self._actualizar_grupos()
            if es_nuevo:
                self._agregar_burbuja(
                    '',
                    f'Te agregaron al grupo '
                    f'"{nombre}".',
                    '',
                    'server'
                )

        elif tipo == 'grupo_eliminado':
            nombre = mensaje.get('nombre')
            self.grupos.pop(nombre, None)
            self._actualizar_grupos()
            if (
                self.combo_destinatario.get()
                == f'Grupo: {nombre}'
            ):
                self.combo_destinatario.set(
                    'Todos'
                )
                self._redibujar_chat()

        elif tipo == 'grupo_msg':
            emisor = mensaje.get('emisor')
            nombre_grupo = mensaje.get('grupo')
            contenido = self._contenido_legible(
                mensaje
            )
            visible = self._agregar_burbuja(
                emisor,
                contenido,
                hora,
                'grupo',
                grupo=nombre_grupo,
                id_mensaje=id_mensaje
            )
            if emisor != self.nickname:
                mencionado = es_mencionado(
                    self.nickname, contenido
                )
                reproducir_beep(
                    mencion=mencionado
                )
                self._registrar_confirmacion_entrante(
                    mensaje, visible
                )

        elif tipo == 'historial_msg':
            contenido = self._contenido_legible(
                mensaje
            )
            self._agregar_burbuja(
                mensaje.get('emisor', ''),
                contenido,
                hora,
                'msg',
                id_mensaje=id_mensaje,
                sala=mensaje.get(
                    'sala', self.sala_actual
                ),
                historico=True
            )

        elif tipo == 'historial':
            self._agregar_burbuja(
                '',
                mensaje.get('contenido', ''),
                '',
                'historial'
            )

        elif tipo == 'file':
            emisor = mensaje.get('emisor')
            nombre = mensaje.get(
                'nombre_archivo'
            )
            es_propio = emisor == self.nickname
            ruta = guardar_archivo(
                emisor,
                nombre,
                mensaje.get('datos')
            )
            destinatario_original = mensaje.get(
                'destinatario', 'todos'
            )
            if es_propio:
                destinatario_mostrado = (
                    'Todos'
                    if destinatario_original
                    == 'todos'
                    else destinatario_original
                )
                extra = (
                    f'Enviado a '
                    f'{destinatario_mostrado}'
                )
            else:
                extra = f'Guardado en: {ruta}'
                reproducir_beep()

            if es_imagen(nombre):
                self._mostrar_preview_imagen(
                    ruta, emisor
                )

            self._agregar_burbuja(
                emisor,
                f'Archivo: {nombre}',
                hora,
                'archivo',
                extra=extra,
                id_mensaje=id_mensaje,
                sala=mensaje.get('sala'),
                destinatario=destinatario_original
            )

        elif tipo == 'ack':
            id_estado = mensaje.get(
                'id_mensaje'
            )
            self.estados_mensajes[
                id_estado
            ] = 'ack'
            self._redibujar_chat()

        elif tipo == 'estado':
            id_estado = mensaje.get(
                'id_mensaje'
            )
            self.estados_mensajes[
                id_estado
            ] = mensaje.get(
                'estado', 'delivered'
            )
            self._redibujar_chat()

        elif tipo == 'error_envio':
            id_estado = mensaje.get(
                'id_mensaje'
            )
            self.estados_mensajes[
                id_estado
            ] = 'error'
            self._redibujar_chat()
            messagebox.showerror(
                'Mensaje no enviado',
                mensaje.get(
                    'contenido',
                    'No se pudo enviar el mensaje.'
                )
            )

        elif tipo == 'reaccion':
            self._registrar_reaccion(
                mensaje.get('id_mensaje'),
                mensaje.get('emisor'),
                mensaje.get('emoji')
            )

        elif tipo == 'typing':
            emisor = mensaje.get('emisor')
            destinatario = mensaje.get(
                'destinatario'
            )
            sala = mensaje.get('sala')
            vista_general = not (
                self.combo_destinatario.get()
                .startswith('Grupo: ')
            )
            if emisor != self.nickname:
                if (
                    destinatario == self.nickname
                    or (
                        destinatario == 'todos'
                        and sala == self.sala_actual
                        and vista_general
                    )
                ):
                    self._mostrar_typing(emisor)

        elif tipo == 'desconexion':
            self._agregar_burbuja(
                '',
                'Desconectado del servidor',
                '',
                'server'
            )
            self.conectado = False

        elif tipo == 'error':
            self._agregar_burbuja(
                '',
                f'Error: {mensaje.get("contenido")}',
                '',
                'server'
            )


    def _registrar_reaccion(self, id_mensaje, emisor, emoji):
        if id_mensaje is None or not emoji:
            return
        reacciones = self.reacciones_por_mensaje.setdefault(id_mensaje, {})
        for usuarios in reacciones.values():
            usuarios.discard(emisor)
        reacciones.setdefault(emoji, set()).add(emisor)
        self.reacciones_por_mensaje[id_mensaje] = {e: u for e, u in reacciones.items() if u}
        self._redibujar_chat()

    def _redibujar_chat(self):
        pegado_abajo = self.area_chat.yview()[1] >= 0.999
        fraccion_scroll = self.area_chat.yview()[0]

        self.area_chat.configure(state=tk.NORMAL)
        self.area_chat.delete('1.0', tk.END)
        self.area_chat.configure(state=tk.DISABLED)
        self._marca_agua_presente = False
        self._historial_mostrado = False

        eventos = self.eventos_chat
        self.eventos_chat = []  # se vuelve a poblar solo al reinsertar cada burbuja
        vista_activa = self.combo_destinatario.get()
        hay_visibles = any(self._evento_visible(ev, vista_activa) for ev in eventos)

        if not eventos or not hay_visibles:
            for ev in eventos:
                self.eventos_chat.append(ev)
            self._mostrar_marca_agua()
        else:
            for ev in eventos:
                self._agregar_burbuja(
                    ev['emisor'],
                    ev['contenido'],
                    ev['hora'],
                    ev['tipo'],
                    extra=ev['extra'],
                    id_mensaje=ev['id_mensaje'],
                    grupo=ev.get('grupo'),
                    sala=ev.get('sala'),
                    historico=ev.get('historico', False),
                    destinatario=ev.get('destinatario')
                )
            # Nota: los previews de imagen embebidos (_mostrar_preview_imagen)
            # no se re-insertan en un redibujado -- se pierde el thumbnail
            # inline, pero el texto "Archivo: nombre / Guardado en: ruta"
            # se mantiene y el archivo sigue disponible en esa ruta.

        if pegado_abajo:
            self.area_chat.see(tk.END)
        else:
            self.area_chat.yview_moveto(fraccion_scroll)

    def _mostrar_typing(self, emisor):
        self.label_typing.configure(text=f'{emisor} está escribiendo...')
        self.root.after(3000, lambda: self.label_typing.configure(text=''))

    def _actualizar_usuarios(self, usuarios):
        self.usuarios_actuales = usuarios
        for fila in self.lista_usuarios.winfo_children():
            fila.destroy()

        for u in usuarios:
            texto = f'{u} (tú)' if u == self.nickname else u
            ctk.CTkButton(
                self.lista_usuarios, text=f'  {texto}', anchor='w',
                image=self._obtener_avatar(u, 24), compound='left',
                fg_color='transparent', hover_color=self.tema['borde'],
                text_color=self.tema['online'], font=('Segoe UI', 15),
                corner_radius=8, height=32,
                command=lambda u=u: self._seleccionar_usuario(u)
            ).pack(fill=tk.X, pady=2)
        self._actualizar_titulo_vista()
        self._recalcular_destinatarios()

    def _recalcular_destinatarios(self):
        valores = ['Todos']
        valores += [u for u in self.usuarios_actuales if u != self.nickname]
        valores += [f'Grupo: {nombre}' for nombre in self.grupos]
        destinatario_actual = self.combo_destinatario.get()
        self.combo_destinatario.configure(values=valores)
        if destinatario_actual not in valores:
            self.combo_destinatario.set('Todos')
            if destinatario_actual != 'Todos':
                self._redibujar_chat()

    def _seleccionar_grupo(self, nombre_grupo):
        self.combo_destinatario.set(f'Grupo: {nombre_grupo}')
        self._cambiar_vista()

    def _cambiar_vista(self, _valor_elegido=None):
        self._redibujar_chat()
        self._actualizar_titulo_vista()
        self._confirmar_lecturas_visibles()

    def _destinatario_protocolo(self):
        # El combo muestra 'Todos' (mayúscula, para que se lea bien), pero
        # el servidor espera literalmente 'todos' en minúscula para typing/
        # archivos (los mensajes de texto no tienen este problema porque
        # usan enviar_mensaje_publico(), que ni siquiera manda destinatario).
        # Sin esta traducción, "Todos" nunca calza con el chequeo del
        # servidor y el envío queda silenciosamente sin destinatario válido.
        valor = self.combo_destinatario.get()
        return 'todos' if valor == 'Todos' else valor

    def _ir_a_chat_general(self):
        self.combo_destinatario.set('Todos')
        if self.sala_actual != 'General':
            salir_sala(self.sock)
        else:
            self._cambiar_vista()

    def _actualizar_titulo_vista(self):
        vista = self.combo_destinatario.get()
        if vista.startswith('Grupo: '):
            nombre = vista[len('Grupo: '):]
            cantidad = len(
                self.grupos.get(
                    nombre, {}
                ).get('miembros', [])
            )
            self.label_titulo.configure(
                text=(
                    f'👥 {nombre} · {cantidad} '
                    f'miembro{"s" if cantidad != 1 else ""}'
                )
            )
        else:
            cantidad = self.salas.get(
                self.sala_actual, 0
            )
            self.label_titulo.configure(
                text=(
                    f'🚪 {self.sala_actual} · '
                    f'{cantidad} en la sala'
                )
            )

    def _salir_de_grupo(self, nombre_grupo):
        salir_grupo(self.sock, nombre_grupo)

    def _actualizar_grupos(self):
        for fila in self.lista_grupos.winfo_children():
            fila.destroy()

        for nombre, info in self.grupos.items():
            fila = ctk.CTkFrame(self.lista_grupos, fg_color='transparent')
            fila.pack(fill=tk.X, pady=2)
            # Los botones ✕/＋ se empaquetan PRIMERO (side=RIGHT) para que
            # reserven su espacio antes que el de nombre -- si se empaqueta
            # el de nombre primero con fill=X+expand, un nombre de grupo
            # largo lo hace crecer sin límite y empuja a ✕/＋ fuera del
            # ancho visible de la barra lateral (quedan sin verse ni poder
            # clickearse).
            ctk.CTkButton(
                fila, text='✕', width=26, height=26,
                fg_color='transparent', hover_color=self.tema['borde'],
                text_color=self.tema['archivo'], font=('Segoe UI', 13, 'bold'),
                corner_radius=6, command=lambda n=nombre: self._salir_de_grupo(n)
            ).pack(side=tk.RIGHT, padx=(4, 0))
            ctk.CTkButton(
                fila, text='＋', width=26, height=26,
                fg_color='transparent', hover_color=self.tema['borde'],
                text_color=self.tema['texto_secundario'], font=('Segoe UI', 13, 'bold'),
                corner_radius=6, command=lambda n=nombre: self._mostrar_invitar_grupo(n)
            ).pack(side=tk.RIGHT, padx=(4, 0))
            # El ícono va en un CTkLabel aparte, con su propio espacio fijo,
            # en vez de "image=" dentro del botón de nombre: si el botón
            # queda con poco ancho disponible (fila angosta, texto largo),
            # CTkButton prioriza el texto y el ícono deja de dibujarse. Con
            # un widget dedicado, el ícono siempre tiene su lugar reservado.
            ctk.CTkLabel(
                fila, text='', image=self._obtener_avatar_grupo(nombre, 22),
                fg_color='transparent', width=24
            ).pack(side=tk.LEFT, padx=(2, 0))
            nombre_mostrado = nombre if len(nombre) <= 14 else nombre[:13] + '…'
            ctk.CTkButton(
                fila, text=f' {nombre_mostrado} · {len(info["miembros"])} miembros', anchor='w',
                fg_color='transparent', hover_color=self.tema['borde'],
                text_color=self.tema['grupo'], font=('Segoe UI', 14),
                corner_radius=8, height=32,
                command=lambda n=nombre: self._seleccionar_grupo(n)
            ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._recalcular_destinatarios()
        self._actualizar_titulo_vista()

    def _enviar_mensaje(self):
        texto = self.entry_mensaje.get().strip()
        if not texto or not self.conectado:
            return

        destinatario = self.combo_destinatario.get()
        try:
            if destinatario == 'Todos':
                id_mensaje = enviar_mensaje_publico(
                    self.sock, texto
                )
            elif destinatario.startswith('Grupo: '):
                id_mensaje = enviar_mensaje_grupo(
                    self.sock,
                    destinatario[len('Grupo: '):],
                    texto
                )
            else:
                id_mensaje = enviar_mensaje_privado(
                    self.sock,
                    destinatario,
                    texto
                )
        except Exception as exc:
            messagebox.showerror(
                'Error',
                f'No se pudo enviar el mensaje: {exc}'
            )
            return

        self.estados_mensajes[
            id_mensaje
        ] = 'pending'
        self.entry_mensaje.delete(0, tk.END)

    def _enviar_archivo(self):
        if not self.conectado:
            return
        destinatario_vista = self.combo_destinatario.get()
        if destinatario_vista.startswith('Grupo: '):
            messagebox.showinfo(
                'Enviar archivo',
                'Por ahora no se pueden enviar archivos a un grupo. Elegí "Todos" o un usuario.'
            )
            return
        ruta = filedialog.askopenfilename(title='Seleccionar archivo')
        if not ruta:
            return
        if not os.path.exists(ruta):
            messagebox.showerror('Error', 'El archivo no existe.')
            return

        destinatario = self._destinatario_protocolo()
        try:
            # No se agrega una burbuja local acá -- el servidor ahora
            # siempre hace eco del archivo de vuelta al emisor (mismo
            # patrón que los mensajes privados de texto), así que la
            # burbuja llega sola por _manejar_mensaje con el id real
            # (necesario para que las reacciones calcen) y sin duplicar.
            enviar_archivo(self.sock, ruta, destinatario)
        except Exception as e:
            messagebox.showerror('Error', f'No se pudo enviar el archivo: {e}')

    def _procesar_cola(self):
        while not self.cola_mensajes.empty():
            mensaje = self.cola_mensajes.get()
            self._manejar_mensaje(mensaje)
        self.root.after(100, self._procesar_cola)

    def _escuchar(self):
        while self.conectado:
            try:
                mensaje = recibir(self.sock)
                if not mensaje:
                    self.cola_mensajes.put({'tipo': 'desconexion'})
                    break
                self.cola_mensajes.put(mensaje)
            except Exception as e:
                self.cola_mensajes.put({'tipo': 'error', 'contenido': str(e)})
                break

    @property
    def root(self):
        return self.master


# ORQUESTADOR PRINCIPAL
class ChatGUI:
    def __init__(self, root):
        self.root = root
        self.root.title('Chat con Sockets')
        self.root.geometry('1050x700')
        self.root.minsize(850, 550)

        self.tema = TEMA_OSCURO
        self.sock = None
        self.nickname = ''
        self.conectado = False
        self.hilo_escucha = None

        try:
            self._icono = crear_icono_mascota(self.tema)
            self.root.iconphoto(True, self._icono)
        except Exception:
            pass

        self.login_frame = LoginFrame(
            self.root, self.tema, self._conectar, self._cambiar_tema
        )
        self.login_frame.pack(fill=tk.BOTH, expand=True)

        self.chat_frame = None

        self.root.protocol('WM_DELETE_WINDOW', self._salir)
        self.root.bind('<Escape>', lambda e: self._salir())
        self.root.bind('<Control-l>', lambda e: self._limpiar_chat())

    def _cambiar_tema(self):
        self.tema = TEMA_CLARO if self.tema is TEMA_OSCURO else TEMA_OSCURO
        if self.login_frame:
            self.login_frame._aplicar_tema(self.tema)
        if self.chat_frame:
            self.chat_frame._aplicar_tema(self.tema)

    def _limpiar_chat(self):
        if self.chat_frame:
            self.chat_frame._historial_mostrado = False
            self.chat_frame._mostrar_marca_agua()

    def _conectar(
        self, ip, puerto, nickname,
        avatar='circulo', color=None
    ):
        try:
            self.sock = conectar(ip, puerto)
            enviar_nickname(
                self.sock, nickname, avatar, color
            )
            respuesta = recibir(self.sock)
        except Exception as exc:
            self.login_frame.mostrar_error(
                f'No se pudo conectar: {exc}'
            )
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass
            self.sock = None
            return

        if respuesta:
            codigo = respuesta.get('contenido')
            errores = {
                'NICK_INVALIDO': (
                    'Nickname ya en uso o inválido.'
                ),
                'CLAVE_REQUERIDA': (
                    'El cliente debe usar cifrado Fernet.'
                ),
                'CLAVE_INCOMPATIBLE': (
                    'La clave no coincide. Copia el mismo '
                    'archivo cliente/clave_chat.key en '
                    'todos los clientes.'
                ),
            }
            if codigo in errores:
                self.login_frame.mostrar_error(
                    errores[codigo]
                )
                self.sock.close()
                self.sock = None
                return

        self.nickname = nickname
        self.conectado = True

        self.login_frame.pack_forget()

        self.chat_frame = ChatFrame(
            self.root, self.tema, self._desconectar, self._cambiar_tema, ip=ip, puerto=puerto
        )
        self.chat_frame.sock = self.sock
        self.chat_frame.nickname = nickname
        self.chat_frame.conectado = True
        self.chat_frame.avatares_usuarios[nickname] = avatar
        if color:
            self.chat_frame.colores_usuarios[nickname] = color
        self.chat_frame.pack(fill=tk.BOTH, expand=True)

        self.chat_frame._manejar_mensaje({
            'tipo': 'server', 'contenido': f'👾 ¡Bienvenido, {nickname}!'
        })

        self.hilo_escucha = threading.Thread(
            target=self.chat_frame._escuchar, daemon=True
        )
        self.hilo_escucha.start()

    def _desconectar(self):
        self.conectado = False
        if self.sock:
            cerrar(self.sock)
            self.sock = None
        if self.chat_frame:
            self.chat_frame.pack_forget()
            self.chat_frame = None
        self.login_frame = LoginFrame(self.root, self.tema, self._conectar, self._cambiar_tema)
        self.login_frame.pack(fill=tk.BOTH, expand=True)

    def _salir(self):
        if self.conectado and self.sock:
            cerrar(self.sock)
        self.root.destroy()


def main():
    ctk.set_appearance_mode('dark')
    ctk.set_widget_scaling(1.0)
    root = ctk.CTk()
    app = ChatGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
