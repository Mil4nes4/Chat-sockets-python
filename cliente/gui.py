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
    'propio': '#9aa3ff',
    'propio_fondo': '#404eed',
    'otros_fondo': '#40444b',
    'privado': '#ffb454',
    'privado_fondo': '#4f442b',
    'server': '#3ddc84',
    'server_fondo': '#2f4f3f',
    'historial': '#9a9fa6',
    'archivo': '#ff6b6e',
    'online': '#3ddc84',
    'busqueda': '#fee75c'
}

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
            winsound.MessageBeep()
        else:
            print('\a', end='')
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
            font=('Courier New', 11, 'bold'), justify=tk.CENTER
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

        self.boton_conectar = tk.Button(
            frame_central, text='Conectar al chat',
            bg=self.tema['acento'], fg='white',
            activebackground=self.tema['acento_hover'],
            font=('Segoe UI', 12, 'bold'), relief=tk.FLAT,
            command=self._intentar_conectar, cursor='hand2'
        )
        self.boton_conectar.pack(fill=tk.X, pady=(24, 0), ipady=12)

        self.label_error = tk.Label(
            frame_central, text='', fg='#ed4245',
            bg=self.tema['panel'], font=('Segoe UI', 10)
        )
        self.label_error.pack(pady=(10, 0))

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
    def __init__(self, master, tema, on_desconectar, **kwargs):
        super().__init__(master, bg=tema['fondo'], **kwargs)
        self.tema = tema
        self.on_desconectar = on_desconectar
        self.nickname = ''
        self.conectado = False
        self.sock = None
        self.cola_mensajes = queue.Queue()
        self.hilo_escucha = None
        self.ultimo_typing = 0
        self.imagenes = []  # Referencias para evitar que se borren

        self._construir()
        self._procesar_cola()

    def _construir(self):
        # Barra superior
        frame_superior = tk.Frame(self, bg=self.tema['panel'], height=50)
        frame_superior.pack(fill=tk.X)
        frame_superior.pack_propagate(False)

        self.label_titulo = tk.Label(
            frame_superior, text='Chat con Sockets',
            bg=self.tema['panel'], fg=self.tema['texto'],
            font=('Segoe UI', 13, 'bold')
        )
        self.label_titulo.pack(side=tk.LEFT, padx=15, pady=10)

        self.boton_buscar = tk.Button(
            frame_superior, text='🔍 Buscar', bg=self.tema['entrada'],
            fg=self.tema['texto'], relief=tk.FLAT, cursor='hand2',
            font=('Segoe UI', 11), padx=16, pady=8,
            command=self._mostrar_busqueda
        )
        self.boton_buscar.pack(side=tk.RIGHT, padx=5)

        self.boton_desconectar = tk.Button(
            frame_superior, text='Desconectar', bg='#ed4245',
            fg='white', relief=tk.FLAT, cursor='hand2',
            font=('Segoe UI', 11, 'bold'), padx=16, pady=8,
            command=self.on_desconectar
        )
        self.boton_desconectar.pack(side=tk.RIGHT, padx=15)

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
        self.frame_central = tk.Frame(self, bg=self.tema['fondo'])
        self.frame_central.pack(fill=tk.BOTH, expand=True)

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

        scrollbar = tk.Scrollbar(frame_chat, command=self.area_chat.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.area_chat.config(yscrollcommand=scrollbar.set)

        # Indicador de escribiendo
        self.label_typing = tk.Label(
            self, text='', bg=self.tema['fondo'], fg=self.tema['texto_secundario'],
            font=('Segoe UI', 10, 'italic'), anchor='w'
        )
        self.label_typing.pack(fill=tk.X, padx=15)

        # Barra inferior de entrada
        frame_inferior = tk.Frame(self, bg=self.tema['panel'], padx=10, pady=10)
        frame_inferior.pack(fill=tk.X, side=tk.BOTTOM)

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

        self.boton_enviar = tk.Button(
            frame_inferior, text='Enviar', bg=self.tema['acento'], fg='white',
            activebackground=self.tema['acento_hover'], relief=tk.FLAT,
            font=('Segoe UI', 11, 'bold'), cursor='hand2',
            command=self._enviar_mensaje
        )
        self.boton_enviar.pack(side=tk.LEFT, padx=5, ipady=6, ipadx=14)

        self._configurar_tags()

    def _configurar_tags(self):
        t = self.tema
        self.area_chat.tag_config('hora', foreground=t['texto_secundario'], font=('Segoe UI', 10))
        self.area_chat.tag_config('nombre', foreground=t['texto'], font=('Segoe UI', 12, 'bold'))
        self.area_chat.tag_config('propio_nombre', foreground=t['propio'], font=('Segoe UI', 12, 'bold'))
        self.area_chat.tag_config('propio_texto', foreground=t['propio'], font=('Segoe UI', 12))
        self.area_chat.tag_config('otro_texto', foreground=t['texto'], font=('Segoe UI', 12))
        self.area_chat.tag_config('privado_texto', foreground=t['privado'], font=('Segoe UI', 12))
        self.area_chat.tag_config('server_texto', foreground=t['server'], font=('Segoe UI', 12))
        self.area_chat.tag_config('historial_texto', foreground=t['historial'], font=('Segoe UI', 11, 'italic'))
        self.area_chat.tag_config('archivo_texto', foreground=t['archivo'], font=('Segoe UI', 12))
        self.area_chat.tag_config('busqueda', background=t['busqueda'], foreground='black')

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

        if tipo == 'server':
            self.area_chat.insert(tk.END, '\n')
            self.area_chat.insert(tk.END, f'  {contenido}  ', 'server_texto')
            self.area_chat.insert(tk.END, '\n')
        elif tipo == 'historial':
            self.area_chat.insert(tk.END, f'{hora} ', 'hora')
            self.area_chat.insert(tk.END, f'{contenido}\n', 'historial_texto')
        else:
            self.area_chat.insert(tk.END, '\n')

            if tipo == 'priv':
                tag_nombre = 'nombre'
                tag_texto = 'privado_texto'
                prefijo = f'[Privado] {emisor}'
            elif tipo == 'archivo':
                tag_nombre = 'nombre'
                tag_texto = 'archivo_texto'
                prefijo = f'{emisor}'
            elif emisor == self.nickname:
                tag_nombre = 'propio_nombre'
                tag_texto = 'propio_texto'
                prefijo = 'Tú'
            else:
                tag_nombre = 'nombre'
                tag_texto = 'otro_texto'
                prefijo = emisor

            self.area_chat.insert(tk.END, f'{prefijo}  ', tag_nombre)
            self.area_chat.insert(tk.END, f'{hora}\n', 'hora')
            self.area_chat.insert(tk.END, f'{contenido}\n', tag_texto)

            if extra:
                self.area_chat.insert(tk.END, f'{extra}\n', 'hora')

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
        self.label_titulo.config(text=f'Chat con Sockets - {len(usuarios)} en línea')

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
            self.chat_frame.area_chat.config(state=tk.NORMAL)
            self.chat_frame.area_chat.delete('1.0', tk.END)
            self.chat_frame.area_chat.config(state=tk.DISABLED)

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
            self.root, self.tema, self._desconectar
        )
        self.chat_frame.sock = self.sock
        self.chat_frame.nickname = nickname
        self.chat_frame.conectado = True
        self.chat_frame.pack(fill=tk.BOTH, expand=True)

        if respuesta:
            self.chat_frame._manejar_mensaje({
                'tipo': 'server', 'contenido': respuesta.get('contenido')
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
