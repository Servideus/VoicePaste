# Compatibility entry point. The root spec is authoritative.
from pathlib import Path
SPECPATH = str(Path(SPECPATH).parent)
exec(compile((Path(SPECPATH) / 'VoicePaste.spec').read_text(encoding='utf-8'), 'VoicePaste.spec', 'exec'))
