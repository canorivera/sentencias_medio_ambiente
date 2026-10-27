# Estructura del repositorio

```
sentencias_medio_ambiente/
├── .env.example            Plantilla de variables de entorno
├── README.md               Descripción general del proyecto
├── REPO_STRUCTURE.md       Este archivo
├── AGENTS.md               Reglas de trabajo para el proyecto
└── code/
    ├── .venv/                Entorno virtual de Python (no se versiona)
    ├── requirements.txt      Dependencias de Python
    ├── 101_downloading/      Descarga de las resoluciones del catálogo
    ├── 102_text_extraction/  Extracción de texto (texto embebido u OCR) y comparación de opciones de OCR
    └── 103_classification/   Libro de códigos de términos y clasificación de resoluciones
```

## Convención de nombres de scripts

| Prefijo | Uso |
|---|---|
| `0XX` | Scripts maestros y de configuración |
| `1XX` | Obtención y limpieza de datos |
| `2XX` | Análisis exploratorio y descriptivo |
| `3XX` | Análisis inferencial |

Dentro de una carpeta, los scripts de una misma etapa llevan una letra en el orden en que se corren (`102a`, `102b`...). Los módulos sin número (`ocr.py`, `keywords.py`) son funciones que comparten los scripts.

## Carpetas de código

### `code/101_downloading/`

Descarga cada resolución listada en los CSV del catálogo.

- `101_download_rulings.py`: lee `DATA_DIR/catalogue/*.csv` y guarda los PDF en `DATA_DIR/raw/<año de resolución>/<número de expediente>/`. Las resoluciones sin fecha van a `sin_fecha/`. Omite los archivos ya descargados y escribe una bitácora en `DATA_DIR/logs/download_log.csv`.

```bash
code/.venv/Scripts/python code/101_downloading/101_download_rulings.py            # todo
code/.venv/Scripts/python code/101_downloading/101_download_rulings.py --limit 20 # prueba
```

### `code/102_text_extraction/`

Extrae el texto de cada PDF. Por página: usa el texto embebido si el PDF salió de Word y el texto es visible y no está bajo un testado; si no, hace OCR con PaddleOCR-VL-1.6 (layout en Paddle, reconocimiento en un servidor de modelo). Los PDF dañados se reparan o se rescatan sus imágenes. Las reglas están en `ocr.py`.

- `ocr.py`: funciones comunes (apertura y reparación de PDF, reglas del texto embebido, OCR por tandas, perfiles `estandar` y `alta`).
- `102a_benchmark_sample.py`: elige 30 páginas de prueba por estratos (digital, escaneo bueno y malo, girada, tabla, vida silvestre) y deja sus imágenes en `DATA_DIR/benchmark/paginas/`. Las transcripciones de referencia van en `DATA_DIR/benchmark/referencias/` (reglas en su `LEEME.md`).
- `102b_extract_text.py`: extrae el texto del corpus y escribe `DATA_DIR/text/<perfil>/<año>/<expediente>/<archivo>.md` y `.json`. En la laptop usa llama.cpp (lo inicia solo). Omite lo ya hecho y anota cada documento en `DATA_DIR/logs/ocr_<perfil>.csv`.
- `102c_colab.py`: corre el benchmark o la extracción en máquinas de Colab con GPU, manejadas desde la laptop con el CLI de Colab (como en el proyecto JANN). La máquina baja los PDF de PROFEPA y devuelve el texto en zips. Correr desde PowerShell.
- `102d_benchmark_run.py`: corre cada opción de OCR sobre las páginas de prueba.
- `202_benchmark_scores.py`: compara cada opción contra las referencias (errores de carácter, palabras y términos del libro de códigos encontrados) y escribe `DATA_DIR/benchmark/resultados_*.csv`.
- `requirements_colab.txt`, `requirements_colab_vllm.txt`: entornos de la máquina de Colab (Paddle y vLLM van en entornos separados).

```bash
code/.venv/Scripts/python code/102_text_extraction/102b_extract_text.py --perfil estandar --limit 5     # prueba en la laptop
code/.venv/Scripts/python code/102_text_extraction/102c_colab.py benchmark --gpu L4 --configs paddle_144 paddle_200_ori paddle_300_ori olmocr_200 tesseract_300 --piloto 40
code/.venv/Scripts/python code/102_text_extraction/202_benchmark_scores.py
code/.venv/Scripts/python code/102_text_extraction/102c_colab.py lote --gpu L4 --workers colab1 colab2 --perfil estandar
code/.venv/Scripts/python code/102_text_extraction/102c_colab.py lote --gpu L4 --workers colab1 --perfil alta --lista <DATA_DIR>/classification/candidatas_estandar.csv
```

### `code/103_classification/`

Marca las resoluciones de interés (vida silvestre) por términos de búsqueda y por la serie del expediente.

- `codebook.csv`: libro de códigos. Una fila por término: patrón, peso, errores de OCR tolerados, contexto requerido o excluido, fuente y justificación. Es la única fuente de verdad de los términos.
- `CODEBOOK.md`: versión legible del libro de códigos (la genera `103_classify.py`, no se edita a mano).
- `keywords.py`: normalización del texto y búsqueda tolerante a errores de OCR.
- `103_classify.py`: lee `DATA_DIR/text/<perfil>/` y escribe en `DATA_DIR/classification/` la clasificación por resolución, cada aparición de cada término con su contexto, y la lista de candidatas para la segunda pasada de OCR. Reglas: serie 2C.27.3 o 3S.3 (vida silvestre en el cuadro de clasificación archivística de PROFEPA), o puntaje de 6 o más (suma de pesos de términos distintos).

```bash
code/.venv/Scripts/python code/103_classification/103_classify.py --perfil estandar
```

## Datos (fuera del repositorio)

Ubicados en `DATA_DIR` (Dropbox):

```
sentencias_profepa/
├── catalogue/       Catálogo de resoluciones y laudos de PROFEPA, un CSV por año (2021-2025)
├── raw/             PDF descargados. No se modifican.
├── text/<perfil>/   Texto extraído (.md y .json por documento)
├── benchmark/       Páginas de prueba, transcripciones de referencia, salidas y resultados de cada opción de OCR
├── classification/  Clasificación de resoluciones y apariciones de términos
└── logs/            Bitácoras de los scripts (descargas, OCR, sesiones de Colab)
```
