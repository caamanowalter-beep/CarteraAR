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

# ── Estilos globales + UX móvil ──────────────────────────────────────────────
st.markdown("""
<style>
    [data-testid="stSidebarNav"] { display: none !important; }
    [data-testid="stSidebar"] { background-color: #1a1f2e !important; }
    [data-testid="stSidebar"] * { color: #e2e8f0 !important; }
    [data-testid="stSidebar"] .stRadio label {
        color: #e2e8f0 !important; font-size: 13px !important;
        padding: 4px 0 !important; min-height: 28px !important;
    }
    [data-testid="stSidebar"] hr { border-color: #2d3748 !important; }
    div[data-testid="stMetricValue"] > div { font-size: 17px !important; }
    div[data-testid="stMetricLabel"] { font-size: 11px !important; }
    div[data-testid="stMetricDelta"] { font-size: 11px !important; }
    .stTabs [data-baseweb="tab"] {
        font-size: 12px !important; padding: 5px 8px !important; min-height: 30px !important;
    }
    [data-testid="stDataFrame"] { overflow-x: auto !important; }
    [data-testid="stDataFrame"] table { font-size: 11px !important; }
    [data-testid="stDataFrame"] th {
        font-size: 10px !important; white-space: nowrap !important; padding: 3px 5px !important;
    }
    [data-testid="stDataFrame"] td { font-size: 11px !important; padding: 3px 5px !important; }
    .stButton > button {
        min-height: 32px !important; font-size: 12px !important;
        border-radius: 6px !important; padding: 3px 10px !important;
    }
    .stTextInput input, .stNumberInput input {
        min-height: 30px !important; font-size: 12px !important; padding: 3px 8px !important;
    }
    .stSelectbox > div > div { min-height: 30px !important; font-size: 12px !important; }
    .stSelectbox label, .stTextInput label, .stNumberInput label,
    .stDateInput label, .stSlider label {
        font-size: 11px !important; margin-bottom: 1px !important;
    }
    .block-container {
        padding-top: 0.8rem !important; padding-bottom: 0.8rem !important;
        max-width: 1200px !important;
    }
    h1 { font-size: 19px !important; margin-bottom: 6px !important; }
    h2 { font-size: 16px !important; margin-bottom: 5px !important; }
    h3 { font-size: 14px !important; margin-bottom: 4px !important; }
    h4 { font-size: 13px !important; margin-bottom: 3px !important; }
    @media (max-width: 768px) {
        .block-container { padding-left: 0.8rem !important; padding-right: 0.8rem !important; }
        div[data-testid="stMetricValue"] > div { font-size: 15px !important; }
        .stTabs [data-baseweb="tab"] { font-size: 10px !important; padding: 4px 5px !important; }
    }
</style>
""", unsafe_allow_html=True)

# ── Autenticación ─────────────────────────────────────────────────────────────
try:
    import auth
    AUTH_DISPONIBLE = True
except Exception:
    AUTH_DISPONIBLE = False

if AUTH_DISPONIBLE:
    if not auth.esta_logueado():
        auth.render_login()
        st.stop()

# ── Navegación lateral ────────────────────────────────────────────────────────
# Manejar navegación desde botones de acceso rápido (móvil)
if "_nav_override" in st.session_state:
    _nav_target = st.session_state.pop("_nav_override")
    st.session_state["_pagina_actual"] = _nav_target
with st.sidebar:
    import os
    logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo_financieramente.png")
    col_logo, col_title = st.columns([1, 3])
    with col_logo:
        if os.path.exists(logo_path):
            st.image(logo_path, width=55)
    with col_title:
        st.markdown(
            '<div style="padding-top:4px">'
            '<span style="font-size:17px;font-weight:700;color:#e2e8f0">Cartera AR</span><br>'
            '<a href="https://www.instagram.com/financieramente.ok" '
            'target="_blank" style="color:#4f8ef7;font-size:11px;text-decoration:none">'
            '@financieramente.ok</a></div>',
            unsafe_allow_html=True
        )
    if AUTH_DISPONIBLE and auth.esta_logueado():
        try:
            u = auth.get_usuario_actual()
            if u:
                st.markdown(
                    f'<div style="background:#1e2130;padding:7px 10px;border-radius:8px;'
                    f'margin:6px 0;border-left:3px solid #4f8ef7">'
                    f'<div style="color:#aaa;font-size:10px">Usuario</div>'
                    f'<div style="color:#e2e8f0;font-size:12px;font-weight:600">{u.get("nombre","")}</div>'
                    f'<div style="color:#aaa;font-size:10px">{u.get("email","")}</div></div>',
                    unsafe_allow_html=True
                )
                if st.button("Cerrar sesion", key="btn_logout_top",
                             use_container_width=True, type="secondary"):
                    auth.logout()
                    st.rerun()
        except Exception:
            pass
    st.markdown("---")
    
    _opciones = [
        # ── Dashboard ──
        "\U0001f3e0 Inicio",
        # ── Mi Cartera ──
        "\U0001f4bc Mi Cartera",
        "\U0001fa99 Crypto",
        "\U0001f4c8 Historial P&L",
        "\U0001f504 Se\u00f1al de Rotaci\u00f3n",
        # ── An\u00e1lisis ──
        "\U0001f4ca An\u00e1lisis de Cartera",
        "\U0001f4c8 An\u00e1lisis T\u00e9cnico",
        "\U0001f3c6 vs Benchmark",
        # ── Mercado ──
        "\U0001f1e6\U0001f1f7 CEDEARs",
        "\U0001f3e6 Bonos y ON",
        "\U0001f4f0 Info de Mercado",
        # ── Configuraci\u00f3n ──
        "\U0001f514 Alertas y Notif.",
    ]
    _idx = 0
    pagina = st.radio(
        "Navegación", _opciones,
        index=_idx,
        label_visibility="collapsed"
    )
    st.session_state["_pagina_actual"] = pagina
    st.markdown("---")
    st.caption("v3.0 — Financieramente.ok")

    # Info usuario ya mostrada arriba del sidebar

# ── Enrutamiento ──────────────────────────────────────────────────────────────
import importlib

_PAGINAS = {
    "🏠 Inicio":             "pages.inicio",
    "📊 Análisis de Cartera":"pages.analisis",
    "📈 Análisis Técnico":   "pages.tecnico",
    "🇦🇷 CEDEARs":          "pages.cedears",
    "💼 Mi Cartera":         "pages.mi_cartera",
    "🪙 Crypto":             "pages.crypto",
    "📈 Historial P&L":      "pages.historial",
    "🏆 vs Benchmark":       "pages.benchmark",
    "🔄 Señal de Rotación":  "pages.rotacion",
    "📰 Info de Mercado":    "pages.mercado",
    "🔔 Alertas y Notif.":   "pages.alertas_config",
    "🏦 Bonos y ON":         "pages.bonos",
}

# ── Auto-snapshot al iniciar sesión ──────────────────────────────────────────
# Guarda automáticamente el valor de todas las carteras una vez por día
if AUTH_DISPONIBLE and auth.esta_logueado():
    _hoy = __import__('datetime').date.today().strftime("%Y-%m-%d")
    _snap_key = f"snapshot_done_{_hoy}"
    

if pagina in _PAGINAS:
    modulo = importlib.import_module(_PAGINAS[pagina])
    importlib.reload(modulo)
    modulo.render()