"""Mide cuántas páginas por segundo procesa una máquina según el número de procesos de 102b.

Corre en la máquina de Colab (lo lanza 102c_colab.py velocidad), con el servidor del modelo ya
activo. Por cada número de procesos:
    1. reparte la misma lista de PDF entre los procesos y los deja trabajar MINUTOS minutos,
       cada corrida con su propia carpeta de datos (así todas empiezan con los mismos PDF)
    2. cuenta las páginas con OCR de los documentos terminados después de CALENTAR minutos
       y las divide entre el tiempo de esa ventana
    3. registra cada 10 s el uso de la GPU
Escribe <DATA_DIR>/benchmark/velocidad/<gpu>.csv y lo empaca en la carpeta de envío.

Uso (en Colab):
    python 102e_speed_test.py --lista inputs/velocidad.csv --procesos 4 8 12 --minutos 15 --gpu L4 --envio /content/work/ship
"""

import argparse
import csv
import os
import subprocess
import threading
import time
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
CALENTAR = 3   # minutos que no cuentan (carga de modelos de layout y primeras descargas)


def gpu_sampler(samples, stop):
    while not stop.is_set():
        out = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True).stdout.strip().split(",")
        if len(out) == 2:
            samples.append((time.time(), float(out[0]), float(out[1])))
        stop.wait(10)


def run(rows, processes, minutes, base, python):
    """Lanza los procesos, espera MINUTOS y devuelve (inicio, fin, filas de la bitácora)."""
    data_dir = base / f"data_p{processes}"
    (data_dir / "logs").mkdir(parents=True, exist_ok=True)
    children = []
    start = time.time()
    for k in range(processes):
        part = data_dir / f"parte_{k}.csv"
        with open(part, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["pdf", "url", "bytes"])
            writer.writeheader()
            writer.writerows(rows[k::processes])
        env = dict(os.environ, DATA_DIR=str(data_dir), OCR_SESSION=f"v{processes}_{k}")
        children.append(subprocess.Popen(
            [python, "-u", str(HERE / "102b_extract_text.py"), "--perfil", "estandar", "--pedazo", str(part), "--descargar"],
            env=env, stdout=open(data_dir / f"proceso_{k}.log", "w"), stderr=subprocess.STDOUT))
    time.sleep(minutes * 60)
    for p in children:
        p.terminate()
    for p in children:
        try:
            p.wait(timeout=60)
        except subprocess.TimeoutExpired:
            p.kill()
    end = time.time()
    log_rows = []
    for f in (data_dir / "logs").glob("ocr_estandar_*.csv"):
        with open(f, encoding="utf-8") as fh:
            log_rows += list(csv.DictReader(fh))
    return start, end, log_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lista", required=True, help="CSV con pdf, url, bytes")
    parser.add_argument("--procesos", nargs="+", type=int, required=True)
    parser.add_argument("--minutos", type=float, default=15)
    parser.add_argument("--gpu", required=True)
    parser.add_argument("--envio", required=True)
    parser.add_argument("--python", default="/content/paddle_env/bin/python")
    args = parser.parse_args()

    try:   # sin servidor del modelo las corridas no miden nada
        urllib.request.urlopen("http://127.0.0.1:8118/v1/models", timeout=10)
    except OSError:
        raise SystemExit("el servidor del modelo no responde (ver /content/work/vllm.log)")
    with open(args.lista, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    base = Path("/content/work/velocidad")
    results = []
    for n in args.procesos:
        samples, stop = [], threading.Event()
        threading.Thread(target=gpu_sampler, args=(samples, stop), daemon=True).start()
        start, end, log_rows = run(rows, n, args.minutos, base, args.python)
        stop.set()
        window_start = start + CALENTAR * 60
        done = [r for r in log_rows if datetime.fromisoformat(r["fecha"]).timestamp() >= window_start]
        pages = sum(int(r["paginas_ocr"]) for r in done)
        seconds = end - window_start
        util = [u for t, u, m in samples if t >= window_start]
        mem = [m for t, u, m in samples if t >= window_start]
        results.append({
            "gpu": args.gpu, "procesos": n, "minutos_ventana": round(seconds / 60, 1),
            "documentos": len(done), "paginas_ocr": pages, "paginas_por_segundo": round(pages / seconds, 3),
            "uso_gpu_promedio": round(sum(util) / len(util), 1) if util else "",
            "memoria_gpu_max_mb": max(mem) if mem else "",
            "errores": sum(not r["estado"].startswith("ok") for r in done),
        })
        print(results[-1], flush=True)

    out = base / "data" / "benchmark" / "velocidad" / f"{args.gpu}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    Path(args.envio).mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(Path(args.envio) / f"velocidad_{args.gpu}.zip", "w") as z:
        z.write(out, f"benchmark/velocidad/{args.gpu}.csv")


if __name__ == "__main__":
    main()
