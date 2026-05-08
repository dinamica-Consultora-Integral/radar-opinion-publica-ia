import streamlit as st
import sqlite3
import subprocess
from datetime import datetime
from collections import Counter, defaultdict

DB = "radar_opinion_publica.db"
APP = "Radar de Opinión Pública IA"

st.set_page_config(page_title=APP, page_icon="📡", layout="wide")

# ================= BASE =================
def ahora():
    return datetime.now().strftime("%Y-%m-%d %H:%M")

def db():
    return sqlite3.connect(DB)

def q(sql, p=(), fetch=False):
    con = db()
    cur = con.cursor()
    cur.execute(sql, p)
    if fetch:
        data = cur.fetchall()
        con.close()
        return data
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
        fecha_creacion TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS usuarios(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT UNIQUE,
        password TEXT,
        cliente TEXT,
        rol TEXT DEFAULT 'cliente',
        activo TEXT DEFAULT 'Si',
        fecha_creacion TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS palabras_clave(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente TEXT,
        palabra TEXT,
        tipo TEXT DEFAULT 'Obligatoria',
        activo TEXT DEFAULT 'Si',
        fecha_creacion TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS fuentes_sociales(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente TEXT,
        medio TEXT,
        red_social TEXT,
        url_perfil TEXT,
        palabras_clave TEXT,
        activo TEXT DEFAULT 'Si',
        fecha_creacion TEXT
    )""")
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
        estado TEXT DEFAULT 'Pendiente'
    )""")
    con.commit()
    con.close()


def seed():
    # Sistema limpio: solo super admin inicial.
    # Clientes, usuarios, palabras clave y perfiles se cargan desde Administración.
    try:
        total = q("SELECT COUNT(*) FROM usuarios", fetch=True)[0][0]
    except Exception:
        total = 0
    if total == 0:
        q("INSERT INTO usuarios(usuario,password,cliente,rol,activo,fecha_creacion) VALUES(?,?,?,?,?,?)",
          ("admin", "1234", "Todos", "super_admin", "Si", ahora()))


def rol_login():
    return st.session_state.get("rol", "cliente")

def clientes_lista(incluir_todos=False):
    lista = [x[0] for x in q("SELECT nombre FROM clientes WHERE activo='Si' ORDER BY nombre", fetch=True)]
    return (["Todos"] + lista) if incluir_todos else lista

def cliente_trabajo():
    if rol_login() == "super_admin":
        return st.session_state.get("cliente_trabajo", "Todos")
    return cliente_login()

# ================= IA SIMPLE =================
def analizar(texto):
    t = (texto or "").lower()
    negativas = ["reclamo","problema","queja","denuncia","malestar","critica","crítica","inseguridad","abandono","falta","demora","grave","conflicto","enojo","irregularidad"]
    positivas = ["obra","avance","inauguracion","inauguración","mejora","entrega","beneficio","programa","desarrollo","crecimiento","convenio","fortalecimiento","acompañamiento","logro"]
    n = sum(1 for x in negativas if x in t)
    p = sum(1 for x in positivas if x in t)
    if n > p:
        tono, riesgo, rec = "Negativo", ("Alto" if n >= 2 else "Medio"), "Revisar contexto, monitorear comentarios y evaluar respuesta institucional."
    elif p > n:
        tono, riesgo, rec = "Positivo", "Bajo", "Amplificar si acompaña la estrategia comunicacional."
    else:
        tono, riesgo, rec = "Neutro", "Bajo", "Registrar y monitorear evolución."
    if "facebook.com" in t or "instagram.com" in t or "x.com" in t:
        tema = "Red social / conversación pública"
    elif "municip" in t or "intend" in t or "concejo" in t:
        tema = "Gestión institucional"
    elif "seguridad" in t or "robo" in t:
        tema = "Seguridad"
    elif "obra" in t or "calle" in t or "pavimento" in t:
        tema = "Obra pública"
    elif "reclamo" in t or "vecinos" in t:
        tema = "Reclamo ciudadano"
    else:
        tema = "General"
    return tono, tema, riesgo, rec


def guardar_publicacion(cliente, fuente, tipo, titulo, texto, link):
    tono, tema, riesgo, rec = analizar(f"{titulo} {texto} {link}")
    q("""INSERT INTO publicaciones(fecha,cliente,fuente,tipo,titulo,texto,link,tono,tema,riesgo,recomendacion,estado)
         VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", (ahora(), cliente, fuente, tipo, titulo, texto, link, tono, tema, riesgo, rec, "Pendiente"))

# ================= CONSULTAS FILTRADAS =================
def obtener_publicaciones():
    c = cliente_trabajo()
    if c == "Todos":
        return q("SELECT id,fecha,cliente,fuente,tipo,titulo,texto,link,tono,tema,riesgo,recomendacion,estado FROM publicaciones ORDER BY id DESC", fetch=True)
    return q("SELECT id,fecha,cliente,fuente,tipo,titulo,texto,link,tono,tema,riesgo,recomendacion,estado FROM publicaciones WHERE cliente=? ORDER BY id DESC", (c,), fetch=True)

def obtener_keywords():
    c = cliente_trabajo()
    if c == "Todos":
        return q("SELECT id,cliente,palabra,tipo,activo,fecha_creacion FROM palabras_clave ORDER BY id DESC", fetch=True)
    return q("SELECT id,cliente,palabra,tipo,activo,fecha_creacion FROM palabras_clave WHERE cliente=? ORDER BY id DESC", (c,), fetch=True)

def obtener_fuentes():
    c = cliente_trabajo()
    if c == "Todos":
        return q("SELECT id,cliente,medio,red_social,url_perfil,palabras_clave,activo,fecha_creacion FROM fuentes_sociales ORDER BY id DESC", fetch=True)
    return q("SELECT id,cliente,medio,red_social,url_perfil,palabras_clave,activo,fecha_creacion FROM fuentes_sociales WHERE cliente=? ORDER BY id DESC", (c,), fetch=True)

def dividir(data):
    return [x for x in data if (x[4] or "").lower()=="web"], [x for x in data if (x[4] or "").lower()!="web"]

def resumen_tono(data):
    c = Counter([x[8] or "Neutro" for x in data])
    return {"Positivo":c.get("Positivo",0), "Negativo":c.get("Negativo",0), "Neutro":c.get("Neutro",0)}

def resumen_riesgo(data):
    c = Counter([x[10] or "Bajo" for x in data])
    return {"Bajo":c.get("Bajo",0), "Medio":c.get("Medio",0), "Alto":c.get("Alto",0)}

def run_script(nombre):
    try:
        r = subprocess.run(["python3", nombre], capture_output=True, text=True)
        return (r.stdout or "") + (r.stderr or "") or "Proceso ejecutado."
    except Exception as e:
        return f"No se pudo ejecutar {nombre}: {e}"

def mostrar(data, etiqueta):
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
            st.write(f"**{etiqueta}:** {link}")
        st.write(f"**Texto:** {texto}")

# ================= LOGIN =================
if "login" not in st.session_state:
    st.session_state.login = False

if not st.session_state.login:
    st.markdown(f"# 📡 {APP}")
    st.markdown("### Plataforma inteligente de monitoreo y análisis comunicacional")
    col1, col2, col3 = st.columns([1,1.2,1])
    with col2:
        usuario = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        if st.button("Ingresar", use_container_width=True):
            r = q("SELECT usuario,cliente,rol FROM usuarios WHERE usuario=? AND password=? AND activo='Si'", (usuario,password), fetch=True)
            if r:
                st.session_state.login = True
                st.session_state.usuario = r[0][0]
                st.session_state.cliente = r[0][1]
                st.session_state.rol = r[0][2]
                st.session_state.cliente_trabajo = r[0][1]
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")
        with st.expander("Usuarios iniciales"):
            st.write("admin / 1234")
            
    st.stop()

# ================= SIDEBAR =================
st.sidebar.markdown(f"## 📡 {APP}")
st.sidebar.caption(f"Usuario: {st.session_state.get('usuario')}")
st.sidebar.caption(f"Rol: {rol_login()}")
if rol_login() == "super_admin":
    st.session_state.cliente_trabajo = st.sidebar.selectbox("Cliente en trabajo", clientes_lista(incluir_todos=True), index=0)
else:
    st.session_state.cliente_trabajo = cliente_login()
st.sidebar.success(f"Vista actual: {cliente_trabajo()}")

menu = ["Dashboard", "Motor de búsqueda", "Redes Sociales", "Cargar publicación", "Análisis Web", "Análisis Redes", "Informe Ejecutivo"]
if rol_login() == "super_admin":
    menu.insert(1, "Administración")
menu += ["Configuración", "Cerrar sesión"]
op = st.sidebar.radio("Menú", menu)
if op == "Cerrar sesión":
    st.session_state.login = False
    st.rerun()

data = obtener_publicaciones()
web, redes = dividir(data)

# ================= PANTALLAS =================
if op == "Dashboard":
    st.markdown(f"# 📊 Dashboard · {APP}")
    st.write(f"Vista actual: **{cliente_trabajo()}**")
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Total", len(data)); c2.metric("Web", len(web)); c3.metric("Redes", len(redes))
    c4.metric("Negativas", sum(1 for x in data if x[8]=="Negativo")); c5.metric("Riesgo alto", sum(1 for x in data if x[10]=="Alto"))
    a,b = st.columns(2)
    with a:
        st.subheader("Tono general"); st.bar_chart(resumen_tono(data))
    with b:
        st.subheader("Riesgo"); st.bar_chart(resumen_riesgo(data))
    st.subheader("Lectura por medio")
    medios = defaultdict(lambda:{"Total":0,"Positivo":0,"Negativo":0,"Neutro":0})
    for x in data:
        fuente = x[3] or "Sin fuente"; tono = x[8] or "Neutro"
        medios[fuente]["Total"] += 1; medios[fuente][tono] += 1
    if not medios: st.info("Sin datos.")
    for m,v in sorted(medios.items(), key=lambda z:z[1]["Total"], reverse=True):
        st.write(f"**{m}** → Total {v['Total']} | Positivas {v['Positivo']} | Negativas {v['Negativo']} | Neutras {v['Neutro']}")

elif op == "Administración":
    st.markdown("# 🔐 Administración")
    tab1, tab2, tab3 = st.tabs(["Clientes", "Usuarios", "Palabras clave"])
    with tab1:
        with st.form("cliente_form"):
            nombre = st.text_input("Nombre del cliente", value="Municipalidad de Suardi")
            desc = st.text_input("Descripción", value="Cliente municipal")
            if st.form_submit_button("Crear cliente"):
                try:
                    q("INSERT INTO clientes(nombre,descripcion,activo,fecha_creacion) VALUES(?,?,?,?)", (nombre,desc,"Si",ahora()))
                    st.success("Cliente creado."); st.rerun()
                except Exception as e: st.error(f"No se pudo crear: {e}")
        for x in q("SELECT id,nombre,descripcion,activo,fecha_creacion FROM clientes ORDER BY nombre", fetch=True):
            st.write(f"**{x[1]}** | {x[3]} | {x[2]}")
    with tab2:
        with st.form("usuario_form"):
            usuario = st.text_input("Usuario")
            password = st.text_input("Contraseña")
            cliente = st.selectbox("Cliente asignado", clientes_lista(incluir_todos=True))
            rol = st.selectbox("Rol", ["cliente", "super_admin"])
            if st.form_submit_button("Crear usuario"):
                try:
                    q("INSERT INTO usuarios(usuario,password,cliente,rol,activo,fecha_creacion) VALUES(?,?,?,?,?,?)", (usuario,password,cliente,rol,"Si",ahora()))
                    st.success("Usuario creado."); st.rerun()
                except Exception as e: st.error(f"No se pudo crear: {e}")
        for x in q("SELECT id,usuario,cliente,rol,activo,fecha_creacion FROM usuarios ORDER BY id DESC", fetch=True):
            st.write(f"**{x[1]}** | Cliente: {x[2]} | Rol: {x[3]} | {x[4]}")
    with tab3:
        with st.form("kw_form"):
            cliente = st.selectbox("Cliente", clientes_lista())
            palabra = st.text_input("Patrón exacto", value="Municipalidad de Suardi")
            tipo = st.selectbox("Tipo", ["Obligatoria", "Complementaria"])
            if st.form_submit_button("Guardar palabra clave"):
                q("INSERT INTO palabras_clave(cliente,palabra,tipo,activo,fecha_creacion) VALUES(?,?,?,?,?)", (cliente,palabra,tipo,"Si",ahora()))
                st.success("Palabra guardada."); st.rerun()
        for x in q("SELECT id,cliente,palabra,tipo,activo,fecha_creacion FROM palabras_clave ORDER BY id DESC", fetch=True):
            st.write(f"**{x[1]}** → {x[2]} | {x[3]} | {x[4]}")

elif op == "Motor de búsqueda":
    st.markdown("# 🔎 Motor de búsqueda")
    st.info("Cada cliente trabaja con sus propias palabras clave. No se mezclan resultados.")
    st.subheader("Palabras clave activas")
    kws = obtener_keywords()
    if not kws: st.warning("No hay palabras clave para esta vista.")
    for x in kws: st.write(f"**{x[2]}** | {x[3]} | {x[4]}")
    if st.button("Ejecutar motor web", use_container_width=True): st.code(run_script("noticias.py"))

elif op == "Redes Sociales":
    st.markdown("# 📱 Redes Sociales")
    if cliente_trabajo() == "Todos":
        st.warning("Seleccioná un cliente específico en la barra lateral antes de cargar perfiles.")
    else:
        with st.form("red_form"):
            medio = st.text_input("Medio", value="Radio República")
            red = st.selectbox("Red social", ["Facebook", "Instagram", "X"])
            url = st.text_input("URL perfil")
            palabras = st.text_area("Patrones exactos", value="Municipalidad de Morteros\nSebastián Demarchi")
            if st.form_submit_button("Guardar perfil"):
                q("INSERT INTO fuentes_sociales(cliente,medio,red_social,url_perfil,palabras_clave,activo,fecha_creacion) VALUES(?,?,?,?,?,?,?)", (cliente_trabajo(),medio,red,url,palabras,"Si",ahora()))
                st.success("Perfil guardado."); st.rerun()
    st.subheader("Perfiles cargados")
    fuentes = obtener_fuentes()
    if not fuentes: st.info("Sin perfiles.")
    for x in fuentes: st.write(f"**{x[2]}** | {x[3]} | {x[1]} | {x[4]}")
    if st.button("Ejecutar escaneo redes", use_container_width=True): st.code(run_script("redes.py"))

elif op == "Cargar publicación":
    st.markdown("# ➕ Cargar publicación")
    if cliente_trabajo() == "Todos": st.warning("Seleccioná un cliente específico en la barra lateral.")
    else:
        with st.form("manual"):
            fuente = st.text_input("Fuente"); tipo = st.selectbox("Tipo", ["Web", "Red Social"])
            titulo = st.text_input("Título"); texto = st.text_area("Texto"); link = st.text_input("Link")
            if st.form_submit_button("Analizar y guardar"):
                guardar_publicacion(cliente_trabajo(), fuente, tipo, titulo, texto, link)
                st.success("Guardado."); st.rerun()

elif op == "Análisis Web":
    st.markdown("# 🌐 Análisis Web"); st.caption(f"Registros web: {len(web)}")
    a,b = st.columns(2)
    with a: st.bar_chart(resumen_tono(web))
    with b: st.bar_chart(resumen_riesgo(web))
    mostrar(web, "Link noticia")

elif op == "Análisis Redes":
    st.markdown("# 📱 Análisis Redes"); st.caption(f"Registros redes: {len(redes)}")
    a,b = st.columns(2)
    with a: st.bar_chart(resumen_tono(redes))
    with b: st.bar_chart(resumen_riesgo(redes))
    mostrar(redes, "Link red social")

elif op == "Informe Ejecutivo":
    st.markdown("# 📝 Informe Ejecutivo IA")
    st.write(f"Vista: **{cliente_trabajo()}**")
    st.write(f"Total: **{len(data)}**")
    st.write(f"Web: **{len(web)}** | Redes: **{len(redes)}**")
    st.write(f"Positivas: **{sum(1 for x in data if x[8]=='Positivo')}** | Negativas: **{sum(1 for x in data if x[8]=='Negativo')}** | Neutras: **{sum(1 for x in data if x[8]=='Neutro')}**")
    if any(x[10]=="Alto" for x in data): st.warning("Se detectan publicaciones de riesgo alto. Revisar prioridad de respuesta.")
    elif sum(1 for x in data if x[8]=="Negativo") > sum(1 for x in data if x[8]=="Positivo"): st.warning("La conversación presenta señales sensibles. Se recomienda seguimiento activo.")
    elif data: st.success("La conversación se mantiene estable o favorable.")
    else: st.info("Sin datos suficientes para informe.")

elif op == "Configuración":
    st.markdown("# ⚙️ Configuración")
    st.warning("Estas acciones borran datos SOLO de la vista actual.")
    c1,c2,c3 = st.columns(3)
    if c1.button("Borrar Web", use_container_width=True):
        if cliente_trabajo()=="Todos": q("DELETE FROM publicaciones WHERE LOWER(tipo)='web'")
        else: q("DELETE FROM publicaciones WHERE cliente=? AND LOWER(tipo)='web'", (cliente_trabajo(),))
        st.rerun()
    if c2.button("Borrar Redes", use_container_width=True):
        if cliente_trabajo()=="Todos": q("DELETE FROM publicaciones WHERE LOWER(COALESCE(tipo,''))!='web'")
        else: q("DELETE FROM publicaciones WHERE cliente=? AND LOWER(COALESCE(tipo,''))!='web'", (cliente_trabajo(),))
        st.rerun()
    if c3.button("Borrar TODO", use_container_width=True):
        if cliente_trabajo()=="Todos": q("DELETE FROM publicaciones")
        else: q("DELETE FROM publicaciones WHERE cliente=?", (cliente_trabajo(),))
        st.rerun()
