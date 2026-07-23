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
    /* ── Ocultar nav automática ── */
    [data-testid="stSidebarNav"] { display: none !important; }

    /* ── Sidebar oscuro ── */
    [data-testid="stSidebar"] { background-color: #1a1f2e !important; }
    [data-testid="stSidebar"] * { color: #e2e8f0 !important; }
    [data-testid="stSidebar"] .stRadio label {
        color: #e2e8f0 !important;
        font-size: 15px !important;
        padding: 6px 0 !important;
        min-height: 36px !important;  /* botones más grandes en móvil */
    }
    [data-testid="stSidebar"] hr { border-color: #2d3748 !important; }

    /* ── Métricas ── */
    .metric-card {
        background: #1e2130; border-radius: 10px;
        padding: 16px 20px; margin-bottom: 10px;
    }
    div[data-testid="stMetricValue"] > div { font-size: 24px; }

    /* ── Tabs más grandes en móvil ── */
    .stTabs [data-baseweb="tab"] {
        font-size: 13px !important;
        padding: 8px 10px !important;
        min-height: 40px !important;
    }

    /* ── Tablas responsivas ── */
    [data-testid="stDataFrame"] {
        overflow-x: auto !important;
        -webkit-overflow-scrolling: touch !important;
    }
    [data-testid="stDataFrame"] table {
        font-size: 12px !important;
    }
    [data-testid="stDataFrame"] th {
        font-size: 11px !important;
        white-space: nowrap !important;
        padding: 4px 6px !important;
    }
    [data-testid="stDataFrame"] td {
        font-size: 12px !important;
        padding: 4px 6px !important;
    }

    /* ── Botones más grandes en móvil ── */
    .stButton > button {
        min-height: 44px !important;
        font-size: 14px !important;
        border-radius: 8px !important;
    }

    /* ── Inputs más grandes ── */
    .stTextInput input, .stNumberInput input, .stSelectbox select {
        min-height: 40px !important;
        font-size: 14px !important;
    }

    /* ── Formularios más compactos en móvil ── */
    @media (max-width: 768px) {
        /* Reducir padding en móvil */
        .block-container {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            padding-top: 1rem !important;
        }
        /* Métricas más compactas */
        div[data-testid="stMetricValue"] > div { font-size: 18px !important; }
        div[data-testid="stMetricLabel"] { font-size: 11px !important; }
        /* Tabs más pequeños */
        .stTabs [data-baseweb="tab"] {
            font-size: 11px !important;
            padding: 6px 6px !important;
        }
        /* Ocultar columnas menos importantes en tablas */
        .hide-mobile { display: none !important; }
    }

    /* ── Gráficos responsivos ── */
    .js-plotly-plot {
        width: 100% !important;
    }

    /* ── Cards de información ── */
    div[style*="border-radius:10px"] {
        margin-bottom: 8px !important;
    }

    /* ── Expanders más compactos ── */
    .streamlit-expanderHeader {
        font-size: 14px !important;
        min-height: 40px !important;
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
    # Logo y nombre
    import os
    logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo_financieramente.png")
    if os.path.exists(logo_path):
        st.image(logo_path, width=80)
    st.markdown(
        '<div style="text-align:left;margin-bottom:4px">'
        '<span style="font-size:20px;font-weight:700;color:#e2e8f0">📈 Cartera AR</span><br>'
        '<a href="https://www.instagram.com/financieramente.ok?igsh=MTFkbDJwdDEzNWYzcA==" '
        'target="_blank" style="color:#4f8ef7;font-size:12px;text-decoration:none">'
        '📸 @financieramente.ok</a>'
        '</div>',
        unsafe_allow_html=True
    )
    st.markdown("---")
    _opciones = ["🏠 Inicio", "📊 Análisis de Cartera", "📈 Análisis Técnico",
                 "🇦🇷 CEDEARs", "💼 Mi Cartera", "📈 Historial P&L",
                 "🏆 vs Benchmark", "🔄 Señal de Rotación",
                 "📰 Info de Mercado", "🏦 Bonos y ON",
                 "🔔 Alertas y Notif."]
    _idx = 0
    if "_pagina_actual" in st.session_state and st.session_state["_pagina_actual"] in _opciones:
        _idx = _opciones.index(st.session_state["_pagina_actual"])
    pagina = st.radio(
        "Navegación", _opciones,
        index=_idx,
        label_visibility="collapsed"
    )
    st.session_state["_pagina_actual"] = pagina
    st.markdown("---")
    st.caption("v3.0 — Financieramente.ok")

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
    if _snap_key not in st.session_state:
        try:
            import cartera_db as _cdb
            import core as _core
            _uid  = auth.get_user_id()
            _ccl  = _core.obtener_dolar_ccl()
            _carts = _cdb.listar_carteras(usuario_id=_uid)
            if not _carts.empty:
                from pages.historial import guardar_snapshot, init_historial_db
                init_historial_db()
                for _, _row in _carts.iterrows():
                    guardar_snapshot(_row['id'], _ccl)
            st.session_state[_snap_key] = True
        except Exception:
            pass  # No interrumpir la app si falla el snapshot

if pagina in _PAGINAS:
    modulo = importlib.import_module(_PAGINAS[pagina])
    importlib.reload(modulo)
    modulo.render()