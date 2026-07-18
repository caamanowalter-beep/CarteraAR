"""
app.py — Punto de entrada de la aplicación Streamlit con autenticación.
Ejecutar con: streamlit run app.py
"""
import streamlit as st

st.set_page_config(
    page_title="Cartera AR",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Estilos globales ──────────────────────────────────────────────────────────
st.markdown("""
<style>
    [data-testid="stSidebarNav"] { display: none !important; }
    [data-testid="stSidebar"] { background-color: #1a1f2e !important; }
    [data-testid="stSidebar"] * { color: #e2e8f0 !important; }
    [data-testid="stSidebar"] .stRadio label {
        color: #e2e8f0 !important; font-size: 15px !important; padding: 4px 0 !important;
    }
    [data-testid="stSidebar"] hr { border-color: #2d3748 !important; }
    .metric-card {
        background: #1e2130; border-radius: 10px;
        padding: 16px 20px; margin-bottom: 10px;
    }
    .stTabs [data-baseweb="tab"] { font-size: 15px; }
    div[data-testid="stMetricValue"] > div { font-size: 28px; }
</style>
""", unsafe_allow_html=True)

# ── Autenticación ─────────────────────────────────────────────────────────────
try:
    import auth
    AUTH_DISPONIBLE = True
except Exception:
    AUTH_DISPONIBLE = False

# Si la autenticación está disponible, verificar login
if AUTH_DISPONIBLE:
    if not auth.esta_logueado():
        auth.render_login()
        st.stop()  # No mostrar nada más hasta que el usuario se loguee

# ── Navegación lateral ────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📈 Cartera AR")
    st.markdown("---")
    pagina = st.radio(
        "Navegación",
        ["🏠 Inicio",
         "📊 Análisis de Cartera",
         "📈 Análisis Técnico",
         "🇦🇷 CEDEARs",
         "💼 Mi Cartera",
         "📰 Info de Mercado",
         "🏦 Bonos y ON"],
        label_visibility="collapsed"
    )
    st.markdown("---")
    st.caption("v3.0 — Walter Caamaño")

    # Mostrar usuario logueado y botón de cerrar sesión
    if AUTH_DISPONIBLE:
        auth.render_usuario_sidebar()

# ── Enrutamiento ──────────────────────────────────────────────────────────────
import importlib

_PAGINAS = {
    "🏠 Inicio":             "pages.inicio",
    "📊 Análisis de Cartera":"pages.analisis",
    "📈 Análisis Técnico":   "pages.tecnico",
    "🇦🇷 CEDEARs":          "pages.cedears",
    "💼 Mi Cartera":         "pages.mi_cartera",
    "📰 Info de Mercado":    "pages.mercado",
    "🏦 Bonos y ON":         "pages.bonos",
}

if pagina in _PAGINAS:
    modulo = importlib.import_module(_PAGINAS[pagina])
    importlib.reload(modulo)
    modulo.render()