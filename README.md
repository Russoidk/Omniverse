# Omniverse 1.0.5

**Omniverse — Forja de Mundos** es una aplicación de escritorio para organizar proyectos creativos. Permite administrar personajes, lugares, acontecimientos, cronologías y redes conceptuales desde una interfaz local.

Esta publicación contiene el **código fuente**. El instalador de Windows se distribuye por separado en la sección **Releases** de GitHub.

## Funcionalidades

- Gestión de cuentas y proyectos locales.
- Fichas de personajes, rasgos, citas, historias y relaciones.
- Administración de lugares y acontecimientos.
- Cronología con eras y lapsos temporales.
- Red conceptual con filtros, relaciones y controles de distribución.
- Exportación de fichas y cronologías a PDF y PNG.
- Aplicación de escritorio mediante Electron y servidor local Django.

## Tecnologías

- Python y Django.
- SQLite.
- HTML, CSS y JavaScript.
- Electron y electron-builder.

## Requisitos para desarrollar

- Windows 10/11 de 64 bits.
- Python 3.12 a 3.14.
- Node.js y npm (para ejecutar o compilar la versión Electron).

## Obtener el código

Clona el repositorio desde GitHub o descarga el ZIP del código fuente. Abre una terminal en la carpeta `Omniverse`.

### Ejecutar Django en modo web local

En PowerShell:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

Después abre `http://127.0.0.1:8000/` en el navegador. La base de datos local se crea al aplicar las migraciones y queda excluida del repositorio mediante `.gitignore`.

### Ejecutar la aplicación Electron

Instala las dependencias de Node y ejecuta:

```powershell
npm ci
npm start
```

Electron prepara su entorno local de Python y las dependencias de Django en el primer inicio. Si no tienes Python instalado, ejecuta primero el descargador oficial incluido en el proyecto:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\download-python.ps1
```

Se requiere conexión a Internet durante la primera preparación para descargar las dependencias de Python.

### Volver a generar el instalador de Windows

En una máquina Windows con Node.js instalado, desde la carpeta del proyecto ejecuta:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\download-python.ps1
npm ci
npm run dist
```

Electron-builder genera el instalador dentro de `release/`. El instalador `.exe` no se incluye en el repositorio: se adjunta a una Release de GitHub para que las personas puedan descargarlo sin mezclar binarios con el historial del código fuente.

## Datos y privacidad

Este repositorio no contiene bases de datos SQLite, cuentas, contraseñas, imágenes subidas por usuarios ni proyectos personales. Cada ejecución crea/usa su propia base de datos local. Los datos de la aplicación instalada se guardan en la carpeta de datos del usuario de Windows, no en el repositorio.

Omniverse está preparado como aplicación local de escritorio. La configuración incluida no debe considerarse una configuración lista para alojar públicamente como servicio web de producción.

## Estructura general

- `accounts/`: cuentas y autenticación.
- `characters/`: personajes y relaciones.
- `concept_map/`: red conceptual.
- `projects/`: proyectos.
- `timeline/`: cronología y acontecimientos.
- `website/`: páginas del sitio local.
- `omniverse/`: configuración y rutas principales de Django.
- `templates/` y `static/`: interfaz y recursos visuales.
- `build/`: iconos y configuración del instalador NSIS.

## Versión

Código fuente: **1.0.5**.
