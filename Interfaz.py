# cliente_gui.py
# Interfaz grafica para el proyecto StrangerTEC Morse Translator
# Se conecta a la Raspberry Pi Pico W por WiFi usando sockets TCP

import socket
import threading
import random
import json
import os
import tkinter as tk
from tkinter import messagebox, simpledialog

# -----------------------------------------------------------
# CONFIGURACION INICIAL
# -----------------------------------------------------------

# IP de la Pico W (la que aparece en Thonny al conectarse al WiFi)
SERVER_IP = "10.125.27.34"
PORT = 1717

# Archivo donde se guardan las frases entre sesiones
FRASES_FILE = "frases.json"

# Frases por defecto si no existe el archivo
FRASES_DEFAULT = ["SI", "NO", "SOS", "YES", "OPA", "HOLA", "TEC", "123", "2026", "WOW"]

# -----------------------------------------------------------
# MANEJO DE FRASES (guardar y cargar del archivo)
# -----------------------------------------------------------

def cargar_frases():
    # Si existe el archivo de frases lo carga, sino usa las por defecto
    if os.path.exists(FRASES_FILE):
        try:
            with open(FRASES_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return FRASES_DEFAULT.copy()

def guardar_frases():
    # Guarda la lista actual de frases en el archivo JSON
    with open(FRASES_FILE, "w") as f:
        json.dump(frases, f)

# -----------------------------------------------------------
# VARIABLES GLOBALES DEL JUEGO
# -----------------------------------------------------------

frases = cargar_frases()   # lista de frases disponibles
frase_actual = ""          # frase que se esta jugando en este momento
puntaje_a = 0              # puntos acumulados del jugador A
puntaje_b = 0              # puntos acumulados del jugador B
top10 = []                 # lista de tuplas (nombre, puntaje) para el top 10
turno = "A"                # indica de quien es el turno en modo escucha
ronda = 1                  # ronda actual en modo simple (1, 2 o 3)
mi_socket = None           # socket de conexion con la Pico W

# -----------------------------------------------------------
# FUNCIONES DE RED
# -----------------------------------------------------------

def conectar():
    # Intenta conectarse a la Pico W con la IP que escribio el usuario
    global mi_socket
    ip = campo_ip.get().strip()
    try:
        mi_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        mi_socket.settimeout(120)
        mi_socket.connect((ip, PORT))
        # La Pico manda un mensaje de bienvenida al conectarse
        respuesta = mi_socket.recv(1024).decode().strip()
        escribir_log("Pico W: " + respuesta)
        boton_conectar.config(state=tk.DISABLED)
        etiqueta_estado.config(text="Conectado a " + ip, fg="#00ff00")
    except Exception as e:
        messagebox.showerror("Error", "No se pudo conectar: " + str(e))

def enviar_comando(comando):
    # Manda un texto a la Pico y espera una respuesta
    # Retorna la respuesta o None si hubo error
    if mi_socket is None:
        return None
    try:
        mi_socket.send(comando.encode())
        respuesta = mi_socket.recv(1024).decode().strip()
        escribir_log("Pico W: " + respuesta)
        return respuesta
    except Exception as e:
        escribir_log("Error: " + str(e))
        return None

def enviar_frase_en_hilo(frase, cuando_termine=None):
    # Manda una frase a la Pico para que la transmita
    # Esto se hace en un hilo separado porque la transmision tarda varios segundos
    # y si no, la interfaz se congela mientras espera
    def hilo():
        if mi_socket is None:
            return
        try:
            # Mandar el comando
            mi_socket.send(("FRASE:" + frase).encode())
            # La Pico responde dos veces:
            # primero "OK:Transmitiendo" y luego "OK:Fin transmision"
            r1 = mi_socket.recv(1024).decode().strip()
            escribir_log("Pico W: " + r1)
            r2 = mi_socket.recv(1024).decode().strip()
            escribir_log("Pico W: " + r2)
            # Cuando termina llama a la funcion que recibio como parametro
            if cuando_termine:
                root.after(0, cuando_termine)
        except Exception as e:
            escribir_log("Error en hilo: " + str(e))

    threading.Thread(target=hilo, daemon=True).start()

def pedir_boton_en_hilo(cuando_llegue):
    # Le dice a la Pico que espere la entrada del boton del jugador B
    # Tambien en hilo separado porque puede tardar mucho esperando al jugador
    def hilo():
        if mi_socket is None:
            return
        try:
            mi_socket.send("LEER_BOTON".encode())
            # Primera respuesta: "OK:Esperando boton"
            r1 = mi_socket.recv(1024).decode().strip()
            escribir_log("Pico W: " + r1)
            # Segunda respuesta: "RESULTADO:lo_que_escribio_el_jugador"
            r2 = mi_socket.recv(1024).decode().strip()
            escribir_log("Pico W: " + r2)
            if r2.startswith("RESULTADO:"):
                texto = r2[10:].strip()  # quitar el prefijo "RESULTADO:"
                root.after(0, lambda: cuando_llegue(texto))
        except Exception as e:
            escribir_log("Error en hilo: " + str(e))

    threading.Thread(target=hilo, daemon=True).start()

# -----------------------------------------------------------
# FUNCIONES DE PUNTAJE
# -----------------------------------------------------------

def calcular_puntaje(original, respuesta):
    # Compara letra por letra la respuesta con la frase original
    # Cada letra correcta vale 10 puntos multiplicado por el nivel
    niveles = {"FACIL": 1, "MEDIO": 2, "DIFICIL": 3}
    multiplicador = niveles.get(nivel_var.get(), 1)
    puntos = 0
    original = original.upper().strip()
    respuesta = respuesta.upper().strip()
    for i in range(min(len(original), len(respuesta))):
        if original[i] == respuesta[i]:
            puntos += 10 * multiplicador
    return puntos

def agregar_al_top10(nombre, puntos):
    # Agrega un puntaje al top 10 y lo ordena de mayor a menor
    top10.append((nombre, puntos))
    top10.sort(key=lambda x: x[1], reverse=True)
    # Si hay mas de 10 entradas elimina la ultima
    if len(top10) > 10:
        top10.pop()

def posicion_en_top10(puntos):
    # Revisa en que posicion quedaria este puntaje en el top 10
    # Retorna None si no entra
    lista_temporal = sorted(top10 + [("_temporal_", puntos)], key=lambda x: x[1], reverse=True)
    for i, (nombre, _) in enumerate(lista_temporal[:10]):
        if nombre == "_temporal_":
            return i + 1
    return None

# -----------------------------------------------------------
# LOG
# -----------------------------------------------------------

def escribir_log(texto):
    # Agrega una linea al cuadro de log en la pantalla principal
    caja_log.config(state=tk.NORMAL)
    caja_log.insert(tk.END, texto + "\n")
    caja_log.see(tk.END)
    caja_log.config(state=tk.DISABLED)

# -----------------------------------------------------------
# NAVEGACION ENTRE PANTALLAS
# -----------------------------------------------------------

def ir_al_menu():
    pantalla_menu.tkraise()

def ir_a_simple():
    pantalla_simple.tkraise()

def ir_a_escucha():
    pantalla_escucha.tkraise()

# -----------------------------------------------------------
# MODO TRANSMISION SIMPLE
# -----------------------------------------------------------

def empezar_modo_simple():
    # Reinicia todo y empieza el juego en modo simple
    global puntaje_a, ronda, frase_actual
    puntaje_a = 0
    ronda = 1
    nivel_var.set("FACIL")        # ronda 1 siempre empieza en facil
    frase_actual = random.choice(frases)
    campo_respuesta_simple.delete(0, tk.END)
    etiqueta_puntos_simple.config(text="Puntaje: 0")
    ir_a_simple()
    transmitir_ronda_simple()

def transmitir_ronda_simple():
    # Manda la frase a la Pico para que la transmita y actualiza la UI
    etiqueta_ronda.config(text="Ronda: " + str(ronda) + " / 3")
    etiqueta_frase_simple.config(text="Frase: " + frase_actual)
    etiqueta_aviso_simple.config(text="Transmitiendo...", fg="yellow")
    boton_validar_simple.config(state=tk.DISABLED)

    # Primero le dice la velocidad a la Pico
    enviar_comando("VELOCIDAD:" + nivel_var.get())
    escribir_log("Transmitiendo '" + frase_actual + "' en nivel " + nivel_var.get())

    # Luego manda la frase en un hilo y cuando termine habilita el boton
    def cuando_termine():
        etiqueta_aviso_simple.config(text="Escribe lo que recibiste", fg="#00ff00")
        boton_validar_simple.config(state=tk.NORMAL)
        campo_respuesta_simple.focus()

    enviar_frase_en_hilo(frase_actual, cuando_termine)

def validar_respuesta_simple():
    # Revisa la respuesta del jugador, suma puntos y pasa a la siguiente ronda
    global puntaje_a, ronda, frase_actual
    respuesta = campo_respuesta_simple.get().strip().upper()
    puntos = calcular_puntaje(frase_actual, respuesta)
    puntaje_a += puntos
    escribir_log("Respuesta: '" + respuesta + "' | Correcta: '" + frase_actual + "' | +" + str(puntos) + " pts")
    etiqueta_puntos_simple.config(text="Puntaje: " + str(puntaje_a))
    campo_respuesta_simple.delete(0, tk.END)

    if ronda < 3:
        # Todavia hay rondas, subir dificultad y nueva frase
        ronda += 1
        niveles = ["FACIL", "MEDIO", "DIFICIL"]
        nivel_var.set(niveles[ronda - 1])
        frase_actual = random.choice(frases)
        transmitir_ronda_simple()
    else:
        # Se acabaron las 3 rondas
        terminar_modo_simple()

def terminar_modo_simple():
    # Muestra el puntaje final y pregunta si entro al top 10
    pos = posicion_en_top10(puntaje_a)
    mensaje = "Puntaje final: " + str(puntaje_a) + " pts\n\n"
    if pos:
        nombre = simpledialog.askstring("Top 10", "Entraste al lugar #" + str(pos) + "\n¿Cual es tu nombre?")
        if nombre:
            agregar_al_top10(nombre, puntaje_a)
            mensaje += "Guardado en el lugar #" + str(pos)
    else:
        mensaje += "No entraste al Top 10 esta vez."
    messagebox.showinfo("Resultado", mensaje)
    nivel_var.set("FACIL")
    ir_al_menu()

# -----------------------------------------------------------
# MODO ESCUCHA Y TRANSMISION
# -----------------------------------------------------------

def empezar_modo_escucha():
    # Reinicia todo y empieza el juego en modo escucha
    global puntaje_a, puntaje_b, turno, frase_actual
    puntaje_a = 0
    puntaje_b = 0
    turno = "A"
    frase_actual = random.choice(frases)
    campo_respuesta_escucha.delete(0, tk.END)
    etiqueta_pts_a.config(text="Jugador A: 0 pts")
    etiqueta_pts_b.config(text="Jugador B: 0 pts")
    ir_a_escucha()
    preparar_turno()

def preparar_turno():
    # Configura la pantalla segun quien le toca y transmite la frase
    etiqueta_frase_escucha.config(text="Frase: " + frase_actual)
    etiqueta_aviso_escucha.config(text="Transmitiendo...", fg="yellow")
    boton_validar_escucha.config(state=tk.DISABLED)
    boton_leer_boton.config(state=tk.DISABLED)

    if turno == "A":
        etiqueta_turno.config(text="Turno: Jugador A - escribe en la PC", fg="#00ccff")
        campo_respuesta_escucha.config(state=tk.NORMAL)
        campo_respuesta_escucha.delete(0, tk.END)
    else:
        etiqueta_turno.config(text="Turno: Jugador B - usa el boton de la maqueta", fg="yellow")
        campo_respuesta_escucha.config(state=tk.DISABLED)

    # Enviar velocidad y luego la frase
    enviar_comando("VELOCIDAD:" + nivel_var.get())
    escribir_log("Turno " + turno + " | Frase: '" + frase_actual + "'")

    def cuando_termine():
        etiqueta_aviso_escucha.config(text="Listo para responder", fg="#00ff00")
        if turno == "A":
            boton_validar_escucha.config(state=tk.NORMAL)
            campo_respuesta_escucha.focus()
        else:
            boton_leer_boton.config(state=tk.NORMAL)

    enviar_frase_en_hilo(frase_actual, cuando_termine)

def validar_jugador_a():
    # Valida la respuesta del jugador A y pasa el turno al jugador B
    global puntaje_a, turno
    respuesta = campo_respuesta_escucha.get().strip().upper()
    puntos = calcular_puntaje(frase_actual, respuesta)
    puntaje_a += puntos
    etiqueta_pts_a.config(text="Jugador A: " + str(puntaje_a) + " pts")
    escribir_log("Jugador A: '" + respuesta + "' | +" + str(puntos) + " pts")

    # Ahora le toca al jugador B
    turno = "B"
    preparar_turno()

def leer_boton_jugador_b():
    # Activa la lectura del boton fisico para el jugador B
    global puntaje_b, turno, frase_actual
    boton_leer_boton.config(state=tk.DISABLED)
    etiqueta_aviso_escucha.config(text="Esperando boton...", fg="orange")
    escribir_log("Esperando entrada del Jugador B...")

    def cuando_llegue(resultado):
        global puntaje_b, turno, frase_actual
        puntos = calcular_puntaje(frase_actual, resultado)
        puntaje_b += puntos
        etiqueta_pts_b.config(text="Jugador B: " + str(puntaje_b) + " pts")
        escribir_log("Jugador B: '" + resultado + "' | +" + str(puntos) + " pts")

        # Mostrar quien gano esta ronda
        if puntaje_a >= puntaje_b:
            ganador = "Jugador A"
        else:
            ganador = "Jugador B"
        messagebox.showinfo("Resultado de Ronda",
            "Jugador A: " + str(puntaje_a) + " pts\n" +
            "Jugador B: " + str(puntaje_b) + " pts\n\n" +
            "Ganador: " + ganador)

        # Empezar nueva ronda con nueva frase
        turno = "A"
        frase_actual = random.choice(frases)
        campo_respuesta_escucha.config(state=tk.NORMAL)
        preparar_turno()

    pedir_boton_en_hilo(cuando_llegue)

# -----------------------------------------------------------
# EDITOR DE FRASES
# -----------------------------------------------------------

def abrir_editor():
    # Abre una ventana para que el usuario pueda cambiar las frases
    ventana = tk.Toplevel(root)
    ventana.title("Editar frases")
    ventana.configure(bg="#1a1a2e")
    ventana.geometry("300x420")

    tk.Label(ventana, text="Lista de frases",
             bg="#1a1a2e", fg="white", font=("Arial", 11, "bold")).pack(pady=8)
    tk.Label(ventana, text="Maximo 16 caracteres por frase",
             bg="#1a1a2e", fg="#888", font=("Arial", 9)).pack()

    # Crear un campo de texto por cada frase
    campos = []
    for i in range(10):
        fila = tk.Frame(ventana, bg="#1a1a2e")
        fila.pack(pady=2)
        tk.Label(fila, text=str(i + 1) + ".", bg="#1a1a2e", fg="#aaa", width=3).pack(side=tk.LEFT)
        campo = tk.Entry(fila, width=18)
        if i < len(frases):
            campo.insert(0, frases[i])
        campo.pack(side=tk.LEFT)
        campos.append(campo)

    def guardar_cambios():
        global frases
        # Leer lo que escribio el usuario en cada campo
        nuevas = []
        for campo in campos:
            texto = campo.get().strip().upper()
            if 1 <= len(texto) <= 16:
                nuevas.append(texto)
        if len(nuevas) == 0:
            messagebox.showwarning("Error", "Debe haber al menos una frase valida")
            return
        frases = nuevas
        guardar_frases()
        messagebox.showinfo("Listo", "Frases guardadas")
        ventana.destroy()

    tk.Button(ventana, text="Guardar", command=guardar_cambios,
              bg="#e94560", fg="white", width=14).pack(pady=12)

# -----------------------------------------------------------
# TOP 10
# -----------------------------------------------------------

def ver_top10():
    # Abre una ventana con los mejores puntajes
    ventana = tk.Toplevel(root)
    ventana.title("Top 10")
    ventana.configure(bg="#1a1a2e")
    ventana.geometry("260x340")

    tk.Label(ventana, text="Top 10", font=("Arial", 14, "bold"),
             bg="#1a1a2e", fg="#e94560").pack(pady=10)

    if len(top10) == 0:
        tk.Label(ventana, text="Todavia no hay puntajes",
                 bg="#1a1a2e", fg="white").pack(pady=20)
    else:
        for i, (nombre, pts) in enumerate(top10[:10]):
            linea = str(i + 1) + ". " + nombre + " - " + str(pts) + " pts"
            tk.Label(ventana, text=linea, bg="#1a1a2e", fg="yellow",
                     font=("Courier", 11)).pack(pady=2)

# -----------------------------------------------------------
# CONSTRUIR LA VENTANA PRINCIPAL
# -----------------------------------------------------------

root = tk.Tk()
root.title("StrangerTEC Morse Translator")
root.geometry("500x600")
root.configure(bg="#1a1a2e")
root.resizable(False, False)

# Variable para el nivel de dificultad (compartida entre pantallas)
nivel_var = tk.StringVar(value="FACIL")

# Contenedor donde van todas las pantallas apiladas
contenedor = tk.Frame(root, bg="#1a1a2e")
contenedor.pack(fill=tk.BOTH, expand=True)

# Crear las tres pantallas
pantalla_menu    = tk.Frame(contenedor, bg="#1a1a2e")
pantalla_simple  = tk.Frame(contenedor, bg="#1a1a2e")
pantalla_escucha = tk.Frame(contenedor, bg="#1a1a2e")

for pantalla in (pantalla_menu, pantalla_simple, pantalla_escucha):
    pantalla.place(relwidth=1, relheight=1)

# -----------------------------------------------------------
# PANTALLA MENU
# -----------------------------------------------------------

tk.Label(pantalla_menu, text="StrangerTEC",
         font=("Arial", 22, "bold"), bg="#1a1a2e", fg="#e94560").pack(pady=(30, 2))
tk.Label(pantalla_menu, text="Morse Translator",
         font=("Arial", 11), bg="#1a1a2e", fg="#888").pack(pady=(0, 6))
tk.Label(pantalla_menu, text="Daniel Solano  |  Aarón Umaña",
         font=("Arial", 9), bg="#1a1a2e", fg="#555").pack(pady=(0, 14))

# Fila de conexion
fila_ip = tk.Frame(pantalla_menu, bg="#1a1a2e")
fila_ip.pack(pady=4)
tk.Label(fila_ip, text="IP Pico W:", bg="#1a1a2e", fg="white").pack(side=tk.LEFT)
campo_ip = tk.Entry(fila_ip, width=16)
campo_ip.insert(0, SERVER_IP)
campo_ip.pack(side=tk.LEFT, padx=4)
boton_conectar = tk.Button(fila_ip, text="Conectar", command=conectar,
                            bg="#e94560", fg="white")
boton_conectar.pack(side=tk.LEFT)

etiqueta_estado = tk.Label(pantalla_menu, text="Desconectado", bg="#1a1a2e", fg="red")
etiqueta_estado.pack(pady=4)

# Selector de velocidad
fila_vel = tk.Frame(pantalla_menu, bg="#1a1a2e")
fila_vel.pack(pady=6)
tk.Label(fila_vel, text="Velocidad:", bg="#1a1a2e", fg="white").pack(side=tk.LEFT, padx=4)
for n in ["FACIL", "MEDIO", "DIFICIL"]:
    tk.Radiobutton(fila_vel, text=n, variable=nivel_var, value=n,
                   bg="#1a1a2e", fg="yellow", selectcolor="#333",
                   activebackground="#1a1a2e").pack(side=tk.LEFT, padx=6)

# Botones de modo y opciones
tk.Button(pantalla_menu, text="Modo Transmision Simple",
          command=empezar_modo_simple, width=28,
          bg="#16213e", fg="white", pady=8).pack(pady=6)
tk.Button(pantalla_menu, text="Modo Escucha y Transmision",
          command=empezar_modo_escucha, width=28,
          bg="#16213e", fg="white", pady=8).pack(pady=6)
tk.Button(pantalla_menu, text="Editar frases",
          command=abrir_editor, width=28,
          bg="#16213e", fg="#aaa", pady=6).pack(pady=4)
tk.Button(pantalla_menu, text="Ver Top 10",
          command=ver_top10, width=28,
          bg="#16213e", fg="yellow", pady=6).pack(pady=4)

# Caja de log
tk.Label(pantalla_menu, text="Log de comunicacion:", bg="#1a1a2e", fg="#444").pack(pady=(12, 0))
caja_log = tk.Text(pantalla_menu, height=5, width=56, bg="#090909",
                   fg="#00aa00", font=("Courier", 8), state=tk.DISABLED)
caja_log.pack(padx=8, pady=2)

# -----------------------------------------------------------
# PANTALLA MODO SIMPLE
# -----------------------------------------------------------

tk.Label(pantalla_simple, text="Modo Transmision Simple",
         font=("Arial", 13, "bold"), bg="#1a1a2e", fg="#e94560").pack(pady=14)

etiqueta_ronda = tk.Label(pantalla_simple, text="Ronda: 1 / 3",
                           bg="#1a1a2e", fg="#aaa")
etiqueta_ronda.pack()

etiqueta_frase_simple = tk.Label(pantalla_simple, text="Frase: ---",
                                  font=("Arial", 13), bg="#1a1a2e", fg="yellow")
etiqueta_frase_simple.pack(pady=6)

etiqueta_aviso_simple = tk.Label(pantalla_simple, text="",
                                  bg="#1a1a2e", fg="yellow", font=("Arial", 10))
etiqueta_aviso_simple.pack(pady=2)

tk.Label(pantalla_simple, text="Escribe lo que recibiste:",
         bg="#1a1a2e", fg="#aaa").pack(pady=(10, 2))

campo_respuesta_simple = tk.Entry(pantalla_simple, width=22, font=("Arial", 13))
campo_respuesta_simple.pack(pady=4)

etiqueta_puntos_simple = tk.Label(pantalla_simple, text="Puntaje: 0",
                                   font=("Arial", 12), bg="#1a1a2e", fg="#00ff00")
etiqueta_puntos_simple.pack(pady=6)

boton_validar_simple = tk.Button(pantalla_simple, text="Validar respuesta",
                                  command=validar_respuesta_simple,
                                  bg="#e94560", fg="white",
                                  font=("Arial", 11), pady=6, width=20,
                                  state=tk.DISABLED)
boton_validar_simple.pack(pady=8)

tk.Button(pantalla_simple, text="Volver al menu", command=ir_al_menu,
          bg="#333", fg="white").pack(pady=4)

# -----------------------------------------------------------
# PANTALLA MODO ESCUCHA
# -----------------------------------------------------------

tk.Label(pantalla_escucha, text="Modo Escucha y Transmision",
         font=("Arial", 13, "bold"), bg="#1a1a2e", fg="#e94560").pack(pady=10)

etiqueta_frase_escucha = tk.Label(pantalla_escucha, text="Frase: ---",
                                   font=("Arial", 13), bg="#1a1a2e", fg="yellow")
etiqueta_frase_escucha.pack(pady=4)

etiqueta_turno = tk.Label(pantalla_escucha, text="",
                           font=("Arial", 11), bg="#1a1a2e", fg="#00ccff")
etiqueta_turno.pack(pady=4)

# Fila de puntajes
fila_puntajes = tk.Frame(pantalla_escucha, bg="#1a1a2e")
fila_puntajes.pack(pady=4)
etiqueta_pts_a = tk.Label(fila_puntajes, text="Jugador A: 0 pts",
                           bg="#1a1a2e", fg="white", width=20)
etiqueta_pts_a.pack(side=tk.LEFT, padx=6)
etiqueta_pts_b = tk.Label(fila_puntajes, text="Jugador B: 0 pts",
                           bg="#1a1a2e", fg="white", width=20)
etiqueta_pts_b.pack(side=tk.LEFT, padx=6)

etiqueta_aviso_escucha = tk.Label(pantalla_escucha, text="",
                                   bg="#1a1a2e", fg="yellow", font=("Arial", 10))
etiqueta_aviso_escucha.pack(pady=4)

tk.Label(pantalla_escucha, text="Respuesta Jugador A:",
         bg="#1a1a2e", fg="#aaa").pack(pady=(6, 2))

campo_respuesta_escucha = tk.Entry(pantalla_escucha, width=22, font=("Arial", 13))
campo_respuesta_escucha.pack(pady=4)

boton_validar_escucha = tk.Button(pantalla_escucha, text="Validar (Jugador A)",
                                   command=validar_jugador_a,
                                   bg="#e94560", fg="white",
                                   pady=6, width=22, state=tk.DISABLED)
boton_validar_escucha.pack(pady=4)

boton_leer_boton = tk.Button(pantalla_escucha, text="Leer boton (Jugador B)",
                              command=leer_boton_jugador_b,
                              bg="#16213e", fg="yellow",
                              pady=6, width=22, state=tk.DISABLED)
boton_leer_boton.pack(pady=4)

tk.Button(pantalla_escucha, text="Volver al menu", command=ir_al_menu,
          bg="#333", fg="white").pack(pady=6)

# -----------------------------------------------------------
# ARRANCAR
# -----------------------------------------------------------

# Mostrar el menu al inicio
pantalla_menu.tkraise()
root.mainloop()
