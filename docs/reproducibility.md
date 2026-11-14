# Reproducibility check

The full generator was run twice with seed `20261022`, once into `data/full/` and again into `data/full-repeat/`, using separate SQLite databases. Both runs produced 5,000 employees, 180,000 monthly salary records, 1,800 effective-dated compensation bands, and 81 ground-truth rows. Both validation summaries reported zero integrity errors.

Command used to compare exported artifacts:

```bash
cd backend
python validation.py --compare ../data/full ../data/full-repeat
```

Result: `identical: true`, 36 compared files on each side, zero mismatches. `data/full/checksums.json` records the SHA-256 of each export. Both generated directories are excluded from Git. Recreate them with the generator; no generated full dataset is committed.
