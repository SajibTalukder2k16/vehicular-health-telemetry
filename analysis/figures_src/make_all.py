#!/usr/bin/env python3
"""Regenerate every manuscript figure and copy the results into
manuscript/figures/.   Run: python3 make_all.py
"""
import glob
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FIGDIR = os.path.join(HERE, '..', 'figures')
MANUSCRIPT = os.path.join(HERE, '..', '..', 'manuscript', 'figures')

scripts = sorted(glob.glob(os.path.join(HERE, 'fig*.py')))
for script in scripts:
    print(f'--- {os.path.basename(script)}')
    subprocess.run([sys.executable, script], check=True, cwd=HERE)

os.makedirs(MANUSCRIPT, exist_ok=True)
n = 0
for f in glob.glob(os.path.join(FIGDIR, 'fig*.p??')):
    shutil.copy(f, MANUSCRIPT)
    n += 1
print(f'copied {n} files to {MANUSCRIPT}')
