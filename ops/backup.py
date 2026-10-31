"""Run from project root: python ops/backup.py backups/store.dump"""
import pathlib
import subprocess
import sys

path = pathlib.Path(sys.argv[1])
path.parent.mkdir(parents=True, exist_ok=True)
# Stream binary output directly; never decode a PostgreSQL custom archive.
with path.open('xb') as output:
    result = subprocess.run(['docker', 'compose', 'exec', '-T', 'db', 'pg_dump',
                             '-U', 'ecommerce_user', '-d', 'ecommerce_db', '-Fc'], stdout=output)
if result.returncode:
    path.unlink()
    raise SystemExit(result.returncode)
print(f'Backup saved: {path}')
