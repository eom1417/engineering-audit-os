import json
import sys

dossier = json.load(open(sys.argv[1]))
rows = sorted(dossier.get('claims', []), key=lambda c: -(c.get('priority') or 0.0))
for row in rows[:10]:
    location = row.get('location') or ''
    statement = (row.get('statement') or '')[:200]
    print(row.get('id', ''), location, statement)
