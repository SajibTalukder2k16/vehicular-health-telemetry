#!/usr/bin/env python3
"""DEPRECATED: figure code now lives in figures_src/, one file per figure.

  figures_src/fig0_architecture.py       architecture diagram
  figures_src/fig1_feasibility_heatmap.py
  figures_src/fig2_delay_ecdf.py
  figures_src/fig3_delivery_vs_isd.py
  figures_src/fig4_aoi_timeseries.py
  figures_src/fig5_cqi_vs_distance.py
  figures_src/make_all.py                run all + copy to manuscript/figures
  make_effects_table.py                  main-effects table (main_effects.csv)

This stub just runs make_all.py.
"""
import os, subprocess, sys
subprocess.run([sys.executable,
                os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'figures_src', 'make_all.py')], check=True)
