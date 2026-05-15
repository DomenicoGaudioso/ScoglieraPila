from __future__ import annotations

import importlib.util
import json
import math
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_src():
    spec = importlib.util.spec_from_file_location("scogliera_pila_src", ROOT / "src.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def assert_close(name: str, actual: float, expected: float, tol: float) -> None:
    if math.isnan(actual) or abs(actual - expected) > tol:
        raise AssertionError(f"{name}: actual={actual!r}, expected={expected!r}, tol={tol}")


def main() -> None:
    src = load_src()
    bench = json.loads((ROOT / "test" / "benchmark" / "base.json").read_text(encoding="utf-8"))
    dati = src.DatiScogliera(**bench["input"])
    d50 = src.calcola_d50(dati)
    spessore = src.spessore_rivestimento(d50, dati.fattore_spessore)
    larghezza = src.larghezza_apron(dati.ys_atteso, dati.fattore_larghezza)
    massa = src.massa_masso_tipico(d50, dati.S_s, dati.rho)
    vol = src.volume_massa_per_metro(d50, spessore, larghezza, dati.S_s, dati.rho)
    actual = {
        "D50": d50,
        "spessore": spessore,
        "larghezza_apron": larghezza,
        "massa_masso_kg": massa["massa_masso [kg]"],
        "massa_t_m": vol["Massa_roccia [t/m]"],
    }
    tol = float(bench["abs_tolerance"])
    for key, expected in bench["expected"].items():
        assert_close(key, float(actual[key]), float(expected), tol)
    print("OK ScoglieraPila benchmark: base")


if __name__ == "__main__":
    main()
