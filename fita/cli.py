"""
FITA command-line interface.

Usage examples:

  # Import a standard FITS cube -> .fita
  fita from-fits NGC1068.fits output.fita --stretch asinh

  # Import a PSD file -> .fita
  fita from-psd composite.psd output.fita

  # Re-select flux range and recompute alpha
  fita reselect output.fita --fmin 10 --fmax 5000 --stretch log

  # Print layer info
  fita info output.fita

  # Export RGB composite FITS for qFITSView
  fita rgb output.fita rgb_out.fits --r 1 --g 2 --b 3

  # Write DS9 analysis menu file
  fita ds9-plugin ./fita_ds9.ana

  # Write FITS Liberator sidecar JSON
  fita liberator output.fita
"""

import argparse
import sys


def _safe_console():
    """Stop the CLI dying on a non-ASCII character in a Windows console.

    The legacy Windows console is cp1252; printing any character outside it
    (a layer name, a target name, an object with an accent, a path) raises
    UnicodeEncodeError and takes the whole command down.  Layer names come
    from user data, so this is reachable from ordinary use, not just from
    decorative characters in our own help text.

    Prefer real UTF-8 when the stream can do it; otherwise keep the console's
    own encoding but degrade unmappable characters to '?' instead of raising.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:          # not a TextIOWrapper (piped/captured)
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            try:
                reconfigure(errors="replace")
            except Exception:
                pass                     # nothing more we can safely do


def cmd_from_fits(args):
    from .io import from_fits_cube, write
    print(f"Importing FITS cube: {args.input}")
    layers = from_fits_cube(
        args.input,
        flux_min=args.fmin,
        flux_max=args.fmax,
        stretch_mode=args.stretch,
    )
    write(args.output, layers, pack=args.pack)
    print(f"Written {len(layers)} layers to {args.output}")


def cmd_from_psd(args):
    from .psd_import import import_psd
    from .io import write
    print(f"Importing PSD: {args.input}")
    layers = import_psd(args.input, flux_scale=args.flux_scale, stretch_mode=args.stretch)
    write(args.output, layers)
    print(f"Written {len(layers)} layers to {args.output}")


def cmd_reselect(args):
    from .io import read, write
    layers = read(args.fita_file)
    for l in layers:
        l.recompute_alpha(args.fmin, args.fmax, args.stretch)
    write(args.fita_file, layers, overwrite=True)
    print(f"Reselected flux range [{args.fmin}, {args.fmax}] stretch={args.stretch}")


def cmd_info(args):
    from .io import read
    layers = read(args.fita_file)
    print(f"FITA file: {args.fita_file}")
    print(f"  {len(layers)} layer(s)")
    for l in layers:
        wave = f"{l.wave_cval*1e9:.2f} nm" if l.wave_cval else "-"
        print(
            f"  [{l.layer_id:3d}] {l.name:<24s}  "
            f"shape={l.shape}  wave={wave}  "
            f"blend={l.blend_mode}  opacity={l.opacity:.2f}  "
            f"flux=[{l.flux_min:.3g}, {l.flux_max:.3g}]  "
            f"alpha={l.alpha_src}"
        )


def cmd_rgb(args):
    from .cube import FITACube
    from .plugins.qfitsview import export_rgb_fits
    cube = FITACube.load(args.fita_file)
    export_rgb_fits(cube, args.output, args.r, args.g, args.b, stretch_mode=args.stretch)
    print(f"RGB FITS written: {args.output}")


def cmd_ds9_plugin(args):
    from .plugins.ds9 import write_analysis_file
    write_analysis_file(args.output)


def cmd_liberator(args):
    from .io import read
    from .plugins.qfitsview import write_liberator_sidecar
    layers = read(args.fita_file)
    write_liberator_sidecar(args.fita_file, layers)


def cmd_conform(args):
    """Validate .fita file(s) against FITA_FORMAT_STANDARD.md v1.1."""
    from .validate import validate
    worst = 0
    for path in args.fita_files:
        report = validate(path)
        if args.quiet:
            print(f"{report.level:15s} {path}")
        else:
            print(report)
            print()
        if report.fatal is not None or not report.is_core:
            worst = 2                      # not even CORE conformant
        elif not report.is_full and worst < 1:
            worst = 1                      # CORE but not FULL

    # N-4 (ATOP audit, 2026-08-02): this used to exit 0 unless --strict was
    # given, so `fita conform --quiet` returned SILENT SUCCESS on files with
    # dozens of MUST violations. The analysis was right and the wrapper threw
    # it away -- the project's characteristic defect occurring inside the tool
    # built to catch it.
    #
    # Non-conformance now ALWAYS exits 2. --strict additionally demands
    # FITA-FULL, exiting 1 for a file that is merely CORE. A conformant file
    # never fails by default; a non-conformant one never passes.
    if worst >= 2:
        sys.exit(2)
    sys.exit(1 if (args.strict and worst == 1) else 0)


def cmd_doctor(args):
    """Diagnose whether this INSTALL works from the current directory."""
    from .doctor import doctor
    code = doctor(verbose=args.verbose)
    sys.exit(code if args.strict else 0)


def main():
    _safe_console()
    parser = argparse.ArgumentParser(
        prog="fita",
        description="FITA - Flexible Image Transfer Alpha CLI",
    )
    sub = parser.add_subparsers(dest="command")

    # from-fits
    p = sub.add_parser("from-fits", help="Import FITS cube -> .fita")
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--fmin",    type=float, default=None)
    p.add_argument("--fmax",    type=float, default=None)
    p.add_argument("--stretch", default="asinh",
                   choices=["linear", "log", "sqrt", "asinh", "power"])
    p.add_argument("--pack",    default="FLOAT32", choices=["FLOAT32", "SPLIT16"])
    p.set_defaults(func=cmd_from_fits)

    # from-psd
    p = sub.add_parser("from-psd", help="Import Photoshop PSD -> .fita")
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--flux-scale", type=float, default=1.0)
    p.add_argument("--stretch",    default="linear")
    p.set_defaults(func=cmd_from_psd)

    # reselect
    p = sub.add_parser("reselect", help="Re-derive alpha from new flux range")
    p.add_argument("fita_file")
    p.add_argument("--fmin",    type=float, required=True)
    p.add_argument("--fmax",    type=float, required=True)
    p.add_argument("--stretch", default="asinh")
    p.set_defaults(func=cmd_reselect)

    # info
    p = sub.add_parser("info", help="Print layer info")
    p.add_argument("fita_file")
    p.set_defaults(func=cmd_info)

    # rgb
    p = sub.add_parser("rgb", help="Export RGB FITS for qFITSView")
    p.add_argument("fita_file")
    p.add_argument("output")
    p.add_argument("--r", type=int, required=True)
    p.add_argument("--g", type=int, required=True)
    p.add_argument("--b", type=int, required=True)
    p.add_argument("--stretch", default="asinh")
    p.set_defaults(func=cmd_rgb)

    # ds9-plugin
    p = sub.add_parser("ds9-plugin", help="Write DS9 analysis menu file")
    p.add_argument("output", nargs="?", default="fita.ds9.ana")
    p.set_defaults(func=cmd_ds9_plugin)

    # liberator
    p = sub.add_parser("liberator", help="Write FITS Liberator sidecar JSON")
    p.add_argument("fita_file")
    p.set_defaults(func=cmd_liberator)

    # conform - the conformance checker (standard S2.1)
    p = sub.add_parser("conform",
                       help="Validate .fita against the format standard (FITA-CORE/FULL)")
    p.add_argument("fita_files", nargs="+")
    p.add_argument("--quiet",  action="store_true",
                   help="one line per file: LEVEL and path only")
    p.add_argument("--strict", action="store_true",
                   help="exit 2 if any file is not FITA-CORE, 1 if not FITA-FULL")
    p.set_defaults(func=cmd_conform)

    # doctor - is this INSTALL correct, from here?
    p = sub.add_parser("doctor",
                       help="Diagnose this FITA installation (imports, PATH, "
                            "deps, and a write/read self-test)")
    p.add_argument("--verbose", action="store_true",
                   help="show remedies for passing checks too")
    p.add_argument("--strict", action="store_true",
                   help="exit 2 on failure, 1 on warnings (for CI)")
    p.set_defaults(func=cmd_doctor)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)
    args.func(args)


if __name__ == "__main__":
    main()
