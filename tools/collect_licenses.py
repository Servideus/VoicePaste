"""Collect installed dependency notices for the binary and source package."""
from importlib.metadata import distributions
from pathlib import Path
import hashlib

root = Path(__file__).resolve().parents[1]
output = root / "third_party_licenses"
output.mkdir(exist_ok=True)
index = []
for dist in sorted(distributions(), key=lambda item: item.metadata["Name"].lower()):
    name = dist.metadata["Name"]
    index.append(f"{name}=={dist.version}")
    for entry in dist.files or []:
        if entry.name.lower().startswith(("license", "copying", "copyright")) or any(part.lower() == "licenses" for part in entry.parts):
            source = Path(dist.locate_file(entry))
            if source.is_file():
                suffix = hashlib.sha256(str(entry).encode()).hexdigest()[:8]
                target = output / f"{name}-{suffix}-{entry.name}"
                target.write_bytes(source.read_bytes())
(output / "PACKAGES.txt").write_text("\n".join(index) + "\n", encoding="utf-8")
print(f"Collected notices for {len(index)} installed packages in {output.name}")
