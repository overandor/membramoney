#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import hashlib
import textwrap

ROOT = Path('/Users/alep/Downloads')
OUTPUT_DIR = ROOT / 'gate_mm_beast'
OUTPUT_FILE = OUTPUT_DIR / 'gate_mm_unified_onefile.py'
MANIFEST_FILE = OUTPUT_DIR / 'gate_mm_unified_onefile_manifest.txt'

SOURCE_DIRS = [
    ROOT / 'gate_mm_beast' / 'app',
    ROOT / 'gate_mm_beast' / 'scripts',
    ROOT / 'Hedging_Project' / 'src',
    ROOT / 'ENA_Hedging_Project' / 'src',
]

EXTRA_FILES = [
    ROOT / 'gate_multi_ticker_mm_prod.py',
    ROOT / 'gateaioms.py',
    ROOT / 'beast.py',
    ROOT / 'Hedging_Project' / 'real_time_trader.py',
    ROOT / 'Hedging_Project' / 'proper_exchange_connection.py',
    ROOT / 'Hedging_Project' / 'fixed_signature_trader.py',
    ROOT / 'ENA_Hedging_Project' / 'run_ena_hedging.py',
]

SKIP_PARTS = {'__pycache__', '.git', '.venv', '.pytest_cache'}


def discover_files() -> list[Path]:
    out: list[Path] = []
    for d in SOURCE_DIRS:
        if not d.exists():
            continue
        for p in sorted(d.rglob('*.py')):
            if any(part in SKIP_PARTS for part in p.parts):
                continue
            out.append(p)
    for f in EXTRA_FILES:
        if f.exists() and f.suffix == '.py':
            out.append(f)
    # de-duplicate while preserving order
    uniq: list[Path] = []
    seen = set()
    for p in out:
        sp = str(p)
        if sp in seen:
            continue
        seen.add(sp)
        uniq.append(p)
    return uniq


def read_text_safe(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8', errors='replace')
    except Exception as exc:
        return f"# [read_error] {path}: {exc}\n"


def to_archive_comment_block(text: str) -> str:
    out: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("from __future__ import"):
            out.append(f"# [stripped_future_import] {line}")
        else:
            out.append(f"# {line}" if line else "#")
    return "\n".join(out)


def launcher_block() -> str:
    return textwrap.dedent(
        '''
        import os
        import sys
        from pathlib import Path

        def _run_unified_launcher() -> int:
            root = Path(__file__).resolve().parent
            if (root / "app").exists():
                app_root = root
            elif (root / "gate_mm_beast" / "app").exists():
                app_root = root / "gate_mm_beast"
            else:
                print("ERROR: gate_mm_beast directory not found next to this file.")
                return 1
            sys.path.insert(0, str(app_root))

            mode = "paper"
            if len(sys.argv) > 1:
                mode = str(sys.argv[1]).strip().lower()
            else:
                mode = str(os.getenv("MODE", "paper")).strip().lower()

            if mode not in {"paper", "live", "replay"}:
                print(f"ERROR: unsupported mode '{mode}'. Use paper/live/replay.")
                return 2

            if mode in {"paper", "replay"}:
                os.environ["MODE"] = mode

            from app.main import run
            return int(run())

        if __name__ == "__main__":
            raise SystemExit(_run_unified_launcher())
        '''
    ).strip("\n")


def build() -> tuple[int, int]:
    files = discover_files()
    created = datetime.now(timezone.utc).isoformat()
    lines: list[str] = [
        '#!/usr/bin/env python3',
        '# -*- coding: utf-8 -*-',
        '"""',
        'UNIFIED ONE-FILE PROJECT BUNDLE',
        f'Generated UTC: {created}',
        f'Total source files: {len(files)}',
        '',
        'This file is a consolidated archive of multiple project modules.',
        'Sections are delimited with source file paths for reappraisal/review.',
        'Launcher usage: python gate_mm_unified_onefile.py [paper|live|replay]',
        '"""',
        '',
        launcher_block(),
        '',
        '# ===== ARCHIVE SOURCE SECTIONS (COMMENTED) =====',
        '',
    ]

    manifest: list[str] = [f'Generated UTC: {created}', '']

    for idx, f in enumerate(files, start=1):
        rel = f.relative_to(ROOT)
        text = read_text_safe(f)
        archived_text = to_archive_comment_block(text.rstrip('\n'))
        digest = hashlib.sha256(text.encode('utf-8', errors='replace')).hexdigest()[:16]
        marker_top = f"# ===== BEGIN [{idx}/{len(files)}] {rel} sha256={digest} ====="
        marker_bot = f"# ===== END   [{idx}/{len(files)}] {rel} ====="
        lines.extend([marker_top, archived_text, marker_bot, ''])
        manifest.append(f'{idx:04d}  {rel}  sha256={digest}  lines={text.count(chr(10)) + 1}')

    OUTPUT_FILE.write_text('\n'.join(lines), encoding='utf-8')
    MANIFEST_FILE.write_text('\n'.join(manifest) + '\n', encoding='utf-8')
    return len(files), OUTPUT_FILE.stat().st_size


if __name__ == '__main__':
    count, size = build()
    print(f'Created: {OUTPUT_FILE}')
    print(f'Manifest: {MANIFEST_FILE}')
    print(f'Files bundled: {count}')
    print(f'Output size: {size} bytes')
