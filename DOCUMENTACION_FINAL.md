# 📈 Cartera AR — Documentación Final del Proyecto

**Versión**: 3.0  
**Autor**: Walter Caamaño  
**Fecha**: Julio 2026  
**URL**: https://cartera-ar.streamlit.app

---

## 🏗️ Arquitectura del sistema

```
CarteraAR/
├── .streamlit/
│   ├── config.toml          ← Tema oscuro
│   └── secrets.toml         ← Credenciales Supabase (NO subir a GitHub)
├── data/
│   ├── BYMA-Tabla-CEDEARs.pdf
│   └── ratios_cedear.csv
├── scripts/
│   ├── app.py               ← Punto de entrada Streamlit
│   ├── auth.py              ← Autenticación multi-usuario
│   ├── cartera_db.py        ← Base de datos (SQLite local / PostgreSQL Supabase)
│   ├── cedear_mapper.py     ← Equivalencias CEDEAR ↔ ADR
│   ├── core.py              ← Markowitz, fundamentales, CCL
│   ├── market_info.py       ← Noticias, ratings, ETFs, bonos, MEP
│   ├── tecnico.py           ← RSI, MA, Squeeze, ADX, Order Blocks
│   ├── Historico.py         ← Análisis desktop (genera Excel)
│   ├── generar_reporte.py   ← Reporte Excel ejecutivo
│   ├── setup_db.py          ← Crear tablas en Supabase
│   ├── verificar_supabase.py← Verificar estado de la DB
│   └── pages/
│       ├── inicio.py        ← Página de bienvenida
│       ├── analisis.py      ← Markowitz + Fundamentales
│       ├── tecnico.py       ← Análisis técnico por ticker
│       ├── cedears.py       ← Valor implícito CEDEARs
│       ├── mi_cartera.py    ← Gestión multi-cartera
│       ├── rotacion.py      ← Señal de rotación combinada
│       ├── mercado.py       ← Noticias + ratings + ETFs
│       └── bonos.py         ← Bonos soberanos + ONs + tipos de cambio
├── .gitignore
├── README.md
└── requirements.txt
```

---

## 🗄️ Base de datos (Supabase PostgreSQL)

### Tablas

| Tabla | Descripción | Registros típicos |
|-------|-------------|-------------------|
| `usuarios` | Cuentas de usuario con auth | 1-10 |
| `carteras` | Carteras por usuario | 1-5 por usuario |
| `posiciones` | Acciones y CEDEARs | 5-50 por cartera |
| `movimientos` | Compras y ventas | Ilimitado |
| `ganancias_realizadas` | Ventas cerradas | Ilimitado |
| `renta_fija` | Bonos, LECAPs, ONs | 1-20 por cartera |
| `fci` | Fondos comunes | 1-10 por cartera |
| `alertas` | Alertas por precio/RSI | 1-20 por cartera |

### Columnas clave

```sql
-- Carteras asociadas a usuarios
carteras.usuario_id → usuarios.id

-- Posiciones con tipo de activo
posiciones.es_cedear = 0 (internacional) | 1 (CEDEAR/local ARS)

-- Renta fija con precio en % del VN
renta_fija.precio_compra_pct = 85.50 (85.50% del valor nominal)
```

---

## 🔐 Autenticación

- **Sistema**: SHA-256 + salt aleatorio (sin dependencias externas)
- **Sesión**: `st.session_state` de Streamlit
- **Privacidad**: cada usuario ve SOLO sus propias carteras
- **Roles**: usuario normal / admin (campo `es_admin`)

### Usuarios actuales
| ID | Nombre | Email |
|----|--------|-------|
| 1 | Walter Caamaño | caamanowalter@gmail.com |
| 2 | Mauro Manghessi | mauro.m021@gmail.com |
| 3 | Cecilia Carattoni | cecarattoni@gmail.com |

---

## 📊 Módulos de análisis

### 1. Markowitz (core.py)
- Descarga histórica vía yfinance
- Portafolio Equilibrado, Mínima Varianza, Máximo Sharpe
- Frontera eficiente con 200 puntos
- Correlaciones y covarianzas

### 2. Análisis Técnico (tecnico.py)
- **RSI (14)**: Wilder's RMA, divergencias bull/bear, estadísticas históricas
- **MA 9/21**: Golden/Death Cross, retornos post-cruce a 10/20/30/60 días
- **Squeeze Momentum**: BB vs KC, momentum lineal (regresión), niveles de compresión
- **ADX**: DI+/DI-, fuerza de tendencia
- **Order Blocks**: swings + volumen institucional, soportes/resistencias activos

### 3. Señal de Rotación (rotacion.py)
```
Score 0-100 = Markowitz(30) + RSI(25) + Squeeze+ADX(25) + Order Blocks(20)

≥70 + subponderado → 🟢 SUMAR
≥70               → 🟢 COMPRAR/MANTENER
55-69 + subpond.  → 🟡 CONSIDERAR SUMAR
45-54             → 🟡 MANTENER
30-44 + sobrepond.→ 🔴 REDUCIR
<30               → 🔴 VENDER/REDUCIR
```

### 4. CEDEARs (cedear_mapper.py + core.py)
- Equivalencias CEDEAR ↔ ADR desde BYMA API (cache 7 días)
- Precio ARS desde ticker `.BA` en Yahoo Finance
- Valor implícito = (Precio USD / Ratio) × CCL
- CCL desde DolarApi.com / ArgentinaDatos / DolarSi (fallback)

### 5. Información de mercado (market_info.py)
- Noticias vía Yahoo Finance RSS
- Ratings de analistas (upgrades/downgrades)
- Precio objetivo consenso + upside
- Próximos earnings y dividendos
- Métricas ETF (AUM, yield, retornos, beta, top holdings)
- Tipos de cambio: CCL, MEP, Oficial, Blue, Cripto
- Bonos soberanos desde ArgentinaDatos + BYMA
- ONs corporativas desde BYMA

---

## 🚀 Deploy y mantenimiento

### Actualizar la app
```cmd
cd "C:\Users\User\Desktop\Carteras PY"
git add .
git commit -m "Descripción del cambio"
git push
```
Streamlit Cloud detecta el push y redespliega automáticamente (~2 min).

### Verificar estado de Supabase
```cmd
cd scripts
python verificar_supabase.py
```

### Backup de datos
```cmd
python -c "
import psycopg2, pandas as pd
con = psycopg2.connect('postgresql://postgres.vcrnckjhuohtqeqaopmo:Wc4001Bc3086@aws-1-sa-east-1.pooler.supabase.com:6543/postgres')
for tabla in ['carteras','posiciones','movimientos','renta_fija','fci']:
    df = pd.read_sql(f'SELECT * FROM {tabla}', con)
    df.to_csv(f'backup_{tabla}.csv', index=False)
    print(f'✅ {tabla}: {len(df)} registros')
con.close()
"
```

### Agregar nuevo usuario (admin)
```cmd
python -c "
import psycopg2, hashlib, secrets
email = 'nuevo@email.com'
nombre = 'Nombre Apellido'
password = 'contraseña123'
salt = secrets.token_hex(32)
h = hashlib.sha256(f'{salt}{password}'.encode()).hexdigest()
con = psycopg2.connect('postgresql://postgres.vcrnckjhuohtqeqaopmo:Wc4001Bc3086@aws-1-sa-east-1.pooler.supabase.com:6543/postgres')
cur = con.cursor()
cur.execute('INSERT INTO usuarios (email,nombre,password_hash,salt,creado) VALUES (%s,%s,%s,%s,NOW())',
            (email, nombre, h, salt))
con.commit()
con.close()
print(f'Usuario {nombre} creado')
"
```

---

## 📱 Acceso

| Dispositivo | URL |
|-------------|-----|
| PC / Mac | https://cartera-ar.streamlit.app |
| Celular | https://cartera-ar.streamlit.app |
| Local (PC encendida) | http://192.168.100.11:8501 |

---

## 🔧 Mantenimiento periódico

### Mensual
- [ ] Actualizar `ratios_cedear.csv` desde BYMA
- [ ] Verificar que las APIs de CCL siguen funcionando
- [ ] Revisar alertas activas

### Trimestral
- [ ] Backup de la base de datos
- [ ] Actualizar `requirements.txt` con nuevas versiones
- [ ] Revisar equivalencias CEDEAR ↔ ADR

### Ante errores
1. Revisar logs en Streamlit Cloud → "Manage app" → "Logs"
2. Ejecutar `python verificar_supabase.py`
3. Verificar que Yahoo Finance no cambió su API

---

## 📦 Dependencias principales

```
streamlit>=1.45.0      ← Framework web
yfinance>=0.2.66       ← Datos de mercado
pandas>=2.0.0          ← Procesamiento de datos
numpy>=1.24.0          ← Cálculos numéricos
scipy>=1.10.0          ← Optimización Markowitz
plotly>=5.0.0          ← Gráficos interactivos
psycopg2-binary>=2.9.0 ← Conexión PostgreSQL/Supabase
openpyxl>=3.1.0        ← Exportar Excel
deep-translator>=1.11.0← Traducción de noticias
```

---

## 🐛 Bugs conocidos y soluciones

| Bug | Causa | Solución |
|-----|-------|----------|
| Precio CEDEAR incorrecto | Yahoo Finance rate limiting | Esperar y recargar |
| `INTERNACIONALES_DIRECTOS` no definida | Cache de Streamlit Cloud | Push con cambio en cedear_mapper.py |
| `applymap` deprecated | pandas 2.x | Usar `.map()` |
| `background_gradient` falla | matplotlib no instalado | Usar `.map()` con colores inline |
| Login no aparece | app.py viejo en GitHub | Push del app.py con auth |

---

## 📈 Roadmap futuro

### Corto plazo
- [ ] Notificaciones Telegram cuando se dispara una alerta
- [ ] Actualización automática del PDF de ratios BYMA
- [ ] Precio actual de bonos en tiempo real (BYMA API)
- [ ] Actualización automática VCP de FCIs (CAFCI API)

### Mediano plazo
- [ ] Análisis de riesgo de cartera (VaR, CVaR)
- [ ] Comparación vs benchmark (SPY, Merval)
- [ ] Historial de P&L en el tiempo (gráfico de evolución)
- [ ] Importar operaciones desde broker (CSV de IOL, Balanz, etc.)

### Largo plazo
- [ ] App móvil nativa (React Native)
- [ ] Integración con brokers vía API
- [ ] Alertas por email además de Telegram
- [ ] Análisis de opciones y futuros