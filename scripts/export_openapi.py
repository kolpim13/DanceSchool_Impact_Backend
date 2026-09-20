"""Run from the repository root. Does not connect to the database."""
import json
from pathlib import Path
from main import app

if __name__ == '__main__':
    path = Path('contracts/openapi.json')
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + '\n')
    print(path)
