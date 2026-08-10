"""Run the example chain end to end and regenerate everything in ``data/``.

The examples are a pipeline: each one reads the JSON the previous wrote, so they
only make sense in order. Every one of them also ends in ``viewer.show()``,
which blocks on a window - so this sets ``COMPAS_TF_HEADLESS``, which makes
:func:`compas_tf.viewer.make_viewer` build the scene for real and then skip the
event loop. A broken scene still raises; only the window is gone.

    python tools/run_examples.py            # the whole chain
    python tools/run_examples.py 8 9 10     # only those, by number

Exit code is the number of examples that failed.
"""

import pathlib
import re
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).parent.parent
EXAMPLES = HERE / "examples"

# Run each example with Viewer.show() neutered. This lives HERE, not in
# compas_tf, so the examples stay stock compas_viewer - they build the scene for
# real (a bad geometry or an unregistered scene object still raises) and only
# the blocking Qt event loop is skipped.
PREAMBLE = """
import runpy, sys
from compas_viewer import Viewer
Viewer.show = lambda self, *a, **k: print("[viewer] headless -> window skipped")
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
"""

# Pipeline order. 14_bed and 14_frame both read what 8 wrote, hence the tie.
ORDER = [
    "example_model_1_floorguide.py",
    "example_model_2_column_model.py",
    "example_model_3_columns_model.py",
    "example_model_4_quarters.py",
    "example_model_5_oculus.py",
    "example_model_6_contacts_floor.py",
    "example_model_7_contacts_cantilever.py",
    "example_model_8_contacts_cantilevers.py",
    "example_model_9_wedge_connector.py",
    "example_model_10_shoring.py",
    "example_model_11_full.py",
    "example_model_12_fab_column.py",
    "example_model_13_fab_oculus.py",
    "example_model_14_fab_quarter_bed.py",
    "example_model_14_fab_quarter_frame.py",
    "example_model_15_fab_formwork.py",
    "example_model_16_fab_connectors.py",
    "example_model_17_quantities.py",
    "example_model_18_write_model_and_brep.py",
    "example_model_19_read_model.py",
    "example_model_20_read_brep.py",
]


def main(argv: list) -> int:
    wanted = set(argv)
    names = [n for n in ORDER if not wanted or re.search(r"example_model_(\d+)", n).group(1) in wanted]

    # PYTHONIOENCODING: the child's stdout is a pipe here, not a console, so on
    # Windows it defaults to cp1252 and any non-ASCII an example prints kills it
    # with UnicodeEncodeError - a failure of this runner, not of the example.
    env = {
        **__import__("os").environ,
        "COMPAS_TF_HEADLESS": "1",
        "PYTHONWARNINGS": "ignore",
        "PYTHONIOENCODING": "utf-8",
    }
    failed = []
    for name in names:
        path = EXAMPLES / name
        start = time.perf_counter()
        proc = subprocess.run(
            [sys.executable, "-c", PREAMBLE, str(path)],
            cwd=str(HERE),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        dt = time.perf_counter() - start
        if proc.returncode == 0:
            print(f"  OK    {name:44s} {dt:6.1f}s")
        else:
            failed.append(name)
            tail = (proc.stderr.strip().splitlines() or ["(no stderr)"])[-1]
            print(f"  FAIL  {name:44s} {dt:6.1f}s  {tail[:110]}")

    print(f"\n{len(names) - len(failed)}/{len(names)} ok")
    if failed:
        print("failed:", ", ".join(failed))
    return len(failed)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
