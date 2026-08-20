"""Print the fabrication part list as an aligned terminal table.

The raw markdown is unreadable once rows carry image tags and full GitHub
URLs, and editor previews mangle it further. This strips a row down to its
text (images -> [img], links -> their label) and aligns the columns:

    python tools/print_part_table.py
"""

import pathlib
import re

FABRICATION = pathlib.Path(__file__).parent.parent / "docs" / "fabrication.md"


def cell_text(cell: str) -> str:
    cell = re.sub(r"<span[^>]*class=\"online_3d_viewer\"[^>]*></span>", "[3d]", cell)  # embedded viewers
    cell = re.sub(r"<[^>]+>", "", cell)  # any other raw HTML
    cell = re.sub(r"\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)", "[img]", cell)  # linked images
    cell = re.sub(r"!\[[^\]]*\]\([^)]*\)", "[img]", cell)  # images
    cell = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", cell)  # inline links keep their label
    cell = re.sub(r"\[([^\]]*)\]\[[^\]]*\]", r"\1", cell)  # reference links keep their label
    cell = cell.replace("`", "")
    return cell.strip()


def print_table(rows: list) -> None:
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    for index, row in enumerate(rows):
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
        if index == 0:
            print("  ".join("-" * width for width in widths))
    print()


def main() -> None:
    rows = []
    for line in FABRICATION.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("###"):
            print(line.lstrip("# "))
        if not line.startswith("|"):
            if rows:
                print_table(rows)  # the table ended
                rows = []
            continue
        cells = [cell_text(cell) for cell in line.strip("|").split("|")]
        if all(set(cell) <= set("-: ") for cell in cells):
            continue  # the | --- | separator
        rows.append(cells)
    if rows:
        print_table(rows)


if __name__ == "__main__":
    main()
