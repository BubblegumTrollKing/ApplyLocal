"""Copy installed runtime license files into the portable distribution."""
from importlib.metadata import distribution
from pathlib import Path
import shutil
import sys

destination = Path("dist/licenses")
destination.mkdir(parents=True, exist_ok=True)
for name in ("playwright", "jsonschema", "attrs", "jsonschema-specifications", "referencing",
             "rpds-py", "typing-extensions", "pyee", "greenlet"):
    dist = distribution(name)
    for item in dist.files or []:
        filename = str(item)
        base = Path(filename).name.lower()
        if any(base.startswith(s) for s in ("license", "notice", "copying", "copyright")):
            path = Path(dist.locate_file(item))
            if path.is_file():
                target = destination / name / filename.replace("/", "__").replace("\\", "__")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)

# Python and Tcl/Tk are bundled by PyInstaller, outside pip's distribution metadata.
for root, label in ((Path(sys.base_prefix), "python"),
                    (Path(sys.base_prefix) / "tcl", "tcl-tk")):
    if root.is_dir():
        candidates = list(root.glob("LICENSE*")) if label == "python" else list(root.rglob("license*"))
        for index, path in enumerate(candidates):
            if path.is_file():
                folder = destination / label
                folder.mkdir(exist_ok=True)
                shutil.copy2(path, folder / f"{index}-{path.name}")
