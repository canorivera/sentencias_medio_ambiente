# sentencias_medio_ambiente

Análisis jurídico de las resoluciones y laudos emitidos por la Procuraduría Federal de Protección al Ambiente (PROFEPA) entre 2021 y 2025. El objetivo es identificar qué herramientas legales de la institución resultan más eficaces para proteger la vida silvestre.

## Etapas

1. **Descarga.** Las resoluciones listadas en el catálogo de transparencia de PROFEPA: 6,029 PDF, unas 104,000 páginas.
2. **Extracción de texto.** Por página, texto embebido confiable u OCR con PaddleOCR-VL-1.6. Corre en Colab (o en la laptop).
3. **Clasificación.** Libro de códigos de términos de búsqueda y serie del expediente. Las candidatas pasan por una segunda pasada de OCR a mayor resolución.
4. **Análisis con LLMs** de las resoluciones de interés (pendiente).

## Extracción de texto

- **Texto embebido** solo en PDF exportados de Word con texto visible y sin testados encima (~5% de las páginas). Las capas de texto que deja el escáner tienen muchos errores y no se usan.
- **OCR** con PaddleOCR-VL-1.6 a 200 ppp, con corrección de páginas giradas (~5% de los escaneos están de lado o de cabeza). Se conservan encabezados y pies, que traen el monto de la multa y las medidas correctivas. Se limpian los bucles de repetición que el modelo genera en sellos y emblemas.
- **PDF dañados**: se reparan, se dibujan con un segundo motor o se rescatan sus imágenes. Solo 1 de 6,029 quedó ilegible.

Opciones comparadas en 30 páginas de prueba con transcripción de referencia (`202_benchmark_scores.py`):

| Opción | Errores de carácter (mediana) | Palabras recuperadas | Términos de búsqueda encontrados |
|---|---|---|---|
| PaddleOCR-VL, 200 ppp + giro (elegida) | 4.3% | 94.5% | 100% |
| PaddleOCR-VL en la laptop (llama.cpp) | 4.5% | 95.7% | 100% |
| PaddleOCR-VL, 144 ppp (por omisión) | 5.0% | 93.6% | 100% |
| olmOCR-2 | 16.7% | 81.5% | 97.6% |
| Tesseract | 11.1% | 85.3% | 100% |
| Texto embebido del PDF | 39.1% | 53.8% | 90.5% |

Las transcripciones de referencia son un borrador y falta revisarlas a mano (`DATA_DIR/benchmark/referencias/revision.csv`).

## Costo y tiempo

Medido en Colab con una GPU L4 y 4 procesos por máquina: 0.57 páginas por segundo.

| Concepto | Cálculo | Resultado |
|---|---|---|
| Páginas con OCR | 104,018 páginas menos ~5% con texto embebido | ~99,000 |
| Horas de L4 | 99,000 / 0.57 / 3,600 | ~48 |
| Unidades de Colab | 1.54 por hora de L4, más instalación y reinicios | ~77 (~0.013 por resolución) |
| Costo | ~$0.10 por unidad (paquete de 100 por $9.99) | **~$8 USD** |
| Tiempo | dos sesiones L4 en paralelo | ~1 día |

La segunda pasada (300 ppp sobre ~27% de resoluciones candidatas) suma ~25 unidades (~$2.50 USD). En la laptop (RTX 5070) el mismo trabajo no cuesta, pero tarda ~3.3 días seguidos.

Comparación con otras nubes, a la misma velocidad por GPU (precios de octubre de 2026, varían por región):

| Opción | GPU | Precio por hora | Total estimado |
|---|---|---|---|
| Colab | L4 | ~$0.15 | ~$8 |
| AWS g6.xlarge (bajo demanda) | L4 | $0.80 | ~$40 |
| AWS g6.xlarge (spot, interrumpible) | L4 | ~$0.35-0.55 | ~$18-28 |
| Azure NC4as_T4_v3 | T4 (~1.8 veces más lenta) | $0.53 | ~$46 |
| Azure NC24ads_A100_v4 | A100 | $3.67 | ~$60 |

## Configuración

Los datos no viven en el repositorio. Están en Dropbox, en la carpeta indicada por `DATA_DIR`.

```bash
cp .env.example .env          # y llenar las rutas
python -m venv code/.venv
code/.venv/Scripts/python -m pip install -r code/requirements.txt
```

Herramientas fuera del repositorio, con sus rutas en `.env`:

- llama.cpp (build Windows CUDA de github.com/ggml-org/llama.cpp) y el modelo `PaddlePaddle/PaddleOCR-VL-1.6-GGUF` de Hugging Face, para el OCR en la laptop (`LLAMA_SERVER_EXE`, `OCR_MODEL_DIR`).
- CLI de Colab, para el OCR en Colab (`COLAB_CLI_PYTHON`, `COLAB_CLI_WIN`). Los comandos de Colab se corren desde PowerShell.

## Uso

```bash
code/.venv/Scripts/python code/101_downloading/101_download_rulings.py
code/.venv/Scripts/python code/102_text_extraction/102c_colab.py lote --gpu L4 --workers colab1 colab2 --procesos 4 --perfil estandar
code/.venv/Scripts/python code/103_classification/103_classify.py --perfil estandar
code/.venv/Scripts/python code/102_text_extraction/102c_colab.py lote --gpu L4 --workers colab1 --procesos 4 --perfil alta --lista <DATA_DIR>/classification/candidatas_estandar.csv
```

El detalle de cada script está en [REPO_STRUCTURE.md](REPO_STRUCTURE.md).
