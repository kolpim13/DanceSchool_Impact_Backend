"""Run from the repository root. Does not connect to the database."""
import json
from pathlib import Path
from shutil import copyfile
from main import app

if __name__ == '__main__':
    project_root = Path(__file__).resolve().parents[2]
    source = project_root / 'Backend' / 'contracts' / 'openapi.json'
    destination = project_root / 'Site' / 'contracts' / 'openapi.json'
    source.parent.mkdir(parents=True, exist_ok=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + '\n')
    copyfile(source, destination)
    print(source)
    print(destination)
