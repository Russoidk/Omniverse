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
