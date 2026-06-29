import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog

# Asegura que el módulo cliente_chat se pueda importar desde cualquier ubicación
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cliente.cliente_chat import (
    conectar, recibir, enviar_nickname, enviar_mensaje_publico,
    enviar_mensaje_privado, solicitar_lista, enviar_archivo, guardar_archivo, cerrar
)

COLOR_FONDO = '#36393f'
COLOR_PANEL = '#2f3136'
COLOR_ENTRADA = '#40444b'
COLOR_TEXTO = '#dcddde'
COLOR_ACENTO = '#7289da'
COLOR_PRIVADO = '#faa61a'
COLOR_SERVIDOR = '#43b581'
COLOR_HISTORIAL = '#72767d'


class ChatGUI:
    def __init__(self, root):
        self.root = root
        self.root.title('Chat con Sockets')
        self.root.configure(bg=COLOR_FONDO)
        self.root.geometry('900x600')
        self.root.minsize(700, 400)

        self.sock = None
        self.nickname = ''
        self.conectado = False
        self.hilo_escucha = None
        self.cola_mensajes = queue.Queue()

        self._construir_interfaz()
        self._procesar_cola()

        self.root.protocol('WM_DELETE_WINDOW', self._salir)

    def _construir_interfaz(self):
        # Frame superior: conexión
        frame_conexion = tk.Frame(self.root, bg=COLOR_PANEL, padx=10, pady=10)
        frame_conexion.pack(fill=tk.X)

        tk.Label(frame_conexion, text='IP:', bg=COLOR_PANEL, fg=COLOR_TEXTO).pack(side=tk.LEFT)
        self.entry_ip = tk.Entry(frame_conexion, width=15, bg=COLOR_ENTRADA, fg=COLOR_TEXTO, insertbackground=COLOR_TEXTO)
        self.entry_ip.insert(0, '127.0.0.1')
        self.entry_ip.pack(side=tk.LEFT, padx=5)

        tk.Label(frame_conexion, text='Puerto:', bg=COLOR_PANEL, fg=COLOR_TEXTO).pack(side=tk.LEFT)
        self.entry_puerto = tk.Entry(frame_conexion, width=7, bg=COLOR_ENTRADA, fg=COLOR_TEXTO, insertbackground=COLOR_TEXTO)
        self.entry_puerto.insert(0, '5000')
        self.entry_puerto.pack(side=tk.LEFT, padx=5)

        tk.Label(frame_conexion, text='Nickname:', bg=COLOR_PANEL, fg=COLOR_TEXTO).pack(side=tk.LEFT)
        self.entry_nick = tk.Entry(frame_conexion, width=15, bg=COLOR_ENTRADA, fg=COLOR_TEXTO, insertbackground=COLOR_TEXTO)
        self.entry_nick.pack(side=tk.LEFT, padx=5)

        self.boton_conectar = tk.Button(
            frame_conexion, text='Conectar', bg=COLOR_ACENTO, fg='white',
            activebackground='#5b6eae', command=self._conectar
        )
        self.boton_conectar.pack(side=tk.LEFT, padx=5)

        # Frame central: chat + lista de usuarios
        frame_central = tk.Frame(self.root, bg=COLOR_FONDO)
        frame_central.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.area_chat = scrolledtext.ScrolledText(
            frame_central, wrap=tk.WORD, state=tk.DISABLED,
            bg=COLOR_FONDO, fg=COLOR_TEXTO, font=('Segoe UI', 11),
            padx=10, pady=10
        )
        self.area_chat.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.area_chat.tag_config('propio', foreground=COLOR_ACENTO)
        self.area_chat.tag_config('privado', foreground=COLOR_PRIVADO)
        self.area_chat.tag_config('server', foreground=COLOR_SERVIDOR)
        self.area_chat.tag_config('historial', foreground=COLOR_HISTORIAL)
        self.area_chat.tag_config('archivo', foreground=COLOR_PRIVADO)

        frame_usuarios = tk.Frame(frame_central, bg=COLOR_PANEL, width=180)
        frame_usuarios.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        frame_usuarios.pack_propagate(False)

        tk.Label(frame_usuarios, text='Usuarios', bg=COLOR_PANEL, fg=COLOR_TEXTO,
                 font=('Segoe UI', 11, 'bold')).pack(pady=5)
        self.lista_usuarios = tk.Listbox(
            frame_usuarios, bg=COLOR_PANEL, fg=COLOR_TEXTO,
            selectbackground=COLOR_ACENTO, font=('Segoe UI', 10),
            highlightthickness=0, borderwidth=0
        )
        self.lista_usuarios.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Frame inferior: entrada y controles
        frame_inferior = tk.Frame(self.root, bg=COLOR_PANEL, padx=10, pady=10)
        frame_inferior.pack(fill=tk.X)

        self.entry_mensaje = tk.Entry(
            frame_inferior, bg=COLOR_ENTRADA, fg=COLOR_TEXTO,
            insertbackground=COLOR_TEXTO, font=('Segoe UI', 11)
        )
        self.entry_mensaje.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.entry_mensaje.bind('<Return>', lambda e: self._enviar_mensaje())
        self.entry_mensaje.config(state=tk.DISABLED)

        tk.Label(frame_inferior, text='Para:', bg=COLOR_PANEL, fg=COLOR_TEXTO).pack(side=tk.LEFT)
        self.combo_destinatario = ttk.Combobox(
            frame_inferior, values=['Todos'], state='readonly', width=12
        )
        self.combo_destinatario.set('Todos')
        self.combo_destinatario.pack(side=tk.LEFT, padx=5)

        self.boton_archivo = tk.Button(
            frame_inferior, text='Adjuntar archivo', bg=COLOR_ENTRADA, fg=COLOR_TEXTO,
            command=self._enviar_archivo
        )
        self.boton_archivo.pack(side=tk.LEFT, padx=5)
        self.boton_archivo.config(state=tk.DISABLED)

        self.boton_enviar = tk.Button(
            frame_inferior, text='Enviar', bg=COLOR_ACENTO, fg='white',
            activebackground='#5b6eae', command=self._enviar_mensaje
        )
        self.boton_enviar.pack(side=tk.LEFT, padx=5)
        self.boton_enviar.config(state=tk.DISABLED)

    def _agregar_linea(self, texto, etiqueta=None):
        self.area_chat.config(state=tk.NORMAL)
        self.area_chat.insert(tk.END, texto + '\n', etiqueta)
        self.area_chat.see(tk.END)
        self.area_chat.config(state=tk.DISABLED)

    def _conectar(self):
        ip = self.entry_ip.get().strip()
        puerto_str = self.entry_puerto.get().strip()
        nickname = self.entry_nick.get().strip()

        if not nickname:
            messagebox.showwarning('Nickname requerido', 'Debes ingresar un nickname.')
            return

        try:
            puerto = int(puerto_str)
        except ValueError:
            messagebox.showerror('Puerto inválido', 'El puerto debe ser un número entero.')
            return

        try:
            self.sock = conectar(ip, puerto)
        except Exception as e:
            messagebox.showerror('Error de conexión', f'No se pudo conectar: {e}')
            return

        enviar_nickname(self.sock, nickname)
        respuesta = recibir(self.sock)

        if respuesta and respuesta.get('contenido') == 'NICK_INVALIDO':
            messagebox.showerror('Nickname inválido', 'El nickname ya está en uso o es inválido.')
            self.sock.close()
            self.sock = None
            return

        self.nickname = nickname
        self.conectado = True

        self.entry_ip.config(state=tk.DISABLED)
        self.entry_puerto.config(state=tk.DISABLED)
        self.entry_nick.config(state=tk.DISABLED)
        self.boton_conectar.config(text='Desconectar', command=self._desconectar)
        self.entry_mensaje.config(state=tk.NORMAL)
        self.boton_enviar.config(state=tk.NORMAL)
        self.boton_archivo.config(state=tk.NORMAL)

        if respuesta:
            self._agregar_linea(f'[SERVIDOR] {respuesta.get("contenido")}', 'server')

        self.hilo_escucha = threading.Thread(target=self._escuchar, daemon=True)
        self.hilo_escucha.start()

    def _desconectar(self):
        self._limpiar_conexion()

    def _limpiar_conexion(self):
        self.conectado = False
        if self.sock:
            cerrar(self.sock)
            self.sock = None

        self.entry_ip.config(state=tk.NORMAL)
        self.entry_puerto.config(state=tk.NORMAL)
        self.entry_nick.config(state=tk.NORMAL)
        self.boton_conectar.config(text='Conectar', command=self._conectar)
        self.entry_mensaje.config(state=tk.DISABLED)
        self.boton_enviar.config(state=tk.DISABLED)
        self.boton_archivo.config(state=tk.DISABLED)
        self.lista_usuarios.delete(0, tk.END)
        self.combo_destinatario['values'] = ['Todos']
        self.combo_destinatario.set('Todos')

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

    def _procesar_cola(self):
        while not self.cola_mensajes.empty():
            mensaje = self.cola_mensajes.get()
            self._manejar_mensaje(mensaje)
        self.root.after(100, self._procesar_cola)

    def _manejar_mensaje(self, mensaje):
        tipo = mensaje.get('tipo')
        hora = mensaje.get('hora', '')
        prefijo_hora = f'[{hora}] ' if hora else ''

        if tipo == 'msg':
            emisor = mensaje.get('emisor')
            etiqueta = 'propio' if emisor == self.nickname else None
            self._agregar_linea(f'{prefijo_hora}{emisor}: {mensaje["contenido"]}', etiqueta)

        elif tipo == 'priv':
            emisor = mensaje.get('emisor')
            self._agregar_linea(
                f'{prefijo_hora}[PRIVADO de {emisor}]: {mensaje["contenido"]}', 'privado'
            )

        elif tipo == 'server':
            self._agregar_linea(f'[SERVIDOR] {mensaje["contenido"]}', 'server')

        elif tipo == 'usuarios':
            usuarios = mensaje.get('contenido', [])
            self.lista_usuarios.delete(0, tk.END)
            valores = ['Todos']
            for u in usuarios:
                self.lista_usuarios.insert(tk.END, u)
                if u != self.nickname:
                    valores.append(u)
            self.combo_destinatario['values'] = valores

        elif tipo == 'historial':
            self._agregar_linea(f'[HISTORIAL] {mensaje["contenido"]}', 'historial')

        elif tipo == 'file':
            try:
                ruta = guardar_archivo(
                    mensaje.get('emisor'),
                    mensaje.get('nombre_archivo'),
                    mensaje.get('datos')
                )
                self._agregar_linea(
                    f'{prefijo_hora}[ARCHIVO de {mensaje["emisor"]}] Guardado en: {ruta}',
                    'archivo'
                )
            except Exception as e:
                self._agregar_linea(f'[ERROR] No se pudo guardar el archivo: {e}', 'server')

        elif tipo == 'desconexion':
            self._agregar_linea('[Desconectado del servidor]', 'server')
            self._limpiar_conexion()

        elif tipo == 'error':
            self._agregar_linea(f'[ERROR] {mensaje.get("contenido")}', 'server')

    def _enviar_mensaje(self):
        texto = self.entry_mensaje.get().strip()
        if not texto or not self.conectado:
            return

        destinatario = self.combo_destinatario.get()
        if destinatario == 'Todos':
            enviar_mensaje_publico(self.sock, texto)
        else:
            enviar_mensaje_privado(self.sock, destinatario, texto)
            self._agregar_linea(f'[PRIVADO para {destinatario}]: {texto}', 'privado')

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
            self._agregar_linea(f'[TÚ] Enviaste {os.path.basename(ruta)} a {destinatario}.', 'propio')
        except Exception as e:
            messagebox.showerror('Error', f'No se pudo enviar el archivo: {e}')

    def _salir(self):
        if self.conectado:
            self._desconectar()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = ChatGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
