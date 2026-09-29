import os
import re
import urllib.request
import html

USERNAME = "op-sihab"
URL = f"https://github.com/users/{USERNAME}/contributions"

def fetch_contributions_html():
    req = urllib.request.Request(
        URL,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8")

def parse_contributions(content):
    # Total contributions
    total_match = re.search(r'([0-9,]+)\s+contributions\s+in the last year', content)
    total_str = total_match.group(1) if total_match else "167"

    # Months header
    months = []
    month_matches = re.finditer(
        r'<td class="ContributionCalendar-label"[^>]*colspan="(\d+)"[^>]*>\s*<span class="sr-only">([^<]+)</span>\s*<span aria-hidden="true"[^>]*>([^<]+)</span>',
        content
    )
    for m in month_matches:
        colspan = int(m.group(1))
        full_name = m.group(2).strip()
        short_name = m.group(3).strip()
        months.append((colspan, full_name, short_name))

    # Parse tooltips for nice title hover
    tooltips = {}
    for tm in re.finditer(r'<tool-tip[^>]*for="([^"]+)"[^>]*>(.*?)</tool-tip>', content):
        cell_id = tm.group(1)
        tip_text = html.unescape(tm.group(2).strip())
        tooltips[cell_id] = tip_text

    # Cells
    cells = []
    cell_pattern = re.finditer(r'<td[^>]*class="ContributionCalendar-day"[^>]*>', content)
    for m in cell_pattern:
        tag = m.group(0)
        date_m = re.search(r'data-date="([^"]+)"', tag)
        id_m = re.search(r'id="(contribution-day-component-(\d+)-(\d+))"', tag)
        level_m = re.search(r'data-level="(\d+)"', tag)
        if date_m and id_m and level_m:
            cell_id = id_m.group(1)
            row = int(id_m.group(2))
            col = int(id_m.group(3))
            date = date_m.group(1)
            level = int(level_m.group(1))
            tip = tooltips.get(cell_id, f"{level} contributions on {date}")
            cells.append({
                "row": row,
                "col": col,
                "date": date,
                "level": level,
                "tip": tip
            })

    return total_str, months, cells

def generate_svg(total_str, months, cells, theme="dark"):
    is_dark = theme == "dark"

    # Palette
    if is_dark:
        bg_card = "#0d1117"
        border_card = "#30363d"
        inner_border = "#21262d"
        text_primary = "#f0f6fc"
        text_accent = "#38bdf8"
        text_muted = "#7d8590"
        link_color = "#58a6ff"
        # Contribution level squares (Dark mode GitHub colors)
        color_levels = {
            0: "#161b22",
            1: "#0e4429",
            2: "#006d32",
            3: "#26a641",
            4: "#39d353"
        }
        cell_stroke = "#21262d"
        glow_color = "#38bdf8"
    else:
        bg_card = "#ffffff"
        border_card = "#d0d7de"
        inner_border = "#d0d7de"
        text_primary = "#1f2328"
        text_accent = "#0969da"
        text_muted = "#656d76"
        link_color = "#0969da"
        # Contribution level squares (Exact light mode colors from user image)
        color_levels = {
            0: "#ebedf0",
            1: "#9be9a8",
            2: "#40c463",
            3: "#30a14e",
            4: "#216e39"
        }
        cell_stroke = "rgba(27,31,35,0.06)"
        glow_color = "#2ea44f"

    # Layout dimensions
    card_width = 850
    card_height = 205
    start_x = 75
    start_y = 65
    box_size = 11
    box_gap = 3
    stride = box_size + box_gap

    # Build months labels
    months_svg = []
    current_col = 0
    for colspan, full_name, short_name in months:
        mx = start_x + (current_col * stride)
        months_svg.append(
            f'<text x="{mx}" y="{start_y - 10}" fill="{text_muted}" font-size="11" font-family="-apple-system,BlinkMacSystemFont,\'Segoe UI\',Helvetica,Arial,sans-serif">{short_name}</text>'
        )
        current_col += colspan

    # Build day of week labels (Mon = row 1, Wed = row 3, Fri = row 5)
    days_svg = []
    day_labels = [(1, "Mon"), (3, "Wed"), (5, "Fri")]
    for row_idx, label in day_labels:
        dy = start_y + (row_idx * stride) + 9
        days_svg.append(
            f'<text x="{start_x - 30}" y="{dy}" fill="{text_muted}" font-size="10" font-family="-apple-system,BlinkMacSystemFont,\'Segoe UI\',Helvetica,Arial,sans-serif">{label}</text>'
        )

    # Build cells
    cells_svg = []
    for c in cells:
        cx = start_x + (c["col"] * stride)
        cy = start_y + (c["row"] * stride)
        color = color_levels.get(c["level"], color_levels[0])
        safe_tip = html.escape(c["tip"])
        stroke_attr = f'stroke="{cell_stroke}" stroke-width="0.5"' if c["level"] == 0 else ""
        cells_svg.append(
            f'<rect class="cell" x="{cx}" y="{cy}" width="{box_size}" height="{box_size}" rx="2.5" fill="{color}" {stroke_attr} data-date="{c["date"]}" data-level="{c["level"]}"><title>{safe_tip}</title></rect>'
        )

    # Legend at bottom right
    legend_start_x = start_x + (53 * stride) - 105
    legend_y = start_y + (7 * stride) + 16
    legend_cells = []
    for lvl in range(5):
        lx = legend_start_x + 30 + (lvl * (box_size + 2))
        lcolor = color_levels[lvl]
        lstroke = f'stroke="{cell_stroke}" stroke-width="0.5"' if lvl == 0 else ""
        legend_cells.append(
            f'<rect x="{lx}" y="{legend_y - 9}" width="{box_size}" height="{box_size}" rx="2" fill="{lcolor}" {lstroke} />'
        )

    # Inner grid border (bounding the graph area like GitHub does)
    inner_box_x = start_x - 42
    inner_box_y = start_y - 28
    inner_box_w = (53 * stride) + 48
    inner_box_h = (7 * stride) + 54

    svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {card_width} {card_height}" width="100%" height="100%">
  <defs>
    <style>
      .text-title {{
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
        font-size: 15px;
        font-weight: 600;
        fill: {text_primary};
      }}
      .text-meta {{
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
        font-size: 11px;
        fill: {text_muted};
      }}
      .cell {{
        cursor: pointer;
        transition: transform 0.12s ease-in-out, stroke 0.12s ease-in-out;
        transform-origin: center;
      }}
      .cell:hover {{
        stroke: {glow_color};
        stroke-width: 1.5px;
      }}
    </style>
  </defs>

  <!-- Outer Card Frame -->
  <rect width="{card_width}" height="{card_height}" rx="12" fill="{bg_card}" stroke="{border_card}" stroke-width="1" />

  <!-- Inner Calendar Border (exact match to GitHub profile graph box) -->
  <rect x="{inner_box_x}" y="{inner_box_y}" width="{inner_box_w}" height="{inner_box_h}" rx="8" fill="none" stroke="{inner_border}" stroke-width="1" />

  <!-- Card Header -->
  <text x="{inner_box_x + 16}" y="{inner_box_y + 19}" class="text-title">
    <tspan fill="{text_accent}">{total_str}</tspan> contributions in the last year
  </text>
  <text x="{inner_box_x + inner_box_w - 16}" y="{inner_box_y + 19}" text-anchor="end" class="text-meta">
    GitHub Activity &amp; Metrics
  </text>

  <!-- Month Labels -->
  {''.join(months_svg)}

  <!-- Day Labels -->
  {''.join(days_svg)}

  <!-- Heatmap Contribution Squares -->
  {''.join(cells_svg)}

  <!-- Footer Info & Legend -->
  <a href="https://docs.github.com/articles/why-are-my-contributions-not-showing-up-on-my-profile" target="_blank">
    <text x="{inner_box_x + 16}" y="{legend_y}" class="text-meta" style="cursor: pointer; text-decoration: underline;">
      Learn how we count contributions
    </text>
  </a>

  <text x="{legend_start_x}" y="{legend_y}" class="text-meta">Less</text>
  {''.join(legend_cells)}
  <text x="{legend_start_x + 30 + (5 * (box_size + 2)) + 4}" y="{legend_y}" class="text-meta">More</text>
</svg>'''
    return svg_content

def main():
    print(f"Fetching contribution data for {USERNAME}...")
    try:
        content = fetch_contributions_html()
    except Exception as e:
        print(f"Direct fetch failed: {e}. Checking local cache...")
        if os.path.exists("gh_contrib.html"):
            try:
                with open("gh_contrib.html", "r", encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open("gh_contrib.html", "r", encoding="utf-16") as f:
                    content = f.read()
        else:
            raise

    total_str, months, cells = parse_contributions(content)
    print(f"Parsed {total_str} contributions across {len(cells)} days.")

    os.makedirs("assets", exist_ok=True)

    # 1. Dark Theme
    dark_svg = generate_svg(total_str, months, cells, theme="dark")
    dark_path = os.path.join("assets", "github-contributions-dark.svg")
    with open(dark_path, "w", encoding="utf-8") as f:
        f.write(dark_svg)
    print(f"Saved: {dark_path}")

    # 2. Light Theme (Matches user's image exactly)
    light_svg = generate_svg(total_str, months, cells, theme="light")
    light_path = os.path.join("assets", "github-contributions-light.svg")
    with open(light_path, "w", encoding="utf-8") as f:
        f.write(light_svg)
    print(f"Saved: {light_path}")

    # 3. Default (dark)
    default_path = os.path.join("assets", "github-contributions.svg")
    with open(default_path, "w", encoding="utf-8") as f:
        f.write(dark_svg)
    print(f"Saved: {default_path}")

if __name__ == "__main__":
    main()
