
import streamlit as st
import sqlite3
import subprocess
from datetime import datetime
from collections import Counter, defaultdict

DB = "radar_opinion_publica.db"
APP = "Radar de Opinión Pública IA"

st.set_page_config(page_title=APP, page_icon="📡", layout="wide")

def db():
    return sqlite3.connect(DB)

def q(sql, p=(), fetch=False):
    con = db()
    cur = con.cursor()
    cur.execute(sql, p)
    if fetch:
        r = cur.fetchall()
        con.close()
        return r
    con.commit()
    con.close()

def init():
    con = db()
    c = con.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS clientes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT UNIQUE,
        descripcion TEXT,
        activo TEXT DEFAULT 'Si',
        fecha_creacion TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS usuarios(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT UNIQUE,
        password TEXT,
        cliente TEXT,
        rol TEXT DEFAULT 'cliente',
        activo TEXT DEFAULT 'Si',
        fecha_creacion TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS palabras_clave(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente TEXT,
        palabra TEXT,
        tipo TEXT DEFAULT 'Obligatoria',
        activo TEXT DEFAULT 'Si',
        fecha_creacion TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS fuentes_sociales(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente TEXT,
        medio TEXT,
        red_social TEXT,
        url_perfil TEXT,
        palabras_clave TEXT,
        activo TEXT DEFAULT 'Si',
        fecha_creacion TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS publicaciones(
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
        estado TEXT DEFAULT 'Pendiente')""")
    con.commit()
    con.close()

def seed():
    if q("SELECT COUNT(*) FROM clientes", fetch=True)[0][0] == 0:
        for n in ["Municipalidad de Morteros", "Municipalidad de Brinkmann", "Municipalidad de Suardi"]:
            q("INSERT INTO clientes(nombre,descripcion,activo,fecha_creacion) VALUES(?,?,?,?)",
              (n, "Cliente inicial", "Si", datetime.now().strftime("%Y-%m-%d %H:%M")))
    if q("SELECT COUNT(*) FROM usuarios", fetch=True)[0][0] == 0:
        users = [
            ("admin", "1234", "Todos", "super_admin"),
            ("morteros", "1111", "Municipalidad de Morteros", "cliente"),
            ("brinkmann", "2222", "Municipalidad de Brinkmann", "cliente"),
            ("suardi", "3333", "Municipalidad de Suardi", "cliente"),
        ]
        for u,p,c,r in users:
            q("INSERT INTO usuarios(usuario,password,cliente,rol,activo,fecha_creacion) VALUES(?,?,?,?,?,?)",
              (u,p,c,r,"Si",datetime.now().strftime("%Y-%m-%d %H:%M")))

def analizar(txt):
    t = (txt or "").lower()
    neg = ["reclamo","problema","queja","denuncia","malestar","critica","crítica","inseguridad","abandono","falta","demora","grave"]
    pos = ["obra","avance","inauguracion","inauguración","mejora","entrega","beneficio","programa","desarrollo","crecimiento","convenio"]
    n = sum(1 for x in neg if x in t)
    p = sum(1 for x in pos if x in t)
    if n > p:
        tono = "Negativo"; riesgo = "Alto" if n >= 2 else "Medio"; rec = "Revisar contexto, monitorear comentarios y evaluar respuesta institucional."
    elif p > n:
        tono = "Positivo"; riesgo = "Bajo"; rec = "Amplificar si acompaña la estrategia comunicacional."
    else:
        tono = "Neutro"; riesgo = "Bajo"; rec = "Registrar y monitorear evolución."
    if "facebook.com" in t or "instagram.com" in t or "x.com" in t:
        tema = "Red social / conversación pública"
    elif "municip" in t or "intend" in t or "concejo" in t:
        tema = "Gestión institucional"
    elif "seguridad" in t or "robo" in t:
        tema = "Seguridad"
    elif "obra" in t or "calle" in t:
        tema = "Obra pública"
    elif "reclamo" in t or "vecinos" in t:
        tema = "Reclamo ciudadano"
    else:
        tema = "General"
    return tono, tema, riesgo, rec

def guardar_pub(cliente, fuente, tipo, titulo, texto, link):
    tono, tema, riesgo, rec = analizar(f"{titulo} {texto} {link}")
    q("""INSERT INTO publicaciones(fecha,cliente,fuente,tipo,titulo,texto,link,tono,tema,riesgo,recomendacion,estado)
         VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
      (datetime.now().strftime("%Y-%m-%d %H:%M"), cliente, fuente, tipo, titulo, texto, link, tono, tema, riesgo, rec, "Pendiente"))

def clientes():
    return q("SELECT id,nombre,descripcion,activo,fecha_creacion FROM clientes ORDER BY nombre", fetch=True)

def usuarios():
    return q("SELECT id,usuario,cliente,rol,activo,fecha_creacion FROM usuarios ORDER BY id DESC", fetch=True)

def palabras(cliente):
    if cliente == "Todos":
        return q("SELECT id,cliente,palabra,tipo,activo,fecha_creacion FROM palabras_clave ORDER BY id DESC", fetch=True)
    return q("SELECT id,cliente,palabra,tipo,activo,fecha_creacion FROM palabras_clave WHERE cliente=? ORDER BY id DESC", (cliente,), fetch=True)

def fuentes(cliente):
    if cliente == "Todos":
        return q("SELECT id,cliente,medio,red_social,url_perfil,palabras_clave,activo,fecha_creacion FROM fuentes_sociales ORDER BY id DESC", fetch=True)
    return q("SELECT id,cliente,medio,red_social,url_perfil,palabras_clave,activo,fecha_creacion FROM fuentes_sociales WHERE cliente=? ORDER BY id DESC", (cliente,), fetch=True)

def publicaciones():
    return q("SELECT id,fecha,cliente,fuente,tipo,titulo,texto,link,tono,tema,riesgo,recomendacion,estado FROM publicaciones ORDER BY id DESC", fetch=True)

def filtrar_cliente(data):
    c = st.session_state.get("cliente", "Todos")
    return data if c == "Todos" else [x for x in data if x[2] == c]

def dividir(data):
    web = [x for x in data if (x[4] or "").lower() == "web"]
    redes = [x for x in data if (x[4] or "").lower() != "web"]
    return web, redes

def resumen_tono(data):
    c = Counter([x[8] or "Neutro" for x in data])
    return {"Positivo":c.get("Positivo",0),"Negativo":c.get("Negativo",0),"Neutro":c.get("Neutro",0)}

def resumen_riesgo(data):
    c = Counter([x[10] or "Bajo" for x in data])
    return {"Bajo":c.get("Bajo",0),"Medio":c.get("Medio",0),"Alto":c.get("Alto",0)}

def run_script(nombre):
    try:
        r = subprocess.run(["python3", nombre], capture_output=True, text=True, cwd="/Users/mort/Desktop")
        return (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return str(e)

def mostrar(data, link_label):
    if not data:
        st.info("Sin registros.")
        return
    for x in data:
        pid, fecha, cliente, fuente, tipo, titulo, texto, link, tono, tema, riesgo, rec, estado = x
        st.markdown("---")
        st.markdown(f"### {titulo or 'Publicación sin título'}")
        st.write(f"**Fecha:** {fecha} | **Cliente:** {cliente}")
        st.write(f"**Fuente:** {fuente} | **Tipo:** {tipo}")
        st.write(f"**Tono IA:** {tono} | **Tema:** {tema} | **Riesgo:** {riesgo}")
        st.write(f"**Recomendación IA:** {rec}")
        if link:
            st.write(f"**{link_label}:** {link}")
        st.write(f"**Texto:** {texto}")

init()
seed()

if "login" not in st.session_state:
    st.session_state.login = False

if not st.session_state.login:
    st.markdown(f"# 📡 {APP}")
    st.markdown("### Plataforma inteligente de monitoreo y análisis comunicacional")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Ingresar", use_container_width=True):
        r = q("SELECT usuario,cliente,rol FROM usuarios WHERE usuario=? AND password=? AND activo='Si'", (u,p), fetch=True)
        if r:
            st.session_state.login = True
            st.session_state.usuario = r[0][0]
            st.session_state.cliente = r[0][1]
            st.session_state.rol = r[0][2]
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")
    with st.expander("Usuarios iniciales"):
        st.write("admin / 1234")
        st.write("morteros / 1111")
        st.write("brinkmann / 2222")
        st.write("suardi / 3333")
    st.stop()

cliente_actual = st.session_state.get("cliente", "Todos")
rol = st.session_state.get("rol", "cliente")

st.sidebar.markdown(f"## 📡 {APP}")
st.sidebar.caption(f"Acceso: {cliente_actual}")
st.sidebar.caption(f"Rol: {rol}")

menu = ["Dashboard","Motor de búsqueda","Redes Sociales","Cargar publicación","Análisis Web","Análisis Redes","Informe Ejecutivo"]
if rol == "super_admin":
    menu.insert(1, "Administración")
menu += ["Configuración","Cerrar sesión"]

op = st.sidebar.radio("Menú", menu)

if op == "Cerrar sesión":
    st.session_state.login = False
    st.rerun()

data = filtrar_cliente(publicaciones())
web, redes = dividir(data)

if op == "Dashboard":
    st.markdown(f"# 📊 Dashboard · {APP}")
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Total", len(data)); c2.metric("Web", len(web)); c3.metric("Redes", len(redes))
    c4.metric("Negativas", sum(1 for x in data if x[8]=="Negativo")); c5.metric("Riesgo alto", sum(1 for x in data if x[10]=="Alto"))
    a,b = st.columns(2)
    with a:
        st.subheader("Tono general")
        st.bar_chart(resumen_tono(data))
    with b:
        st.subheader("Riesgo")
        st.bar_chart(resumen_riesgo(data))
    st.subheader("Lectura por medio")
    medios = defaultdict(lambda: {"Total":0,"Positivo":0,"Negativo":0,"Neutro":0})
    for x in data:
        f = x[3] or "Sin fuente"; tono = x[8] or "Neutro"
        medios[f]["Total"] += 1; medios[f][tono] += 1
    for m,v in sorted(medios.items(), key=lambda z:z[1]["Total"], reverse=True):
        st.write(f"**{m}** → Total {v['Total']} | Positivas {v['Positivo']} | Negativas {v['Negativo']} | Neutras {v['Neutro']}")

elif op == "Administración":
    st.markdown("# 🔐 Administración")
    t1,t2,t3 = st.tabs(["Clientes","Usuarios","Palabras clave"])
    with t1:
        with st.form("cliente"):
            nombre = st.text_input("Nombre cliente", value="Municipalidad de Suardi")
            desc = st.text_input("Descripción", value="Cliente municipal")
            if st.form_submit_button("Crear cliente"):
                q("INSERT INTO clientes(nombre,descripcion,activo,fecha_creacion) VALUES(?,?,?,?)",(nombre,desc,"Si",datetime.now().strftime("%Y-%m-%d %H:%M")))
                st.rerun()
        for x in clientes():
            st.write(f"**{x[1]}** | {x[3]} | {x[2]}")
    with t2:
        lista = ["Todos"] + [x[1] for x in clientes()]
        with st.form("usuario"):
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña")
            cl = st.selectbox("Cliente", lista)
            rolx = st.selectbox("Rol", ["cliente","super_admin"])
            if st.form_submit_button("Crear usuario"):
                q("INSERT INTO usuarios(usuario,password,cliente,rol,activo,fecha_creacion) VALUES(?,?,?,?,?,?)",(u,p,cl,rolx,"Si",datetime.now().strftime("%Y-%m-%d %H:%M")))
                st.rerun()
        for x in usuarios():
            st.write(f"**{x[1]}** | Cliente: {x[2]} | Rol: {x[3]} | {x[4]}")
    with t3:
        lista = [x[1] for x in clientes()]
        with st.form("keyword"):
            cl = st.selectbox("Cliente", lista)
            pal = st.text_input("Palabra exacta", value="Municipalidad de Suardi")
            tipo = st.selectbox("Tipo", ["Obligatoria","Complementaria"])
            if st.form_submit_button("Guardar palabra"):
                q("INSERT INTO palabras_clave(cliente,palabra,tipo,activo,fecha_creacion) VALUES(?,?,?,?,?)",(cl,pal,tipo,"Si",datetime.now().strftime("%Y-%m-%d %H:%M")))
                st.rerun()
        for x in palabras("Todos"):
            st.write(f"**{x[1]}** → {x[2]} | {x[3]}")

elif op == "Motor de búsqueda":
    st.markdown("# 🔎 Motor de búsqueda")
    st.info("Usar palabras clave exactas por cliente para evitar mezclas.")
    st.subheader("Palabras clave activas")
    for x in palabras(cliente_actual):
        st.write(f"**{x[2]}** | {x[3]} | {x[4]}")
    if st.button("Ejecutar motor web", use_container_width=True):
        st.code(run_script("noticias.py"))

elif op == "Redes Sociales":
    st.markdown("# 📱 Redes Sociales")
    if rol == "super_admin":
        cl = st.selectbox("Cliente", [x[1] for x in clientes()])
    else:
        cl = cliente_actual
        st.write(f"Cliente: **{cl}**")
    with st.form("red"):
        medio = st.text_input("Medio", value="Radio República")
        red = st.selectbox("Red", ["Facebook","Instagram","X"])
        url = st.text_input("URL perfil")
        pals = st.text_area("Palabras exactas", value="Municipalidad de Morteros\nSebastián Demarchi")
        if st.form_submit_button("Guardar perfil"):
            q("INSERT INTO fuentes_sociales(cliente,medio,red_social,url_perfil,palabras_clave,activo,fecha_creacion) VALUES(?,?,?,?,?,?,?)",(cl,medio,red,url,pals,"Si",datetime.now().strftime("%Y-%m-%d %H:%M")))
            st.rerun()
    for x in fuentes(cliente_actual):
        st.write(f"**{x[2]}** | {x[3]} | {x[1]} | {x[4]}")
    if st.button("Ejecutar escaneo redes", use_container_width=True):
        st.code(run_script("redes.py"))

elif op == "Cargar publicación":
    st.markdown("# ➕ Cargar publicación")
    with st.form("manual"):
        if rol == "super_admin":
            cl = st.selectbox("Cliente", [x[1] for x in clientes()])
        else:
            cl = cliente_actual
            st.write(f"Cliente: **{cl}**")
        fuente = st.text_input("Fuente")
        tipo = st.selectbox("Tipo", ["Web","Red Social"])
        titulo = st.text_input("Título")
        texto = st.text_area("Texto")
        link = st.text_input("Link")
        if st.form_submit_button("Guardar"):
            guardar_pub(cl, fuente, tipo, titulo, texto, link)
            st.rerun()

elif op == "Análisis Web":
    st.markdown("# 🌐 Análisis Web")
    st.bar_chart(resumen_tono(web))
    st.bar_chart(resumen_riesgo(web))
    mostrar(web, "Link noticia")

elif op == "Análisis Redes":
    st.markdown("# 📱 Análisis Redes")
    st.bar_chart(resumen_tono(redes))
    st.bar_chart(resumen_riesgo(redes))
    mostrar(redes, "Link red social")

elif op == "Informe Ejecutivo":
    st.markdown("# 📝 Informe Ejecutivo IA")
    st.write(f"Total: **{len(data)}**")
    st.write(f"Web: **{len(web)}** | Redes: **{len(redes)}**")
    st.write(f"Positivas: **{sum(1 for x in data if x[8]=='Positivo')}** | Negativas: **{sum(1 for x in data if x[8]=='Negativo')}** | Neutras: **{sum(1 for x in data if x[8]=='Neutro')}**")
    if any(x[10]=="Alto" for x in data):
        st.warning("Se detectan publicaciones de riesgo alto. Revisar prioridad de respuesta.")
    elif sum(1 for x in data if x[8]=="Negativo") > sum(1 for x in data if x[8]=="Positivo"):
        st.warning("La conversación presenta señales sensibles. Se recomienda seguimiento activo.")
    else:
        st.success("La conversación se mantiene estable o favorable.")

elif op == "Configuración":
    st.markdown("# ⚙️ Configuración")
    st.warning("Borrado de datos del cliente actual.")
    c1,c2,c3 = st.columns(3)
    if c1.button("Borrar Web"):
        if cliente_actual=="Todos": q("DELETE FROM publicaciones WHERE LOWER(tipo)='web'")
        else: q("DELETE FROM publicaciones WHERE cliente=? AND LOWER(tipo)='web'",(cliente_actual,))
        st.rerun()
    if c2.button("Borrar Redes"):
        if cliente_actual=="Todos": q("DELETE FROM publicaciones WHERE LOWER(COALESCE(tipo,''))!='web'")
        else: q("DELETE FROM publicaciones WHERE cliente=? AND LOWER(COALESCE(tipo,''))!='web'",(cliente_actual,))
        st.rerun()
    if c3.button("Borrar TODO"):
        if cliente_actual=="Todos": q("DELETE FROM publicaciones")
        else: q("DELETE FROM publicaciones WHERE cliente=?",(cliente_actual,))
        st.rerun()
