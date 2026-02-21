import os
import datetime

base_v13 = r"c:\hfoDev\hfo_gen_89_hot_obsidian_forge\1_silver\projects\omega_v13_microkernel"
base_v14 = r"c:\hfoDev\hfo_gen_89_hot_obsidian_forge\2_gold\projects\omega_v14_microkernel"

ts = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
out_path = os.path.join(r"c:\hfoDev", f"{ts}_omega_v13_v14_monolith.md")

EXCLUDES = {"node_modules", "dist", "exemplars", "reports", ".git", "coverage", ".stryker-tmp", "test-results"}
SKIP_FILES = {"package-lock.json"}

EXT_LANG = {
    ".ts": "typescript",
    ".js": "javascript",
    ".mjs": "javascript",
    ".json": "json",
    ".html": "html",
    ".py": "python",
    ".scxml": "xml",
    ".md": "markdown",
    ".txt": "text",
}

def get_files(base):
    files = []
    for root, dirs, fnames in os.walk(base):
        dirs[:] = sorted([d for d in dirs if d not in EXCLUDES])
        for fn in sorted(fnames):
            if fn in SKIP_FILES:
                continue
            ext = os.path.splitext(fn)[1].lower()
            if ext in EXT_LANG:
                files.append(os.path.join(root, fn))
    return files

files_v13 = get_files(base_v13)
files_v14 = get_files(base_v14)

def sort_key(fp, base):
    ext = os.path.splitext(fp)[1].lower()
    order = {".md": 0, ".ts": 1, ".html": 2, ".js": 3, ".mjs": 3, ".json": 4, ".scxml": 5, ".py": 6}
    return (order.get(ext, 99), os.path.relpath(fp, base).replace("\\", "/").lower())

files_v13.sort(key=lambda fp: sort_key(fp, base_v13))
files_v14.sort(key=lambda fp: sort_key(fp, base_v14))

lines = []
lines.append("# Omega v13 & v14 Microkernel  Complete Monolith\n\n")
lines.append(f"**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n")
lines.append(f"**Files included:** {len(files_v13) + len(files_v14)}  \n")
lines.append(f"**Source v13:** {base_v13}\n")
lines.append(f"**Source v14:** {base_v14}\n\n")
lines.append("---\n\n")
lines.append("## Table of Contents\n\n")

lines.append("### V13 Files\n")
for i, fp in enumerate(files_v13, 1):
    rel = os.path.relpath(fp, base_v13).replace("\\", "/")
    lines.append(f"{i}. 13/{rel}\n")

lines.append("\n### V14 Files\n")
for i, fp in enumerate(files_v14, 1):
    rel = os.path.relpath(fp, base_v14).replace("\\", "/")
    lines.append(f"{i}. 14/{rel}\n")

lines.append("\n---\n\n")

def append_files(files, base, prefix):
    for fp in files:
        rel = os.path.relpath(fp, base).replace("\\", "/")
        ext = os.path.splitext(fp)[1].lower()
        lang = EXT_LANG.get(ext, "text")
        lines.append(f"\n\n---\n\n## {prefix}/{rel}\n\n")
        try:
            content = open(fp, "r", encoding="utf-8", errors="replace").read()
        except Exception as e:
            content = f"[ERROR reading file: {e}]"
        if lang == "markdown":
            lines.append(content)
            if not content.endswith("\n"):
                lines.append("\n")
        else:
            lines.append(f"`{lang}\n{content}\n`\n")

append_files(files_v13, base_v13, "v13")
append_files(files_v14, base_v14, "v14")

text = "".join(lines)

os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    f.write(text)

size_kb = os.path.getsize(out_path) / 1024
print(f"Output: {out_path}")
print(f"Files:  {len(files_v13) + len(files_v14)}")
print(f"Size:   {size_kb:.1f} KB  ({int(size_kb*1024):,} bytes)")
