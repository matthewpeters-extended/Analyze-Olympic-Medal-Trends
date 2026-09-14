"""Shared figure style for every chart in this project.

Colours come from a documented, colourblind checked categorical palette. Only the
first three slots are used anywhere in this repository, because those three are the
ones validated for every pair rather than only for neighbouring pairs:

    slot 1  blue    #2a78d6
    slot 2  orange  #eb6834
    slot 3  aqua    #1baf7a

Rules applied here, and worth keeping if you add a chart:

  * one y axis per chart, never two scales on one plot
  * a colour means an entity, never a rank, so a series keeps its colour everywhere
  * series are direct labelled as well as legended, so identity never rests on
    colour alone
  * grid and axes recede, marks do not
  * figures are written at 150 dpi on an opaque light surface, because they are
    embedded in a README that GitHub renders on both light and dark backgrounds
"""

from __future__ import annotations

import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SOFT = "#52514e"
INK_FAINT = "#8a8985"
GRID = "#e6e5e1"
BAND = "#f2f1ee"

BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
SERIES = (BLUE, ORANGE, AQUA)


def apply_style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.size": 11,
        "font.family": "sans-serif",
        "text.color": INK,
        "axes.labelcolor": INK_SOFT,
        "axes.edgecolor": GRID,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlecolor": INK,
        "axes.titlelocation": "left",
        "axes.titlepad": 14,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.color": INK_SOFT,
        "ytick.color": INK_SOFT,
        "xtick.labelcolor": INK_SOFT,
        "ytick.labelcolor": INK_SOFT,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "legend.frameon": False,
        "legend.fontsize": 10,
        "lines.linewidth": 2.0,
        "lines.solid_capstyle": "round",
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "savefig.dpi": 150,
        "savefig.bbox": "tight",
    })


def tidy(ax, ylabel: str = "", grid: bool = True) -> None:
    if grid:
        ax.yaxis.grid(True)
        ax.xaxis.grid(False)
        ax.set_axisbelow(True)
    if ylabel:
        ax.set_ylabel(ylabel)
    ax.tick_params(length=0)


def caption(fig, text: str, width: int = 110) -> None:
    """Source or method note under the plot.

    Wrapped, because savefig with a tight bounding box will widen the whole canvas
    to fit a long single line of text and quietly stretch the figure.
    """
    fig.text(0.0, -0.02, textwrap.fill(" ".join(text.split()), width),
             ha="left", va="top", fontsize=9, color=INK_FAINT, linespacing=1.4)


def label_end(ax, x, y, text: str, color: str, dx: float = 1.5, dy: float = 0.0) -> None:
    """Direct label at the right hand end of a series."""
    ax.annotate(
        text, xy=(x, y), xytext=(x + dx, y + dy), textcoords="data",
        color=color, fontsize=10, fontweight="bold", va="center", ha="left",
        annotation_clip=False,
    )
