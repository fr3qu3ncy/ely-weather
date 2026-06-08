#!/bin/bash
# Regenerate Ely weather site and push to GitHub Pages
set -e
cd /tmp/ely-weather
python3 generate.py
git add -A
if ! git diff --cached --quiet; then
  git commit -m "Update $(date +%Y-%m-%d_%H:%M)"
  git push
  echo "Pushed update"
else
  echo "No changes"
fi
