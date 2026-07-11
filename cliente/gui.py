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
    enviar_typing, guardar_archivo, cerrar, EMOJIS_COMUNES, enviar_reaccion
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
    'busqueda': '#fee75c'
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
    'busqueda': '#fee75c'
}

PALETA_USUARIOS = [
    '#f783ac', '#74c0fc', '#ffd43b', '#69db7c',
    '#da77f2', '#4dabf7', '#ff922b', '#63e6be'
]


def color_usuario(nickname):
    indice = sum(ord(c) for c in nickname) % len(PALETA_USUARIOS)
    return PALETA_USUARIOS[indice]

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


def reproducir_beep():
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
        self._construir()

    def _construir(self):
        self.frame_tarjeta = ctk.CTkFrame(self, fg_color=self.tema['fondo'], corner_radius=0)
        self.frame_tarjeta.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

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
        self.boton_conectar.pack(pady=(24, 0))

        self.label_error = ctk.CTkLabel(
            self.frame_central, text='', text_color='#ed4245',
            fg_color='transparent', font=('Segoe UI', 12)
        )
        self.label_error.pack(pady=(10, 0))

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

    def _aplicar_tema(self, tema):
        self.tema = tema
        self.configure(fg_color=tema['fondo'])
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

        self.on_conectar(ip, puerto, nickname)

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
        self.tags_usuario = set()
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
        self.frame_usuarios = tk.Frame(self.frame_central, bg=self.tema['panel'], width=225)
        self.frame_usuarios.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=10)
        self.frame_usuarios.pack_propagate(False)

        self.label_usuarios = ctk.CTkLabel(
            self.frame_usuarios, text='USUARIOS EN LÍNEA', fg_color='transparent',
            text_color=self.tema['texto_secundario'], font=('Segoe UI', 13, 'bold')
        )
        self.label_usuarios.pack(anchor='w', padx=12, pady=(15, 5))

        self.lista_usuarios = ctk.CTkScrollableFrame(
            self.frame_usuarios, fg_color=self.tema['panel'], corner_radius=0
        )
        self.lista_usuarios.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

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
            font=('Segoe UI', 14)
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
        self.label_usuarios.configure(text_color=tema['texto_secundario'])
        self.lista_usuarios.configure(fg_color=tema['panel'])
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
        for fila in self.lista_usuarios.winfo_children():
            fila.configure(hover_color=tema['borde'], text_color=tema['online'])

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
            'privado': t['privado_fondo'], 'archivo': t['archivo_fondo']
        }
        colores_nombre = {
            'propio': t['propio'], 'otro': t['texto'],
            'privado': t['texto'], 'archivo': t['texto']
        }
        colores_texto = {
            'propio': t['propio'], 'otro': t['texto'],
            'privado': t['privado'], 'archivo': t['archivo']
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

    def _tag_avatar(self, nickname):
        tag_id = f'avatar_{nickname}'
        if tag_id not in self.tags_usuario:
            self.area_chat._textbox.tag_config(tag_id, foreground=color_usuario(nickname))
            self.tags_usuario.add(tag_id)
        return tag_id

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
        if usuario != self.nickname:
            self.combo_destinatario.set(usuario)
            self.entry_mensaje.focus()

    def _on_typing(self, event):
        if not self.conectado:
            return
        ahora = time.time()
        if ahora - self.ultimo_typing > 2:
            self.ultimo_typing = ahora
            try:
                destinatario = self.combo_destinatario.get()
                enviar_typing(self.sock, destinatario)
            except Exception:
                pass

    def _agregar_burbuja(self, emisor, contenido, hora, tipo='msg', alinear='izquierda', extra='',
                          id_mensaje=None):
        self.eventos_chat.append({
            'emisor': emisor, 'contenido': contenido, 'hora': hora,
            'tipo': tipo, 'extra': extra, 'id_mensaje': id_mensaje
        })

        reacciones_texto = ''
        if id_mensaje is not None:
            reacciones = self.reacciones_por_mensaje.get(id_mensaje)
            if reacciones:
                reacciones_texto = '  '.join(f'{emoji} {len(nicks)}' for emoji, nicks in reacciones.items())

        self.area_chat.configure(state=tk.NORMAL)
        self._limpiar_marca_agua()

        if tipo == 'server':
            self.area_chat.insert(tk.END, '\n')
            self.area_chat.insert(tk.END, f'{contenido}\n', 'server_texto')
        elif tipo == 'historial':
            if not self._historial_mostrado:
                self.area_chat.insert(tk.END, '\n')
                self.area_chat.insert(tk.END, '──── Historial anterior ────\n', 'divisor')
                self._historial_mostrado = True
            self.area_chat.insert(tk.END, f'{hora} ', 'hora')
            self.area_chat.insert(tk.END, f'{contenido}\n', 'historial_texto')
        else:
            es_propio = (emisor == self.nickname)
            inicio = self.area_chat.index(tk.END)
            self.area_chat.insert(tk.END, '\n')

            if tipo == 'priv':
                tag_nombre = 'nombre_privado'
                tag_texto = 'privado_texto'
                tag_hora = 'hora_privado'
                prefijo = '[Privado] Tú' if es_propio else f'[Privado] {emisor}'
            elif tipo == 'archivo':
                tag_nombre = 'nombre_archivo'
                tag_texto = 'archivo_texto'
                tag_hora = 'hora_archivo'
                prefijo = 'Tú' if es_propio else emisor
            elif es_propio:
                tag_nombre = 'nombre_propio'
                tag_texto = 'propio_texto'
                tag_hora = 'hora_propio'
                prefijo = 'Tú'
            else:
                tag_nombre = 'nombre_otro'
                tag_texto = 'otro_texto'
                tag_hora = 'hora_otro'
                prefijo = emisor

            self.area_chat.insert(tk.END, '┃ ', tag_texto)
            if tipo == 'msg' and not es_propio:
                avatar = self._tag_avatar(emisor)
                self.area_chat.insert(tk.END, '● ', (tag_nombre, avatar))
                self.area_chat.insert(tk.END, f'{prefijo}  ', (tag_nombre, avatar))
            else:
                self.area_chat.insert(tk.END, f'{prefijo}  ', tag_nombre)
            self.area_chat.insert(tk.END, f'{hora}\n', tag_hora)
            self.area_chat.insert(tk.END, '┃ ', tag_texto)
            self.area_chat.insert(tk.END, f'{contenido}\n', tag_texto)

            if extra:
                self.area_chat.insert(tk.END, f'{extra}\n', tag_hora)

            if reacciones_texto:
                self.area_chat.insert(tk.END, f'{reacciones_texto}\n', tag_hora)

            fin = self.area_chat.index(tk.END)

            if id_mensaje is not None:
                tag_mensaje = f'msg_{id_mensaje}'
                self.area_chat.tag_add(tag_mensaje, inicio, fin)
                self.area_chat._textbox.tag_bind(
                    tag_mensaje, '<Button-3>',
                    lambda e, i=id_mensaje: self._mostrar_selector_reaccion(e, i)
                )

            if es_propio:
                self.area_chat.tag_add('derecha', inicio, fin)

        self.area_chat.see(tk.END)
        self.area_chat.configure(state=tk.DISABLED)

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

    def _manejar_mensaje(self, mensaje):
        tipo = mensaje.get('tipo')
        hora = mensaje.get('hora', '')

        if tipo == 'msg':
            emisor = mensaje.get('emisor')
            self._agregar_burbuja(emisor, mensaje['contenido'], hora, 'msg', id_mensaje=mensaje.get('id'))
            if emisor != self.nickname:
                reproducir_beep()

        elif tipo == 'priv':
            emisor = mensaje.get('emisor')
            self._agregar_burbuja(emisor, mensaje['contenido'], hora, 'priv', id_mensaje=mensaje.get('id'))
            if emisor != self.nickname:
                reproducir_beep()

        elif tipo == 'server':
            self._agregar_burbuja('', mensaje['contenido'], '', 'server')

        elif tipo == 'usuarios':
            self._actualizar_usuarios(mensaje.get('contenido', []))

        elif tipo == 'historial':
            self._agregar_burbuja('', mensaje['contenido'], '', 'historial')

        elif tipo == 'file':
            emisor = mensaje.get('emisor')
            nombre = mensaje.get('nombre_archivo')
            if emisor != self.nickname:
                ruta = guardar_archivo(emisor, nombre, mensaje.get('datos'))
                extra = f'Guardado en: {ruta}'
                if es_imagen(nombre):
                    self._mostrar_preview_imagen(ruta, emisor)
                reproducir_beep()
            else:
                extra = f'Enviado a {mensaje.get("destinatario", "todos")}'
            self._agregar_burbuja(emisor, f'Archivo: {nombre}', hora, 'archivo', extra=extra, id_mensaje=mensaje.get('id'))

        elif tipo == 'reaccion':
            self._registrar_reaccion(mensaje.get('id_mensaje'), mensaje.get('emisor'), mensaje.get('emoji'))

        elif tipo == 'typing':
            emisor = mensaje.get('emisor')
            destinatario = mensaje.get('destinatario')
            if emisor != self.nickname:
                if destinatario == 'todos' or destinatario == self.nickname:
                    self._mostrar_typing(emisor)

        elif tipo == 'desconexion':
            self._agregar_burbuja('', 'Desconectado del servidor', '', 'server')
            self.conectado = False

        elif tipo == 'error':
            self._agregar_burbuja('', f'Error: {mensaje.get("contenido")}', '', 'server')

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

        if not eventos:
            self._mostrar_marca_agua()
        else:
            for ev in eventos:
                self._agregar_burbuja(
                    ev['emisor'], ev['contenido'], ev['hora'], ev['tipo'],
                    extra=ev['extra'], id_mensaje=ev['id_mensaje']
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
        for fila in self.lista_usuarios.winfo_children():
            fila.destroy()

        valores = ['Todos']
        for u in usuarios:
            simbolo = '●' if u != self.nickname else '● (tú)'
            ctk.CTkButton(
                self.lista_usuarios, text=f'{simbolo} {u}', anchor='w',
                fg_color='transparent', hover_color=self.tema['borde'],
                text_color=self.tema['online'], font=('Segoe UI', 15),
                corner_radius=8, height=32,
                command=lambda u=u: self._seleccionar_usuario(u)
            ).pack(fill=tk.X, pady=2)
            if u != self.nickname:
                valores.append(u)
        self.combo_destinatario.configure(values=valores)
        self.label_titulo.configure(text=f'👾 Chat con Sockets - {len(usuarios)} en línea')

    def _enviar_mensaje(self):
        texto = self.entry_mensaje.get().strip()
        if not texto or not self.conectado:
            return

        destinatario = self.combo_destinatario.get()
        if destinatario == 'Todos':
            enviar_mensaje_publico(self.sock, texto)
        else:
            enviar_mensaje_privado(self.sock, destinatario, texto)
            self._agregar_burbuja(self.nickname, texto, time.strftime('%H:%M:%S'), 'priv')

        self.entry_mensaje.delete(0, tk.END)

    def _enviar_archivo(self):
        if not self.conectado:
            return
        ruta = filedialog.askopenfilename(title='Seleccionar archivo')
        if not ruta:
            return
        if not os.path.exists(ruta):
            messagebox.showerror('Error', 'El archivo no existe.')
            return

        destinatario = self.combo_destinatario.get()
        try:
            enviar_archivo(self.sock, ruta, destinatario)
            nombre = os.path.basename(ruta)
            self._agregar_burbuja(
                self.nickname, f'Archivo: {nombre}', time.strftime('%H:%M:%S'),
                'archivo', extra=f'Enviado a {destinatario}'
            )
            if es_imagen(nombre):
                self._mostrar_preview_imagen(ruta, self.nickname)
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

    def _conectar(self, ip, puerto, nickname):
        try:
            self.sock = conectar(ip, puerto)
        except Exception as e:
            self.login_frame.mostrar_error(f'No se pudo conectar: {e}')
            return

        enviar_nickname(self.sock, nickname)
        respuesta = recibir(self.sock)

        if respuesta and respuesta.get('contenido') == 'NICK_INVALIDO':
            self.login_frame.mostrar_error('Nickname ya en uso o inválido.')
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
