"""Deterministic, standalone SVG charts with text alternatives."""

from html import escape


def svg(title, description, content, height=300):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 {height}" '
        'role="img" aria-labelledby="title description" font-family="system-ui,sans-serif">\n'
        f'<title id="title">{escape(title)}</title>\n'
        f'<desc id="description">{escape(description)}</desc>\n'
        f'<rect width="720" height="{height}" rx="12" fill="#fff"/>\n'
        f'<text x="24" y="34" font-size="19" fill="#152735">{escape(title)}</text>\n'
        f'{content}\n</svg>\n'
    )


def bars(title, rows):
    """Plot signed values against a common zero line."""
    values = [float(value) for _, value in rows]
    scale = 420 / (max(0, *values) - min(0, *values) or 1)
    zero = 162 - min(0, *values) * scale
    height = 64 + 42 * len(rows)
    elements = [f'<path d="M {zero:.2f},52 V {height - 18}" stroke="#586a76"/>']
    for index, ((label, value), numeric) in enumerate(zip(rows, values)):
        y = 58 + 42 * index
        offset = numeric * scale
        left = min(zero, zero + offset)
        elements.extend([
            f'<text x="24" y="{y + 15}" fill="#152735">{escape(label)}</text>',
            f'<rect x="{left:.2f}" y="{y}" width="{abs(offset):.2f}" height="20" fill="#166e68"/>',
            f'<text x="600" y="{y + 15}" fill="#152735">{escape(str(value))}</text>',
        ])
    return svg(title, ", ".join(f"{label}: {value}" for label, value in rows),
               "\n".join(elements), height)


def event_curve(name, series, key, label):
    """Plot only observed source points, using their original event indexes."""
    values = [float(point[key]) for point in series]
    low, high = min(values), max(values)
    span = high - low or 1
    end = series[-1]["event_index"]
    points = " ".join(
        f"{116 + 572 * point['event_index'] / (end or 1):.2f},{217 - 152 * (value - low) / span:.2f}"
        for point, value in zip(series, values)
    )
    elements = [
        '<path d="M 116,62 V 217 H 688" fill="none" stroke="#586a76"/>',
        f'<polyline points="{points}" fill="none" stroke="#166e68" stroke-width="3"/>',
        '<text x="24" y="223" fill="#152735">' + f"{low:,.2f}</text>",
        '<text x="116" y="242" fill="#152735">0</text>',
        f'<text x="688" y="242" text-anchor="end" fill="#152735">{end}</text>',
        '<text x="402" y="271" text-anchor="middle" fill="#152735">Synthetic ledger event index</text>',
    ]
    if high != low:
        elements.append(f'<text x="24" y="71" fill="#152735">{high:,.2f}</text>')
    for point in points.split():
        x, y = point.split(",")
        elements.append(f'<circle cx="{x}" cy="{y}" r="2.8" fill="#166e68"/>')
    return svg(f"Hypothetical synthetic · {name.title()} · {label} (USD)",
               f"{len(series)} observations, event index 0 through {end}, "
               f"values range from {low:,.2f} to {high:,.2f} USD. "
               "See summary.json for all event values.", "\n".join(elements))

