"""
app.py — Punto de entrada de la aplicación Streamlit.
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
    /* Ocultar navegación automática de Streamlit (páginas de la carpeta pages/) */
    [data-testid="stSidebarNav"] { display: none !important; }

    /* Sidebar — fondo oscuro con texto claro */
    [data-testid="stSidebar"] {
        background-color: #1a1f2e !important;
    }
    [data-testid="stSidebar"] * {
        color: #e2e8f0 !important;
    }
    [data-testid="stSidebar"] .stRadio label {
        color: #e2e8f0 !important;
        font-size: 15px !important;
        padding: 4px 0 !important;
    }
    [data-testid="stSidebar"] .stRadio div[role="radiogroup"] {
        gap: 4px !important;
    }
    /* Radio button seleccionado */
    [data-testid="stSidebar"] .stRadio label[data-baseweb="radio"] span {
        color: #e2e8f0 !important;
    }
    /* Títulos y texto en sidebar */
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] div {
        color: #e2e8f0 !important;
    }
    /* Separador */
    [data-testid="stSidebar"] hr {
        border-color: #2d3748 !important;
    }

    /* Contenido principal */
    .metric-card {
        background: #1e2130; border-radius: 10px;
        padding: 16px 20px; margin-bottom: 10px;
    }
    .metric-card h3 { color: #a0aec0; font-size: 13px; margin: 0 0 4px 0; }
    .metric-card p  { color: #ffffff;  font-size: 24px; font-weight: 700; margin: 0; }
    .stTabs [data-baseweb="tab"] { font-size: 15px; }
    div[data-testid="stMetricValue"] > div { font-size: 28px; }
</style>
""", unsafe_allow_html=True)

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
         "📰 Info de Mercado"],
        label_visibility="collapsed"
    )
    st.markdown("---")
    st.caption("v3.0 — Walter Caamaño")

# ── Enrutamiento ──────────────────────────────────────────────────────────────
import importlib

_PAGINAS = {
    "🏠 Inicio":             "pages.inicio",
    "📊 Análisis de Cartera":"pages.analisis",
    "📈 Análisis Técnico":   "pages.tecnico",
    "🇦🇷 CEDEARs":          "pages.cedears",
    "💼 Mi Cartera":         "pages.mi_cartera",
    "📰 Info de Mercado":    "pages.mercado",
}

if pagina in _PAGINAS:
    modulo = importlib.import_module(_PAGINAS[pagina])
    importlib.reload(modulo)   # fuerza recarga al cambiar de página
    modulo.render()