"""Scenario registry: the 25 screenshot states and their pilot drivers.

Each scenario is a frozen record (bilingual title and description -- the
Chinese strings are gallery content, not comments) plus an async driver that
builds its app, presses the evidence-backed key sequence and saves one SVG.
Key sequences follow the smoke-scenario precedents catalogued in
``.trae/documents/readme-screenshots-plans/overview.md`` (research item 4):

- ex command line: :func:`run_command` (F5 entry, command without ``:``);
- quick open: ``app.editor.execute_action("quick_open")``;
- command palette: ``alt+shift+p``; which-key: ``f9``;
- screensaver: ``alt+shift+s`` (intercepted by name in ``Editor.handle_key``);
- terminal: ``:term``; shell overlay: ``f2``; hex: binary open; game:
  the ``game`` command registered by the bundled ``games.lua`` extension;
- manual: ``f8``.

The theme is process-global state, so the theme scenario restores the
default in a ``finally`` block to keep later scenarios deterministic.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from textual.widget import Widget
from tools.screenshots.cli_reports import (
    diag_report_svg,
    smoke_report_svg,
)
from tools.screenshots.driver import DriverFn, YateApp, make_app, save_svg
from tools.smoke_test.scenarios._base import run_command, type_text, wait_until
from yate.config import ScreenSaverConfig, YateConfig
from yate.editor_components import theme as yate_theme
from yate.editor_components.canvas_screen import CanvasScreen
from yate.editor_components.file_manager.screen import (
    FileManagerScreen,
    PreviewLog,
)
from yate.editor_components.screensaver import ScreensaverScreen
from yate.editor_components.manual import MarkdownDocScreen
from yate.editor_components.theme import DEFAULT_THEME

__all__ = ["SCENARIOS", "Scenario"]

#: Frame size shared by every scenario (the overview fixes 100x30).
_SIZE: tuple[int, int] = (100, 30)


async def _require(  # noqa: Any - mirrors the shared wait_until signature
    pilot: Any,
    predicate: Callable[[], bool],
    *,
    what: str,
    timeout: float = 5.0,
) -> None:
    """Fail the scenario loudly when its awaited state never arrives.

    :func:`wait_until` returns ``False`` on timeout instead of raising, so
    its result must be consumed: saving a screenshot of a state that was
    never reached would publish the wrong image as the feature's evidence.
    """
    if not await wait_until(pilot, predicate, timeout=timeout):
        raise RuntimeError(f"state not reached: {what}")


def _highlight_landed(app: YateApp) -> bool:
    """True when the active view's syntax tokens are current in the DOM.

    Highlight tokens land on a background worker after the first frame;
    :meth:`EditorView.highlight_probe` exposes the landing state.
    """
    view = app.editor.panes.active_view
    if view is None:
        return False
    probe = view.highlight_probe()
    return (
        probe.tokens is not None
        and probe.doc is view.doc
        and probe.version == view.doc.buffer.content_version
    )


def _preview_text(pane: PreviewLog) -> str:
    """Extract the rendered text of a preview ``RichLog`` pane."""
    return "\n".join(strip.text for strip in pane.lines)


def _file_manager_ready(app: YateApp) -> bool:
    """True once the listing has rows and the preview shows real content.

    The preview pane walks through "(empty directory)" (no cursor yet) and
    "loading…" (worker in flight) before the cursor entry's content lands;
    the frame is only allowed once that final state is reached.
    """
    if not isinstance(app.screen, FileManagerScreen):
        return False
    listing = app.screen.query_one("#file-manager-list", Widget)
    preview = app.screen.query_one("#file-manager-preview", PreviewLog)
    text = _preview_text(preview)
    return (
        bool(listing.children)
        and bool(text)
        and "loading" not in text
        and "empty directory" not in text
    )


def _screensaver_full(app: YateApp) -> bool:
    """True when the screensaver screen holds at least eight walkers."""
    screen = app.screen
    return isinstance(screen, ScreensaverScreen) and len(screen.walkers) >= 8


@dataclass(frozen=True)
class Scenario:
    """One screenshot state: registry metadata plus its async driver."""

    name: str
    title_en: str
    title_zh: str
    desc_en: str
    desc_zh: str
    size: tuple[int, int]
    driver: DriverFn
    #: True for the three slow subprocess-report scenarios (``--skip-cli``).
    skip_cli: bool = False


# --------------------------------------------------------------------------
# driver bodies
# --------------------------------------------------------------------------


async def _welcome_screen(svg_path: Path, fixtures: Path) -> None:
    """Empty untitled buffer startup: the welcome screen."""
    app = make_app()
    async with app.run_test(size=_SIZE) as pilot:
        await pilot.pause()
        save_svg(app, svg_path)


async def _layout_explorer(svg_path: Path, fixtures: Path) -> None:
    """Directory startup (browse mode, explorer visible) with a file opened.

    Syntax tokens land on a background worker; the driver waits for them
    so the editor pane shows the highlighted buffer.
    """
    app = make_app(target=fixtures)
    async with app.run_test(size=_SIZE) as pilot:
        await pilot.pause()
        await run_command(pilot, "e sample.py")
        await pilot.pause()
        await _require(
            pilot, lambda: _highlight_landed(app), what="syntax tokens"
        )
        save_svg(app, svg_path)


async def _keymap_vsc(svg_path: Path, fixtures: Path) -> None:
    """Default vsc keymap; the status bar shows the VSC chip."""
    app = make_app(target=fixtures / "sample.py")
    async with app.run_test(size=_SIZE) as pilot:
        await pilot.pause()
        save_svg(app, svg_path)


async def _keymap_vim(svg_path: Path, fixtures: Path) -> None:
    """Vim keymap startup with the ``:`` ex command line open."""
    app = make_app(target=fixtures / "sample.py", keymap="vim")
    async with app.run_test(size=_SIZE) as pilot:
        await pilot.pause()
        await pilot.press(":")
        await type_text(pilot, "w")
        save_svg(app, svg_path)


async def _syntax_highlighting(svg_path: Path, fixtures: Path) -> None:
    """A Python file open: tree-sitter syntax highlighting.

    Tokens land on a background worker after the first frame; the driver
    waits for them so the frame shows the colored buffer, not plain text.
    """
    app = make_app(target=fixtures / "sample.py")
    async with app.run_test(size=_SIZE) as pilot:
        await pilot.pause()
        await _require(
            pilot, lambda: _highlight_landed(app), what="syntax tokens"
        )
        save_svg(app, svg_path)


async def _theme_onelight(svg_path: Path, fixtures: Path) -> None:
    """``:set theme=onelight`` switches to the light theme.

    The yate theme is process-global; the ``finally`` restores the default
    so later scenarios in the same process keep the mocha palette.
    """
    app = make_app(target=fixtures / "sample.py")
    try:
        async with app.run_test(size=_SIZE) as pilot:
            await pilot.pause()
            await run_command(pilot, "set theme=onelight")
            await pilot.pause()
            save_svg(app, svg_path)
    finally:
        yate_theme.set_theme(DEFAULT_THEME)


async def _quick_open(svg_path: Path, fixtures: Path) -> None:
    """The fuzzy file finder overlay (quick open action)."""
    app = make_app(target=fixtures / "sample.py")
    async with app.run_test(size=_SIZE) as pilot:
        await pilot.pause()
        app.editor.execute_action("quick_open")
        await _require(
            pilot,
            lambda: len(app.screen_stack) == 2,
            what="quick open overlay",
        )
        save_svg(app, svg_path)


async def _command_palette(svg_path: Path, fixtures: Path) -> None:
    """The command palette overlay (``alt+shift+p``)."""
    app = make_app(target=fixtures / "sample.py")
    async with app.run_test(size=_SIZE) as pilot:
        await pilot.pause()
        await pilot.press("alt+shift+p")
        await _require(
            pilot,
            lambda: len(app.screen_stack) == 2,
            what="command palette overlay",
        )
        save_svg(app, svg_path)


async def _tabs(svg_path: Path, fixtures: Path) -> None:
    """Three files opened in sequence: the multi-buffer tab bar."""
    app = make_app(target=fixtures / "a.txt")
    async with app.run_test(size=_SIZE) as pilot:
        await pilot.pause()
        await run_command(pilot, "e b.txt")
        await run_command(pilot, "e c.txt")
        await pilot.pause()
        save_svg(app, svg_path)


async def _split_panes(svg_path: Path, fixtures: Path) -> None:
    """``:vsplit`` plus ``:split``: the pane tree with three leaves."""
    app = make_app(target=fixtures / "sample.py")
    async with app.run_test(size=_SIZE) as pilot:
        await pilot.pause()
        await run_command(pilot, "vsplit")
        await run_command(pilot, "split")
        await pilot.pause()
        save_svg(app, svg_path)


async def _find_replace(svg_path: Path, fixtures: Path) -> None:
    """``ctrl+f`` opens the find mode with a query typed in."""
    app = make_app(target=fixtures / "sample.py")
    async with app.run_test(size=_SIZE) as pilot:
        await pilot.pause()
        await pilot.press("ctrl+f")
        await type_text(pilot, "greet")
        save_svg(app, svg_path)


async def _shell_overlay(svg_path: Path, fixtures: Path) -> None:
    """``f2`` shell command overlay showing a real ``python --version``."""
    app = make_app(target=fixtures / "sample.py")
    async with app.run_test(size=_SIZE) as pilot:
        await pilot.pause()
        await pilot.press("f2")
        await type_text(pilot, "python --version")
        await pilot.press("enter")
        await _require(
            pilot,
            lambda: len(app.screen_stack) == 2,
            what="shell output overlay",
        )
        await pilot.pause()
        save_svg(app, svg_path)


async def _integrated_terminal(svg_path: Path, fixtures: Path) -> None:
    """``:term`` opens the bottom terminal dock (real PTY shell)."""
    app = make_app(target=fixtures / "sample.py")
    async with app.run_test(size=_SIZE) as pilot:
        await pilot.pause()
        await run_command(pilot, "term")
        panel = app.editor.terminal_panel
        await _require(pilot, lambda: panel.display, what="terminal panel")
        await pilot.pause(0.5)
        save_svg(app, svg_path)


async def _extensions(svg_path: Path, fixtures: Path) -> None:
    """Default startup with the bundled extensions loaded (status bar)."""
    app = make_app(target=fixtures / "sample.py")
    async with app.run_test(size=_SIZE) as pilot:
        await pilot.pause()
        save_svg(app, svg_path)


async def _lsp_completion(svg_path: Path, fixtures: Path) -> None:
    """``ctrl+space`` completion popup over a Python buffer.

    The cursor moves to an empty line of ``sample.py`` and types ``gr``;
    the popup lists the Python identifiers from the buffer (Greeter,
    greet, greeting).  The bundled ``python_lsp`` extension is disabled so
    the run actually exercises the buffer fallback source, honestly
    labeled in the gallery.  Syntax tokens must land before saving so the
    buffer itself is highlighted.
    """
    config = YateConfig(disabled_extensions=["python_lsp"])
    app = make_app(target=fixtures / "sample.py", config=config)
    async with app.run_test(size=_SIZE) as pilot:
        await pilot.pause()
        await pilot.press("down")
        await type_text(pilot, "gr")
        await pilot.press("ctrl+space")
        popup = app.editor.completion_popup
        await _require(pilot, lambda: popup.is_open, what="completion popup")
        await _require(
            pilot, lambda: _highlight_landed(app), what="syntax tokens"
        )
        save_svg(app, svg_path)


async def _screensaver(svg_path: Path, fixtures: Path) -> None:
    """``alt+shift+s`` screensaver: the full roster fills the screen.

    The full character roster walks at once and the spawn window is
    tightened to ``dist_bounds=(0.05, 0.15)`` of the journey (~0.5-1.7s
    between spawns on a 100-column screen); the frame is saved once at
    least eight sprites are on screen.  The sampled walk animation itself
    stays non-deterministic (declared in the gallery Report note).
    """
    config = YateConfig(
        screen_saver=ScreenSaverConfig(
            enable=True,
            interval=0,
            dist_lower_bound=0.05,
            dist_upper_bound=0.15,
        )
    )
    app = make_app(config=config)
    async with app.run_test(size=_SIZE) as pilot:
        await pilot.pause()
        await pilot.press("alt+shift+s")
        await _require(
            pilot,
            lambda: len(app.screen_stack) == 2,
            what="screensaver screen",
        )
        await _require(
            pilot,
            lambda: _screensaver_full(app),
            what="screensaver walkers (>=8)",
            timeout=45.0,
        )
        await pilot.pause(0.5)
        save_svg(app, svg_path)


async def _manual(svg_path: Path, fixtures: Path) -> None:
    """``f8`` opens the in-app bilingual manual (markdown doc screen)."""
    app = make_app(target=fixtures / "sample.py")
    async with app.run_test(size=_SIZE) as pilot:
        await pilot.pause()
        await pilot.press("f8")
        await _require(
            pilot,
            lambda: len(app.screen_stack) == 2
            and isinstance(app.screen, MarkdownDocScreen),
            what="manual screen",
        )
        await pilot.pause(0.5)
        save_svg(app, svg_path)


async def _game_snake(svg_path: Path, fixtures: Path) -> None:
    """``:game snake`` runs the Lua extension game on a canvas screen."""
    app = make_app(target=fixtures / "sample.py")
    async with app.run_test(size=_SIZE) as pilot:
        await pilot.pause()
        await run_command(pilot, "game snake")
        await _require(
            pilot,
            lambda: len(app.screen_stack) == 2
            and isinstance(app.screen, CanvasScreen),
            what="game canvas screen",
        )
        await pilot.pause(0.5)
        save_svg(app, svg_path)


async def _file_manager(svg_path: Path, fixtures: Path) -> None:
    """``filemanager_dir=`` startup form: the fullscreen file manager.

    Listing rows mount through a ``call_after_refresh`` retry, the cursor
    lands on the first entry via ``_restore_index``, and the preview pane
    walks through "loading…" before the entry content lands; the driver
    waits for that final state so the frame shows the populated listing
    and preview.  No key is pressed: a keypress here races the row mount
    and lands on a different entry between runs.
    """
    app = make_app(file_manager_dir=fixtures)
    async with app.run_test(size=_SIZE) as pilot:
        await pilot.pause()
        await _require(
            pilot,
            lambda: len(app.screen_stack) == 2,
            what="file manager screen",
        )
        await _require(
            pilot,
            lambda: _file_manager_ready(app),
            what="file manager listing and preview",
            timeout=10.0,
        )
        save_svg(app, svg_path)


async def _hex_view(svg_path: Path, fixtures: Path) -> None:
    """``hex_file=`` startup form: the binary file in the hex dump view."""
    app = make_app(hex_file=fixtures / "thing.bin")
    async with app.run_test(size=_SIZE) as pilot:
        await pilot.pause()
        await _require(
            pilot,
            lambda: len(app.screen_stack) == 2,
            what="hex view screen",
        )
        save_svg(app, svg_path)


async def _diff_view(svg_path: Path, fixtures: Path) -> None:
    """``diff_files=`` startup form: the side-by-side diff overlay."""
    app = make_app(
        diff_files=[fixtures / "left.txt", fixtures / "right.txt"]
    )
    async with app.run_test(size=_SIZE) as pilot:
        await pilot.pause()
        await _require(
            pilot,
            lambda: len(app.screen_stack) == 2,
            what="diff view screen",
        )
        save_svg(app, svg_path)


async def _which_key(svg_path: Path, fixtures: Path) -> None:
    """``f9`` pins the full which-key keymap sheet.

    The sheet opens with a staggered row animation; the extra settle pause
    lets it finish so the captured frame is reproducible.
    """
    app = make_app(target=fixtures / "sample.py")
    async with app.run_test(size=_SIZE) as pilot:
        await pilot.pause()
        await pilot.press("f9")
        await pilot.pause(1.5)
        save_svg(app, svg_path)


async def _smoke_report(svg_path: Path, fixtures: Path) -> None:
    """Real ``--tag view`` smoke run; ANSI output re-rendered via Rich."""
    svg_path.write_text(smoke_report_svg(), encoding="utf-8")


async def _diag_report(svg_path: Path, fixtures: Path) -> None:
    """Real ``yate --diag`` run; ANSI output re-rendered via Rich."""
    svg_path.write_text(diag_report_svg(), encoding="utf-8")


# --------------------------------------------------------------------------
# registry (overview scenario order 1-25)
# --------------------------------------------------------------------------

SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        name="welcome-screen",
        title_en="Welcome screen",
        title_zh="欢迎界面",
        desc_en="Empty untitled buffer startup showing the welcome screen.",
        desc_zh="空缓冲区启动，显示欢迎界面。",
        size=_SIZE,
        driver=_welcome_screen,
    ),
    Scenario(
        name="layout-explorer",
        title_en="VS Code-style layout",
        title_zh="VS Code 风格布局",
        desc_en=(
            "Directory startup in browse mode with a file opened: explorer, "
            "tab bar, editor and status bar."
        ),
        desc_zh="目录启动（浏览模式）并打开文件：资源管理器、标签栏、编辑器与状态栏。",
        size=_SIZE,
        driver=_layout_explorer,
    ),
    Scenario(
        name="keymap-vsc",
        title_en="VSC keymap",
        title_zh="VSC 键位方案",
        desc_en="Default vsc keymap; the status bar shows the VSC chip.",
        desc_zh="默认 vsc 键位方案，状态栏显示 VSC 标识。",
        size=_SIZE,
        driver=_keymap_vsc,
    ),
    Scenario(
        name="keymap-vim",
        title_en="Vim keymap",
        title_zh="Vim 键位方案",
        desc_en="Vim keymap startup with the ``:`` ex command line open.",
        desc_zh="Vim 键位方案启动，``:`` 命令行处于打开状态。",
        size=_SIZE,
        driver=_keymap_vim,
    ),
    Scenario(
        name="syntax-highlighting",
        title_en="Syntax highlighting",
        title_zh="语法高亮",
        desc_en="A Python file open with tree-sitter syntax highlighting.",
        desc_zh="打开 Python 文件，展示 tree-sitter 语法高亮。",
        size=_SIZE,
        driver=_syntax_highlighting,
    ),
    Scenario(
        name="theme-onelight",
        title_en="One Light theme",
        title_zh="One Light 主题",
        desc_en="``:set theme=onelight`` switches to the light palette.",
        desc_zh="执行 ``:set theme=onelight`` 切换到浅色主题。",
        size=_SIZE,
        driver=_theme_onelight,
    ),
    Scenario(
        name="quick-open",
        title_en="Quick open (fuzzy finding)",
        title_zh="快速打开（模糊查找）",
        desc_en="The fuzzy file finder overlay over the editor.",
        desc_zh="编辑器上方的模糊文件查找浮层。",
        size=_SIZE,
        driver=_quick_open,
    ),
    Scenario(
        name="command-palette",
        title_en="Command palette",
        title_zh="命令面板",
        desc_en="The command palette overlay (``alt+shift+p``).",
        desc_zh="命令面板浮层（``alt+shift+p``）。",
        size=_SIZE,
        driver=_command_palette,
    ),
    Scenario(
        name="tabs",
        title_en="Multi-buffer tabs",
        title_zh="多缓冲区标签页",
        desc_en="Three files opened in sequence: the tab bar at work.",
        desc_zh="依次打开三个文件，展示标签栏。",
        size=_SIZE,
        driver=_tabs,
    ),
    Scenario(
        name="split-panes",
        title_en="Split panes",
        title_zh="窗格拆分",
        desc_en="``:vsplit`` plus ``:split``: a pane tree with three leaves.",
        desc_zh="执行 ``:vsplit`` 与 ``:split``，形成三叶窗格树。",
        size=_SIZE,
        driver=_split_panes,
    ),
    Scenario(
        name="find-replace",
        title_en="Find & replace",
        title_zh="查找与替换",
        desc_en="``ctrl+f`` find mode with a query typed in.",
        desc_zh="按 ``ctrl+f`` 进入查找模式并输入关键词。",
        size=_SIZE,
        driver=_find_replace,
    ),
    Scenario(
        name="shell-overlay",
        title_en="Shell commands",
        title_zh="Shell 命令",
        desc_en="``f2`` shell overlay showing a real ``python --version`` run.",
        desc_zh="按 ``f2`` 打开 shell 浮层，真实运行 ``python --version``。",
        size=_SIZE,
        driver=_shell_overlay,
    ),
    Scenario(
        name="integrated-terminal",
        title_en="Integrated terminal",
        title_zh="集成终端",
        desc_en="``:term`` opens the bottom terminal dock (real PTY shell).",
        desc_zh="执行 ``:term`` 打开底部终端停靠区（真实 PTY shell）。",
        size=_SIZE,
        driver=_integrated_terminal,
    ),
    Scenario(
        name="extensions",
        title_en="Python extensions",
        title_zh="Python 扩展",
        desc_en=(
            "Default startup with the bundled extensions loaded; the status "
            "bar lists the extension segment."
        ),
        desc_zh="默认启动并加载内置扩展，状态栏显示扩展段。",
        size=_SIZE,
        driver=_extensions,
    ),
    Scenario(
        name="lsp-completion",
        title_en="LSP support / completion",
        title_zh="LSP 支持与补全",
        desc_en=(
            "``ctrl+space`` completion popup over a Python buffer; without "
            "a language server this is the buffer-words fallback source."
        ),
        desc_zh="在 Python 缓冲区按 ``ctrl+space`` 弹出补全框；无语言服务器时为缓冲区单词回退来源。",
        size=_SIZE,
        driver=_lsp_completion,
    ),
    Scenario(
        name="screensaver",
        title_en="Screensaver mode",
        title_zh="屏保模式",
        desc_en=(
            "``alt+shift+s`` screensaver: the full character roster fills "
            "the screen."
        ),
        desc_zh="按 ``alt+shift+s`` 进入屏保，全角色花名册精灵铺满屏幕。",
        size=_SIZE,
        driver=_screensaver,
    ),
    Scenario(
        name="manual",
        title_en="In-app manual",
        title_zh="应用内手册",
        desc_en="``f8`` opens the bilingual manual (markdown doc screen).",
        desc_zh="按 ``f8`` 打开双语手册（markdown 文档屏）。",
        size=_SIZE,
        driver=_manual,
    ),
    Scenario(
        name="game-snake",
        title_en="Lua extension game",
        title_zh="Lua 扩展游戏",
        desc_en="``:game snake`` runs the bundled games.lua extension.",
        desc_zh="执行 ``:game snake`` 运行内置 games.lua 扩展。",
        size=_SIZE,
        driver=_game_snake,
    ),
    Scenario(
        name="file-manager",
        title_en="File manager",
        title_zh="文件管理器",
        desc_en=(
            "``filemanager_dir=`` startup form: the fullscreen manager "
            "with the listing and the preview pane populated."
        ),
        desc_zh="``filemanager_dir=`` 启动形态：全屏文件管理器，列表与预览均已填充。",
        size=_SIZE,
        driver=_file_manager,
    ),
    Scenario(
        name="hex-view",
        title_en="Hex view",
        title_zh="十六进制视图",
        desc_en="``hex_file=`` startup form: a binary file in the hex dump.",
        desc_zh="``hex_file=`` 启动形态：二进制文件的十六进制转储。",
        size=_SIZE,
        driver=_hex_view,
    ),
    Scenario(
        name="diff-view",
        title_en="Diff view",
        title_zh="差异视图",
        desc_en="``diff_files=`` startup form: side-by-side diff overlay.",
        desc_zh="``diff_files=`` 启动形态：并排差异对比浮层。",
        size=_SIZE,
        driver=_diff_view,
    ),
    Scenario(
        name="which-key",
        title_en="Which-key sheet",
        title_zh="Which-key 键位表",
        desc_en="``f9`` pins the full keymap sheet for the active keymap.",
        desc_zh="按 ``f9`` 固定显示当前键位方案的完整键位表。",
        size=_SIZE,
        driver=_which_key,
    ),
    Scenario(
        name="smoke-report",
        title_en="Smoke test report",
        title_zh="冒烟测试报告",
        desc_en=(
            "Real ``tools.smoke_test run --tag view`` output, re-rendered "
            "from ANSI through Rich."
        ),
        desc_zh="真实运行 ``tools.smoke_test run --tag view``，ANSI 输出经 Rich 重渲染。",
        size=_SIZE,
        driver=_smoke_report,
        skip_cli=True,
    ),
    Scenario(
        name="diag-report",
        title_en="Diagnostics report",
        title_zh="诊断报告",
        desc_en="Real ``yate --diag`` environment and config report.",
        desc_zh="真实运行 ``yate --diag`` 的环境与配置报告。",
        size=_SIZE,
        driver=_diag_report,
        skip_cli=True,
    ),
)
