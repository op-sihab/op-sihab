import os
import re
import urllib.request
import html
from datetime import datetime, timedelta

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
    total_str = total_match.group(1) if total_match else "309"

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

    # Parse tooltips
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

    # Sort cells by date for accurate streak calculations
    sorted_cells = sorted(cells, key=lambda x: x["date"])

    # Calculate Streaks
    active_dates = set(c["date"] for c in sorted_cells if c["level"] > 0)
    
    start_dt = datetime.strptime(sorted_cells[0]["date"], "%Y-%m-%d").date()
    end_dt = datetime.strptime(sorted_cells[-1]["date"], "%Y-%m-%d").date()

    all_streaks = []
    cur_streak = 0
    cur_start = None
    d = start_dt

    while d <= end_dt:
        ds = d.strftime("%Y-%m-%d")
        if ds in active_dates:
            if cur_streak == 0:
                cur_start = d
            cur_streak += 1
        else:
            if cur_streak > 0:
                all_streaks.append((cur_streak, cur_start, d - timedelta(days=1)))
                cur_streak = 0
        d += timedelta(days=1)

    if cur_streak > 0:
        all_streaks.append((cur_streak, cur_start, end_dt))

    # Longest Streak
    longest_len, longest_start, longest_end = max(all_streaks, key=lambda x: x[0]) if all_streaks else (0, start_dt, start_dt)
    
    # Current Streak (must touch today or yesterday)
    today = end_dt
    yesterday = today - timedelta(days=1)
    
    current_len = 0
    current_start = today
    current_end = today
    if all_streaks:
        last_s = all_streaks[-1]
        if last_s[2] == today or last_s[2] == yesterday:
            current_len, current_start, current_end = last_s

    # Format date ranges (e.g., "Aug 28 - Sep 1", "Sep 26 - Sep 29")
    def format_range(s_date, e_date):
        if s_date == e_date:
            return s_date.strftime("%b %d").replace(" 0", " ")
        return f"{s_date.strftime('%b')} {s_date.day} - {e_date.strftime('%b')} {e_date.day}"

    # First active date to Present for total contributions
    first_active = min([datetime.strptime(c["date"], "%Y-%m-%d").date() for c in sorted_cells if c["level"] > 0], default=start_dt)
    total_range = f"{first_active.strftime('%b')} {first_active.day} - Present"

    longest_range = format_range(longest_start, longest_end)
    current_range = format_range(current_start, current_end) if current_len > 0 else today.strftime("%b %d")

    streak_data = {
        "total_contributions": total_str,
        "total_range": total_range,
        "current_streak": current_len,
        "current_range": current_range,
        "longest_streak": longest_len,
        "longest_range": longest_range,
    }

    return total_str, months, cells, streak_data

def generate_svg(total_str, months, cells, theme="dark"):
    is_dark = theme == "dark"

    if is_dark:
        bg_card = "#0d1117"
        border_card = "#30363d"
        inner_border = "#21262d"
        text_primary = "#f0f6fc"
        text_accent = "#38bdf8"
        text_muted = "#7d8590"
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
        color_levels = {
            0: "#ebedf0",
            1: "#9be9a8",
            2: "#40c463",
            3: "#30a14e",
            4: "#216e39"
        }
        cell_stroke = "rgba(27,31,35,0.06)"
        glow_color = "#2ea44f"

    card_width = 850
    card_height = 205
    start_x = 75
    start_y = 65
    box_size = 11
    box_gap = 3
    stride = box_size + box_gap

    months_svg = []
    current_col = 0
    for colspan, full_name, short_name in months:
        mx = start_x + (current_col * stride)
        months_svg.append(
            f'<text x="{mx}" y="{start_y - 10}" fill="{text_muted}" font-size="11" font-family="-apple-system,BlinkMacSystemFont,\'Segoe UI\',Helvetica,Arial,sans-serif">{short_name}</text>'
        )
        current_col += colspan

    days_svg = []
    day_labels = [(1, "Mon"), (3, "Wed"), (5, "Fri")]
    for row_idx, label in day_labels:
        dy = start_y + (row_idx * stride) + 9
        days_svg.append(
            f'<text x="{start_x - 30}" y="{dy}" fill="{text_muted}" font-size="10" font-family="-apple-system,BlinkMacSystemFont,\'Segoe UI\',Helvetica,Arial,sans-serif">{label}</text>'
        )

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

  <rect width="{card_width}" height="{card_height}" rx="12" fill="{bg_card}" stroke="{border_card}" stroke-width="1" />
  <rect x="{inner_box_x}" y="{inner_box_y}" width="{inner_box_w}" height="{inner_box_h}" rx="8" fill="none" stroke="{inner_border}" stroke-width="1" />

  <text x="{inner_box_x + 16}" y="{inner_box_y + 19}" class="text-title">
    <tspan fill="{text_accent}">{total_str}</tspan> contributions in the last year
  </text>
  <text x="{inner_box_x + inner_box_w - 16}" y="{inner_box_y + 19}" text-anchor="end" class="text-meta">
    GitHub Activity &amp; Metrics
  </text>

  {''.join(months_svg)}
  {''.join(days_svg)}
  {''.join(cells_svg)}

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

def generate_streak_svg(streak_data, theme="dark"):
    is_dark = theme == "dark"

    if is_dark:
        bg_card = "#0D1117"
        border_card = "#30363D"
        line_color = "#30363D"
        text_num = "#70A5FD"
        text_accent_num = "#BF91F3"
        text_label = "#94A3B8"
        text_curr_label = "#38BDF8"
        text_date = "#38BDAE"
        ring_color = "#38BDF8"
        fire_color = "#F59E0B"
    else:
        bg_card = "#FFFFFF"
        border_card = "#D0D7DE"
        line_color = "#D0D7DE"
        text_num = "#0969DA"
        text_accent_num = "#8250DF"
        text_label = "#656D76"
        text_curr_label = "#0969DA"
        text_date = "#1A7F37"
        ring_color = "#0969DA"
        fire_color = "#D97706"

    total_cnt = streak_data["total_contributions"]
    total_range = streak_data["total_range"]
    curr_streak = streak_data["current_streak"]
    curr_range = streak_data["current_range"]
    longest_streak = streak_data["longest_streak"]
    longest_range = streak_data["longest_range"]

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 495 195" width="495" height="195">
  <defs>
    <style>
      .num {{
        font-family: 'Segoe UI', Ubuntu, -apple-system, sans-serif;
        font-weight: 700;
        font-size: 28px;
        text-anchor: middle;
      }}
      .lbl {{
        font-family: 'Segoe UI', Ubuntu, -apple-system, sans-serif;
        font-weight: 400;
        font-size: 14px;
        text-anchor: middle;
      }}
      .lbl-curr {{
        font-family: 'Segoe UI', Ubuntu, -apple-system, sans-serif;
        font-weight: 700;
        font-size: 14px;
        text-anchor: middle;
      }}
      .dt {{
        font-family: 'Segoe UI', Ubuntu, -apple-system, sans-serif;
        font-weight: 400;
        font-size: 12px;
        text-anchor: middle;
      }}
      @keyframes flamePulse {{
        0%, 100% {{ transform: scale(1); }}
        50% {{ transform: scale(1.1); }}
      }}
      .flame {{
        transform-origin: 247.5px 38px;
        animation: flamePulse 2s ease-in-out infinite;
      }}
    </style>
  </defs>

  <rect width="495" height="195" rx="6" fill="{bg_card}" stroke="{border_card}" stroke-width="1" />

  <!-- Dividers -->
  <line x1="170" y1="40" x2="170" y2="160" stroke="{line_color}" stroke-width="1" />
  <line x1="325" y1="40" x2="325" y2="160" stroke="{line_color}" stroke-width="1" />

  <!-- Total Contributions Column -->
  <g transform="translate(85, 0)">
    <text x="0" y="80" class="num" fill="{text_num}">{total_cnt}</text>
    <text x="0" y="112" class="lbl" fill="{text_label}">Total Contributions</text>
    <text x="0" y="140" class="dt" fill="{text_date}">{total_range}</text>
  </g>

  <!-- Current Streak Column -->
  <g transform="translate(247.5, 0)">
    <!-- Ring -->
    <circle cx="0" cy="74" r="38" fill="none" stroke="{ring_color}" stroke-width="4.5" stroke-linecap="round" />
    
    <!-- Flame Icon atop ring -->
    <g class="flame" transform="translate(-12, 18)">
      <path fill="{fire_color}" d="M12 2C9.5 5 7 7.5 7 11a5 5 0 0 0 10 0c0-3.5-2.5-6-5-9zm0 13a3 3 0 0 1-3-3c0-1.5 1-2.8 2-3.8.4.8 1 1.5 1.5 2.2.4-.6.8-1.4.9-2.4 1 1.2 1.6 2.5 1.6 4a3 3 0 0 1-3 3z" />
    </g>

    <text x="0" y="83" class="num" fill="{text_accent_num}">{curr_streak}</text>
    <text x="0" y="132" class="lbl-curr" fill="{text_curr_label}">Current Streak</text>
    <text x="0" y="156" class="dt" fill="{text_date}">{curr_range}</text>
  </g>

  <!-- Longest Streak Column -->
  <g transform="translate(410, 0)">
    <text x="0" y="80" class="num" fill="{text_num}">{longest_streak}</text>
    <text x="0" y="112" class="lbl" fill="{text_label}">Longest Streak</text>
    <text x="0" y="140" class="dt" fill="{text_date}">{longest_range}</text>
  </g>
</svg>'''
    return svg

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

    total_str, months, cells, streak_data = parse_contributions(content)
    print(f"Parsed {total_str} contributions across {len(cells)} days.")
    print("Streak Data:", streak_data)

    os.makedirs("assets", exist_ok=True)

    # Heatmaps
    dark_svg = generate_svg(total_str, months, cells, theme="dark")
    with open(os.path.join("assets", "github-contributions-dark.svg"), "w", encoding="utf-8") as f:
        f.write(dark_svg)

    light_svg = generate_svg(total_str, months, cells, theme="light")
    with open(os.path.join("assets", "github-contributions-light.svg"), "w", encoding="utf-8") as f:
        f.write(light_svg)

    with open(os.path.join("assets", "github-contributions.svg"), "w", encoding="utf-8") as f:
        f.write(dark_svg)

    # Streaks
    dark_streak = generate_streak_svg(streak_data, theme="dark")
    with open(os.path.join("assets", "github-streak-dark.svg"), "w", encoding="utf-8") as f:
        f.write(dark_streak)

    light_streak = generate_streak_svg(streak_data, theme="light")
    with open(os.path.join("assets", "github-streak-light.svg"), "w", encoding="utf-8") as f:
        f.write(light_streak)

    with open(os.path.join("assets", "github-streak.svg"), "w", encoding="utf-8") as f:
        f.write(dark_streak)

    print("All SVGs updated successfully!")

if __name__ == "__main__":
    main()
