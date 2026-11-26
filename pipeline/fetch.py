"""Download every raw source listed in sources.py into pipeline/raw/ (skips files already present)."""
import sys
import time
import urllib.request
from pathlib import Path

from sources import SOURCES

RAW = Path(__file__).parent / "raw"


def download(url: str, dest: Path, tries: int = 5) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "france2027-pipeline"})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=300) as r, open(dest.with_suffix(dest.suffix + ".part"), "wb") as f:
                while chunk := r.read(1 << 20):
                    f.write(chunk)
            dest.with_suffix(dest.suffix + ".part").rename(dest)
            return
        except Exception as e:  # flaky proxies / servers: back off and retry
            print(f"  retry {i + 1}/{tries} for {dest.name}: {e}", file=sys.stderr)
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"could not download {url}")


def main(force: bool = False) -> None:
    RAW.mkdir(exist_ok=True)
    for src in SOURCES:
        for name, url in src["files"].items():
            dest = RAW / name
            if dest.exists() and not force:
                print(f"have {name}")
                continue
            print(f"get  {name}")
            download(url, dest)


if __name__ == "__main__":
    main(force="--force" in sys.argv)
