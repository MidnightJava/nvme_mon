from rich.console import Console
from rich.panel import Panel
from rich.text import Text
import shutil
from datetime import datetime

# Smooth block sequence (full + fractions)
FULL = "█"
FRACTIONS = ["", "▏", "▎", "▍", "▌", "▋", "▊", "▉"]
DATE_FORMAT = "%Y-%m-%d"

# Threshold coloring (percent)
def bar_color_for_value(temp):
    if temp < 50:
        return "green"
    elif temp < 65:
        return "yellow"
    else:
        return "red"


def render_bar(label, value, last_date, max_value, width):
    pct = value / max_value if max_value else 0
    val_text = f"{value:3.0f}"

    # Determine color by threshold
    color = bar_color_for_value(label)

    # Compute block counts
    total_blocks = max(0.2, pct * width)
    full = int(total_blocks)
    frac = int((total_blocks - full) * 8)

    bar = FULL * full + (FRACTIONS[frac] if frac > 0 else "")

    # Embed percentage text INSIDE the bar
    # To do this: replace beginning of bar text with percentage string
    # but color its background to match bar color
    # Pad/center the percentage in the bar
    bar_text = Text()
    if len(bar) >= len(val_text):
        left_padding = (len(bar) - len(val_text)) // 2
        right_padding = len(bar) - len(val_text) - left_padding
        bar_text.append(bar[:right_padding], style=color)
        val_segment = Text(val_text, style=f"bright_white on {color}")
        bar_text.append(val_segment)
        bar_text.append(bar[left_padding:], style=color)
    else:        
        # Bar too short: show percentage after bar
        val_segment = Text(val_text)
        bar_text.append(bar, style=color)
        bar_text.append(val_segment)

    # Label + bar
    line = Text()
    line.append(f"{label:<5} ")
    line.append(bar_text)
    line.append(f"   {datetime.strftime(last_date.date(), DATE_FORMAT)}", style="gray50")
    return line


def print_histogram(
    data,
    *,
    max_width=50,
    box=True,
    spacing=1,
    title="Histogram"
):
    console = Console(force_terminal=True, color_system="standard", legacy_windows=False, safe_box=False)

    # Auto terminal width
    term_width = shutil.get_terminal_size((80, 20)).columns
    width = min(max_width, term_width - 20)

    max_value = max(v["count"] for _, v in data.items())

    lines = []
    lines.append(Text("Temp | Count | Last Occurrence", style="bright_green"))
    lines.append(Text(""))

    for label, value in data.items():
        line = render_bar(label, value["count"], value["last_date"],  max_value, width)
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

def print_temp_info(
    data,
    *,
    max_width=50,
    box=True,
    spacing=1,
    title="Histogram"
):
    console = Console(force_terminal=True, color_system="standard", legacy_windows=False, safe_box=False)

    # Auto terminal width
    term_width = shutil.get_terminal_size((80, 20)).columns
    width = min(max_width, term_width - 20)

    lines = []
    for k,v in data.items():
        lines.append(Text(f"{k}: {v}"))
    lines.append(Text(""))

     # Put inside box or print raw
    if box:
        console.print(Panel(Text("\n").join(lines), title=title))
    else:
        for l in lines:
            console.print(l)

def print_health_info(
    data,
    *,
    max_width=50,
    box=True,
    spacing=1,
    title="Histogram"
):
    console = Console(force_terminal=True, color_system="standard", legacy_windows=False, safe_box=False)

    # Auto terminal width
    term_width = shutil.get_terminal_size((80, 20)).columns
    width = min(max_width, term_width - 20)

    lines = []
    for k,v in data.items():
        lines.append(Text(f"{k}: {v}"))
    
     # Put inside box or print raw
    if box:
        console.print(Panel(Text("\n").join(lines), title=title))
    else:
        for l in lines:
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
