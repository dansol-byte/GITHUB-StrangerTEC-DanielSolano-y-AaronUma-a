# main.py - MicroPython para Raspberry Pi Pico W
# StrangerTEC Morse Translator
import network
import socket
import time
from machine import Pin, PWM

# ─── CONFIGURACION WIFI ───────────────────────────────────────────────────────
SSID     = "NOMBRE_DE_TU_RED"   # <-- Cambia esto
PASSWORD = "TU_CONTRASENA"      # <-- Cambia esto
PORT     = 1717

# ─── PINES ────────────────────────────────────────────────────────────────────
DATA   = Pin(18, Pin.OUT)
CLOCK  = Pin(19, Pin.OUT)
COL0   = Pin(16, Pin.OUT)
BUTTON = Pin(15, Pin.IN, Pin.PULL_DOWN)
DIPSW  = Pin(17, Pin.IN, Pin.PULL_DOWN)
buzzer = PWM(Pin(14))
buzzer.duty_u16(0)

# ─── TIEMPOS ──────────────────────────────────────────────────────────────────
# Para LEDs: cuanto tiempo se ilumina cada letra (ms)
TIEMPO_LED = {
    "FACIL":   2000,
    "MEDIO":   1200,
    "DIFICIL": 700,
}

# Para buzzer Morse: duracion del punto en ms (raya = punto x 3)
TIEMPO_MORSE = {
    "FACIL":   600,
    "MEDIO":   350,
    "DIFICIL": 200,
}

velocidad_actual = "FACIL"

# ─── CODIGO MORSE ─────────────────────────────────────────────────────────────
MORSE = {
    'A':'.-',   'B':'-...','C':'-.-.','D':'-..',  'E':'.',
    'F':'..-.','G':'--.',  'H':'....','I':'..',   'J':'.---',
    'K':'-.-', 'L':'.-..','M':'--',  'N':'-.',   'O':'---',
    'P':'.--.','Q':'--.-','R':'.-.',  'S':'...',  'T':'-',
    'U':'..-', 'V':'...-','W':'.--', 'X':'-..-', 'Y':'-.--',
    'Z':'--..',
    '0':'-----','1':'.----','2':'..---','3':'...--','4':'....-',
    '5':'.....','6':'-....','7':'--...','8':'---..',  '9':'----.',
    '+':'.-.-.', '-':'-....-',
}

# Morse invertido para decodificar entrada del boton
MORSE_INV = {v: k for k, v in MORSE.items()}

# ─── LAYOUT DEL TABLERO ───────────────────────────────────────────────────────
TABLERO = {
    'A':(0,0), 'C':(0,1), 'E':(0,2), 'G':(0,3), 'I':(0,4),
    'K':(0,5), 'M':(0,6), 'O':(0,7), 'Q':(0,8), 'S':(0,9),
    'U':(0,10),'W':(0,11),'Y':(0,12),
    'B':(1,0), 'D':(1,1), 'F':(1,2), 'H':(1,3), 'J':(1,4),
    'L':(1,5), 'N':(1,6), 'P':(1,7), 'R':(1,8), 'T':(1,9),
    'V':(1,10),'X':(1,11),'Z':(1,12),
    '0':(2,0), '1':(2,1), '2':(2,2), '3':(2,3), '4':(2,4),
    '5':(2,5), '6':(2,6), '7':(2,7), '8':(2,8), '9':(2,9),
    '-':(2,10),'+':(2,11),
}

# ─── CONTROL DE REGISTROS ─────────────────────────────────────────────────────
def shift_out(data_16bits):
    for i in range(15, -1, -1):
        bit = (data_16bits >> i) & 1
        DATA.value(bit)
        CLOCK.value(1)
        time.sleep_us(10)
        CLOCK.value(0)
        time.sleep_us(10)

def apagar_todo():
    shift_out(0x0000)
    COL0.value(0)

def encender_led(fila, columna):
    apagar_todo()
    valor = 1 << fila
    if columna == 0:
        COL0.value(1)
    else:
        valor |= (1 << (columna + 2))
    shift_out(valor)

# ─── BUZZER ───────────────────────────────────────────────────────────────────
def buzzer_on():
    buzzer.freq(600)
    buzzer.duty_u16(30000)

def buzzer_off():
    buzzer.duty_u16(0)

# ─── TRANSMISION POR LED (switch OFF) ────────────────────────────────────────
def transmitir_frase_leds(frase):
    """
    Ilumina cada letra de la frase por X ms segun la dificultad.
    Pausa breve entre letras.
    """
    t_letra  = TIEMPO_LED[velocidad_actual]
    t_pausa  = 300  # ms de pausa entre letras

    for char in frase.upper():
        if char == ' ':
            time.sleep_ms(t_pausa * 2)
        elif char in TABLERO:
            fila, col = TABLERO[char]
            encender_led(fila, col)
            time.sleep_ms(t_letra)
            apagar_todo()
            time.sleep_ms(t_pausa)

    apagar_todo()

# ─── TRANSMISION POR BUZZER EN MORSE (switch ON) ─────────────────────────────
def transmitir_simbolo_morse(simbolo):
    """Punto o raya con el buzzer."""
    t = TIEMPO_MORSE[velocidad_actual]
    duracion = t if simbolo == '.' else t * 3
    buzzer_on()
    time.sleep_ms(duracion)
    buzzer_off()
    time.sleep_ms(t)  # pausa entre simbolos (1 unidad)

def transmitir_frase_morse(frase):
    """
    Transmite la frase en codigo Morse con el buzzer.
    Tiempos segun el PDF: punto=1u, raya=3u, entre simbolos=1u,
    entre letras=3u, entre palabras=7u.
    """
    t = TIEMPO_MORSE[velocidad_actual]

    for char in frase.upper():
        if char == ' ':
            time.sleep_ms(t * 4)  # 7u total (ya van 3 de la ultima letra)
        elif char in MORSE:
            for simbolo in MORSE[char]:
                transmitir_simbolo_morse(simbolo)
            time.sleep_ms(t * 2)  # completar 3u entre letras (ya va 1u)

    buzzer_off()

# ─── TRANSMISION PRINCIPAL ────────────────────────────────────────────────────
def transmitir_frase(frase):
    """Decide si transmitir por LED o por buzzer segun el switch."""
    modo = DIPSW.value()  # 0 = luces, 1 = sonido
    if modo == 0:
        transmitir_frase_leds(frase)
    else:
        transmitir_frase_morse(frase)

# ─── LECTURA MORSE DEL BOTON (entrada jugador B) ─────────────────────────────
def leer_morse_boton():
    """
    Lee la entrada del boton y devuelve la frase en texto.
    Presion corta  = punto  (< 2.5 unidades)
    Presion larga  = raya   (>= 2.5 unidades)
    Pausa media    = fin de letra (>= 3 unidades)
    Pausa larga    = fin de palabra (>= 7 unidades)
    Sin actividad 10 unidades = fin de frase
    """
    t = TIEMPO_MORSE[velocidad_actual]
    umbral_raya    = int(t * 2.5)
    umbral_letra   = t * 3
    umbral_palabra = t * 7
    umbral_fin     = t * 10

    simbolos_letra  = []
    frase_resultado = ""
    ultima_accion   = time.ticks_ms()

    while True:
        if BUTTON.value() == 1:
            t_inicio = time.ticks_ms()
            buzzer_on()  # suena mientras el jugador mantiene presionado el boton

            # Esperar que suelten
            while BUTTON.value() == 1:
                time.sleep_ms(10)

            buzzer_off()  # deja de sonar cuando sueltan
            duracion = time.ticks_diff(time.ticks_ms(), t_inicio)
            simbolo  = '.' if duracion < umbral_raya else '-'
            simbolos_letra.append(simbolo)
            ultima_accion = time.ticks_ms()

        else:
            pausa = time.ticks_diff(time.ticks_ms(), ultima_accion)

            if pausa >= umbral_fin:
                # Fin de frase
                if simbolos_letra:
                    codigo = ''.join(simbolos_letra)
                    frase_resultado += MORSE_INV.get(codigo, '?')
                    simbolos_letra = []
                break

            elif pausa >= umbral_palabra and simbolos_letra:
                # Fin de palabra
                codigo = ''.join(simbolos_letra)
                frase_resultado += MORSE_INV.get(codigo, '?') + ' '
                simbolos_letra  = []
                ultima_accion   = time.ticks_ms()

            elif pausa >= umbral_letra and simbolos_letra:
                # Fin de letra
                codigo = ''.join(simbolos_letra)
                frase_resultado += MORSE_INV.get(codigo, '?')
                simbolos_letra  = []
                ultima_accion   = time.ticks_ms()

        time.sleep_ms(10)

    return frase_resultado.strip()

# ─── WIFI ─────────────────────────────────────────────────────────────────────
def conectar_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)
    print("Conectando a WiFi", end="")
    for _ in range(20):
        if wlan.isconnected():
            break
        print(".", end="")
        time.sleep(0.5)
    if wlan.isconnected():
        ip = wlan.ifconfig()[0]
        print("\nConectado! IP:", ip)
        return ip
    print("\nError: no se pudo conectar")
    return None

# ─── SERVIDOR TCP ─────────────────────────────────────────────────────────────
def iniciar_servidor(ip):
    global velocidad_actual
    s = socket.socket()
    s.bind((ip, PORT))
    s.listen(1)
    print("Esperando conexion en {}:{}".format(ip, PORT))

    while True:
        conn, addr = s.accept()
        print("Cliente conectado:", addr)
        conn.send("OK:Conectado a Pico W\n".encode())

        while True:
            try:
                data = conn.recv(1024)
                if not data:
                    break
                msg = data.decode().strip()
                print("Cmd:", msg)

                # ── Encender LED individual ───────────────────────────────
                if msg.startswith("LED:"):
                    try:
                        p = msg.split(":")
                        f = int(p[1][1:])
                        c = int(p[2][1:])
                        if 0 <= f <= 2 and 0 <= c <= 12:
                            encender_led(f, c)
                            conn.send("OK:LED encendido\n".encode())
                        else:
                            conn.send("ERROR:Fuera de rango\n".encode())
                    except:
                        conn.send("ERROR:Formato invalido\n".encode())

                # ── Transmitir frase (LED o Morse segun switch) ───────────
                elif msg.startswith("FRASE:"):
                    frase = msg[6:]
                    modo  = "luces" if DIPSW.value() == 0 else "sonido"
                    conn.send("OK:Transmitiendo en {}\n".format(modo).encode())
                    transmitir_frase(frase)
                    conn.send("OK:Fin transmision\n".encode())

                # ── Cambiar velocidad ─────────────────────────────────────
                elif msg.startswith("VELOCIDAD:"):
                    nivel = msg[10:].strip()
                    if nivel in TIEMPO_LED:
                        velocidad_actual = nivel
                        conn.send("OK:Velocidad {}\n".format(nivel).encode())
                    else:
                        conn.send("ERROR:Nivel invalido\n".encode())

                # ── Leer boton del jugador B ──────────────────────────────
                elif msg == "LEER_BOTON":
                    conn.send("OK:Esperando boton\n".encode())
                    resultado = leer_morse_boton()
                    conn.send("RESULTADO:{}\n".format(resultado).encode())

                # ── Apagar todo ───────────────────────────────────────────
                elif msg == "APAGAR":
                    apagar_todo()
                    buzzer_off()
                    conn.send("OK:Apagado\n".encode())

                else:
                    conn.send("ERROR:Comando desconocido\n".encode())

            except Exception as e:
                print("Error:", e)
                break

        conn.close()
        apagar_todo()
        buzzer_off()
        print("Desconectado, esperando...")

# ─── MAIN ─────────────────────────────────────────────────────────────────────
apagar_todo()
buzzer_off()
ip = conectar_wifi()
if ip:
    iniciar_servidor(ip)
