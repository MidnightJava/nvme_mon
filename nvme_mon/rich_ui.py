from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.color import Color, parse_rgb_hex
from rich.style import Style
import shutil
from datetime import datetime
import curses
import os

# Smooth block sequence (full + fractions)
FULL = "█"
FRACTIONS = ["", "▏", "▎", "▍", "▌", "▋", "▊", "▉"]
DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
TIME_FORMAT = "%H:%M:%S"

YELLOW_THRESHOLD = 60
RED_THRESHOLD = 70

RESULTS_SCOPE_MAP = {
    "top_5": {"text": "Top 5", "style": "bright_blue"},
    "all": {"text": "All", "style": "bright_blue"},
    "yellow": {"text": f"Temp >= {YELLOW_THRESHOLD}", "style": "yellow"},
    "red": {"text": f"Temp >= {RED_THRESHOLD}", "style": "bright_red"},
}

# Threshold coloring (percent)
def bar_color_for_value(temp):
    if temp < YELLOW_THRESHOLD:
        return "green"
    elif temp < RED_THRESHOLD:
        return "yellow"
    else:
        return "red"
    
def render_top_line_text(sort_key):
    return (Text("Temp | Count | Last Occurrence  (Sorting by ", style="bright_green") +
        Text(f"{sort_key})", style="bright_red") +
        Text(f"   Last updated: {datetime.now().strftime(TIME_FORMAT)}", style="gray50"))

def render_resulots_text(results_scope):
    return (Text("Showing ") +
        Text(f"{RESULTS_SCOPE_MAP[results_scope]["text"]}", style=f"{RESULTS_SCOPE_MAP[results_scope]["style"]}") +
        Text(" Results"))


def render_bar(label, value, last_date, dt_display, max_value, width):
    pct = value / max_value if max_value else 0
    val_text = f"{value:3.0f}"

    # Determine color by threshold
    color = bar_color_for_value(label)

    # Compute block counts
    total_blocks = max(0.2, pct * width)
    full = int(total_blocks)
    frac = int((total_blocks - full) * 8)

    bar = FULL * full + (FRACTIONS[frac] if frac > 0 else "")

    bar_text = Text()
    if len(bar) >= len(val_text):
        left_padding = (len(bar) - len(val_text)) // 2
        right_padding = len(bar) - len(val_text) - left_padding
        bar_text.append(bar[:right_padding], style=color)
        val_segment = Text(val_text, style=f"bold black on {color}")
        bar_text.append(val_segment)
        bar_text.append(bar[left_padding:], style=color)
    else:        
        # Bar too short: show value after bar
        val_segment = Text(val_text)
        bar_text.append(bar, style=color)
        bar_text.append(val_segment)

    # Label + bar
    line = Text()
    line.append(f"{label:<5} ")
    line.append(bar_text)
    if dt_display == "date":
        line.append(f"   {datetime.strftime(last_date, DATE_FORMAT)}", style="gray50")
    else:
        line.append(f"   {datetime.strftime(last_date, DATETIME_FORMAT)}", style="gray50")
    return line


def print_histogram(
    data,
    *,
    dt_display="date",
    sort_key="Temperature",
    results_scope="top_5",
    max_width=170,
    box=True,
    spacing=1,
    title="Histogram"
):
    console = Console(force_terminal=True, color_system="standard", legacy_windows=False, safe_box=False)

    # Auto terminal width
    term_width = shutil.get_terminal_size((80, 20)).columns
    width = min(max_width, term_width - 20)

    max_value = max(v["count"] for _, v in data.items()) if len(data.items()) else 0

    lines = []
    lines.append(render_top_line_text(sort_key))
    lines.append(Text(""))
    lines.append(render_resulots_text(results_scope))
    lines.append(Text(""))

    for label, value in data.items():
        line = render_bar(label, value["count"], value["last_date"],  dt_display, max_value, width)
        lines.append(line)
        # vertical spacing (empty lines)
        for _ in range(spacing):
            lines.append(Text(""))

    # Put inside box or print raw
    if box:
        console.print(Panel(Text("\n").join(lines), title=title))
    else:
        for l in lines:
            console.print(l)
    console.clear_live

def print_general_info(
    data,
    *,
    max_width=80
):
    console = Console(force_terminal=True, color_system="standard", legacy_windows=False, safe_box=True)

    line = Text(f"Device: ") + Text(data["Device"], style="bold blue on white") + Text(f"    Log Info: {data["Log Data"]}")
    console.print(Panel(line))

def print_disk_info(
    data,
    *,
    max_width=200,
    box=True,
    title="Histogram"
):
    console = Console(force_terminal=True, color_system="standard", legacy_windows=False, safe_box=False)

    # Auto terminal width
    term_width = shutil.get_terminal_size((80, 20)).columns
    width = min(max_width, term_width - 20)

    max_item_width = max([len(k) + len(str(v)) for k,v in data.items()])
    if width >= (max_item_width * 3):
        num_cols = 3
    elif width >= (max_item_width * 2):
        num_cols = 2
    else:
        num_cols = 1

    lines = []
    for k,v in data.items():
        text = Text(f"{k}: ") + Text(f"{v}", Style(color = Color.from_triplet(parse_rgb_hex("F5A818"))))
        text.align('left', width // num_cols, ' ')
        lines.append(text)

    
    new_lines = [Text("")]
    if num_cols == 3:
        for i in range(0, len(lines), 3):
            if i + 2 < len(lines):
                new_lines.append(lines[i] + lines[i+1] + lines[i+2])
            elif i + 1 < len(lines):
                new_lines.append(lines[i] + lines[i+1])
            else:
                new_lines.append(lines[i])
    elif num_cols == 2:
        for i in range(0, len(lines), 2):
            if i + 1 < len(lines):
                new_lines.append(lines[i] + lines[i+1])
            else:
                new_lines.append(lines[i])
    else:
        new_lines = lines

    new_lines.append(Text(""))
    
     # Put inside box or print raw
    if box:
        console.print(Panel(Text("\n").join(new_lines), title=title))
    else:
        for l in new_lines:
            console.print(l)


# ----------------- Example -----------------
if __name__ == "__main__":
    histogram_data = dict([
        (90, {"count":12, "last_date": datetime.today()}),
        (37, {"count": 6, "last_date": datetime.today()}),
        (53, {"count": 18, "last_date": datetime.today()}),
        (70, {"count": 9, "last_date": datetime.today()}),
        (65, {"count": 3, "last_date": datetime.today()}),
    ])

    print_histogram(
        histogram_data,
        max_width=40,
        box=True,
        spacing=1
    )
