# Contributing

This repository mirrors signed Portable Resume release artifacts. Product changes belong in [ImL1s/resume-skills](https://github.com/ImL1s/resume-skills); do not edit generated plugin trees by hand.

To validate a marketplace-only change:

```bash
python3 -m unittest discover -s tests -q
python3 scripts/sync_release.py --tag v0.3.2 --asset-dir /path/to/release-assets
python3 -m unittest discover -s tests -q
git diff --check
```

Pull requests should state the upstream tag, explain catalog changes, and include fresh validation output.
