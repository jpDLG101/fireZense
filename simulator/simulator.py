#!/usr/bin/env python3
"""
Firezense Node Simulator
Simula lecturas de los sensores EM500-SMTC (suelo) y EM500-LGT (luz) para un nodo.

Uso:
  python simulator.py                          # selección interactiva, defaults
  python simulator.py --node 2                 # nodo 2, nivel green, cada 5 min
  python simulator.py --node 1 --interval 10   # cada 10 segundos
  python simulator.py --node 3 --level orange  # datos de nivel ORANGE
  python simulator.py --node 2 --backfill 5    # 5 días de histórico (cada 5 min)
  python simulator.py --node 1 --backfill 3 --level red
"""

import argparse
import random
import sys
import time
from datetime import datetime, timedelta, timezone

try:
    import requests
except ImportError:
    print("\n  Error: falta la librería requests.")
    print("  Instalar con: pip install requests\n")
    sys.exit(1)


# ─── Configuración ──────────────────────────────────────────────────────────

DEFAULT_BASE_URL = "http://localhost:8000"
API_KEY          = "tu_api_key_local"
BACKFILL_INTERVAL_SEC = 300  # 5 minutos (igual que el default del simulador)

# Máximo cambio de temperatura por ciclo.
# Mantiene delta_temp_per_min < 0.5°C/min → sin contribución al score de riesgo.
MAX_TEMP_STEP = 0.4

RISK_EMOJI = {"GREEN": "🟢", "YELLOW": "🟡", "ORANGE": "🟠", "RED": "🔴"}

# ─── Perfiles de riesgo (rangos estrictos por nivel) ────────────────────────
#
# Los rangos están calibrados para que el motor calculate_fire_risk()
# devuelva SIEMPRE el nivel correcto dados los valores de suelo + luz:
#
#   GREEN  → score  0-19   (temp baja, humedad alta, lux normal)
#   YELLOW → score 20-44   (temp elevada >35, humedad baja <30)
#   ORANGE → score 45-69   (temp alta >45, humedad crítica <30, EC seco)
#   RED    → score 70+     (temp crítica >60, humedad crítica <20, lux nocturna >100)

PROFILES = {
    "green": {
        "soil_temp":  (15.0,  30.0),
        "moisture":   (40.0,  80.0),
        "ec":         (250.0, 600.0),
        "lux_day":    (1000.0, 30000.0),
        "lux_night":  (0.0,    5.0),
        "battery":    (70,  100),
    },
    "yellow": {
        "soil_temp":  (35.0,  44.9),
        "moisture":   (30.0,  39.9),
        "ec":         (100.0, 200.0),
        "lux_day":    (30000.0, 50000.0),
        "lux_night":  (10.0,   50.0),
        "battery":    (40,  90),
    },
    "orange": {
        "soil_temp":  (45.0,  59.9),
        "moisture":   (20.0,  29.9),
        "ec":         (50.0,  100.0),
        "lux_day":    (40000.0, 60000.0),
        "lux_night":  (50.0,  100.0),
        "battery":    (30,  70),
    },
    "red": {
        "soil_temp":  (60.0,  80.0),
        "moisture":   (5.0,   20.0),
        "ec":         (10.0,  50.0),
        "lux_day":    (50000.0, 100000.0),
        "lux_night":  (100.0, 500.0),
        "battery":    (10,  50),
    },
}


# ─── Estado de temperatura por nodo (suavizado entre ciclos) ────────────────

_last_temp: dict[int, float] = {}


# ─── Generadores de datos ────────────────────────────────────────────────────

def _r(lo: float, hi: float, decimals: int = 1) -> float:
    return round(random.uniform(lo, hi), decimals)


def _smooth_temp(node_id: int, lo: float, hi: float) -> float:
    """Temperatura suavizada: máximo MAX_TEMP_STEP °C de cambio por ciclo."""
    prev = _last_temp.get(node_id)
    if prev is None:
        temp = _r(lo, hi)
    else:
        temp = _r(max(lo, prev - MAX_TEMP_STEP), min(hi, prev + MAX_TEMP_STEP))
    _last_temp[node_id] = temp
    return temp


def _is_night(dt: datetime) -> bool:
    local_hour = (dt + timedelta(hours=-6)).hour
    return local_hour >= 20 or local_hour < 6


def gen_soil(profile: dict, battery: int, node_id: int = 0) -> dict:
    return {
        "temperature": _smooth_temp(node_id, *profile["soil_temp"]),
        "moisture":    _r(*profile["moisture"]),
        "electricity": _r(*profile["ec"]),
        "battery":     battery,
    }


def gen_light(profile: dict, battery: int, dt: datetime) -> dict:
    lux_range = profile["lux_night"] if _is_night(dt) else profile["lux_day"]
    return {
        "illuminance": _r(*lux_range, decimals=0),
        "battery":     battery,
    }


# ─── API helpers ─────────────────────────────────────────────────────────────

def _headers(base_url: str) -> dict:
    return {"X-API-Key": API_KEY, "Content-Type": "application/json"}


def fetch_nodes(base_url: str) -> list:
    try:
        r = requests.get(f"{base_url}/api/v1/nodes", timeout=5)
        r.raise_for_status()
        return r.json().get("nodes", [])
    except requests.exceptions.ConnectionError:
        print(f"\n  Error: no se pudo conectar a {base_url}")
        print("  ¿Está corriendo el backend?  python backend/main.py\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n  Error al obtener nodos: {e}\n")
        sys.exit(1)


def post_reading(base_url: str, node_id: int, sensor_object: dict, timestamp: str) -> dict:
    body = {"node_id": node_id, "sensor_object": sensor_object, "timestamp": timestamp}
    r = requests.post(
        f"{base_url}/api/v1/simulate/uplink",
        headers=_headers(base_url),
        json=body,
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


# ─── UI helpers ──────────────────────────────────────────────────────────────

def print_nodes_table(nodes: list):
    print()
    print("  ID  │ Nombre                      │ Riesgo actual")
    print("  ────┼─────────────────────────────┼───────────────")
    for n in nodes:
        emoji = RISK_EMOJI.get(n.get("risk_level", ""), "⚪")
        lvl   = n.get("risk_level", "SIN DATOS")
        print(f"  {n['id']:<4}│ {n['name']:<27} │ {emoji} {lvl}")
    print()


def select_node_interactive(nodes: list) -> int:
    print_nodes_table(nodes)
    valid = {str(n["id"]) for n in nodes}
    while True:
        choice = input("  Selecciona el ID del nodo: ").strip()
        if choice in valid:
            return int(choice)
        print(f"  ID inválido. Opciones: {', '.join(sorted(valid, key=int))}")


def node_name(nodes: list, node_id: int) -> str:
    for n in nodes:
        if n["id"] == node_id:
            return n["name"]
    return f"Nodo {node_id}"


# ─── Modo continuo ───────────────────────────────────────────────────────────

def run_continuous(base_url: str, node_id: int, profile: dict,
                   interval: int, level: str, nodes: list):
    name = node_name(nodes, node_id)
    print(f"\n  Nodo   : [{node_id}] {name}")
    print(f"  Nivel  : {level.upper()}")
    print(f"  Ciclo  : cada {interval}s  (Ctrl+C para detener)")
    print()
    print("  #    Hora      Temp   Hum    EC      Lux       Riesgo")
    print("  ──────────────────────────────────────────────────────────")

    counter = 0
    try:
        while True:
            counter += 1
            now     = datetime.now(timezone.utc)
            ts      = now.isoformat()
            battery = random.randint(*profile["battery"])

            soil_obj  = gen_soil(profile, battery, node_id)
            light_obj = gen_light(profile, battery, now)

            try:
                res = post_reading(base_url, node_id, soil_obj, ts)
                post_reading(base_url, node_id, light_obj, ts)

                risk_lvl   = res.get("risk_level", "?")
                risk_emoji = RISK_EMOJI.get(risk_lvl, "⚪")
                risk_score = res.get("risk_score", "?")

                hora  = (now + timedelta(hours=-6)).strftime("%H:%M:%S")
                print(
                    f"  {counter:<4} {hora}  "
                    f"{soil_obj['temperature']:>5.1f}°C  "
                    f"{soil_obj['moisture']:>4.1f}%  "
                    f"{soil_obj['electricity']:>6.1f}µS  "
                    f"{light_obj['illuminance']:>8.0f}lx  "
                    f"{risk_emoji} {risk_lvl} ({risk_score})"
                )
            except Exception as e:
                print(f"  {counter:<4} Error: {e}")

            time.sleep(interval)

    except KeyboardInterrupt:
        print(f"\n  Detenido. {counter} ciclo(s) enviados.\n")


# ─── Modo backfill ───────────────────────────────────────────────────────────

def run_backfill(base_url: str, node_id: int, profile: dict,
                 days: int, level: str, nodes: list):
    readings_per_day = 24 * 60 // (BACKFILL_INTERVAL_SEC // 60)  # 288
    total            = days * readings_per_day
    now              = datetime.now(timezone.utc)
    start            = now - timedelta(days=days)

    name = node_name(nodes, node_id)
    print(f"\n  Nodo     : [{node_id}] {name}")
    print(f"  Nivel    : {level.upper()}")
    print(f"  Días     : {days}  ({total} ciclos × 2 sensores = {total * 2} lecturas)")
    print(f"  Desde    : {(start + timedelta(hours=-6)).strftime('%Y-%m-%d %H:%M')} MX")
    print(f"  Hasta    : {(now   + timedelta(hours=-6)).strftime('%Y-%m-%d %H:%M')} MX")
    print()

    errors  = 0
    bar_len = 30

    for i in range(total):
        ts_dt = start + timedelta(seconds=i * BACKFILL_INTERVAL_SEC)
        ts    = ts_dt.isoformat()

        battery   = random.randint(*profile["battery"])
        soil_obj  = gen_soil(profile, battery, node_id)
        light_obj = gen_light(profile, battery, ts_dt)

        try:
            post_reading(base_url, node_id, soil_obj, ts)
            post_reading(base_url, node_id, light_obj, ts)
        except Exception:
            errors += 1

        done = i + 1
        if done % 10 == 0 or done == total:
            pct    = done / total
            filled = int(pct * bar_len)
            bar    = "█" * filled + "░" * (bar_len - filled)
            print(f"\r  [{bar}] {pct*100:5.1f}%  {done}/{total}", end="", flush=True)

    print(f"\n\n  Backfill completo.")
    print(f"  Lecturas insertadas : {(total - errors) * 2}")
    if errors:
        print(f"  Errores             : {errors}")
    print()


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="simulator.py",
        description="Firezense — Simulador de nodo IoT",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
ejemplos:
  python simulator.py
  python simulator.py --node 2
  python simulator.py --node 1 --interval 10
  python simulator.py --node 3 --level orange
  python simulator.py --node 2 --backfill 5
  python simulator.py --node 1 --backfill 3 --level red
  python simulator.py --node 2 --url http://mi-servidor:8000
        """,
    )
    parser.add_argument("--node",     type=int,
                        help="ID del nodo a simular (interactivo si se omite)")
    parser.add_argument("--interval", type=int, default=300,
                        help="Segundos entre lecturas en modo continuo (default: 300)")
    parser.add_argument("--level",    choices=["green", "yellow", "orange", "red"],
                        default="green",
                        help="Nivel de riesgo a simular (default: green)")
    parser.add_argument("--backfill", type=int, metavar="DAYS",
                        help="Insertar N días de datos históricos (lecturas cada 5 min)")
    parser.add_argument("--url",      default=DEFAULT_BASE_URL,
                        help=f"URL base del backend (default: {DEFAULT_BASE_URL})")

    args = parser.parse_args()

    print()
    print("  🔥 Firezense Node Simulator")
    print("  ───────────────────────────")

    nodes = fetch_nodes(args.url)
    if not nodes:
        print("  No hay nodos activos registrados en la base de datos.\n")
        sys.exit(1)

    node_id = args.node
    if node_id is None:
        node_id = select_node_interactive(nodes)
    else:
        valid = [n["id"] for n in nodes]
        if node_id not in valid:
            print(f"\n  Error: el nodo {node_id} no existe o está inactivo.")
            print(f"  IDs disponibles: {valid}\n")
            sys.exit(1)

    profile = PROFILES[args.level]

    if args.backfill:
        run_backfill(args.url, node_id, profile, args.backfill, args.level, nodes)
    else:
        run_continuous(args.url, node_id, profile, args.interval, args.level, nodes)


if __name__ == "__main__":
    main()
