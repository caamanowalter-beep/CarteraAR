"""
pages/inicio.py — Página de bienvenida y resumen del sistema.
"""
import streamlit as st

def render():
    st.title("📈 Cartera AR — Análisis de Portafolios")
    st.markdown("### Bienvenido al sistema de análisis de inversiones")
    st.markdown("---")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.info("📊 **Análisis de Cartera**\n\nMarkowitz, Sharpe, frontera eficiente y fundamentales")
    with col2:
        st.info("🇦🇷 **CEDEARs**\n\nValor implícito vs precio ARS con CCL en tiempo real")
    with col3:
        st.info("💼 **Mi Cartera**\n\nRegistrá tus posiciones y seguí tu P&L en tiempo real")
    with col4:
        st.info("🔔 **Alertas**\n\nConfigurá alertas por precio o RSI por ticker")

    st.markdown("---")
    st.markdown("## ¿Cómo usar la app?")

    with st.expander("📊 Análisis de Cartera", expanded=False):
        st.markdown("""
        1. Ingresá los tickers que querés analizar (separados por coma)
        2. Ajustá los filtros fundamentales (Margen Neto, ROIC, D/E)
        3. La app descarga datos históricos y calcula:
           - **Estadísticas**: retorno esperado, varianza, desviación estándar
           - **Markowitz**: portafolio de mínima varianza y máximo Sharpe
           - **Frontera eficiente**: gráfico interactivo riesgo vs retorno
           - **Fundamentales**: ratios clave por ticker con score 0-100
        4. Exportá los resultados a Excel
        """)

    with st.expander("🇦🇷 CEDEARs", expanded=False):
        st.markdown("""
        1. La app obtiene el **dólar CCL** automáticamente desde 3 fuentes
        2. Carga los **ratios de conversión** desde el PDF de BYMA o CSV
        3. Calcula el **valor implícito** de cada CEDEAR en ARS
        4. Compara con el **precio de mercado** y muestra si está Barato o Caro
        5. Las equivalencias CEDEAR ↔ ADR se actualizan automáticamente
           (BYMA ≠ BMA — Bolsa Argentina ≠ Banco Macro)
        """)

    with st.expander("💼 Mi Cartera", expanded=False):
        st.markdown("""
        1. **Agregá posiciones**: ticker, cantidad, precio de compra, moneda, fecha
        2. La app calcula tu **P&L en tiempo real** (USD y ARS)
        3. Compará tu cartera actual vs el **portafolio óptimo de Markowitz**
        4. Recibí **señales de rotación**: Sumar / Mantener / Reducir
        5. Configurá **alertas** por precio o RSI
        """)

    st.markdown("---")
    st.markdown("## Tickers soportados")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        **Internacionales (NYSE/NASDAQ)**
        - AAPL, MSFT, NVDA, GOOGL, META, AMZN, TSLA
        - KO, MCD, INTC, AMD, ARKK, DOW, MELI, PBR
        - QQQ, SPY, RIO, SNOW, V, VIST, XLF, XLP
        - IBIT, NU, DIS, BRK-A, BRK-B, y más...
        """)
    with col2:
        st.markdown("""
        **Argentinos con ADR**
        - BMA (Banco Macro), GGAL (Galicia)
        - BBAR (BBVA Arg), SUPV (Supervielle)
        - YPFD → YPF, PAMP → PAM
        - CEPU, TGSU2 → TGS, TECO2 → TEO
        - EDN, IRSA → IRS

        **Argentinos sin ADR**
        - BYMA, ALUA, TXAR, TGNO4, LOMA, y más
        """)

    st.markdown("---")
    st.caption("Datos provistos por Yahoo Finance · CCL desde DolarApi / ArgentinaDatos · Ratios CEDEAR desde BYMA")