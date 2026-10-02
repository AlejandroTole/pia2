import os

# Carpetas que no quieres ver en el árbol
EXCLUDE_DIRS = {".venv", "__pycache__", ".git", "node_modules", ".pytest_cache", ".idea", ".vscode"}
OUTPUT_FILE = "estructura.txt"

def build_tree(start_path="."):
    lines = []
    for root, dirs, files in os.walk(start_path):
        # Filtra las carpetas excluidas ANTES de que os.walk baje a ellas
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

        depth = root.replace(start_path, "").count(os.sep)
        indent = "    " * depth
        folder_name = os.path.basename(root) if depth > 0 else os.path.basename(os.path.abspath(start_path))
        lines.append(f"{indent}{folder_name}/")

        sub_indent = "    " * (depth + 1)
        for f in sorted(files):
            lines.append(f"{sub_indent}{f}")

    return "\n".join(lines)

if __name__ == "__main__":
    tree_text = build_tree(".")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(tree_text)
    print(f"✅ Árbol guardado en {OUTPUT_FILE}")
    print(f"   ({len(tree_text.splitlines())} líneas, sin .venv ni __pycache__)")