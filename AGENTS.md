# Reglas de trabajo

## Datos

- Los datos viven fuera del repositorio, en la carpeta indicada por `DATA_DIR` en `.env`. Nunca se guardan datos en el repositorio.
- Los archivos de `DATA_DIR/catalogue` y `DATA_DIR/raw` no se modifican. Todo resultado derivado se escribe en una carpeta nueva.
- Las rutas se construyen a partir de `DATA_DIR`. No se escriben rutas absolutas en el código.

## Código

- Todo el código vive en `code/`, organizado en subcarpetas por etapa.
- Los scripts siguen la convención de prefijos: `0XX` maestros y configuración, `1XX` obtención y limpieza de datos, `2XX` análisis exploratorio y descriptivo, `3XX` análisis inferencial.
- Se usa el entorno virtual `code/.venv`. Toda dependencia nueva se agrega a `code/requirements.txt`.
- Cada subcarpeta nueva se documenta en `REPO_STRUCTURE.md` con su propósito y cómo correrla.

## Control de versiones

- No se modifica el historial de git ni el repositorio remoto sin autorización del responsable del proyecto.
- Las llaves y credenciales van únicamente en `.env`, que no se versiona.

## Estilo

- La documentación se escribe en español, breve y directa.
