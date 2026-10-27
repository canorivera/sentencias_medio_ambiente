"""Corre la extracción de texto en máquinas de Colab con GPU, manejadas desde la laptop.

Usa el CLI oficial de Colab (google-colab-cli), instalado fuera del repositorio como en el
proyecto JANN: COLAB_CLI_PYTHON y COLAB_CLI_WIN en el .env (en Windows el CLI se lanza con
colab_win.py). El permiso de la cuenta de Google se da una sola vez.

Todo viaja con el CLI en archivos .zip de menos de 30 MB (el Drive no se monta):
    ida     código, requisitos y entradas (páginas de prueba o la lista de PDF del trabajador)
    vuelta  los scripts dejan zips en /content/work/ship; cada RECOGER segundos se bajan, se
            desempacan en DATA_DIR (las rutas dentro del zip son relativas a DATA_DIR) y se
            borran de la máquina
La máquina de Colab baja cada PDF directo de PROFEPA (URL de logs/download_log.csv) y lo
borra al terminar: no se suben los 49 GB.

En la máquina hay dos entornos: el de Colab con Paddle (layout, orientación, cliente) y
/content/vllm_env con vLLM (servidor del modelo). Al terminar, o si algo falla, se apaga la
sesión para no gastar unidades.

Uso (desde la raíz del repositorio, en PowerShell):
    code/.venv/Scripts/python code/102_text_extraction/102c_colab.py prueba
    code/.venv/Scripts/python code/102_text_extraction/102c_colab.py benchmark --gpu L4 --configs paddle_144 paddle_200_ori paddle_300_ori olmocr_200 tesseract_300 --piloto 40
    code/.venv/Scripts/python code/102_text_extraction/102c_colab.py lote --gpu L4 --workers colab1 colab2 --procesos 4 --perfil estandar
    code/.venv/Scripts/python code/102_text_extraction/102c_colab.py parar --nombre colab1
"""

import argparse
import csv
import io
import os
import random
import subprocess
import threading
import time
import zipfile
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
load_dotenv(REPO_ROOT / ".env")
DATA_DIR = Path(os.environ["DATA_DIR"])
CLI = [os.environ["COLAB_CLI_PYTHON"], os.environ["COLAB_CLI_WIN"]]
LOGS = DATA_DIR / "logs" / "colab"
SHARDS = DATA_DIR / "logs" / "colab" / "pedazos"

WORK_VM = "/content/work"
REPO_VM = "/content/repo"
DATA_VM = f"{WORK_VM}/data"
RECOGER = 180        # segundos entre bajadas de resultados
SIN_RESPUESTA = 4    # vueltas seguidas sin respuesta para dar la sesión por perdida
TOPE = 600           # segundos máximos de una orden del CLI
PARTE_MB = 30
PETICIONES = 32      # peticiones simultáneas al servidor por proceso de 102b
# Orden larga que mantiene abierta la conexión con el kernel. Sin ella Colab quitó las
# sesiones a los ~22 minutos (proyecto JANN, 2026-10-13).
MANTENER = """
import time
for _ in range(55):
    print('.', end='', flush=True)
    time.sleep(60)
"""

PREPARAR = """
import glob, os, subprocess, sys, zipfile
for z in sorted(glob.glob("/content/subida_*.zip")):
    zipfile.ZipFile(z).extractall("/content")
    os.remove(z)
os.makedirs("{work}/ship", exist_ok=True)
def run(cmd):
    print("$", cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)
run("apt-get -qq update > /dev/null && apt-get -qq install -y tesseract-ocr tesseract-ocr-spa > /dev/null")
run(sys.executable + " -m pip install -q -r {repo}/code/102_text_extraction/requirements_colab.txt")
run("pip install -q uv && uv venv -q --python 3.12 /content/vllm_env")
run("uv pip install -q --python /content/vllm_env/bin/python -r {repo}/code/102_text_extraction/requirements_colab_vllm.txt")
print("listo:", subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                                capture_output=True, text=True).stdout.strip() or "sin GPU")
"""

# Corre en segundo plano en la máquina y deja HECHO con el código de salida al terminar: si la
# laptop pierde la conexión, el trabajo sigue.
CORRER = """
import subprocess
script = {script!r}
subprocess.Popen(["bash", "-c", script], cwd="{repo}", start_new_session=True)
print("lanzado")
"""

ENV_VM = """DATA_DIR={data}
OCR_BACKEND=vllm-server
OCR_SERVER_URL=http://127.0.0.1:8118
OCR_SERVER_PARALLEL=16
OCR_SESSION={sesion}
OCR_GPU={gpu}
VLLM_ENV=/content/vllm_env
"""


def cli(*args, entrada=None, log=None, timeout=TOPE):
    """Corre un comando del CLI y devuelve (código, salida). Con log, escribe cada línea al
    llegar. Pasado `timeout` se mata el proceso (en Windows `colab exec` a veces no sale)."""
    # PYTHONIOENCODING: sin él, el CLI falla al imprimir acentos en la consola de Windows
    p = subprocess.Popen(CLI + list(args), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                         env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    reloj = threading.Timer(timeout, p.kill) if timeout else None
    if reloj:
        reloj.start()
    if entrada:
        p.stdin.write(entrada)
    p.stdin.close()
    lineas = []
    destino = open(log, "a", encoding="utf-8") if log else None
    try:
        for linea in p.stdout:
            lineas.append(linea)
            if destino:
                destino.write(linea)
                destino.flush()
        codigo = p.wait()
    finally:
        if reloj:
            reloj.cancel()
        if destino:
            destino.close()
    return codigo, "".join(lineas)


def escribir(log, texto):
    with open(log, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now():%H:%M:%S}] {texto}\n")
    print(texto, flush=True)


# --- ida -------------------------------------------------------------------------------------
def paquetes_de_subida(nombre, gpu, extras):
    """Zips en memoria, cada uno de menos de PARTE_MB. extras: lista de (origen, destino)."""
    archivos = [(f, f"repo/code/102_text_extraction/{f.name}")
                for f in list(HERE.glob("*.py")) + list(HERE.glob("requirements_colab*.txt"))]
    clasif = REPO_ROOT / "code" / "103_classification"
    archivos += [(clasif / n, f"repo/code/103_classification/{n}") for n in ("keywords.py", "codebook.csv")]
    archivos.append((ENV_VM.format(data=DATA_VM, sesion=nombre, gpu=gpu), "repo/.env"))
    archivos += extras
    partes, buf, z, tam = [], None, None, 0
    for origen, destino in archivos:
        peso = len(origen) if isinstance(origen, str) else origen.stat().st_size
        if z is None or tam + peso > PARTE_MB * 1e6:
            if z is not None:
                z.close()
                partes.append(buf.getvalue())
            buf, tam = io.BytesIO(), 0
            z = zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED)
        if isinstance(origen, str):
            z.writestr(destino, origen)
        else:
            z.write(origen, destino)
        tam += peso
    z.close()
    partes.append(buf.getvalue())
    return partes


def sesion(nombre, gpu, log, extras):
    escribir(log, f"nueva sesión {nombre} ({gpu})")
    # Colab a veces niega la máquina por un rato: se reintenta cada minuto, hasta 10 veces
    for intento in range(10):
        codigo, salida = cli("new", "-s", nombre, "--gpu", gpu, log=log)
        if codigo == 0 and "READY" in salida:
            break
        escribir(log, f"{nombre}: sin máquina (intento {intento + 1}); se reintenta en 60 s")
        time.sleep(60)
    else:
        raise RuntimeError(f"no se pudo crear la sesión {nombre}")
    tmp = LOGS / f"subida_{nombre}"
    tmp.mkdir(parents=True, exist_ok=True)
    for k, parte in enumerate(paquetes_de_subida(nombre, gpu, extras)):
        local = tmp / f"subida_{k:02d}.zip"
        local.write_bytes(parte)
        for intento in range(5):
            if cli("upload", "-s", nombre, str(local), f"/content/subida_{k:02d}.zip", log=log)[0] == 0:
                break
            time.sleep(30 * (intento + 1))
        else:
            raise RuntimeError(f"falló la subida de la parte {k}")
        local.unlink()
    codigo = PREPARAR.format(work=WORK_VM, repo=REPO_VM)
    if cli("exec", "-s", nombre, "--timeout", "3000", entrada=codigo, log=log, timeout=3300)[0] != 0:
        raise RuntimeError(f"falló la preparación de {nombre}")


# --- vuelta ----------------------------------------------------------------------------------
def recoger(nombre, log):
    """Baja los zips listos, los desempaca en DATA_DIR y los borra de la máquina."""
    codigo, salida = cli("ls", "-s", nombre, f"{WORK_VM}/ship")
    if codigo != 0:
        return 0
    n = 0
    for linea in salida.splitlines():
        archivo = linea.strip()
        if not archivo.endswith(".zip"):
            continue   # .part: todavía se está escribiendo
        local = LOGS / "ship" / archivo
        local.parent.mkdir(parents=True, exist_ok=True)
        if cli("download", "-s", nombre, f"{WORK_VM}/ship/{archivo}", str(local))[0] != 0:
            continue
        try:
            zipfile.ZipFile(local).extractall(DATA_DIR)
        except zipfile.BadZipFile:
            local.unlink()
            continue
        cli("rm", "-s", nombre, f"{WORK_VM}/ship/{archivo}")
        local.unlink()
        n += 1
    if n:
        escribir(log, f"{nombre}: {n} paquetes recibidos")
    return n


def terminado(nombre):
    codigo, salida = cli("ls", "-s", nombre, WORK_VM)
    if codigo != 0 or "HECHO" not in salida.split():
        return None
    local = LOGS / f"{nombre}.hecho"
    if cli("download", "-s", nombre, f"{WORK_VM}/HECHO", str(local))[0] != 0:
        return None
    return local.read_text().strip()


def mantener(nombre, parar):
    while not parar.is_set():
        cli("exec", "-s", nombre, "--timeout", "3400", entrada=MANTENER, timeout=3500)
        parar.wait(30)


def trabajo(nombre, gpu, script, extras):
    """Una sesión de principio a fin: "hecho", "perdida" (Colab la quitó) o "error"."""
    log = LOGS / f"{nombre}.log"
    estado = "error"
    parar = threading.Event()
    try:
        sesion(nombre, gpu, log, extras)
        completo = f"({script}) > {WORK_VM}/run.log 2>&1; echo $? > {WORK_VM}/HECHO"
        if cli("exec", "-s", nombre, "--timeout", "600", entrada=CORRER.format(script=completo, repo=REPO_VM),
               log=log, timeout=900)[0] != 0:
            raise RuntimeError("no se pudo lanzar el trabajo")
        threading.Thread(target=mantener, args=(nombre, parar), daemon=True).start()
        fallas = 0
        while True:
            time.sleep(RECOGER)
            if cli("ls", "-s", nombre, WORK_VM, timeout=120)[0] != 0:
                fallas += 1
                if fallas >= SIN_RESPUESTA:
                    estado = "perdida"
                    raise RuntimeError(f"la sesión no responde desde hace {fallas} vueltas")
                continue
            fallas = 0
            recoger(nombre, log)
            cli("download", "-s", nombre, f"{WORK_VM}/run.log", str(LOGS / f"{nombre}.run.log"))
            codigo = terminado(nombre)
            if codigo is not None:
                escribir(log, f"{nombre}: terminó con código {codigo}")
                time.sleep(5)
                recoger(nombre, log)
                cli("download", "-s", nombre, f"{WORK_VM}/run.log", str(LOGS / f"{nombre}.run.log"))
                estado = "hecho"
                break
    except Exception as e:
        escribir(log, f"{nombre}: ERROR {e}")
    finally:   # también si falló a medias: no dejar máquinas encendidas gastando unidades
        parar.set()
        cli("stop", "-s", nombre, log=log)
        escribir(log, f"{nombre}: sesión apagada")
    return estado


# --- pedazos ---------------------------------------------------------------------------------
def pendientes(perfil, lista=None):
    """PDF sin texto todavía en DATA_DIR/text/<perfil>, con su URL y tamaño."""
    with open(DATA_DIR / "logs" / "download_log.csv", encoding="utf-8") as f:
        descargas = {r["dest"]: r for r in csv.DictReader(f) if r["status"] in ("descargado", "ya_existia")}
    if lista:
        with open(lista, encoding="utf-8") as f:
            elegidos = [r["pdf"] for r in csv.DictReader(f)]
    else:
        elegidos = sorted(descargas)
    filas = []
    for pdf in elegidos:
        rel = Path(pdf).relative_to("raw")
        if (DATA_DIR / "text" / perfil / rel.parent / f"{rel.stem}.md").exists():
            continue
        filas.append({"pdf": pdf, "url": descargas[pdf]["url"], "bytes": descargas[pdf]["bytes"]})
    return filas


def escribir_pedazo(nombre, filas):
    SHARDS.mkdir(parents=True, exist_ok=True)
    path = SHARDS / f"{nombre}.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["pdf", "url", "bytes"])
        writer.writeheader()
        writer.writerows(filas)
    return path


def extract_cmd(perfil, nombre, partes):
    """Varios procesos de 102b a la vez en la máquina, cada uno con su parte de la lista. Con
    uno solo el servidor queda subutilizado: en el piloto (L4) generó ~600 tokens/s con 16
    peticiones a la vez y la página tardaba lo mismo que en la laptop."""
    ordenes = []
    for k in range(partes):
        ordenes.append(
            f"(OCR_SESSION={nombre}_{k} OCR_SERVER_PARALLEL={PETICIONES} /content/paddle_env/bin/python -u "
            f"code/102_text_extraction/102b_extract_text.py --perfil {perfil} "
            f"--pedazo {WORK_VM}/inputs/{nombre}_{k}.csv --descargar --envio {WORK_VM}/ship "
            f"> {WORK_VM}/{nombre}_{k}.log 2>&1) & PIDS=\"$PIDS $!\";")
    # wait solo sobre los procesos de 102b: un wait sin argumentos esperaría también al
    # servidor del modelo, que corre en segundo plano y no termina
    return "PIDS=''; " + " ".join(ordenes) + " wait $PIDS"


def subir_partes(nombre, filas, partes):
    """Escribe la lista de cada proceso y devuelve los extras para subirlas."""
    extras = []
    for k in range(partes):
        path = escribir_pedazo(f"{nombre}_{k}", filas[k::partes])
        extras.append((path, f"work/inputs/{nombre}_{k}.csv"))
    return extras


def vllm_cmd():
    """Arranca el servidor de PaddleOCR-VL y espera a que responda."""
    return ("/content/vllm_env/bin/paddleocr genai_server --model_name PaddleOCR-VL-1.6-0.9B "
            "--backend vllm --host 127.0.0.1 --port 8118 > /content/work/vllm.log 2>&1 & "
            "for i in $(seq 1 360); do curl -sf http://127.0.0.1:8118/v1/models > /dev/null && break; sleep 5; done")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("accion", choices=["prueba", "benchmark", "lote", "parar"])
    ap.add_argument("--gpu", nargs="*", default=["L4"], help="una GPU para todos, o una por trabajador")
    ap.add_argument("--configs", nargs="*", default=[])
    ap.add_argument("--piloto", type=int, default=0, help="benchmark: documentos reales para medir velocidad")
    ap.add_argument("--workers", nargs="*", default=[])
    ap.add_argument("--perfil", default="estandar")
    ap.add_argument("--lista", help="lote: CSV con columna pdf (p. ej. candidatas para el perfil alta)")
    ap.add_argument("--procesos", type=int, default=4, help="procesos de 102b por máquina")
    ap.add_argument("--nombre")
    a = ap.parse_args()
    LOGS.mkdir(parents=True, exist_ok=True)

    if a.accion == "prueba":
        log = LOGS / "prueba.log"
        cli("new", "-s", "ocr_prueba", log=log)
        print(cli("exec", "-s", "ocr_prueba", entrada="import sys; print('hola desde Colab', sys.version)")[1])
        print(cli("usage")[1])
        cli("stop", "-s", "ocr_prueba", log=log)

    elif a.accion == "parar":
        cli("stop", "-s", a.nombre)

    elif a.accion == "benchmark":
        bench = DATA_DIR / "benchmark"
        extras = [(bench / "paginas.csv", "work/data/benchmark/paginas.csv")]
        extras += [(f, f"work/data/benchmark/paginas/{f.name}") for f in sorted((bench / "paginas").glob("*.pdf"))]
        pasos = [f"python -u code/102_text_extraction/102d_benchmark_run.py --configs {' '.join(a.configs)}",
                 f"cd {DATA_VM} && zip -qr {WORK_VM}/ship/benchmark_salidas.zip benchmark/salidas && cd {REPO_VM}"]
        if a.piloto:
            # documentos al azar (semilla fija) para medir la velocidad real con el perfil estandar
            filas = pendientes("estandar")
            random.Random(20261027).shuffle(filas)
            extras += subir_partes("piloto", filas[: a.piloto], a.procesos)
            pasos += [vllm_cmd(), extract_cmd("estandar", "piloto", a.procesos)]
        trabajo(f"bench_{a.gpu[0]}", a.gpu[0], " ; ".join(pasos), extras)

    elif a.accion == "lote":
        filas = pendientes(a.perfil, a.lista)
        gpus = a.gpu if len(a.gpu) == len(a.workers) else a.gpu[:1] * len(a.workers)
        print(f"{len(filas)} documentos pendientes para {len(a.workers)} trabajadores")
        hilos = []
        for k, (w, gpu) in enumerate(zip(a.workers, gpus)):
            extras = subir_partes(w, filas[k::len(a.workers)], a.procesos)
            script = vllm_cmd() + " ; " + extract_cmd(a.perfil, w, a.procesos)
            h = threading.Thread(target=trabajo, args=(w, gpu, script, extras))
            h.start()
            hilos.append(h)
        for h in hilos:
            h.join()
        print("Sesiones terminadas. Si alguna se perdió, volver a correr lote: solo toma lo pendiente.")


if __name__ == "__main__":
    main()
