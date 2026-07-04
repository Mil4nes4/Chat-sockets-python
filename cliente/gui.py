import os
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cliente.cliente_chat import (
    conectar, recibir, enviar_nickname, enviar_mensaje_publico,
    enviar_mensaje_privado, solicitar_lista, enviar_archivo,
    enviar_typing, guardar_archivo, cerrar
)

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


def crear_boton_redondeado(parent, texto, comando, bg, fg, fondo_padre,
                            bg_hover=None, ancho=140, alto=42, radio=12,
                            font=('Segoe UI', 11, 'bold')):
    bg_hover = bg_hover or bg
    canvas = tk.Canvas(
        parent, width=ancho, height=alto, bg=fondo_padre,
        highlightthickness=0, cursor='hand2'
    )

    def _dibujar(color):
        canvas.delete('all')
        r = radio
        canvas.create_oval(0, 0, 2 * r, 2 * r, fill=color, outline=color)
        canvas.create_oval(ancho - 2 * r, 0, ancho, 2 * r, fill=color, outline=color)
        canvas.create_oval(0, alto - 2 * r, 2 * r, alto, fill=color, outline=color)
        canvas.create_oval(ancho - 2 * r, alto - 2 * r, ancho, alto, fill=color, outline=color)
        canvas.create_rectangle(r, 0, ancho - r, alto, fill=color, outline=color)
        canvas.create_rectangle(0, r, ancho, alto - r, fill=color, outline=color)
        canvas.create_text(ancho / 2, alto / 2, text=texto, fill=fg, font=font)

    _dibujar(bg)
    canvas.bind('<Button-1>', lambda e: comando())
    canvas.bind('<Enter>', lambda e: _dibujar(bg_hover))
    canvas.bind('<Leave>', lambda e: _dibujar(bg))
    return canvas


def configurar_estilo_ttk(tema):
    style = ttk.Style()
    style.theme_use('clam')
    style.configure(
        'TCombobox',
        fieldbackground=tema['entrada'], background=tema['entrada'],
        foreground=tema['texto'], arrowcolor=tema['texto'],
        bordercolor=tema['borde'], lightcolor=tema['entrada'],
        darkcolor=tema['entrada']
    )
    style.map(
        'TCombobox',
        fieldbackground=[('readonly', tema['entrada'])],
        foreground=[('readonly', tema['texto'])],
        background=[('readonly', tema['entrada'])]
    )


# PANTALLA DE LOGIN
class LoginFrame(tk.Frame):
    def __init__(self, master, tema, on_conectar, **kwargs):
        super().__init__(master, bg=tema['fondo'], **kwargs)
        self.tema = tema
        self.on_conectar = on_conectar
        self._construir()

    def _construir(self):
        self.configure(bg=self.tema['fondo'])

        frame_tarjeta = tk.Frame(self, bg=self.tema['fondo'])
        frame_tarjeta.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        tk.Frame(frame_tarjeta, bg=self.tema['acento'], height=4).pack(fill=tk.X)

        frame_central = tk.Frame(frame_tarjeta, bg=self.tema['panel'], padx=40, pady=32)
        frame_central.pack()

        tk.Label(
            frame_central, text=MASCOTA_ASCII,
            bg=self.tema['panel'], fg=self.tema['server'],
            font=('Lucida Console', 10, 'bold'), justify=tk.CENTER
        ).pack(pady=(0, 14))

        tk.Label(
            frame_central, text='Chat con Sockets',
            bg=self.tema['panel'], fg=self.tema['texto'],
            font=('Segoe UI', 24, 'bold')
        ).pack(pady=(0, 24))

        campos = [
            ('IP del servidor', '127.0.0.1', 'entry_ip'),
            ('Puerto', '5000', 'entry_puerto'),
            ('Nickname', '', 'entry_nick')
        ]

        self.entries = {}
        for label, default, attr in campos:
            tk.Label(
                frame_central, text=label,
                bg=self.tema['panel'], fg=self.tema['texto_secundario'],
                font=('Segoe UI', 11), anchor='w'
            ).pack(fill=tk.X, pady=(12, 3))
            entry = tk.Entry(
                frame_central, width=32,
                bg=self.tema['entrada'], fg=self.tema['texto'],
                insertbackground=self.tema['texto'],
                font=('Segoe UI', 12), relief=tk.FLAT,
                highlightthickness=1, highlightbackground=self.tema['borde'],
                highlightcolor=self.tema['acento']
            )
            entry.insert(0, default)
            entry.pack(fill=tk.X, ipady=8, pady=(0, 5))
            self.entries[attr] = entry

        self.entries['entry_nick'].focus()

        self.boton_conectar = crear_boton_redondeado(
            frame_central, 'Conectar al chat', self._intentar_conectar,
            bg=self.tema['acento'], fg='white', fondo_padre=self.tema['panel'],
            bg_hover=self.tema['acento_hover'], ancho=300, alto=48,
            font=('Segoe UI', 12, 'bold')
        )
        self.boton_conectar.pack(pady=(24, 0))

        self.label_error = tk.Label(
            frame_central, text='', fg='#ed4245',
            bg=self.tema['panel'], font=('Segoe UI', 10)
        )
        self.label_error.pack(pady=(10, 0))

        tk.Label(
            frame_central, text='Sockets TCP · Sistemas Operativos',
            bg=self.tema['panel'], fg=self.tema['texto_secundario'],
            font=('Segoe UI', 9)
        ).pack(pady=(18, 0))

        self.entries['entry_puerto'].bind('<Return>', lambda e: self._intentar_conectar())
        self.entries['entry_nick'].bind('<Return>', lambda e: self._intentar_conectar())

    def _intentar_conectar(self):
        ip = self.entries['entry_ip'].get().strip() or '127.0.0.1'
        puerto_str = self.entries['entry_puerto'].get().strip() or '5000'
        nickname = self.entries['entry_nick'].get().strip()

        try:
            puerto = int(puerto_str)
        except ValueError:
            self.label_error.config(text='El puerto debe ser un número.')
            return

        if not nickname:
            self.label_error.config(text='El nickname no puede estar vacío.')
            return

        self.on_conectar(ip, puerto, nickname)

    def mostrar_error(self, mensaje):
        self.label_error.config(text=mensaje)


# PANTALLA DE CHAT
class ChatFrame(tk.Frame):
    def __init__(self, master, tema, on_desconectar, ip='', puerto=None, **kwargs):
        super().__init__(master, bg=tema['fondo'], **kwargs)
        self.tema = tema
        self.on_desconectar = on_desconectar
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
        self._marca_agua_presente = False
        self._historial_mostrado = False

        self._construir()
        self._procesar_cola()

    def _construir(self):
        # Barra superior
        frame_superior = tk.Frame(self, bg=self.tema['panel'], height=50)
        frame_superior.pack(fill=tk.X)
        frame_superior.pack_propagate(False)

        self.label_titulo = tk.Label(
            frame_superior, text='👾 Chat con Sockets',
            bg=self.tema['panel'], fg=self.tema['texto'],
            font=('Segoe UI', 13, 'bold')
        )
        self.label_titulo.pack(side=tk.LEFT, padx=15, pady=10)

        self.boton_buscar = crear_boton_redondeado(
            frame_superior, '🔍 Buscar', self._mostrar_busqueda,
            bg=self.tema['entrada'], fg=self.tema['texto'], fondo_padre=self.tema['panel'],
            bg_hover=self.tema['borde'], ancho=120, alto=36, font=('Segoe UI', 11)
        )
        self.boton_buscar.pack(side=tk.RIGHT, padx=5, pady=6)

        self.boton_desconectar = crear_boton_redondeado(
            frame_superior, 'Desconectar', self.on_desconectar,
            bg='#ed4245', fg='white', fondo_padre=self.tema['panel'],
            bg_hover='#c93537', ancho=130, alto=36, font=('Segoe UI', 11, 'bold')
        )
        self.boton_desconectar.pack(side=tk.RIGHT, padx=15, pady=6)

        # Línea de acento decorativa bajo la barra superior
        tk.Frame(self, bg=self.tema['acento'], height=2).pack(fill=tk.X)

        # Panel de búsqueda (oculto inicialmente)
        self.frame_busqueda = tk.Frame(self, bg=self.tema['fondo'])
        self.entry_busqueda = tk.Entry(
            self.frame_busqueda, bg=self.tema['entrada'], fg=self.tema['texto'],
            insertbackground=self.tema['texto'], font=('Segoe UI', 10),
            relief=tk.FLAT, highlightthickness=1,
            highlightbackground=self.tema['borde'], highlightcolor=self.tema['acento']
        )
        self.entry_busqueda.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        self.entry_busqueda.bind('<KeyRelease>', lambda e: self._buscar())
        tk.Button(
            self.frame_busqueda, text='Cerrar', bg=self.tema['entrada'],
            fg=self.tema['texto'], relief=tk.FLAT, cursor='hand2',
            command=self._ocultar_busqueda
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
        frame_usuarios = tk.Frame(self.frame_central, bg=self.tema['panel'], width=225)
        frame_usuarios.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=10)
        frame_usuarios.pack_propagate(False)

        tk.Label(
            frame_usuarios, text='USUARIOS EN LÍNEA',
            bg=self.tema['panel'], fg=self.tema['texto_secundario'],
            font=('Segoe UI', 10, 'bold')
        ).pack(anchor='w', padx=12, pady=(15, 5))

        self.lista_usuarios = tk.Listbox(
            frame_usuarios, bg=self.tema['panel'], fg=self.tema['texto'],
            selectbackground=self.tema['acento'], selectforeground='white',
            font=('Segoe UI', 12),
            highlightthickness=0, borderwidth=0, relief=tk.FLAT
        )
        self.lista_usuarios.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.lista_usuarios.bind('<Double-Button-1>', self._seleccionar_usuario)

        # Área de chat
        frame_chat = tk.Frame(self.frame_central, bg=self.tema['fondo'])
        frame_chat.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.area_chat = tk.Text(
            frame_chat, wrap=tk.WORD, state=tk.DISABLED,
            bg=self.tema['fondo'], fg=self.tema['texto'],
            font=('Segoe UI', 11), padx=10, pady=10,
            spacing1=2, spacing3=2, relief=tk.FLAT,
            highlightthickness=1, highlightbackground=self.tema['borde'],
            highlightcolor=self.tema['borde'], borderwidth=0
        )
        self.area_chat.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(
            frame_chat, command=self.area_chat.yview,
            bg=self.tema['borde'], troughcolor=self.tema['panel'],
            activebackground=self.tema['acento'], relief=tk.FLAT,
            highlightthickness=0, borderwidth=0, elementborderwidth=0
        )
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.area_chat.config(yscrollcommand=scrollbar.set)

        # El label de "escribiendo..." se crea aquí (para tener la
        # referencia disponible) pero se empaqueta más abajo, después de
        # toda la barra inferior, para que quede pegado justo encima de
        # ella en la pila de widgets "bottom" (ver comentario junto al
        # pack final de frame_central).
        self.label_typing = tk.Label(
            self, text='', bg=self.tema['fondo'], fg=self.tema['texto_secundario'],
            font=('Segoe UI', 10, 'italic'), anchor='w'
        )

        # Barra de estado de conexión
        frame_estado = tk.Frame(self, bg=self.tema['panel'])
        frame_estado.pack(fill=tk.X, side=tk.BOTTOM)

        texto_estado = f'● Conectado a {self.ip}:{self.puerto}' if self.ip else ''
        self.label_estado = tk.Label(
            frame_estado, text=texto_estado, bg=self.tema['panel'],
            fg=self.tema['online'], font=('Segoe UI', 9), anchor='w'
        )
        self.label_estado.pack(side=tk.LEFT, padx=12, ipady=3)

        tk.Label(
            frame_estado, text='Sockets TCP · Sistemas Operativos',
            bg=self.tema['panel'], fg=self.tema['texto_secundario'],
            font=('Segoe UI', 9), anchor='e'
        ).pack(side=tk.RIGHT, padx=12, ipady=3)

        # Barra inferior de entrada
        frame_inferior = tk.Frame(self, bg=self.tema['panel'], padx=10, pady=10)
        frame_inferior.pack(fill=tk.X, side=tk.BOTTOM)

        # Línea de acento decorativa sobre la barra de envío (simétrica a la de arriba)
        tk.Frame(self, bg=self.tema['acento'], height=2).pack(fill=tk.X, side=tk.BOTTOM)

        self.entry_mensaje = tk.Entry(
            frame_inferior, bg=self.tema['entrada'], fg=self.tema['texto'],
            insertbackground=self.tema['texto'], font=('Segoe UI', 12),
            relief=tk.FLAT, highlightthickness=1,
            highlightbackground=self.tema['borde'], highlightcolor=self.tema['acento']
        )
        self.entry_mensaje.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10), ipady=10)
        self.entry_mensaje.bind('<Return>', lambda e: self._enviar_mensaje())
        self.entry_mensaje.bind('<KeyRelease>', self._on_typing)

        tk.Label(
            frame_inferior, text='Para:', bg=self.tema['panel'],
            fg=self.tema['texto_secundario'], font=('Segoe UI', 11)
        ).pack(side=tk.LEFT)

        self.combo_destinatario = ttk.Combobox(
            frame_inferior, values=['Todos'], state='readonly', width=14,
            font=('Segoe UI', 11)
        )
        self.combo_destinatario.set('Todos')
        self.combo_destinatario.pack(side=tk.LEFT, padx=5)

        self.boton_archivo = tk.Button(
            frame_inferior, text='📎', bg=self.tema['entrada'],
            fg=self.tema['texto'], relief=tk.FLAT, cursor='hand2',
            font=('Segoe UI', 14), padx=6, pady=4,
            command=self._enviar_archivo
        )
        self.boton_archivo.pack(side=tk.LEFT, padx=5)

        self.boton_enviar = crear_boton_redondeado(
            frame_inferior, 'Enviar', self._enviar_mensaje,
            bg=self.tema['acento'], fg='white', fondo_padre=self.tema['panel'],
            bg_hover=self.tema['acento_hover'], ancho=100, alto=40,
            font=('Segoe UI', 11, 'bold')
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

    def _configurar_tags(self):
        t = self.tema

        # Texto genérico
        self.area_chat.tag_config('hora', foreground=t['texto_secundario'], font=('Segoe UI', 10))
        self.area_chat.tag_config('historial_texto', foreground=t['historial'], font=('Segoe UI', 11, 'italic'))
        self.area_chat.tag_config('busqueda', background=t['busqueda'], foreground='black')
        self.area_chat.tag_config(
            'divisor', foreground=t['texto_secundario'], font=('Segoe UI', 10, 'italic'),
            justify=tk.CENTER
        )
        self.area_chat.tag_config(
            'marca_agua', foreground=t['historial'], font=('Lucida Console', 10),
            justify=tk.CENTER
        )
        self.area_chat.tag_config(
            'marca_agua_texto', foreground=t['texto_secundario'], font=('Segoe UI', 11, 'italic'),
            justify=tk.CENTER
        )
        self.area_chat.tag_config(
            'server_texto', foreground=t['server'], background=t['server_fondo'],
            font=('Segoe UI', 12), justify=tk.CENTER
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
            self.area_chat.tag_config(
                f'nombre_{clave}', foreground=colores_nombre[clave], background=fondo,
                font=('Segoe UI', 12, 'bold')
            )
            self.area_chat.tag_config(
                f'{clave}_texto', foreground=colores_texto[clave], background=fondo,
                font=('Segoe UI', 12)
            )
            self.area_chat.tag_config(
                f'hora_{clave}', foreground=t['texto_secundario'], background=fondo,
                font=('Segoe UI', 10)
            )

        # Mensajes propios alineados a la derecha
        self.area_chat.tag_config('derecha', justify=tk.RIGHT)

    def _tag_avatar(self, nickname):
        tag_id = f'avatar_{nickname}'
        if tag_id not in self.tags_usuario:
            self.area_chat.tag_config(tag_id, foreground=color_usuario(nickname))
            self.tags_usuario.add(tag_id)
        return tag_id

    def _mostrar_marca_agua(self):
        self.area_chat.config(state=tk.NORMAL)
        self.area_chat.delete('1.0', tk.END)
        self.area_chat.insert(tk.END, '\n' * 3)
        for fila in MASCOTA_ASCII.split('\n'):
            self.area_chat.insert(tk.END, fila + '\n', 'marca_agua')
        self.area_chat.insert(tk.END, '\n')
        self.area_chat.insert(tk.END, 'Aún no hay mensajes en este chat\n', 'marca_agua_texto')
        self.area_chat.config(state=tk.DISABLED)
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

    def _buscar(self):
        self._quitar_resaltado_busqueda()
        texto = self.entry_busqueda.get().strip().lower()
        if not texto:
            return
        self.area_chat.config(state=tk.NORMAL)
        inicio = '1.0'
        while True:
            pos = self.area_chat.search(texto, inicio, tk.END, nocase=1)
            if not pos:
                break
            fin = f'{pos}+{len(texto)}c'
            self.area_chat.tag_add('busqueda', pos, fin)
            inicio = fin
        self.area_chat.config(state=tk.DISABLED)

    def _quitar_resaltado_busqueda(self):
        self.area_chat.tag_remove('busqueda', '1.0', tk.END)

    def _seleccionar_usuario(self, event):
        seleccion = self.lista_usuarios.curselection()
        if seleccion:
            usuario = self.lista_usuarios.get(seleccion[0])
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

    def _agregar_burbuja(self, emisor, contenido, hora, tipo='msg', alinear='izquierda', extra=''):
        self.area_chat.config(state=tk.NORMAL)
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

            if es_propio:
                fin = self.area_chat.index(tk.END)
                self.area_chat.tag_add('derecha', inicio, fin)

        self.area_chat.see(tk.END)
        self.area_chat.config(state=tk.DISABLED)

    def _mostrar_preview_imagen(self, ruta, emisor):
        if not PIL_DISPONIBLE:
            return False
        try:
            img = Image.open(ruta)
            img.thumbnail((200, 200))
            photo = ImageTk.PhotoImage(img)
            self.imagenes.append(photo)

            self.area_chat.config(state=tk.NORMAL)
            self.area_chat.insert(tk.END, f'[Imagen de {emisor}]\n', 'hora')
            self.area_chat.image_create(tk.END, image=photo)
            self.area_chat.insert(tk.END, '\n\n')
            self.area_chat.see(tk.END)
            self.area_chat.config(state=tk.DISABLED)
            return True
        except Exception:
            return False

    def _manejar_mensaje(self, mensaje):
        tipo = mensaje.get('tipo')
        hora = mensaje.get('hora', '')

        if tipo == 'msg':
            emisor = mensaje.get('emisor')
            self._agregar_burbuja(emisor, mensaje['contenido'], hora, 'msg')
            if emisor != self.nickname:
                reproducir_beep()

        elif tipo == 'priv':
            emisor = mensaje.get('emisor')
            self._agregar_burbuja(emisor, mensaje['contenido'], hora, 'priv')
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
            self._agregar_burbuja(emisor, f'Archivo: {nombre}', hora, 'archivo', extra=extra)

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

    def _mostrar_typing(self, emisor):
        self.label_typing.config(text=f'{emisor} está escribiendo...')
        self.root.after(3000, lambda: self.label_typing.config(text=''))

    def _actualizar_usuarios(self, usuarios):
        self.lista_usuarios.delete(0, tk.END)
        valores = ['Todos']
        for i, u in enumerate(usuarios):
            simbolo = '●' if u != self.nickname else '● (tú)'
            self.lista_usuarios.insert(tk.END, f'{simbolo} {u}')
            self.lista_usuarios.itemconfig(i, fg=self.tema['online'])
            if u != self.nickname:
                valores.append(u)
        self.combo_destinatario['values'] = valores
        self.label_titulo.config(text=f'👾 Chat con Sockets - {len(usuarios)} en línea')

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

        configurar_estilo_ttk(self.tema)
        self.root.option_add('*TCombobox*Listbox.background', self.tema['entrada'])
        self.root.option_add('*TCombobox*Listbox.foreground', self.tema['texto'])
        self.root.option_add('*TCombobox*Listbox.selectBackground', self.tema['acento'])
        self.root.option_add('*TCombobox*Listbox.selectForeground', 'white')

        self.login_frame = LoginFrame(
            self.root, self.tema, self._conectar
        )
        self.login_frame.pack(fill=tk.BOTH, expand=True)

        self.chat_frame = None

        self.root.protocol('WM_DELETE_WINDOW', self._salir)
        self.root.bind('<Escape>', lambda e: self._salir())
        self.root.bind('<Control-l>', lambda e: self._limpiar_chat())

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
            self.root, self.tema, self._desconectar, ip=ip, puerto=puerto
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
        self.login_frame = LoginFrame(self.root, self.tema, self._conectar)
        self.login_frame.pack(fill=tk.BOTH, expand=True)

    def _salir(self):
        if self.conectado and self.sock:
            cerrar(self.sock)
        self.root.destroy()


def main():
    root = tk.Tk()
    app = ChatGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
