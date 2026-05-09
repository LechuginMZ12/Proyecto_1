import tkinter as tk
from tkinter import messagebox
import time
import os
from PIL import Image, ImageTk

# ========================
# SISTEMA DE MUSICA - Windows MCI via ctypes
# Usa winmm.dll (incluido en Windows) para reproducir MP3.
# El bucle infinito se implementa con ventana.after()
# comprobando cada 500ms si la cancion termino para reiniciarla.
# ========================
import ctypes
import ctypes.wintypes

_cancion_actual = None       # nombre de archivo de la cancion activa (None = silencio)
_alias_mci      = "bgmusic"  # alias fijo para el dispositivo MCI abierto

# Rutas relativas de cada cancion de combate, indexadas por numero de zona (1-5)
_CANCIONES_COMBATE = {
    1: "sounds/Comabate1.mp3",
    2: "sounds/Comabate2.mp3",
    3: "sounds/Comabate3.mp3",
    4: "sounds/Comabate4.mp3",
    5: "sounds/Comabate5.mp3",
}
_CANCION_INICIO = "sounds/Inicio_.mp3"   # musica del menu principal y seleccion
_CANCION_MAPA   = "sounds/Mapa_1.mp3"    # musica de la pantalla de mapa


def _mci(comando):
    """Envia un comando al subsistema MCI de Windows y devuelve el codigo de error."""
    try:
        winmm = ctypes.windll.winmm
        ret = winmm.mciSendStringW(comando, None, 0, 0)
        return ret
    except Exception as e:
        print(f"[MUSICA] Error MCI: {e}")
        return -1


def _ruta_corta(ruta_larga):
    """Convierte una ruta larga a formato corto 8.3 de Windows para evitar
    problemas con espacios y acentos en MCI."""
    buf = ctypes.create_unicode_buffer(512)
    ctypes.windll.kernel32.GetShortPathNameW(ruta_larga, buf, 512)
    resultado = buf.value
    # Si GetShortPathName devuelve vacio o igual, usar la original
    return resultado if resultado else ruta_larga


def detener_musica():
    """Detiene y cierra el dispositivo MCI activo."""
    global _cancion_actual
    _cancion_actual = None
    _mci(f"stop {_alias_mci}")
    _mci(f"close {_alias_mci}")


def _verificar_y_reiniciar(archivo, ruta_corta):
    """
    Revisa via MCI si la cancion termino y la reinicia desde el principio.
    Se llama recursivamente con ventana.after().
    """
    if _cancion_actual != archivo:
        return  # cambiaron de cancion o se detuvo
    buf_pos = ctypes.create_unicode_buffer(64)
    buf_dur = ctypes.create_unicode_buffer(64)
    ctypes.windll.winmm.mciSendStringW(
        f"status {_alias_mci} position", buf_pos, 64, 0)
    ctypes.windll.winmm.mciSendStringW(
        f"status {_alias_mci} length",   buf_dur, 64, 0)
    try:
        pos = int(buf_pos.value)
        dur = int(buf_dur.value)
        if dur > 0 and pos >= dur - 200:
            _mci(f"seek {_alias_mci} to start")
            _mci(f"play {_alias_mci}")
    except Exception:
        pass
    ventana.after(500, lambda: _verificar_y_reiniciar(archivo, ruta_corta))


def reproducir_musica(nombre_clave):
    """
    Abre y reproduce un MP3 usando Windows MCI (winmm.dll).
    Usa rutas cortas 8.3 para evitar problemas con espacios y acentos.
    El bucle se gestiona con ventana.after().
    nombre_clave: 'inicio', 'mapa', o int 1-5 (zona de combate).
    """
    global _cancion_actual

    if isinstance(nombre_clave, int):
        archivo = _CANCIONES_COMBATE.get(nombre_clave)
    elif nombre_clave == "inicio":
        archivo = _CANCION_INICIO
    elif nombre_clave == "mapa":
        archivo = _CANCION_MAPA
    else:
        archivo = None

    if archivo is None:
        return

    detener_musica()

    ruta_abs  = os.path.abspath(os.path.join(BASE_DIR, archivo))
    ruta_mci  = _ruta_corta(ruta_abs)   

    if not os.path.isfile(ruta_abs):
        print(f"[MUSICA] Archivo no encontrado: {ruta_abs}")
        return

    print(f"[MUSICA] Abriendo: {ruta_mci}")
    err = _mci(f'open "{ruta_mci}" type mpegvideo alias {_alias_mci}')
    if err != 0:
        print(f"[MUSICA] Error MCI {err} al abrir: {ruta_mci}")
        return

    err = _mci(f"play {_alias_mci}")
    if err != 0:
        print(f"[MUSICA] Error MCI {err} al reproducir")
        return

    _cancion_actual = archivo
    print(f"[MUSICA] Reproduciendo: {archivo}")
    ventana.after(500, lambda: _verificar_y_reiniciar(archivo, ruta_mci))


# Directorio base del script para rutas relativas
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def abs_ruta(relativa):
    """Convierte una ruta relativa en absoluta desde el directorio del script."""
    return os.path.join(BASE_DIR, relativa)

# ========================
# CARGA DE PERSONAJES DESDE ARCHIVO
# Cada funcion lee o parsea de forma recursiva.
# El archivo Personajes.txt tiene una linea por personaje con el formato:
#   nombre, vida, ataque, defensa, carpeta, rango_atk, rango_morir, rango_caminar
# donde los rangos son "inicio-fin" que se expanden a listas de numeros de frame.
# ========================

def cargar_lineas(archivo, lineas):
    """Lee recursivamente todas las líneas del archivo hasta EOF."""
    linea = archivo.readline()
    if not linea:
        return lineas
    lineas.append(linea.strip())
    return cargar_lineas(archivo, lineas)

def parsear_rango(rango_str):
    """Convierte '1-5' en lista [1,2,3,4,5] de forma recursiva."""
    partes = rango_str.strip().split("-")
    inicio = int(partes[0])
    fin    = int(partes[1])
    return construir_rango(inicio, fin, [])

def construir_rango(actual, fin, resultado):
    """Agrega recursivamente cada entero del rango al resultado."""
    if actual > fin:
        return resultado
    resultado.append(actual)
    return construir_rango(actual + 1, fin, resultado)

def parsear_personajes(lineas, i, resultado):
    """Parsea recursivamente las lineas validas en tuplas (nombre,vida,atk,def,carpeta,frames_atk,frames_morir,frames_caminar)."""
    if i >= len(lineas):
        return resultado
    linea = lineas[i]
    if linea == "" or linea.startswith("#"):
        return parsear_personajes(lineas, i + 1, resultado)
    partes = linea.split(",")
    if len(partes) == 8:
        nombre   = partes[0].strip()
        vida     = int(partes[1].strip())
        ataque   = int(partes[2].strip())
        defensa  = int(partes[3].strip())
        carpeta  = partes[4].strip()
        f_atk    = parsear_rango(partes[5])
        f_morir  = parsear_rango(partes[6])
        f_caminar= parsear_rango(partes[7])
        resultado.append((nombre, vida, ataque, defensa, carpeta, f_atk, f_morir, f_caminar))
    return parsear_personajes(lineas, i + 1, resultado)

def leer_personajes(ruta):
    """Abre el archivo y devuelve la lista de tuplas de personajes."""
    with open(ruta, "r", encoding="utf-8") as f:
        lineas = cargar_lineas(f, [])
    return parsear_personajes(lineas, 0, [])

def parsear_avatares(lineas, i, resultado):
    """Parsea recursivamente las lineas en tuplas (nombre, carpeta, archivo)."""
    if i >= len(lineas):
        return resultado
    linea = lineas[i]
    if linea == "" or linea.startswith("#"):
        return parsear_avatares(lineas, i + 1, resultado)
    partes = linea.split(",")
    if len(partes) == 3:
        resultado.append((partes[0].strip(), partes[1].strip(), partes[2].strip()))
    return parsear_avatares(lineas, i + 1, resultado)

def leer_avatares(ruta_archivo):
    """Lee el archivo de avatares y devuelve lista de tuplas (nombre, archivo)."""
    with open(ruta_archivo, "r", encoding="utf-8") as f:
        lineas = cargar_lineas(f, [])
    return parsear_avatares(lineas, 0, [])

# ========================
# DATOS DE PERSONAJES
# ========================
personajes = leer_personajes(abs_ruta("Personajes.txt"))

seleccionados = []
botones_personajes = {}
avatar_elegido = None
puntaje = 0

# Base de datos de personajes
def construir_stats(lista, i, resultado):
    """Construye recursivamente el diccionario de stats de todos los personajes."""
    if i >= len(lista):
        return resultado
    p = lista[i]
    resultado[p[0]] = {
        "vida":      p[1],
        "atk":       p[2],
        "def":       p[3],
        "carpeta":   p[4],
        "f_atk":     p[5],
        "f_morir":   p[6],
        "f_caminar": p[7],
    }
    return construir_stats(lista, i + 1, resultado)

stats_personajes = construir_stats(personajes, 0, {})

# ========================
# GENERACION ALEATORIA DE HOLLOWS 
# ========================

def mezclar_lista(lista, i, semilla):
    """Mezcla recursivamente la lista usando time como semilla."""
    if i <= 0:
        return lista
    semilla = int((semilla * 1.618033) % 1 * 1000000)
    j = semilla % (i + 1)
    lista[i], lista[j] = lista[j], lista[i]
    return mezclar_lista(lista, i - 1, semilla)

def construir_hollows(nombres, i, resultado):
    """Agrupa recursivamente los nombres en sublistas de 3."""
    if i >= len(nombres):
        return resultado
    grupo = [nombres[i], nombres[i + 1], nombres[i + 2]]
    resultado.append(grupo)
    return construir_hollows(nombres, i + 3, resultado)

def extraer_nombres(lista_personajes, i, resultado):
    """Extrae recursivamente los nombres de la lista de tuplas."""
    if i >= len(lista_personajes):
        return resultado
    resultado.append(lista_personajes[i][0])
    return extraer_nombres(lista_personajes, i + 1, resultado)

def generar_hollows():
    """Devuelve 5 grupos de 3 personajes aleatorios sin repeticion."""
    nombres = extraer_nombres(personajes, 0, [])
    semilla = (time.time() % 1) * 1000000
    mezclar_lista(nombres, len(nombres) - 1, semilla)
    return construir_hollows(nombres, 0, [])

hollows = generar_hollows()

# ========================
# SISTEMA DE ANIMACION
# Cada personaje tiene tres acciones: caminar, atk (ataque) y morir.
# Los frames de cada accion se cargan como PhotoImage desde disco y se cachean
# en cache_imagenes para no releerlos en cada batalla.
# La animacion avanza con ventana.after() (recursion indirecta).
# Tambien se cargan versiones volteadas (flip) para el enemigo que aparece a la derecha.
# ========================

# Cache global: {nombre_personaje: {accion: [PhotoImage, ...]}}
# Las claves de accion son: "atk", "morir", "caminar" y sus variantes "_flip"
cache_imagenes = {}

def cargar_frames_accion(carpeta, lista_nums, i, resultado, size, flip=False):
    """Carga recursivamente los frames de una accion desde disco.
    carpeta: subcarpeta con los PNG numerados del personaje.
    lista_nums: lista de indices de frame a cargar (ej. [1,2,3]).
    flip: si True, voltea la imagen horizontalmente (para el personaje enemigo).
    """
    if i >= len(lista_nums):
        return resultado
    num  = lista_nums[i]
    ruta = abs_ruta(os.path.join(carpeta, f"{num}.png"))
    img  = Image.open(ruta).convert("RGBA").resize(size, Image.LANCZOS)
    if flip:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    resultado.append(ImageTk.PhotoImage(img))
    return cargar_frames_accion(carpeta, lista_nums, i + 1, resultado, size, flip)

def cargar_personaje_imagenes(nombre, size=(320, 320)):
    """Carga y cachea frames normales y volteados de un personaje.
    Si el personaje ya esta en cache, no hace nada (evita recargas).
    Carga las tres acciones (atk, morir, caminar) en ambas orientaciones.
    """
    if nombre in cache_imagenes:
        return
    data    = stats_personajes[nombre]
    carpeta = data["carpeta"]
    cache_imagenes[nombre] = {
        "atk":          cargar_frames_accion(carpeta, data["f_atk"],     0, [], size, False),
        "morir":        cargar_frames_accion(carpeta, data["f_morir"],   0, [], size, False),
        "caminar":      cargar_frames_accion(carpeta, data["f_caminar"], 0, [], size, False),
        # Versiones espejadas para mostrar al enemigo mirando hacia la izquierda
        "atk_flip":     cargar_frames_accion(carpeta, data["f_atk"],     0, [], size, True),
        "morir_flip":   cargar_frames_accion(carpeta, data["f_morir"],   0, [], size, True),
        "caminar_flip": cargar_frames_accion(carpeta, data["f_caminar"], 0, [], size, True),
    }

def precargar_personajes(lista, i):
    """Precarga recursivamente las imagenes de una lista de nombres.
    Se llama antes de iniciar el combate para evitar retardos al mostrar sprites.
    """
    if i >= len(lista):
        return
    cargar_personaje_imagenes(lista[i])
    precargar_personajes(lista, i + 1)

# Estado de animacion de cada personaje en pantalla (jugador y enemigo)
# Cada estado guarda: nombre del personaje, accion actual, frame actual y job de after()
anim_jugador  = {"nombre": None, "accion": "caminar", "frame": 0, "job": None}
anim_enemigo  = {"nombre": None, "accion": "caminar", "frame": 0, "job": None}

def animar(estado, label, intervalo=120):
    """Avanza un frame de animacion y se reprograma recursivamente via after().
    - Si la accion es 'morir', se congela en el ultimo frame.
    - Si la accion es 'atk' y termino, vuelve automaticamente a 'caminar'.
    - El intervalo en ms controla la velocidad de la animacion.
    """
    if estado["nombre"] is None:
        return
    nombre = estado["nombre"]
    accion = estado["accion"]
    # Selecciona la clave correcta del cache (normal o volteada)
    clave  = accion + ("_flip" if estado.get("flip") else "")
    frames = cache_imagenes.get(nombre, {}).get(clave, [])
    if not frames:
        return
    idx = estado["frame"] % len(frames)
    label.config(image=frames[idx])
    label.image = frames[idx]   # mantener referencia para evitar garbage collection
    estado["frame"] += 1
    # Animacion de morir: parar en el ultimo frame
    if accion == "morir" and estado["frame"] >= len(frames):
        estado["frame"] = len(frames) - 1
        return
    # Animacion de ataque: al terminar, volver a caminar
    if accion == "atk" and estado["frame"] >= len(frames):
        iniciar_animacion(estado, label, nombre, "caminar", estado.get("flip", False))
        return
    # Programar el siguiente frame con after()
    estado["job"] = frame_combate.after(intervalo, lambda: animar(estado, label, intervalo))

def iniciar_animacion(estado, label, nombre, accion, flip=False):
    """Cancela la animacion anterior e inicia una nueva desde el frame 0.
    Se usa al cambiar de personaje, al atacar o al morir.
    """
    if estado["job"] is not None:
        frame_combate.after_cancel(estado["job"])
        estado["job"] = None
    cargar_personaje_imagenes(nombre)   # no-op si ya esta en cache
    estado["nombre"] = nombre
    estado["accion"] = accion
    estado["frame"]  = 0
    estado["flip"]   = flip
    animar(estado, label)

# ========================
# ESTADO GLOBAL DEL JUEGO
# Estas variables se comparten entre todas las funciones de logica.
# Se modifican con "global" en cada funcion que las necesite escribir.
# ========================
pj              = None   # personaje activo del jugador (dict con vida, atk, etc.)
enemigo         = None   # personaje activo del hollow/enemigo
equipo_jugador  = []     # lista de dicts de los 3 personajes elegidos por el jugador
equipo_hollow   = []     # lista de dicts de los 3 personajes del hollow actual

indice_actual_jugador = 0      # indice en equipo_jugador del personaje activo
modo_defensa_jugador  = False  # True si el jugador eligio Defender este turno
modo_defensa_enemigo  = False  # True si el hollow eligio defender (aleatorio)
indice_accion         = 0      # contador auxiliar para secuencia de acciones del turno

juego_iniciado  = False   # True si ya se cargo el equipo del jugador al menos una vez
zona_actual    = 0        # numero de zona en combate (1-5)
zonas_vencidas = []       # zonas cuyo hollow ya fue derrotado
tabla_puntajes = []       # historial de partidas: [{"nombre", "puntaje", "resultado"}]

# ========================
# FUNCIONES DE NAVEGACION
# Controlan las transiciones entre pantallas (frames de Tkinter).
# Cada funcion oculta el frame actual y muestra el siguiente.
# ========================

def iniciar_juego():
    nombre = entrada_nombre.get()
    if nombre == "":
        messagebox.showwarning("Advertencia", "Ingresa tu nombre")
    else:
        frame_inicio.pack_forget()
        frame_seleccion.pack(fill="both", expand=True)
        # Musica de menu sigue sonando (ya esta activa desde frame_inicio)

def mostrar_about():
    messagebox.showinfo("About", "Tecnológico de Costa Rica, " \
                        "Estudiante: Randall Mora Zamora, "
                        "Profesor: Ellioth Ramirez Trejos, " \
                        "Materia: Introducción a la programación, "
                        "Grupo: 5, " \
                        "Projecto 1: Un juego de combate por turnos, " \
                        "El sistema de combate funciona así: el jugador elige 3 personajes de una lista de 15, " \
                        "cada uno con estadísticas de Vida, Ataque y Defensa. En cada zona enfrenta al Hollow local en duelos uno a uno, " \
                        "ganando quien deje al otro en KO. El Hollow actúa de forma completamente aleatoria. Gana el bando que se quede " \
                        "con todos los personajes del contrario.")

def ir_a_avatar():
    frame_seleccion.pack_forget()
    frame_avatar.pack(fill="both", expand=True)

def ir_a_mapa():
    global puntaje
    puntaje = len(seleccionados) * 100
    frame_avatar.pack_forget()
    frame_mapa.pack(fill="both", expand=True)
    actualizar_perfil()
    reproducir_musica("mapa")

def actualizar_perfil():
    label_nombre.config(text=f"Nombre: {entrada_nombre.get()}")
    # Mostrar imagen del avatar seleccionado usando busqueda recursiva
    img = buscar_img_avatar(avatar_elegido, 0)
    if img:
        label_avatar.config(image=img, width=80, height=80)
        label_avatar.image = img
    else:
        label_avatar.config(text="?", width=8, height=3)
    label_puntaje.config(text=f"Puntaje: {puntaje}")

# ========================
# SELECCION DE PERSONAJE
# ========================

# Guarda el estado de animacion de cada tarjeta: {nombre: {"frame":0,"job":None}}
anim_seleccion = {}

def animar_seleccion(nombre, label, intervalo=150):
    """Anima el frame de caminar en la pantalla de seleccion usando ventana.after."""
    if nombre not in cache_imagenes:
        return
    frames = cache_imagenes[nombre].get("caminar", [])
    if not frames:
        return
    estado = anim_seleccion[nombre]
    idx = estado["frame"] % len(frames)
    label.config(image=frames[idx])
    label.image = frames[idx]
    estado["frame"] += 1
    estado["job"] = ventana.after(intervalo, lambda: animar_seleccion(nombre, label, intervalo))

def crear_personaje(frame, nombre, vida, dano, defensa, fila, columna):
    # Colores de la tarjeta de seleccion
    BG_CARD  = "#1a1a2e"   # fondo principal de la tarjeta
    BG_STATS = "#16213e"   # fondo del bloque de estadisticas
    FG_TITLE = "#f0a500"   # color del nombre del personaje
    FG_STAT  = "#a0c4ff"   # color de los valores de stats

    # Marco exterior de la tarjeta
    contenedor = tk.Frame(frame, bd=1, relief="solid", bg=BG_CARD, padx=4, pady=4)
    contenedor.grid(row=fila, column=columna, padx=5, pady=5)

    # --- Imagen animada del personaje (120x120) ---
    # Se precarga en cache para la animacion de seleccion
    cargar_personaje_imagenes(nombre, size=(120, 120))
    anim_seleccion[nombre] = {"frame": 0, "job": None}

    # Canvas que contiene el label de imagen animada
    canvas_img = tk.Canvas(contenedor, width=120, height=120,
                           bg="#0d0d1a", highlightthickness=0)
    canvas_img.pack()

    # Label flotante sobre el canvas: recibe los PhotoImage de la animacion
    label_img = tk.Label(canvas_img, bg="#0d0d1a")
    label_img.place(x=0, y=0, width=120, height=120)
    animar_seleccion(nombre, label_img)   # arranca la animacion de caminar

    # Nombre del personaje (reemplaza _ por espacios para mejor lectura)
    tk.Label(contenedor, text=nombre.replace("_", " "),
             font=("Arial", 9, "bold"), bg=BG_CARD, fg=FG_TITLE,
             width=14).pack(pady=(2, 0))

    # Bloque de estadisticas: vida, ataque y defensa en una sola linea
    tk.Label(contenedor, text=f"HP: {vida}   ATK: {dano}   DEF: {defensa}",
             font=("Arial", 8), bg=BG_STATS, fg=FG_STAT,
             width=18, pady=3).pack(fill="x")

    # Boton para agregar el personaje al equipo del jugador
    boton = tk.Button(contenedor, text="+ Elegir",
                      font=("Arial", 8, "bold"), bg="#0f3460", fg="white",
                      activebackground="#e94560", activeforeground="white",
                      relief="flat", padx=4, pady=3,
                      command=lambda: seleccionar_personaje(nombre))
    boton.pack(pady=3)

    # Guardar referencia al boton para poder deshabilitarlo/reactivarlo luego
    botones_personajes[nombre] = boton

def seleccionar_personaje(nombre):
    if nombre not in seleccionados and len(seleccionados) < 3:
        seleccionados.append(nombre)
        botones_personajes[nombre].config(
            state="disabled",
            bg="red",
            text="Seleccionado"
        )
        actualizar_panel()
    elif len(seleccionados) >= 3:
        messagebox.showwarning("Limite", "Solo puedes elegir 3 personajes")

def deseleccionar_personaje(indice):
    if len(seleccionados) > indice:
        nombre = seleccionados[indice]
        seleccionados.pop(indice)
        botones_personajes[nombre].config(
            state="normal",
            bg="#0f3460",
            fg="white",
            text="+ Elegir"
        )
        actualizar_panel()

def actualizar_panel():
    if len(seleccionados) >= 1:
        slot1.config(text=seleccionados[0])
    else:
        slot1.config(text="Vacio")

    if len(seleccionados) >= 2:
        slot2.config(text=seleccionados[1])
    else:
        slot2.config(text="Vacio")

    if len(seleccionados) == 3:
        slot3.config(text=seleccionados[2])
        boton_continuar.config(state="normal")
    else:
        slot3.config(text="Vacio")
        boton_continuar.config(state="disabled")

# ========================
# SELECCION DE AVATAR
# ========================

def colorear_hijos(hijos, i, color):
    """Cambia recursivamente el fondo de los widgets hijos de una card."""
    if i >= len(hijos):
        return
    try:
        hijos[i].config(bg=color)
    except Exception:
        pass
    colorear_hijos(hijos, i + 1, color)

def resaltar_card(card, activo):
    """Cambia el fondo de una card y sus hijos para el highlight."""
    color = "#1b5e20" if activo else "#16213e"
    card.config(bg=color)
    colorear_hijos(card.winfo_children(), 0, color)

def resetear_cards(i):
    """Resetea recursivamente el fondo de todas las cards."""
    if i >= len(cards_avatares):
        return
    resaltar_card(cards_avatares[i], False)
    resetear_cards(i + 1)

def encontrar_card(nombre, i):
    """Busca recursivamente la card que corresponde al nombre dado."""
    if i >= len(imgs_avatares_lista):
        return None
    if imgs_avatares_lista[i][0] == nombre:
        return cards_avatares[i]
    return encontrar_card(nombre, i + 1)

def buscar_img_avatar(nombre, i):
    """Busca recursivamente la imagen del avatar por nombre en imgs_avatares_lista."""
    if i >= len(imgs_avatares_lista):
        return None
    if imgs_avatares_lista[i][0] == nombre:
        return imgs_avatares_lista[i][1]
    return buscar_img_avatar(nombre, i + 1)

def seleccionar_avatar(nombre):
    global avatar_elegido
    avatar_elegido = nombre
    resetear_cards(0)
    card = encontrar_card(nombre, 0)
    if card:
        resaltar_card(card, True)
    boton_empezar.config(state="normal")

# ========================
# FUNCIONES RECURSIVAS
# ========================

def ya_existe(nombre, lista, i):
    """Comprueba recursivamente si 'nombre' ya existe en la lista."""
    if i >= len(lista):
        return False
    if lista[i]["nombre"] == nombre:
        return True
    return ya_existe(nombre, lista, i + 1)

def restaurar_o_agregar(nombre, equipo, i):
    """
    Si el personaje ya existe en el equipo (aunque este en KO),
    le restaura la vida completa. Si no existe, lo agrega nuevo.
    """
    data = stats_personajes[nombre]
    if i >= len(equipo):
        # No estaba en la lista, agregar nuevo
        equipo.append({
            "nombre": nombre,
            "vida":   data["vida"],
            "atk":    data["atk"],
            "def":    data["def"]
        })
        return
    if equipo[i]["nombre"] == nombre:
        # Ya existe, restaurar vida
        equipo[i]["vida"] = data["vida"]
        return
    restaurar_o_agregar(nombre, equipo, i + 1)

def copiar_equipo(lista, i, resultado):
    """Copia recursivamente una lista de nombres a dicts con stats completos."""
    if i >= len(lista):
        return resultado

    nombre = lista[i]
    data   = stats_personajes[nombre]

    nuevo = {
        "nombre": nombre,
        "vida":   data["vida"],
        "atk":    data["atk"],
        "def":    data["def"]
    }

    resultado.append(nuevo)
    return copiar_equipo(lista, i + 1, resultado)

def obtener_personaje_vivo(equipo, i):
    """Devuelve el primer personaje vivo a partir del indice i."""
    if i >= len(equipo):
        return None
    if equipo[i]["vida"] > 0:
        return equipo[i]
    return obtener_personaje_vivo(equipo, i + 1)

# ========================
# COMBATE
# El flujo es: iniciar_combate → iniciar_ronda → turno (jugador elige) →
# IA elige accion → se calcula daño → se actualiza UI → si alguien cae,
# se captura su personaje y se llama de nuevo a iniciar_ronda (recursion via after).
# Cuando un equipo queda sin personajes vivos se llama a fin_juego().
# Formula de daño: max(1, ATK_atacante - DEF_defensor)
# ========================

def iniciar_combate(pos):
    """Prepara y muestra la pantalla de combate para la zona indicada.
    Resetea el estado de turno, actualiza los perfiles visuales,
    arma el equipo del hollow de esa zona y lanza la primera ronda.
    """
    global equipo_jugador, equipo_hollow
    global pj, enemigo
    global indice_actual_jugador
    global modo_defensa_jugador, modo_defensa_enemigo
    global juego_iniciado, zona_actual
    zona_actual = pos

    pj = None
    enemigo = None
    indice_actual_jugador = 0
    modo_defensa_jugador = False
    modo_defensa_enemigo = False

    frame_mapa.pack_forget()
    frame_combate.pack(fill="both", expand=True)
    reproducir_musica(pos)  # Cancion de combate segun la zona (1-5)

    # --- Actualizar perfiles superiores ---
    # Perfil del jugador: avatar elegido
    img_av = buscar_img_avatar(avatar_elegido, 0)
    if img_av:
        label_perfil_avatar.config(image=img_av)
        label_perfil_avatar.image = img_av
    label_perfil_nombre_jugador.config(text=entrada_nombre.get() or "Jugador")
    label_perfil_zona.config(text=f"Zona {pos}")

    # Perfil del hollow: imagen segun zona (1-5)
    img_h = imgs_hollows[pos - 1]
    label_perfil_hollow_img.config(image=img_h)
    label_perfil_hollow_img.image = img_h
    label_perfil_nombre_hollow.config(text=f"Hollow {pos}")
    label_perfil_zona_hollow.config(text=f"Zona {pos}")

    # El equipo del jugador se crea solo la primera vez
    if not juego_iniciado:
        equipo_jugador[:] = copiar_equipo(seleccionados, 0, [])
        juego_iniciado = True

    # Cada zona tiene su propio hollow de 3 personajes (pos va de 1 a 5)
    indice_hollow = pos - 1
    equipo_hollow[:] = construir_equipo_hollow(hollows[indice_hollow], 0, [])

    iniciar_ronda()

def construir_equipo_hollow(lista_nombres, i, resultado):
    """Crea recursivamente el equipo del hollow con vida restaurada."""
    if i >= len(lista_nombres):
        return resultado
    nombre = lista_nombres[i]
    data = stats_personajes[nombre]
    resultado.append({
        "nombre": nombre,
        "vida":   data["vida"],
        "atk":    data["atk"],
        "def":    data["def"]
    })
    return construir_equipo_hollow(lista_nombres, i + 1, resultado)

# crear_hollow_global y agregar_lista_hollow eliminados:
# cada zona ahora construye su propio equipo en iniciar_combate.

def elegir_enemigo_aleatorio():
    """Selecciona aleatoriamente un personaje vivo del equipo hollow.
    Usa los microsegundos del reloj del sistema como fuente de aleatoriedad.
    """
    vivos = obtener_indices_vivos(equipo_hollow, 0, [])
    if not vivos:
        return None
    t    = time.time()
    nano = int((t % 1) * 1000000)
    index = nano % len(vivos)
    return equipo_hollow[vivos[index]]


def obtener_indices_vivos(equipo, i, resultado):
    """Recorre recursivamente el equipo y acumula los indices de los vivos."""
    if i >= len(equipo):
        return resultado
    if equipo[i]["vida"] > 0:
        resultado.append(i)
    return obtener_indices_vivos(equipo, i + 1, resultado)


def iniciar_ronda():
    """Selecciona o actualiza el personaje activo de cada bando y arranca las animaciones.
    Si el personaje del jugador cayo en la ronda anterior, toma el siguiente vivo.
    Llama a fin_juego si alguno de los dos equipos queda sin personajes.
    """
    global pj, enemigo

    # Si el jugador no tiene personaje activo o cayo, asignar el proximo vivo
    if pj is None or pj["vida"] <= 0:
        pj = obtener_personaje_vivo(equipo_jugador, 0)

    # El hollow siempre elige un personaje vivo de forma aleatoria
    enemigo = elegir_enemigo_aleatorio()

    if pj is None:
        fin_juego(False)   # jugador sin personajes → derrota
        return
    if enemigo is None:
        fin_juego(True)    # hollow sin personajes → victoria
        return

    actualizar_ui()
    # Arrancar animacion de caminar para ambos personajes
    if pj:
        precargar_personajes([pj["nombre"]], 0)
        iniciar_animacion(anim_jugador, label_img_jugador, pj["nombre"], "caminar")
    if enemigo:
        precargar_personajes([enemigo["nombre"]], 0)
        iniciar_animacion(anim_enemigo, label_img_enemigo, enemigo["nombre"], "caminar", flip=True)


def calcular_dano(atk, defensa):
    """Calcula el daño segun la formula del proyecto: max(1, ATK - DEF)."""
    dano = atk - defensa
    return dano if dano > 0 else 1


def elegir_accion_ai_aleatoria():
    """Elige la accion del Hollow usando microsegundos del reloj.
    Las opciones son: ataque normal, ataque fuerte (x1.5) o defensa.
    """
    acciones = ["normal", "fuerte", "defensa"]
    timestamp    = time.time()
    nanosegundos = int((timestamp % 1) * 1000000)
    indice       = nanosegundos % len(acciones)
    return acciones[indice]


def turno(tipo):
    """Procesa un turno completo: accion del jugador seguida de la del hollow.
    tipo: 'normal' | 'fuerte' | 'defensa'
    - normal: ataque con ATK base.
    - fuerte: ataque con ATK x1.5.
    - defensa: duplica la DEF del jugador para el siguiente golpe recibido.
    Si un personaje cae en KO, pasa al equipo contrario con vida restaurada
    y se inicia una nueva ronda 500 ms despues (via after).
    """
    global modo_defensa_jugador, modo_defensa_enemigo
    global pj, enemigo, equipo_jugador, equipo_hollow, puntaje

    # ---- ACCION DEL JUGADOR ----
    atk_jugador     = pj["atk"]
    defensa_enemigo = enemigo["def"]

    if tipo == "fuerte":
        atk_jugador = int(atk_jugador * 1.5)   # ataque fuerte: +50% de daño

    if tipo == "defensa":
        modo_defensa_jugador = True   # el jugador se defiende este turno
    else:
        if modo_defensa_enemigo:
            defensa_enemigo      = defensa_enemigo * 2   # hollow estaba defendiendo
            modo_defensa_enemigo = False

        dano = calcular_dano(atk_jugador, defensa_enemigo)
        enemigo["vida"] -= dano
        if enemigo["vida"] < 0:
            enemigo["vida"] = 0

        iniciar_animacion(anim_jugador, label_img_jugador, pj["nombre"], "atk")
        actualizar_ui()

        # Enemigo en KO: el jugador lo captura y gana 1 punto
        if enemigo["vida"] <= 0:
            iniciar_animacion(anim_enemigo, label_img_enemigo, enemigo["nombre"], "morir", flip=True)
            nombre = enemigo["nombre"]
            restaurar_o_agregar(nombre, equipo_jugador, 0)
            puntaje += 1
            actualizar_perfil()
            frame_combate.after(500, iniciar_ronda)   # nueva ronda con retardo
            return

    # ---- ACCION DE LA IA (HOLLOW) ----
    accion = elegir_accion_ai_aleatoria()

    atk_enemigo     = enemigo["atk"]
    defensa_jugador = pj["def"]

    if accion == "fuerte":
        atk_enemigo = int(atk_enemigo * 1.5)

    if accion == "defensa":
        modo_defensa_enemigo = True
    else:
        if modo_defensa_jugador:
            defensa_jugador      = defensa_jugador * 2   # jugador estaba defendiendo
            modo_defensa_jugador = False

        dano = calcular_dano(atk_enemigo, defensa_jugador)
        pj["vida"] -= dano
        if pj["vida"] < 0:
            pj["vida"] = 0

        iniciar_animacion(anim_enemigo, label_img_enemigo, enemigo["nombre"], "atk", flip=True)
        actualizar_ui()

        # Jugador en KO: el hollow lo captura
        if pj["vida"] <= 0:
            iniciar_animacion(anim_jugador, label_img_jugador, pj["nombre"], "morir")
            nombre = pj["nombre"]
            restaurar_o_agregar(nombre, equipo_hollow, 0)
            frame_combate.after(500, iniciar_ronda)
            return

    actualizar_ui()


def mostrar_roster_en_combate():
    """Muestra cuántos personajes vivos tiene cada equipo durante el combate."""
    vivos_jugador  = contar_vivos(equipo_jugador, 0)
    vivos_hollow   = contar_vivos(equipo_hollow, 0)
    
    label_roster.config(text=f"Tu equipo: {vivos_jugador}/3  |  Hollow: {vivos_hollow}/3")

def contar_vivos(equipo, i):
    """Cuenta recursivamente personajes con vida > 0."""
    if i >= len(equipo):
        return 0
    vivos = 1 if equipo[i]["vida"] > 0 else 0
    return vivos + contar_vivos(equipo, i + 1)


# capturar_jugador y capturar_personaje integradas directamente en turno()


def fin_juego(gano):
    """
    Se llama cuando un bando se queda sin personajes vivos.
    gano=True  -> el jugador derroto al Hollow.
    gano=False -> el jugador perdio todos sus personajes.
    """
    global puntaje, juego_iniciado

    frame_combate.pack_forget()

    if gano:
        puntaje += 300
        actualizar_perfil()
        juego_iniciado = True
        bloquear_zona(zona_actual)
        # Si ya derroto los 5 hollows, va a resultados
        if len(zonas_vencidas) == 5:
            detener_musica()
            mostrar_resultados("Completo los 5 Hollows!")
        else:
            reproducir_musica("mapa")  # Vuelve la musica del mapa al ganar
            frame_mapa.pack(fill="both", expand=True)
            messagebox.showinfo("Victoria", "Derrotaste al Hollow! +300 puntos")
    else:
        detener_musica()
        mostrar_resultados("Derrota - Sin personajes")


def ocultar_frames(lista, i):
    """Oculta recursivamente una lista de frames."""
    if i >= len(lista):
        return
    lista[i].pack_forget()
    ocultar_frames(lista, i + 1)

def mostrar_resultados(razon):
    """Registra el puntaje y muestra la pantalla de resultados."""
    global tabla_puntajes
    nombre = entrada_nombre.get()
    tabla_puntajes.append({
        "nombre":    nombre if nombre else "Anonimo",
        "puntaje":   puntaje,
        "resultado": razon
    })
    ocultar_frames([frame_combate, frame_mapa, frame_inicio], 0)
    actualizar_tabla_puntajes()
    frame_resultados.pack(fill="both", expand=True)

def actualizar_tabla_puntajes():
    """Reconstruye recursivamente las filas de la tabla en el frame."""
    destruir_hijos(frame_tabla.winfo_children(), 0)
    # Encabezado
    tk.Label(frame_tabla, text="Nombre",    width=15, font=("Arial",10,"bold"), relief="ridge").grid(row=0, column=0)
    tk.Label(frame_tabla, text="Puntaje",   width=10, font=("Arial",10,"bold"), relief="ridge").grid(row=0, column=1)
    tk.Label(frame_tabla, text="Resultado", width=25, font=("Arial",10,"bold"), relief="ridge").grid(row=0, column=2)
    agregar_filas(tabla_puntajes, 0)

def agregar_filas(lista, i):
    """Agrega recursivamente una fila por entrada en la tabla."""
    if i >= len(lista):
        return
    entrada = lista[i]
    fila = i + 1
    tk.Label(frame_tabla, text=entrada["nombre"],    width=15, relief="ridge").grid(row=fila, column=0)
    tk.Label(frame_tabla, text=entrada["puntaje"],   width=10, relief="ridge").grid(row=fila, column=1)
    tk.Label(frame_tabla, text=entrada["resultado"], width=25, relief="ridge").grid(row=fila, column=2)
    agregar_filas(lista, i + 1)

def reiniciar():
    """Resetea todo el estado y vuelve a la pantalla de inicio."""
    global pj, enemigo, equipo_jugador, equipo_hollow
    global indice_actual_jugador, modo_defensa_jugador, modo_defensa_enemigo
    global juego_iniciado, zona_actual, zonas_vencidas, puntaje
    global seleccionados, avatar_elegido, hollows

    pj                    = None
    enemigo               = None
    equipo_jugador[:]     = []
    equipo_hollow[:]      = []
    indice_actual_jugador = 0
    modo_defensa_jugador  = False
    modo_defensa_enemigo  = False
    juego_iniciado        = False
    zona_actual           = 0
    zonas_vencidas[:]     = []
    puntaje               = 0
    seleccionados[:]      = []
    avatar_elegido        = None
    hollows               = generar_hollows()

    # Resetear botones del mapa
    resetear_botones_zona(botones_zona, 0)
    # Resetear botones de seleccion de personajes
    resetear_botones_personajes(0)
    # Limpiar entrada de nombre
    entrada_nombre.delete(0, tk.END)

    frame_resultados.pack_forget()
    frame_inicio.pack(fill="both", expand=True)
    reproducir_musica("inicio")  # Musica de inicio al volver al menu

def resetear_botones_zona(lista, i):
    """Reactiva recursivamente los botones de zona del mapa."""
    if i >= len(lista):
        return
    lista[i].config(state="normal", bg="SystemButtonFace", text=f"Zona {i+1}")
    resetear_botones_zona(lista, i + 1)

def resetear_botones_personajes(i):
    """Resetea recursivamente los botones de seleccion de personajes."""
    if i >= len(personajes):
        return
    nombre = personajes[i][0]
    if nombre in botones_personajes:
        botones_personajes[nombre].config(state="normal", bg="#0f3460", fg="white", text="+ Elegir")
    resetear_botones_personajes(i + 1)

def fin_combate(gano):
    """Compatibilidad: redirige a fin_juego."""
    fin_juego(gano)



# ========================
# CAMBIO DE PERSONAJE
# El jugador puede hacer clic en los botones de su equipo (parte inferior
# del frame de combate) para cambiar al siguiente personaje vivo.
# elegir_personaje(indice) activa el personaje por su posicion en equipo_jugador.
# ========================

def elegir_personaje(indice):
    """Activa el personaje en la posicion dada si esta vivo."""
    global pj, indice_actual_jugador
    if indice < len(equipo_jugador):
        personaje = equipo_jugador[indice]
        if personaje["vida"] > 0:
            pj = personaje
            indice_actual_jugador = indice
            actualizar_ui()
        else:
            messagebox.showwarning("KO", "Ese personaje esta derrotado")

def cambiar_personaje():
    """Busca y activa el proximo personaje vivo distinto del actual."""
    buscar_cambio(0)

def buscar_cambio(i):
    """Recorre recursivamente el equipo hasta encontrar un personaje vivo diferente al actual."""
    global pj, indice_actual_jugador
    if i >= len(equipo_jugador):
        return
    personaje = equipo_jugador[i]
    if personaje["vida"] > 0 and i != indice_actual_jugador:
        pj = personaje
        indice_actual_jugador = i
        actualizar_ui()
        return
    buscar_cambio(i + 1)

# ========================
# UI DE COMBATE
# actualizar_ui() sincroniza todos los elementos visuales del combate
# (nombres, barras de vida, botones del equipo) con el estado actual.
# Las barras cambian de color segun el % de vida restante.
# ========================

def actualizar_ui():
    """Actualiza nombres, barras de vida y botones del equipo en pantalla."""
    if pj:
        label_nombre_jugador.config(text=f"{pj['nombre']} (HP:{pj['vida']})")
        max_vida = stats_personajes[pj["nombre"]]["vida"]
        actualizar_barra(barra_jugador, pj["vida"], max_vida)

    if enemigo:
        label_nombre_enemigo.config(text=f"{enemigo['nombre']} (HP:{enemigo['vida']})")
        max_vida = stats_personajes[enemigo["nombre"]]["vida"]
        actualizar_barra(barra_enemigo, enemigo["vida"], max_vida)

    reconstruir_botones_equipo()
    mostrar_roster_en_combate()

def reconstruir_botones_equipo():
    """Destruye y recrea recursivamente los botones del equipo del jugador.
    Se llama cada turno para reflejar cambios de vida y estado (KO/activo).
    """
    destruir_hijos(frame_personajes.winfo_children(), 0)
    crear_botones_equipo(0)

def destruir_hijos(lista, i):
    """Destruye recursivamente los widgets de una lista."""
    if i >= len(lista):
        return
    lista[i].destroy()
    destruir_hijos(lista, i + 1)

def crear_botones_equipo(i):
    """Crea recursivamente un boton por cada personaje del equipo del jugador.
    Los personajes en KO se muestran en gris y deshabilitados.
    """
    if i >= len(equipo_jugador):
        return
    p      = equipo_jugador[i]
    texto  = f"{p['nombre']}\nHP:{p['vida']}"
    estado = "disabled" if p["vida"] <= 0 else "normal"
    color  = "gray" if p["vida"] <= 0 else "SystemButtonFace"
    btn = tk.Button(frame_personajes, text=texto, width=12,
                    bg=color, state=estado,
                    command=lambda idx=i: elegir_personaje(idx))
    btn.grid(row=0, column=i, padx=5)
    crear_botones_equipo(i + 1)

def actualizar_boton(boton, indice):
    """Mantenido por compatibilidad; ya no se usa directamente."""
    if indice < len(equipo_jugador):
        p     = equipo_jugador[indice]
        texto = f"{p['nombre']}\nHP:{p['vida']}"
        boton.config(text=texto)
        estado = "disabled" if p["vida"] <= 0 else "normal"
        boton.config(state=estado)
    else:
        boton.config(text="---", state="disabled")

def actualizar_barra(canvas, vida_actual, vida_max):
    """Redibuja la barra de vida: verde >50%, amarillo >25%, rojo <=25%."""
    canvas.delete("all")
    vida_actual = max(vida_actual, 0)
    vida_max    = vida_max if vida_max > 0 else 1
    porcentaje  = vida_actual / vida_max
    ancho       = int(250 * porcentaje)
    color = "green"
    if porcentaje < 0.5:
        color = "yellow"
    if porcentaje < 0.25:
        color = "red"
    canvas.create_rectangle(0, 0, ancho, 20, fill=color)

def animar_golpe(label, color="red", delay=150):
    """Destella el fondo del label brevemente para indicar que recibio daño."""
    try:
        original = label.cget("bg")
        if original == "":
            original = "SystemButtonFace"
    except Exception:
        original = "SystemButtonFace"
    label.config(bg=color)
    frame_combate.after(delay, lambda: label.config(bg=original))

# ========================
# VENTANA PRINCIPAL
# Configuracion inicial de la ventana Tkinter: titulo, tamaño y fondo.
# Todos los frames (inicio, seleccion, avatar, mapa, combate, resultados)
# se apilan en la misma ventana; solo uno es visible a la vez via pack/pack_forget.
# ========================
ventana = tk.Tk()
ventana.title("Siegius")
ventana.geometry("1100x720")
ventana.resizable(True, True)

# ========================
# IMAGENES DE AVATARES
# ========================
def cargar_img_avatar(ruta_archivo, size=(180, 180)):
    """Carga y redimensiona la imagen de un avatar al tamano indicado."""
    img = Image.open(ruta_archivo).convert("RGBA").resize(size, Image.LANCZOS)
    return ImageTk.PhotoImage(img)

def cargar_imgs_avatares(lista, i, resultado):
    """Carga recursivamente las imagenes de la lista de avatares."""
    if i >= len(lista):
        return resultado
    nombre, carpeta, archivo = lista[i]
    resultado.append((nombre, cargar_img_avatar(abs_ruta(f"{carpeta}/{archivo}"))))
    return cargar_imgs_avatares(lista, i + 1, resultado)

# Leer avatares desde archivo y cargar imagenes
datos_avatares = leer_avatares(abs_ruta("Avatares.txt"))
imgs_avatares_lista = cargar_imgs_avatares(datos_avatares, 0, [])

# Acceso rapido por indice para compatibilidad con el resto del codigo
img_avatar1 = imgs_avatares_lista[0][1]
img_avatar2 = imgs_avatares_lista[1][1]
img_avatar3 = imgs_avatares_lista[2][1]

# ========================
# IMAGENES DE HOLLOWS (perfil por zona)
# Se cargan al inicio todas las imagenes de los 5 Hollows con recursion.
# Se muestran en la esquina superior derecha de la pantalla de combate.
# ========================
def cargar_img_hollow(num, size=(90, 90)):
    """Carga la imagen de perfil del Hollow de la zona indicada (1-5)."""
    ruta = abs_ruta(os.path.join("Hollows", f"Hollow {num}.png"))
    img  = Image.open(ruta).convert("RGBA").resize(size, Image.LANCZOS)
    return ImageTk.PhotoImage(img)

def cargar_imgs_hollows(num, resultado):
    """Carga recursivamente las imagenes de los 5 hollows (base: num > 5)."""
    if num > 5:
        return resultado
    resultado.append(cargar_img_hollow(num))
    return cargar_imgs_hollows(num + 1, resultado)

# Lista indexada 0-4 → zona 1-5
imgs_hollows = cargar_imgs_hollows(1, [])

# ========================
# FRAME INICIO (pantalla de bienvenida)
# Primera pantalla del juego: muestra el logo, un campo para el nombre
# y los botones INICIAR y About. La musica de inicio comienza aqui.
# ========================
frame_inicio = tk.Frame(ventana, bg="#0d0d1a")

_img_titulo_pil = Image.open(abs_ruta("Fondos/Titulo.png")).convert("RGBA")
img_titulo_tk = ImageTk.PhotoImage(_img_titulo_pil)
label_titulo = tk.Label(frame_inicio, image=img_titulo_tk, bg="#0d0d1a")
label_titulo.image = img_titulo_tk  # evitar garbage collection
label_titulo.pack(pady=20)

tk.Label(frame_inicio, text="Ingresa tu nombre:",
         font=("Arial", 11), bg="#0d0d1a", fg="#e0e0e0").pack()

entrada_nombre = tk.Entry(frame_inicio, font=("Arial", 12),
                          bg="#1a1a2e", fg="#e0e0e0", insertbackground="#e0e0e0",
                          relief="flat", width=22)
entrada_nombre.pack(pady=10, ipady=4)

tk.Button(frame_inicio, text="INICIAR",
          font=("Arial", 12, "bold"), bg="#0f3460", fg="white",
          activebackground="#e94560", relief="flat", width=14,
          command=iniciar_juego).pack(pady=8)

tk.Button(frame_inicio, text="About",
          font=("Arial", 9), bg="#16213e", fg="#888",
          activebackground="#1a1a2e", relief="flat", width=10,
          command=mostrar_about).pack(pady=2)

frame_inicio.pack(fill="both", expand=True)

# ========================
# FRAME SELECCION (pantalla de eleccion de equipo)
# Muestra una grilla scrollable con las 15 tarjetas de personajes.
# El panel lateral derecho muestra los 3 slots del equipo elegido.
# Al seleccionar 3 personajes se habilita el boton CONTINUAR.
# ========================
BG_SEL = "#0d0d1a"
frame_seleccion = tk.Frame(ventana, bg=BG_SEL)

# Titulo
tk.Label(frame_seleccion, text="-- ELIGE TU EQUIPO --",
         font=("Arial", 13, "bold"), bg=BG_SEL, fg="#f0a500"
         ).pack(pady=6)

# Contenedor principal: grilla scrollable + panel lateral
frame_sel_main = tk.Frame(frame_seleccion, bg=BG_SEL)
frame_sel_main.pack(fill="both", expand=True, padx=8)

# ---- Panel lateral (primero para que tome el lado derecho) ----
frame_lateral = tk.Frame(frame_sel_main, bd=2, relief="solid",
                          bg="#16213e", padx=10, width=160)
frame_lateral.pack(side="right", fill="y", padx=6, pady=4)
frame_lateral.pack_propagate(False)

# --- Canvas con scrollbar para la grilla ---
scrollbar_sel = tk.Scrollbar(frame_sel_main, orient="vertical")
canvas_sel = tk.Canvas(frame_sel_main, bg=BG_SEL, highlightthickness=0,
                        yscrollcommand=scrollbar_sel.set)
scrollbar_sel.config(command=canvas_sel.yview)

scrollbar_sel.pack(side="right", fill="y")
canvas_sel.pack(side="left", fill="both", expand=True)

# Frame interior dentro del canvas (aqui van las tarjetas)
frame_grilla = tk.Frame(canvas_sel, bg=BG_SEL)
canvas_sel.create_window((0, 0), window=frame_grilla, anchor="nw")

def actualizar_scroll(event):
    canvas_sel.configure(scrollregion=canvas_sel.bbox("all"))
frame_grilla.bind("<Configure>", actualizar_scroll)

def scroll_rueda(event):
    canvas_sel.yview_scroll(int(-1*(event.delta/120)), "units")
canvas_sel.bind("<MouseWheel>", scroll_rueda)

tk.Label(frame_lateral, text="EQUIPO", font=("Arial", 11, "bold"),
         bg="#16213e", fg="#f0a500").pack(pady=8)

slot1 = tk.Label(frame_lateral, text="[ Vacio ]", bg="#1a1a2e", fg="#888",
                 font=("Arial", 9), width=14, height=3)
slot1.pack(pady=4)
slot1.bind("<Button-1>", lambda e: deseleccionar_personaje(0))

slot2 = tk.Label(frame_lateral, text="[ Vacio ]", bg="#1a1a2e", fg="#888",
                 font=("Arial", 9), width=14, height=3)
slot2.pack(pady=4)
slot2.bind("<Button-1>", lambda e: deseleccionar_personaje(1))

slot3 = tk.Label(frame_lateral, text="[ Vacio ]", bg="#1a1a2e", fg="#888",
                 font=("Arial", 9), width=14, height=3)
slot3.pack(pady=4)
slot3.bind("<Button-1>", lambda e: deseleccionar_personaje(2))

tk.Label(frame_lateral, text="(clic para deseleccionar)",
         font=("Arial", 7), bg="#16213e", fg="#555").pack()

boton_continuar = tk.Button(frame_lateral, text="CONTINUAR >>",
                             state="disabled", command=ir_a_avatar,
                             bg="#0f3460", fg="white", font=("Arial", 10, "bold"),
                             relief="flat", padx=8)
boton_continuar.pack(pady=14)

# ========================
# FRAME AVATAR (pantalla de eleccion de representante)
# Muestra las cards de los 3 avatares disponibles.
# El jugador hace clic en uno para seleccionarlo (se resalta en verde).
# Al seleccionar uno se habilita el boton EMPEZAR que lleva al mapa.
# ========================
frame_avatar = tk.Frame(ventana, bg="#0d0d1a")

tk.Label(frame_avatar, text="-- ELIGE TU AVATAR --",
         font=("Arial", 18, "bold"), bg="#0d0d1a", fg="#f0a500").pack(pady=30)

tk.Label(frame_avatar, text="Tu representante en el mundo",
         font=("Arial", 10), bg="#0d0d1a", fg="#888").pack(pady=2)

frame_avatares = tk.Frame(frame_avatar, bg="#0d0d1a")
frame_avatares.pack(pady=20)

# Contenedor de cada avatar: imagen + nombre
def crear_card_avatar(parent, texto, img, col):
    card = tk.Frame(parent, bg="#16213e", padx=8, pady=8, cursor="hand2")
    card.grid(row=0, column=col, padx=15)
    lbl_img = tk.Label(card, image=img, bg="#16213e")
    lbl_img.pack()
    lbl_nom = tk.Label(card, text=texto, bg="#16213e", fg="#e0e0e0",
                       font=("Arial", 11, "bold"))
    lbl_nom.pack(pady=4)
    return card

# Crear cards dinámicamente desde datos_avatares
cards_avatares = []

def crear_cards_avatares(i):
    """Crea recursivamente las cards de avatar desde datos_avatares."""
    if i >= len(imgs_avatares_lista):
        return
    nombre, img = imgs_avatares_lista[i]
    card = crear_card_avatar(frame_avatares, nombre, img, i)
    cards_avatares.append(card)
    crear_cards_avatares(i + 1)

crear_cards_avatares(0)

# Compatibilidad con el resto del codigo
card_av1 = cards_avatares[0]
card_av2 = cards_avatares[1]
card_av3 = cards_avatares[2]
avatar1 = card_av1
avatar2 = card_av2
avatar3 = card_av3

def bind_hijos(hijos, i, nombre):
    """Vincula recursivamente el click en todos los hijos de una card."""
    if i >= len(hijos):
        return
    hijos[i].bind("<Button-1>", lambda e, n=nombre: seleccionar_avatar(n))
    bind_hijos(hijos, i + 1, nombre)

def bind_card(card, nombre):
    """Vincula el click en toda la card y sus hijos."""
    card.bind("<Button-1>", lambda e: seleccionar_avatar(nombre))
    bind_hijos(card.winfo_children(), 0, nombre)

def vincular_cards(i):
    """Vincula recursivamente los clicks de cada card."""
    if i >= len(cards_avatares):
        return
    nombre = imgs_avatares_lista[i][0]
    bind_card(cards_avatares[i], nombre)
    vincular_cards(i + 1)

vincular_cards(0)

boton_empezar = tk.Button(frame_avatar, text="EMPEZAR >>",
                           state="disabled", command=ir_a_mapa,
                           font=("Arial", 12, "bold"), bg="#0f3460", fg="white",
                           activebackground="#e94560", relief="flat",
                           width=14, pady=6)
boton_empezar.pack(pady=20)

# ========================
# FRAME MAPA (pantalla de navegacion entre zonas)
# Muestra la imagen del mapa con 5 botones posicionados sobre ella.
# Cada boton lleva al combate de su zona. Las zonas vencidas quedan
# bloqueadas en rojo. El perfil del jugador aparece en la esquina superior.
# ========================
frame_mapa = tk.Frame(ventana, bg="#0d0d1a")

tk.Label(frame_mapa, text="-- MAPA DEL MUNDO --",
         font=("Arial", 16, "bold"), bg="#0d0d1a", fg="#f0a500").pack(pady=8)

frame_perfil = tk.Frame(frame_mapa, bg="#16213e", padx=12, pady=8)
frame_perfil.place(x=10, y=10)

label_nombre = tk.Label(frame_perfil, text="Nombre:",
                         font=("Arial", 9), bg="#16213e", fg="#e0e0e0")
label_nombre.pack()

label_avatar = tk.Label(frame_perfil, bg="#1a1a2e")
label_avatar.pack(pady=4)

label_puntaje = tk.Label(frame_perfil, text="Puntaje: 0",
                          font=("Arial", 9, "bold"), bg="#16213e", fg="#f0a500")
label_puntaje.pack()

# ---- Canvas del mapa con imagen de fondo ----
# El canvas ocupa el centro del frame; los botones se colocan encima con place()
MAPA_W = 860
MAPA_H = 550

canvas_mapa = tk.Canvas(frame_mapa, width=MAPA_W, height=MAPA_H,
                         highlightthickness=0, bg="#0d0d1a")
canvas_mapa.pack(pady=4)

# Cargar y escalar la imagen del mapa
_img_mapa_pil = Image.open(abs_ruta("Fondos/mapa.png")).convert("RGBA").resize(
    (MAPA_W, MAPA_H), Image.LANCZOS
)
img_mapa_tk = ImageTk.PhotoImage(_img_mapa_pil)

# Dibujar la imagen centrada en el canvas
canvas_mapa.create_image(MAPA_W // 2, MAPA_H // 2, anchor="center", image=img_mapa_tk)

def bloquear_zona(pos):
    """Marca la zona como vencida y deshabilita su boton en rojo."""
    if pos not in zonas_vencidas:
        zonas_vencidas.append(pos)
    botones_zona[pos - 1].config(state="disabled", bg="#8b0000", fg="white",
                                  text=f"Zona {pos}\nVencida")

def mover(pos):
    if pos in zonas_vencidas:
        messagebox.showwarning("Zona bloqueada", f"Ya derrotaste al Hollow de la Zona {pos}!")
        return
    iniciar_combate(pos)

# Posiciones de los botones sobre el mapa (coordenadas relativas al canvas)
# Se usan .place() con in_=canvas_mapa para quedar encima de la imagen
ubicacion1 = tk.Button(canvas_mapa, text="Zona 1", width=7, height=1,
                       font=("Arial", 8, "bold"), bg="#0f3460", fg="white",
                       activebackground="#e94560", relief="flat",
                       cursor="hand2", command=lambda: mover(1))
ubicacion1.place(x=320, y=140)

ubicacion2 = tk.Button(canvas_mapa, text="Zona 2", width=7, height=1,
                       font=("Arial", 8, "bold"), bg="#0f3460", fg="white",
                       activebackground="#e94560", relief="flat",
                       cursor="hand2", command=lambda: mover(2))
ubicacion2.place(x=290, y=200)

ubicacion3 = tk.Button(canvas_mapa, text="Zona 3", width=7, height=1,
                       font=("Arial", 8, "bold"), bg="#0f3460", fg="white",
                       activebackground="#e94560", relief="flat",
                       cursor="hand2", command=lambda: mover(3))
ubicacion3.place(x=400, y=210)

ubicacion4 = tk.Button(canvas_mapa, text="Zona 4", width=7, height=1,
                       font=("Arial", 8, "bold"), bg="#0f3460", fg="white",
                       activebackground="#e94560", relief="flat",
                       cursor="hand2", command=lambda: mover(4))
ubicacion4.place(x=410, y=270)

ubicacion5 = tk.Button(canvas_mapa, text="Zona 5", width=7, height=1,
                       font=("Arial", 8, "bold"), bg="#0f3460", fg="white",
                       activebackground="#e94560", relief="flat",
                       cursor="hand2", command=lambda: mover(5))
ubicacion5.place(x=340, y=310)

# Lista de botones indexada para poder bloquearlos por posicion
botones_zona = [ubicacion1, ubicacion2, ubicacion3, ubicacion4, ubicacion5]

# ========================
# FRAME COMBATE (pantalla de batalla por turnos)
# Estructura visual:
#   - frame_perfiles: barra superior con avatar del jugador (izq) y hollow (der)
#   - frame_top: sprites animados del personaje activo de cada bando
#   - barras de vida sobre cada sprite
#   - label_roster: contador de personajes vivos por equipo
#   - frame_acciones: botones Ataque / Ataque Fuerte / Defender
#   - frame_personajes: botones del equipo del jugador (se reconstruyen cada turno)
# ========================
BG_COMBATE = "#1a1a2e"

frame_combate = tk.Frame(ventana, bg=BG_COMBATE)

# ---- Perfiles superiores: jugador (izq) y hollow (der) ----
frame_perfiles = tk.Frame(frame_combate, bg=BG_COMBATE)
frame_perfiles.pack(fill="x", padx=16, pady=(8, 0))

# Perfil jugador - izquierda
frame_perfil_jugador = tk.Frame(frame_perfiles, bg="#16213e", padx=6, pady=4)
frame_perfil_jugador.pack(side="left")

label_perfil_avatar = tk.Label(frame_perfil_jugador, bg="#16213e")
label_perfil_avatar.pack(side="left", padx=(0, 6))

frame_perfil_jugador_texto = tk.Frame(frame_perfil_jugador, bg="#16213e")
frame_perfil_jugador_texto.pack(side="left")

label_perfil_nombre_jugador = tk.Label(frame_perfil_jugador_texto,
                                        text="Jugador", font=("Arial", 9, "bold"),
                                        bg="#16213e", fg="#f0a500")
label_perfil_nombre_jugador.pack(anchor="w")

label_perfil_zona = tk.Label(frame_perfil_jugador_texto,
                              text="Zona -", font=("Arial", 8),
                              bg="#16213e", fg="#a0c4ff")
label_perfil_zona.pack(anchor="w")

# Perfil hollow - derecha
frame_perfil_hollow = tk.Frame(frame_perfiles, bg="#16213e", padx=6, pady=4)
frame_perfil_hollow.pack(side="right")

frame_perfil_hollow_texto = tk.Frame(frame_perfil_hollow, bg="#16213e")
frame_perfil_hollow_texto.pack(side="left")

label_perfil_nombre_hollow = tk.Label(frame_perfil_hollow_texto,
                                       text="Hollow", font=("Arial", 9, "bold"),
                                       bg="#16213e", fg="#e94560")
label_perfil_nombre_hollow.pack(anchor="e")

label_perfil_zona_hollow = tk.Label(frame_perfil_hollow_texto,
                                     text="Zona -", font=("Arial", 8),
                                     bg="#16213e", fg="#a0c4ff")
label_perfil_zona_hollow.pack(anchor="e")

label_perfil_hollow_img = tk.Label(frame_perfil_hollow, bg="#16213e")
label_perfil_hollow_img.pack(side="left", padx=(6, 0))

frame_top = tk.Frame(frame_combate, bg=BG_COMBATE)
frame_top.pack(pady=10)

# Jugador
frame_jugador = tk.Frame(frame_top, bg=BG_COMBATE)
frame_jugador.grid(row=0, column=0, padx=40)

label_nombre_jugador = tk.Label(frame_jugador, text="Jugador", width=20,
                                 bg=BG_COMBATE, fg="white", font=("Arial", 10, "bold"))
label_nombre_jugador.pack()

barra_jugador = tk.Canvas(frame_jugador, width=250, height=20, bg="darkred",
                           highlightthickness=0)
barra_jugador.pack()

label_img_jugador = tk.Label(frame_jugador, bg=BG_COMBATE, width=320, height=320)
label_img_jugador.pack(pady=4)

# Enemigo
frame_enemigo = tk.Frame(frame_top, bg=BG_COMBATE)
frame_enemigo.grid(row=0, column=1, padx=40)

label_nombre_enemigo = tk.Label(frame_enemigo, text="Enemigo", width=20,
                                  bg=BG_COMBATE, fg="white", font=("Arial", 10, "bold"))
label_nombre_enemigo.pack()

barra_enemigo = tk.Canvas(frame_enemigo, width=250, height=20, bg="darkred",
                           highlightthickness=0)
barra_enemigo.pack()

label_img_enemigo = tk.Label(frame_enemigo, bg=BG_COMBATE, width=320, height=320)
label_img_enemigo.pack(pady=4)

# Contador de personajes vivos por equipo
label_roster = tk.Label(frame_combate, text="Tu equipo: 0  |  Hollow: 0",
                        font=("Arial", 10), fg="#f0f0f0", bg=BG_COMBATE)
label_roster.pack(pady=4)

# Botones de accion
frame_acciones = tk.Frame(frame_combate, bg=BG_COMBATE)
frame_acciones.pack(pady=10)

btn_ataque  = tk.Button(frame_acciones, text="Ataque",
                        bg="#0f3460", fg="white", activebackground="#e94560",
                        relief="flat", font=("Arial", 10, "bold"),
                        command=lambda: turno("normal"))
btn_ataque.grid(row=0, column=0, padx=5)

btn_fuerte  = tk.Button(frame_acciones, text="Ataque Fuerte",
                        bg="#0f3460", fg="white", activebackground="#e94560",
                        relief="flat", font=("Arial", 10, "bold"),
                        command=lambda: turno("fuerte"))
btn_fuerte.grid(row=0, column=1, padx=5)

btn_defensa = tk.Button(frame_acciones, text="Defender",
                        bg="#0f3460", fg="white", activebackground="#e94560",
                        relief="flat", font=("Arial", 10, "bold"),
                        command=lambda: turno("defensa"))
btn_defensa.grid(row=0, column=2, padx=5)

# Botones de seleccion de personaje (se generan dinamicamente en reconstruir_botones_equipo)
frame_personajes = tk.Frame(frame_combate, bg=BG_COMBATE)
frame_personajes.pack(pady=10)

# ========================
# CREACION DE TARJETAS DE SELECCION
# Se construyen recursivamente. La grilla tiene 5 columnas;
# al llegar a la columna 5 se pasa a la siguiente fila automaticamente.
# ========================
def crear_tarjetas(i, fila, columna):
    """Crea recursivamente las tarjetas de seleccion de personaje."""
    if i >= len(personajes):
        return
    p = personajes[i]
    crear_personaje(frame_grilla, p[0], p[1], p[2], p[3], fila, columna)
    siguiente_col = (columna + 1) % 5
    siguiente_fila = fila + (1 if siguiente_col == 0 else 0)
    crear_tarjetas(i + 1, siguiente_fila, siguiente_col)

crear_tarjetas(0, 0, 0)

# ========================
# FRAME RESULTADOS (pantalla final)
# Muestra la tabla de puntajes acumulados de la sesion.
# El jugador puede volver al menu (reinicia todo el estado) o salir.
# ========================
frame_resultados = tk.Frame(ventana)

tk.Label(frame_resultados, text="TABLA DE PUNTAJES",
         font=("Arial", 18, "bold")).pack(pady=20)

frame_tabla = tk.Frame(frame_resultados, bd=2, relief="solid")
frame_tabla.pack(pady=10)

tk.Button(frame_resultados, text="Volver al Menu",
          font=("Arial", 12), bg="lightblue",
          command=reiniciar).pack(pady=10)

tk.Button(frame_resultados, text="Salir del Juego",
          font=("Arial", 12), bg="salmon",
          command=ventana.destroy).pack(pady=5)

# ========================
# Iniciar musica de menu al arrancar el juego
reproducir_musica("inicio")

ventana.mainloop()