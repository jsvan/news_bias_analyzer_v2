"""
Intelligence Module

This module contains statistical analysis scripts looking for abnormal changes in global sentiments.
It maintains the latest state of analysis in a SQLite database and identifies statistically 
significant changes for the dashboard to showcase to potential customers.

The system focuses on:
- Week-to-week sentiment changes (not day-to-day noise)
- Polarization detection
- Source divergence analysis (sources that historically moved together but begin to diverge)
- Low probability events (p-value < 0.01, ~once per year events)
"""