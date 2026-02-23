import os
import re

files_to_fix = [
    "backend/services/auth.py",
    "backend/services/agent_router.py",
    "backend/services/rag_engine.py",
    "pipeline/core/embedder.py",
    "pipeline/core/ram_tagger.py",
    "pipeline/utils/s3_uploader.py",
    "pipeline/steps/clustering.py",
    "scripts/batch_tagging.py"
]

for file_path in files_to_fix:
    if not os.path.exists(file_path):
        continue
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Add Optional import if not present
    if "from typing import Optional" not in content and re.search(r'\b[a-zA-Z_][a-zA-Z0-9_]*\s*\|\s*None\b', content):
        # Insert after first import
        content = re.sub(r'^(import|from)\s+.*$', r'from typing import Optional\n\g<0>', content, count=1, flags=re.MULTILINE)

    # Replace X | None with Optional[X]
    content = re.sub(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\|\s*None\b', r'Optional[\1]', content)

    # Some variables like tuple[str | None,...] might need more careful replacement if they use tuple[]
    # but the regex should handle str | None nicely.
    # What about tuple[float | None, float | None]?
    # It would become tuple[Optional[float], Optional[float]] which is correct.
    # What about DiaryAction | None? Optional[DiaryAction].

    # Python 3.9 also uses Tuple/Dict over tuple/dict if we really want to be safe,
    # but Python 3.9 DOES support list/dict/tuple generic hints! (PEP 585 was Python 3.9!)
    # So `tuple[Optional[str]]` is perfectly valid 3.9 code.

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

print("Fixed types.")
