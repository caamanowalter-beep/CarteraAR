# 🚀 Deploy en Streamlit Cloud — Paso a paso

## Estructura final del repositorio GitHub

```
CarteraAR/                          ← nombre del repo en GitHub
├── requirements.txt                ← dependencias Python
├── README.md                       ← descripción del proyecto
├── .gitignore                      ← archivos a ignorar
├── .streamlit/
│   └── config.toml                 ← tema y configuración
└── scripts/
    ├── app.py                      ← punto de entrada
    ├── core.py
    ├── cedear_mapper.py
    ├── cartera_db.py
    ├── tecnico.py
    ├── market_info.py
    ├── fuentes.py
    ├── data/
    │   ├── ratios_cedear.csv       ← SÍ subir (datos estáticos)
    │   └── BYMA-Tabla-CEDEARs.pdf ← SÍ subir
    └── pages/
        ├── __init__.py
        ├── inicio.py
        ├── analisis.py
        ├── tecnico.py
        ├── cedears.py
        ├── mi_cartera.py
        └── mercado.py
```

---

## PASO 1 — Crear repositorio en GitHub

1. Ir a [github.com](https://github.com) → **New repository**
2. Nombre: `CarteraAR` (o el que prefieras)
3. Visibilidad: **Public** (requerido para Streamlit Cloud gratuito)
4. NO inicializar con README (lo tenemos nuestro)
5. Click **Create repository**

---

## PASO 2 — Subir el proyecto desde PyCharm

### Opción A — Desde la terminal de PyCharm

```cmd
cd "C:\Users\Dycar\Desktop\Desarrollos Phyton\Cartera"

:: Inicializar Git
git init
git add .
git commit -m "Initial commit — Cartera AR v3.0"

:: Conectar con GitHub (reemplazar TU_USUARIO con tu usuario de GitHub)
git remote add origin https://github.com/TU_USUARIO/CarteraAR.git
git branch -M main
git push -u origin main
```

### Opción B — Desde PyCharm (interfaz gráfica)

1. Menú → **VCS → Enable Version Control Integration → Git**
2. Menú → **Git → GitHub → Share Project on GitHub**
3. Nombre del repo: `CarteraAR`
4. Click **Share**

---

## PASO 3 — Configurar Streamlit Cloud

1. Ir a [share.streamlit.io](https://share.streamlit.io)
2. Click **Sign in with GitHub**
3. Click **New app**
4. Completar:

| Campo | Valor |
|-------|-------|
| **Repository** | `TU_USUARIO/CarteraAR` |
| **Branch** | `main` |
| **Main file path** | `scripts/app.py` |

5. Click **Deploy!**

La app se despliega en ~2-3 minutos en una URL como:
```
https://tu-usuario-carteraar-scripts-app-xxxxx.streamlit.app
```

---

## PASO 4 — Acceso desde celular

Una vez desplegada, la URL funciona en cualquier dispositivo:
- 📱 Celular (cualquier navegador)
- 💻 Tablet
- 🖥️ Otra PC

**Sin necesidad de tener tu PC encendida.**

---

## ⚠️ Consideraciones importantes

### Base de datos (Mi Cartera)
En Streamlit Cloud, los archivos en `/tmp/` se borran cuando el servidor
se reinicia (cada ~24-48hs de inactividad). Para persistencia real:

**Opción gratuita**: Usar **Supabase** (PostgreSQL gratuito en la nube)
- Registro en [supabase.com](https://supabase.com)
- Crear proyecto → obtener connection string
- Agregar en Streamlit Cloud → **Secrets**:
  ```toml
  [database]
  url = "postgresql://..."
  ```

**Opción simple**: Exportar/importar la cartera como CSV desde la app
antes de que el servidor se reinicie.

### Archivos grandes
- `BYMA-Tabla-CEDEARs.pdf` → subir al repo (< 25MB)
- `ratios_cedear.csv` → subir al repo
- `cartera.db` → NO subir (datos personales, se genera en /tmp/)

### Actualizaciones
Para actualizar la app después de cambios:
```cmd
git add .
git commit -m "Descripción del cambio"
git push
```
Streamlit Cloud detecta el push y redespliega automáticamente.

---

## PASO 5 — Verificar el deploy

Checklist post-deploy:
- [ ] La app carga sin errores
- [ ] Navegación entre páginas funciona
- [ ] Análisis de Cartera descarga datos de Yahoo Finance
- [ ] CEDEARs obtiene el CCL
- [ ] Mi Cartera permite crear carteras
- [ ] Info de Mercado muestra noticias

---

## Comandos Git útiles

```cmd
:: Ver estado de archivos
git status

:: Ver historial de commits
git log --oneline

:: Actualizar desde GitHub (si editás desde la web)
git pull

:: Ver diferencias antes de commitear
git diff
```