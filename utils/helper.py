from pathlib import Path

def find_data_file(filename: str) -> Path:
    here = Path(__file__).resolve().parent
    project_root = here.parent  # adjust if your structure differs
    candidates = [
        Path(filename),                          # if caller passes absolute or cwd-relative
        here / filename,                         # next to train_ev_ice.py
        project_root / "data" / filename,        # common data folder
        project_root / filename,                 # project root
        Path.cwd() / filename,                   # streamlit working dir
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError(
        f"Could not find {filename}. Tried:\n" + "\n".join(str(c) for c in candidates)
    )