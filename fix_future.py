import os
files = [
    "backend/services/auth.py",
    "backend/services/agent_router.py",
    "backend/services/rag_engine.py",
    "pipeline/core/embedder.py",
    "pipeline/core/ram_tagger.py",
    "pipeline/utils/s3_uploader.py",
    "pipeline/steps/clustering.py",
    "scripts/batch_tagging.py"
]

for file in files:
    if not os.path.exists(file): continue
    with open(file, 'r') as f:
        lines = f.readlines()
    
    future_idx = -1
    for i, line in enumerate(lines):
        if "from __future__ import annotations" in line:
            future_idx = i
            break
            
    if future_idx > 0:
        lines.insert(0, lines.pop(future_idx))
        with open(file, 'w') as f:
            f.writelines(lines)
