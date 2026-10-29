"""Download Mojang's bedrock-samples metadata (run once, or again to update).

    python3 data/fetch.py            # latest main branch
    python3 data/fetch.py v1.26.60.5 # a specific tag

Files land next to this script. Everything in blocks/, lib/ and export/
validates block IDs, states and entity IDs against these files.
"""
import sys
import urllib.request
from pathlib import Path

BASE = "https://raw.githubusercontent.com/Mojang/bedrock-samples/{ref}/{path}"
FILES = {
    "mojang-blocks.json": "metadata/vanilladata_modules/mojang-blocks.json",
    "mojang-entities.json": "metadata/vanilladata_modules/mojang-entities.json",
    "mojang-commands.json": "metadata/command_modules/mojang-commands.json",
    "version.json": "version.json",
}


def main():
    ref = sys.argv[1] if len(sys.argv) > 1 else "main"
    here = Path(__file__).resolve().parent
    for name, path in FILES.items():
        url = BASE.format(ref=ref, path=path)
        print("fetch", url)
        with urllib.request.urlopen(url, timeout=60) as r:
            (here / name).write_bytes(r.read())
    print("done")


if __name__ == "__main__":
    main()
