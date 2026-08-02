"""
URANODYNE / FITA — main entry point.

Usage:
    python main.py                  # interactive menu
    python main.py demo             # SIMBAD + VizieR + Aladin API demo
    python main.py pipeline         # run full M27 IrenBLink pipeline
    python main.py verify           # verify existing M27 outputs
    python main.py pm               # Gaia PM check on DSS blink cube
    python main.py aladin           # open Aladin Lite viewer in browser
    python main.py info <file.fita> # show cube structure
"""
import sys
import os
import subprocess


MENU = """
==============================================================
         URANODYNE / FITA  --  M27 Dumbbell Nebula
==============================================================
  1  demo      SIMBAD + VizieR + Aladin API demo
  2  pipeline  Run full IrenBLink pipeline (downloads data)
  3  verify    Verify existing M27 pipeline outputs
  4  pm        Gaia DR3 PM check on DSS blink cube
  5  aladin    Open Aladin Lite viewer in browser
  6  info      Show cube structure for m27_full.fita
  q  quit
==============================================================
"""

SCRIPTS = {
    "demo":     "demo_apis.py",
    "pipeline": "run_m27_full.py",
    "verify":   "verify_m27.py",
    "pm":       "run_gaia_pm_check.py",
}

ALIASES = {"1": "demo", "2": "pipeline", "3": "verify", "4": "pm",
           "5": "aladin", "6": "info"}


def run_script(name):
    path = SCRIPTS.get(name)
    if path and os.path.exists(path):
        subprocess.run([sys.executable, path], check=False)
    else:
        print(f"  Script not found: {path}")


def cmd_aladin():
    for candidate in ("m27_aladin_cats.html", "m27_aladin.html"):
        if os.path.exists(candidate):
            print(f"  Opening {candidate} in browser ...")
            subprocess.Popen(["cmd", "/c", "start", candidate])
            return
    print("  No Aladin HTML file found. Run 'demo' first.")


def cmd_info():
    fita = "m27_full.fita"
    if not os.path.exists(fita):
        print(f"  {fita} not found. Run 'pipeline' first.")
        return
    from fita.io import read
    layers = read(fita)
    print(f"\n  {fita}  —  {len(layers)} layers\n")
    print(f"  {'ID':>3}  {'Name':<24}  {'Wavelength':>12}  "
          f"{'Shape':>12}  {'Blend'}")
    print("  " + "-" * 70)
    for l in layers:
        w = l.wave_cval
        ws = (f"{w*1e9:.0f} nm" if w and w < 1e-6
              else f"{w*1e6:.2f} um" if w else "  ?")
        print(f"  {l.layer_id:>3}  {l.name:<24}  {ws:>12}  "
              f"{l.shape[1]:>5}x{l.shape[0]:<5}  {l.blend_mode}")


def dispatch(cmd):
    if cmd in SCRIPTS:
        run_script(cmd)
    elif cmd == "aladin":
        cmd_aladin()
    elif cmd == "info":
        cmd_info()
    elif cmd in ("q", "quit", "exit"):
        sys.exit(0)
    else:
        print(f"  Unknown command: '{cmd}'")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg == "info" and len(sys.argv) > 2:
            # python main.py info some_file.fita
            from fita.io import read
            layers = read(sys.argv[2])
            print(f"\n  {sys.argv[2]}  —  {len(layers)} layers\n")
            for l in layers:
                w = l.wave_cval
                ws = (f"{w*1e9:.0f} nm" if w and w < 1e-6
                      else f"{w*1e6:.2f} um" if w else "  ?")
                print(f"  [{l.layer_id:>2}] {l.name:<24}  {ws:>10}  "
                      f"{l.blend_mode}  {l.shape[1]}x{l.shape[0]}")
        else:
            dispatch(ALIASES.get(arg, arg))
    else:
        print(MENU)
        while True:
            try:
                choice = input("  Choice: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not choice:
                continue
            dispatch(ALIASES.get(choice, choice))
            if choice not in ("q", "quit", "exit"):
                print()
