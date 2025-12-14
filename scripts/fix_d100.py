import subprocess
from pathlib import Path


def get_violations():
    try:
        # Run ruff check
        result = subprocess.run(
            ["python", "-m", "ruff", "check", ".", "--select", "D100"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        output = result.stdout + "\n" + result.stderr

        # Debug: Print first few lines
        print("DEBUG OUTPUT:", output[:500])

        # Regex to find filenames
        # Example: src/features/lats.py:1:1: D100 ...
        # But ruff output format might vary. Assuming default "concise" or similar.
        # Actually default is usually: filename:line:col: code message

        violations = []
        for line in output.splitlines():
            # Format: "--> path/to/file.py:1:1"
            if "--> " in line:
                # Remove "--> " and get path
                path_part = line.split("--> ")[1]
                # Split by ":" to get filename (assuming valid path chars)
                # Windows paths might have drive letter? But usually relative.
                # Safe split: find the .py extension or split by first colon after some chars?
                # Simple split by ":"
                parts = path_part.split(":")
                if len(parts) >= 1:
                    filepath = parts[0].strip()
                    violations.append(filepath)
        return sorted(list(set(violations)))
    except Exception as e:
        print(f"Error running ruff: {e}")
        return []


def fix_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Determine insertion point
        insert_idx = 0
        # Skip shebang
        if lines and lines[0].startswith("#!"):
            insert_idx += 1
        # Skip encoding cookie
        if len(lines) > insert_idx and (
            lines[insert_idx].startswith("# -*-")
            or lines[insert_idx].startswith("# mypy:")
        ):
            insert_idx += 1

        # Determine module name/docstring
        p = Path(path)
        if p.name == "__init__.py":
            doc = '"""Package initialization."""\n'
        else:
            name = p.stem.replace("_", " ").title()
            doc = f'"""{name} module."""\n'

        # Check if docstring already likely exists (double check ruff didn't lie, or avoid double insert)
        # But ruff said D100, so assume missing.

        # Insert
        lines.insert(insert_idx, doc)

        with open(path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print(f"Fixed {path}")
        return True
    except Exception as e:
        print(f"Failed to fix {path}: {e}")
        return False


def main():
    files = get_violations()
    print(f"Found {len(files)} files with D100 violations.")

    count = 0
    for f in files:
        if fix_file(f):
            count += 1

    print(f"Successfully fixed {count} files.")


if __name__ == "__main__":
    main()
