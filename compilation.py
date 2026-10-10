#!/usr/bin/env python3
import argparse
import os
import re
import sys
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
BUILD_CACHE_DIR = ROOT_DIR / ".build"
DIST_DIR = ROOT_DIR / "dist"

DIST_CHAPITRES = DIST_DIR / "chapitres"
DIST_COURS = DIST_DIR / "cours"
DIST_TDS = DIST_DIR / "TDs"
DIST_INTEGRALE = DIST_DIR / "integrale"

env = os.environ.copy()
fonts_dir = (Path.cwd() / "commun" / "fonts").resolve()
current_osfontdir = env.get("OSFONTDIR", "")
env["OSFONTDIR"] = f"{fonts_dir}//:{current_osfontdir}" if current_osfontdir else f"{fonts_dir}//"

def parse_latex_error(log_content: str, max_lines: int = 15) -> str:
    lines = log_content.splitlines()
    for idx, line in enumerate(lines):
        if line.startswith("!") or ": error:" in line.lower():
            start = max(0, idx - 1)
            end = min(len(lines), idx + max_lines)
            return "\n".join(lines[start:end])
    return "\n".join(lines[-50:])

def compile_file (file: Path, dist_dir: Path, cwd_dir: Path, halt_on_error: bool = True) -> bool :
    tex_file = file.resolve()
    if not tex_file.exists():
        print(f"[ERROR] Target file not found: {tex_file}", file=sys.stderr)
        return False

    dist_dir = dist_dir.resolve()
    dist_dir.mkdir(parents=True, exist_ok=True)
    
    rel_path = cwd_dir.resolve().relative_to(ROOT_DIR) if cwd_dir.resolve() != ROOT_DIR else Path()
    aux_dir = (BUILD_CACHE_DIR / rel_path).resolve()
    aux_dir.mkdir(parents=True, exist_ok=True)
    
    lualatex_cmd = (
        'lualatex --synctex=0 --halt-on-error --file-line-error '
        '--interaction=nonstopmode %O %S'
    )

    cmd = [
        "latexmk",
        "-lualatex",
        "-interaction=nonstopmode",
        f"-pdflualatex={lualatex_cmd}",
        f"-auxdir={aux_dir}",
        f"-outdir={dist_dir}",
        "-silent",
        "-e", "$max_repeat=5;",
        str(tex_file)
    ]

    print(f"[*] Compiling {tex_file.name}...")
    result = subprocess.run(
        cmd,
        cwd=cwd_dir.resolve(),
        capture_output=True,
        text=True,
        env=env
    )
    
    if result.returncode != 0 :
        print(f"\n[!] Compilation FAILED for {tex_file.name} (exit {result.returncode})", file=sys.stderr)

        log_file = aux_dir / f"{tex_file.stem}.log"
        error_context = ""
        if log_file.exists():
            try:
                error_context = parse_latex_error(log_file.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                pass

        if not error_context and result.stdout:
            error_context = parse_latex_error(result.stdout)

        print("----------- LaTeX Error Trace -----------", file=sys.stderr)
        print(error_context if error_context else "No error snippet found in log.", file=sys.stderr)
        print("-----------------------------------------", file=sys.stderr)

        if halt_on_error:
            sys.exit(1)
        return False

    print(f"[+] Done: {dist_dir / (tex_file.stem + '.pdf')}")
    return True


def run_tasks(tasks: list[tuple[Path, Path, Path]], halt_on_error: bool = False):
    if not tasks:
        print("[-] No matching files found to compile.")
        return

    max_workers = min(os.cpu_count() or 4, len(tasks))
    print(f"[*] Starting {len(tasks)} compilation tasks across {max_workers} threads...\n")

    failed = False
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(compile_file, tex, out, cwd, halt_on_error): tex
            for tex, out, cwd in tasks
        }
        for fut in as_completed(futures):
            success = fut.result()
            if not success:
                failed = True

    if failed:
        print("\n[!] One or more documents failed to build.", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"\n[+] All compilations completed successfully. Deliverables are in: {DIST_DIR}")

def get_chapter_num(dir_name: str) -> str | None:
    match = re.search(r"(\d+)$", dir_name)
    return str(int(match.group(1))) if match else None

def main():
    parser = argparse.ArgumentParser(description="Compilation script for MPI math course.")

    parser.add_argument("-ch", "--chapitres", default="all", help="Chapters to compile, default : all.")
    parser.add_argument("-m", "--mode", default="chapitre", help="What to compile, default : chapitre, options : chapitre, cours, TD." )
    parser.add_argument("-he", "--halt_on_error", action='store_true', help="Wether the compilation stops or not when a file gets an error while compiling.")
    parser.add_argument("-a", "--all", action='store_true', help='Whether to compile all files or not.')

    args = parser.parse_args()

    chapter_dirs = [d for d in ROOT_DIR.iterdir() if d.is_dir() and d.name.startswith("chapitre")]
    chapter_dirs.sort(key=lambda d: int(get_chapter_num(d.name) or 0))

    tasks: list[tuple[Path, Path, Path]] = []

    if args.all:
        integ_dir = ROOT_DIR / "integrale"
        if integ_dir.exists():
            for name in ["integrale_mpi.tex", "integrale_cours.tex", "integrale_TD.tex"]:
                f = integ_dir / name
                if f.exists():
                    tasks.append((f, DIST_INTEGRALE, integ_dir))

        for chap in chapter_dirs:
            c_num = get_chapter_num(chap.name)
            if not c_num:
                continue
            
            f_chap = chap / f"chapitre{c_num}.tex"
            if f_chap.exists():
                tasks.append((f_chap, DIST_CHAPITRES, chap))
            f_cours = chap / "cours" / f"cours{c_num}.tex"
            if f_cours.exists():
                tasks.append((f_cours, DIST_COURS, chap / "cours"))
            f_td = chap / "TD" / f"TD{c_num}.tex"
            if f_td.exists():
                tasks.append((f_td, DIST_TDS, chap / "TD"))

        run_tasks(tasks, args.halt_on_error)
        return

    if args.chapitres.lower() == "integrale":
        integ_dir = ROOT_DIR / "integrale"
        lookup = {
            "chapitre": "integrale_mpi.tex",
            "cours": "integrale_cours.tex",
            "TD": "integrale_TD.tex",
        }
        
        target_file = integ_dir / lookup[args.mode]
        tasks.append((target_file, DIST_INTEGRALE, integ_dir))
        run_tasks(tasks, args.halt_on_error)
        return

    if args.chapitres.lower() != "all":
        selected_numbers = {str(int(n.strip())) for n in args.chapitres.split(",") if n.strip().isdigit()}
        chapter_dirs = [d for d in chapter_dirs if get_chapter_num(d.name) in selected_numbers]

    for chap in chapter_dirs:
        c_num = get_chapter_num(chap.name)
        if not c_num:
            continue

        if args.mode == "chapitre":
            f = chap / f"chapitre{c_num}.tex"
            if f.exists():
                tasks.append((f, DIST_CHAPITRES, chap))
        elif args.mode == "cours":
            f = chap / "cours" / f"cours{c_num}.tex"
            if f.exists():
                tasks.append((f, DIST_COURS, chap / "cours"))
        elif args.mode == "TD":
            f = chap / "TD" / f"TD{c_num}.tex"
            if f.exists():
                tasks.append((f, DIST_TDS, chap / "TD"))

    run_tasks(tasks, args.halt_on_error)

if __name__ == "__main__":
    main()
