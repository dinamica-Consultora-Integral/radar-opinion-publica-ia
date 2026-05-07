# noticias.py
# Motor de noticias web para gestion publica.
# Guarda siempre con tipo = "Web" para que aparezca en el panel "Noticias Web".

import feedparser
import sqlite3
from datetime import datetime
from urllib.parse import quote_plus

DB_NAME = "radar_opinion_publica.db"

municipio = "Morteros"
intendente = "Sebastian Demarchi"
cliente = "Municipalidad de Morteros"

def conectar():
    return sqlite3.connect(DB_NAME)

def crear_tabla_si_no_existe():
    conn = conectar()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS publicaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT,
        cliente TEXT,
        fuente TEXT,
        tipo TEXT,
        titulo TEXT,
        texto TEXT,
        link TEXT,
        tono TEXT,
        tema TEXT,
        riesgo TEXT,
        recomendacion TEXT,
        estado TEXT DEFAULT 'Pendiente'
    )
    """)
    conn.commit()
    conn.close()

def existe_link(link):
    conn = conectar()
    c = conn.cursor()
    c.execute("SELECT id FROM publicaciones WHERE link = ?", (link,))
    r = c.fetchone()
    conn.close()
    return r is not None

def analizar(texto):
    t = texto.lower()
    negativas = ["reclamo", "problema", "queja", "denuncia", "malestar", "critica", "inseguridad", "abandono", "falta", "demora"]
    positivas = ["obra", "avance", "inauguracion", "mejora", "entrega", "beneficio", "programa", "desarrollo", "crecimiento"]

    n = sum(1 for p in negativas if p in t)
    p = sum(1 for p in positivas if p in t)

    if n > p:
        tono = "Negativo"
        riesgo = "Alto" if n >= 2 else "Medio"
        recomendacion = "Revisar el contexto, monitorear comentarios y preparar respuesta si escala."
    elif p > n:
        tono = "Positivo"
        riesgo = "Bajo"
        recomendacion = "Amplificar si favorece la estrategia de comunicacion."
    else:
        tono = "Neutro"
        riesgo = "Bajo"
        recomendacion = "Registrar y monitorear evolucion."

    if "municip" in t or "intend" in t or "concejo" in t:
        tema = "Gestion institucional"
    elif "seguridad" in t or "robo" in t or "delito" in t:
        tema = "Seguridad"
    elif "salud" in t or "hospital" in t:
        tema = "Salud"
    elif "obra" in t or "calle" in t or "pavimento" in t:
        tema = "Obra publica"
    elif "reclamo" in t or "vecinos" in t:
        tema = "Reclamo ciudadano"
    else:
        tema = "General"

    return tono, tema, riesgo, recomendacion

def guardar_publicacion(cliente, fuente, tipo, titulo, texto, link):
    tono, tema, riesgo, recomendacion = analizar(f"{titulo} {texto} {link}")
    conn = conectar()
    c = conn.cursor()
    c.execute("""
    INSERT INTO publicaciones
    (fecha, cliente, fuente, tipo, titulo, texto, link, tono, tema, riesgo, recomendacion, estado)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        cliente,
        fuente,
        tipo,
        titulo,
        texto,
        link,
        tono,
        tema,
        riesgo,
        recomendacion,
        "Pendiente"
    ))
    conn.commit()
    conn.close()

def google_news_rss(query):
    return f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=es-419&gl=AR&ceid=AR:es"

def obtener_link_real(noticia):
    source = noticia.get("source", {})
    if isinstance(source, dict):
        real = source.get("href", "")
        if real:
            return real
    return noticia.get("link", "")

def ejecutar():
    crear_tabla_si_no_existe()

    queries = [
        f'"Municipalidad de {municipio}"',
        f'"{intendente}" "{municipio}"',
        f'"Municipio de {municipio}"',
        f'"{municipio}" "municipalidad"',
        f'"{municipio}" "intendente"'
    ]

    revisadas = 0
    descartadas = 0
    nuevas = 0

    for query in queries:
        print(f"Buscando web: {query}")
        feed = feedparser.parse(google_news_rss(query))

        for noticia in feed.entries[:15]:
            revisadas += 1
            titulo = noticia.get("title", "Sin titulo")
            resumen = noticia.get("summary", "")
            link = obtener_link_real(noticia)
            fuente = noticia.get("source", {}).get("title", "Google News / Web")
            texto = f"{titulo} {resumen}"
            texto_lower = texto.lower()

            if not (
                "municipalidad" in texto_lower
                or "municipio" in texto_lower
                or intendente.lower() in texto_lower
                or intendente.split()[-1].lower() in texto_lower
            ):
                descartadas += 1
                continue

            if not link:
                descartadas += 1
                continue

            if existe_link(link):
                descartadas += 1
                continue

            guardar_publicacion(
                cliente=cliente,
                fuente=fuente,
                tipo="Web",
                titulo=titulo,
                texto=texto,
                link=link
            )
            nuevas += 1

    print("Proceso terminado")
    print(f"Noticias web revisadas: {revisadas}")
    print(f"Noticias web descartadas: {descartadas}")
    print(f"Noticias web nuevas guardadas: {nuevas}")

if __name__ == "__main__":
    ejecutar()
