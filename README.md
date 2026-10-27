# sentencias_medio_ambiente

Análisis jurídico de las resoluciones y laudos emitidos por la Procuraduría Federal de Protección al Ambiente (PROFEPA) entre 2021 y 2025. El objetivo es identificar qué herramientas legales de la institución resultan más eficaces para proteger la vida silvestre.

## Etapas

1. Descargar las resoluciones listadas en el catálogo de transparencia de PROFEPA.
2. Extraer el texto de cada resolución: texto embebido confiable u OCR con PaddleOCR-VL, en Colab o en la laptop.
3. Clasificar las resoluciones de interés con un libro de códigos de términos y la serie del expediente; segunda pasada de OCR de alta calidad sobre las candidatas.
4. Analizar su contenido a escala con LLMs (pendiente).

## Configuración

Los datos no viven en el repositorio. Están en Dropbox, en la carpeta indicada por `DATA_DIR`.

```bash
cp .env.example .env          # y llenar DATA_DIR
python -m venv code/.venv
code/.venv/Scripts/python -m pip install -r code/requirements.txt
```

El OCR usa un servidor local de llama.cpp (build Windows CUDA de github.com/ggml-org/llama.cpp) con el modelo `PaddlePaddle/PaddleOCR-VL-1.6-GGUF` de Hugging Face. Ambos se instalan fuera del repositorio y sus rutas van en `.env` (`LLAMA_SERVER_EXE`, `OCR_MODEL_DIR`). Para Colab se usa el CLI de Colab, también fuera del repositorio (`COLAB_CLI_PYTHON`, `COLAB_CLI_WIN`).

## Uso

```bash
code/.venv/Scripts/python code/101_downloading/101_download_rulings.py
code/.venv/Scripts/python code/102_text_extraction/102b_extract_text.py --perfil estandar
code/.venv/Scripts/python code/103_classification/103_classify.py --perfil estandar
```

La estructura del proyecto está en [REPO_STRUCTURE.md](REPO_STRUCTURE.md).
