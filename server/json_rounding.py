"""Recursive 4-decimal float rounding for everything served as JSON.

Scores live on a -2..2 scale and the UI shows 1-2 decimals; full float repr
is pure payload bloat (~35% of the raw bytes on the biggest dashboard
responses). One helper, two transports: the snapshot exporter rounds on write
(export_snapshots.write_json) and the live API rounds on render
(extension_api.RoundedJSONResponse), so static and live payloads stay
byte-comparable.

Stdlib-only on purpose - export_snapshots' self-test imports this without the
server env installed.
"""


def round_floats(o, ndigits: int = 4):
    if isinstance(o, float):
        return round(o, ndigits)
    if isinstance(o, dict):
        return {k: round_floats(v, ndigits) for k, v in o.items()}
    if isinstance(o, list):
        return [round_floats(v, ndigits) for v in o]
    return o
