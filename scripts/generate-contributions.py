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
    total_match = re.search(r'([0-9,]+)\s+contributions\s+in the last year', content)
    total_str = total_match.group(1) if total_match else "310"

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

    tooltips = {}
    for tm in re.finditer(r'<tool-tip[^>]*for="([^"]+)"[^>]*>(.*?)</tool-tip>', content):
        cell_id = tm.group(1)
        tip_text = html.unescape(tm.group(2).strip())
        tooltips[cell_id] = tip_text

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

    sorted_cells = sorted(cells, key=lambda x: x["date"])
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

    longest_len, longest_start, longest_end = max(all_streaks, key=lambda x: x[0]) if all_streaks else (0, start_dt, start_dt)
    
    today = end_dt
    yesterday = today - timedelta(days=1)
    
    current_len = 0
    current_start = today
    current_end = today
    if all_streaks:
        last_s = all_streaks[-1]
        if last_s[2] == today or last_s[2] == yesterday:
            current_len, current_start, current_end = last_s

    def format_range(s_date, e_date):
        if s_date == e_date:
            return s_date.strftime("%b %d").replace(" 0", " ")
        return f"{s_date.strftime('%b')} {s_date.day} - {e_date.strftime('%b')} {e_date.day}"

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

def generate_stats_card_svg(total_str, theme="dark"):
    is_dark = theme == "dark"

    if is_dark:
        bg_card = "#0D1117"
        border_card = "#30363D"
        inner_bg = "#161B22"
        inner_border = "#21262D"
        text_title = "#38BDF8"
        text_num = "#F0F6FC"
        text_num_cyan = "#38BDF8"
        text_num_purple = "#BF91F3"
        text_label = "#94A3B8"
        text_sub = "#7D8590"
        badge_bg = "rgba(34, 197, 94, 0.15)"
        badge_text = "#22C55E"
    else:
        bg_card = "#FFFFFF"
        border_card = "#D0D7DE"
        inner_bg = "#F6F8FA"
        inner_border = "#D0D7DE"
        text_title = "#0969DA"
        text_num = "#1F2328"
        text_num_cyan = "#0969DA"
        text_num_purple = "#8250DF"
        text_label = "#57606A"
        text_sub = "#656D76"
        badge_bg = "rgba(26, 127, 55, 0.12)"
        badge_text = "#1A7F37"

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 495 195" width="495" height="195">
  <defs>
    <style>
      .mono-title {{
        font-family: 'SF Mono', 'Geist Mono', 'Fira Code', monospace;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 1.5px;
      }}
      .num-val {{
        font-family: 'Segoe UI', -apple-system, sans-serif;
        font-size: 23px;
        font-weight: 700;
      }}
      .label-desc {{
        font-family: 'SF Mono', 'Geist Mono', monospace;
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 0.8px;
      }}
      .sub-desc {{
        font-family: -apple-system, 'Segoe UI', sans-serif;
        font-size: 10.5px;
      }}
      @keyframes pulseGlow {{
        0%, 100% {{ opacity: 0.8; transform: scale(1); }}
        50% {{ opacity: 1; transform: scale(1.15); }}
      }}
      .pulse-dot {{
        animation: pulseGlow 2s ease-in-out infinite;
        transform-origin: center;
      }}
    </style>
  </defs>

  <!-- Container Box -->
  <rect width="495" height="195" rx="8" fill="{bg_card}" stroke="{border_card}" stroke-width="1" />

  <!-- Eyebrow Header -->
  <text x="24" y="28" class="mono-title" fill="{text_title}">
    TELEMETRY // DEV CONSOLE
  </text>

  <!-- Live Status Badge -->
  <g transform="translate(355, 14)">
    <rect width="118" height="20" rx="10" fill="{badge_bg}" />
    <circle cx="12" cy="10" r="3.5" fill="{badge_text}" class="pulse-dot" />
    <text x="22" y="14" font-family="'SF Mono', 'Geist Mono', monospace" font-size="9.5" font-weight="700" fill="{badge_text}" letter-spacing="0.5">SHIPPING DAILY</text>
  </g>

  <!-- Metric Tile 1: Total Contributions -->
  <g transform="translate(24, 44)">
    <rect width="215" height="58" rx="6" fill="{inner_bg}" stroke="{inner_border}" stroke-width="1" />
    <text x="14" y="28" class="num-val" fill="{text_num_cyan}">{total_str}</text>
    <text x="14" y="44" class="label-desc" fill="{text_label}">TOTAL CONTRIBUTIONS</text>
  </g>

  <!-- Metric Tile 2: Commits -->
  <g transform="translate(255, 44)">
    <rect width="215" height="58" rx="6" fill="{inner_bg}" stroke="{inner_border}" stroke-width="1" />
    <text x="14" y="28" class="num-val" fill="{text_num}">153+</text>
    <text x="14" y="44" class="label-desc" fill="{text_label}">PRODUCTION COMMITS</text>
  </g>

  <!-- Metric Tile 3: Pull Requests -->
  <g transform="translate(24, 114)">
    <rect width="215" height="58" rx="6" fill="{inner_bg}" stroke="{inner_border}" stroke-width="1" />
    <text x="14" y="28" class="num-val" fill="{text_num_purple}">3</text>
    <text x="14" y="44" class="label-desc" fill="{text_label}">PULL REQUESTS MERGED</text>
  </g>

  <!-- Metric Tile 4: Public Repos -->
  <g transform="translate(255, 114)">
    <rect width="215" height="58" rx="6" fill="{inner_bg}" stroke="{inner_border}" stroke-width="1" />
    <text x="14" y="28" class="num-val" fill="{text_num_cyan}">14</text>
    <text x="14" y="44" class="label-desc" fill="{text_label}">ACTIVE REPOSITORIES</text>
  </g>
</svg>'''
    return svg

def generate_langs_card_svg(theme="dark"):
    is_dark = theme == "dark"

    if is_dark:
        bg_card = "#0D1117"
        border_card = "#30363D"
        inner_bg = "#161B22"
        inner_border = "#21262D"
        text_title = "#38BDF8"
        text_lang = "#F0F6FC"
        text_desc = "#94A3B8"
        bar_bg = "#21262D"
        sub_text = "#7D8590"
    else:
        bg_card = "#FFFFFF"
        border_card = "#D0D7DE"
        inner_bg = "#F6F8FA"
        inner_border = "#D0D7DE"
        text_title = "#0969DA"
        text_lang = "#1F2328"
        text_desc = "#57606A"
        bar_bg = "#E1E4E8"
        sub_text = "#656D76"

    # Languages data
    # Python 65%, TypeScript 24%, JavaScript 6%, CSS 5%
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 520 205" width="520" height="205">
  <defs>
    <style>
      .mono-header {{
        font-family: 'SF Mono', 'Geist Mono', 'Fira Code', monospace;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 1.5px;
      }}
      .lang-title {{
        font-family: 'SF Mono', 'Geist Mono', monospace;
        font-size: 12px;
        font-weight: 700;
      }}
      .lang-sub {{
        font-family: -apple-system, 'Segoe UI', sans-serif;
        font-size: 11px;
      }}
      .pct-badge {{
        font-family: 'SF Mono', 'Geist Mono', monospace;
        font-size: 11px;
        font-weight: 700;
      }}
    </style>
  </defs>

  <!-- Container Box -->
  <rect width="520" height="205" rx="8" fill="{bg_card}" stroke="{border_card}" stroke-width="1" />

  <!-- Eyebrow Title -->
  <text x="24" y="28" class="mono-header" fill="{text_title}">
    STACK &amp; RUNTIMES // ARCHITECTURE
  </text>
  <text x="496" y="28" text-anchor="end" font-family="'SF Mono', monospace" font-size="10" fill="{sub_text}" letter-spacing="1">
    VOLUME RATIO
  </text>

  <!-- Progress Bar (Total width: 472px) -->
  <!-- Python: 65% = 306px, TS: 24% = 113px, JS: 6% = 28px, CSS: 5% = 25px -->
  <g transform="translate(24, 40)">
    <rect width="472" height="8" rx="4" fill="{bar_bg}" />
    <rect x="0" y="0" width="306" height="8" rx="4" fill="#38BDF8" />
    <rect x="308" y="0" width="112" height="8" rx="4" fill="#818CF8" />
    <rect x="422" y="0" width="26" height="8" rx="4" fill="#F59E0B" />
    <rect x="450" y="0" width="22" height="8" rx="4" fill="#C084FC" />
  </g>

  <!-- 4 Language Metric Rows (2x2 Grid) -->

  <!-- 1. Python -->
  <g transform="translate(24, 66)">
    <rect width="228" height="52" rx="6" fill="{inner_bg}" stroke="{inner_border}" stroke-width="1" />
    <circle cx="16" cy="26" r="5" fill="#38BDF8" />
    <text x="28" y="22" class="lang-title" fill="{text_lang}">Python</text>
    <text x="28" y="38" class="lang-sub" fill="{text_desc}">FastAPI • Scripts • Data APIs</text>
    <text x="214" y="25" text-anchor="end" class="pct-badge" fill="#38BDF8">65%</text>
  </g>

  <!-- 2. TypeScript -->
  <g transform="translate(268, 66)">
    <rect width="228" height="52" rx="6" fill="{inner_bg}" stroke="{inner_border}" stroke-width="1" />
    <circle cx="16" cy="26" r="5" fill="#818CF8" />
    <text x="28" y="22" class="lang-title" fill="{text_lang}">TypeScript</text>
    <text x="28" y="38" class="lang-sub" fill="{text_desc}">Strict Typing • Next.js • React</text>
    <text x="214" y="25" text-anchor="end" class="pct-badge" fill="#818CF8">24%</text>
  </g>

  <!-- 3. JavaScript -->
  <g transform="translate(24, 130)">
    <rect width="228" height="52" rx="6" fill="{inner_bg}" stroke="{inner_border}" stroke-width="1" />
    <circle cx="16" cy="26" r="5" fill="#F59E0B" />
    <text x="28" y="22" class="lang-title" fill="{text_lang}">JavaScript</text>
    <text x="28" y="38" class="lang-sub" fill="{text_desc}">Node.js • Full-Stack Web Tools</text>
    <text x="214" y="25" text-anchor="end" class="pct-badge" fill="#F59E0B">6%</text>
  </g>

  <!-- 4. CSS & Systems -->
  <g transform="translate(268, 130)">
    <rect width="228" height="52" rx="6" fill="{inner_bg}" stroke="{inner_border}" stroke-width="1" />
    <circle cx="16" cy="26" r="5" fill="#C084FC" />
    <text x="28" y="22" class="lang-title" fill="{text_lang}">Modern UI / CSS</text>
    <text x="28" y="38" class="lang-sub" fill="{text_desc}">Tailwind • Design Systems</text>
    <text x="214" y="25" text-anchor="end" class="pct-badge" fill="#C084FC">5%</text>
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

    # 1. Heatmaps
    dark_svg = generate_svg(total_str, months, cells, theme="dark")
    with open(os.path.join("assets", "github-contributions-dark.svg"), "w", encoding="utf-8") as f:
        f.write(dark_svg)

    light_svg = generate_svg(total_str, months, cells, theme="light")
    with open(os.path.join("assets", "github-contributions-light.svg"), "w", encoding="utf-8") as f:
        f.write(light_svg)

    with open(os.path.join("assets", "github-contributions.svg"), "w", encoding="utf-8") as f:
        f.write(dark_svg)

    # 2. Bespoke Stats Console Cards
    dark_stats = generate_stats_card_svg(total_str, theme="dark")
    with open(os.path.join("assets", "github-stats-dark.svg"), "w", encoding="utf-8") as f:
        f.write(dark_stats)

    light_stats = generate_stats_card_svg(total_str, theme="light")
    with open(os.path.join("assets", "github-stats-light.svg"), "w", encoding="utf-8") as f:
        f.write(light_stats)

    with open(os.path.join("assets", "github-stats.svg"), "w", encoding="utf-8") as f:
        f.write(dark_stats)

    # 3. Bespoke Languages & Architecture Cards
    dark_langs = generate_langs_card_svg(theme="dark")
    with open(os.path.join("assets", "github-langs-dark.svg"), "w", encoding="utf-8") as f:
        f.write(dark_langs)

    light_langs = generate_langs_card_svg(theme="light")
    with open(os.path.join("assets", "github-langs-light.svg"), "w", encoding="utf-8") as f:
        f.write(light_langs)

    with open(os.path.join("assets", "github-langs.svg"), "w", encoding="utf-8") as f:
        f.write(dark_langs)

    print("All premium SVGs generated and updated successfully!")

if __name__ == "__main__":
    main()
