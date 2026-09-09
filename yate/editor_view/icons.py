"""Nerd Font glyphs used throughout the UI.

Requires a Nerd Font patched terminal (https://www.nerdfonts.com/).
Each constant is a single private-use-area codepoint.
"""

# --- files & folders (nf-fa / nf-seti)
FOLDER = "\uf07b"          # 
FOLDER_OPEN = "\uf07c"     # 
FILE = "\uf15b"            # 
FILE_TEXT = "\uf0f6"       # 
CHEVRON_RIGHT = "\uf054"   # 
CHEVRON_DOWN = "\uf078"    # 
DOT = "\uf111"             #  (modified marker)

# --- file type icons (nf-dev / nf-seti)
FILE_ICONS = {
    "py": "\ue73c",        #  python
    "pyw": "\ue73c",
    "js": "\ue781",        #  nodejs
    "ts": "\ue628",        #  typescript
    "tsx": "\ue628",
    "jsx": "\ue7ad",       # react
    "json": "\ue60b",      # 
    "html": "\uf13b",      # 
    "htm": "\uf13b",
    "css": "\ue749",       #  css3
    "scss": "\ue749",
    "md": "\uf48a",        #  markdown
    "rst": "\uf48a",
    "txt": "\uf0f6",       # 
    "toml": "\ue60b",
    "yaml": "\ue60b",
    "yml": "\ue60b",
    "xml": "\uf72d",       # 
    "sh": "\uf489",        #  terminal
    "bash": "\uf489",
    "zsh": "\uf489",
    "bat": "\uf17a",       #  windows
    "cmd": "\uf17a",
    "ps1": "\uf489",
    "c": "\ue61e",         #  c
    "h": "\ue61d",         # 
    "cpp": "\ue61d",
    "hpp": "\ue61d",
    "cc": "\ue61d",
    "rs": "\ue7a8",        #  rust
    "go": "\ue627",        #  go
    "java": "\ue738",      #  java
    "rb": "\ue21e",        #  ruby
    "php": "\ue608",       #  php
    "lua": "\ue620",       #  lua
    "sql": "\uf1c0",       # 
    "csv": "\uf1c3",       # 
    "git": "\ue702",       #  git
    "vim": "\ue62b",       #  vim
    "dockerfile": "\uf308",  #  docker
    "lock": "\uf023",      # 
    "log": "\uf18c",       # 
}

# --- UI symbols (nf-fa / powerline)
SEARCH = "\uf002"         # 
TERMINAL = "\uf120"       # 
SAVE = "\uf0c7"           # 
GEAR = "\uf013"           # 
KEYBOARD = "\uf11c"       # 
CODE_FORK = "\uf126"      # 
CHECK = "\uf00c"          # 
TIMES = "\uf00d"          # 
BAN = "\uf05e"            # 
ARROW_RIGHT = "\uf061"    # 
TRIANGLE_RIGHT = "\ue0b0"  #  (powerline)
TRIANGLE_LEFT = "\ue0b2"   # 
LINE_NUMBERS = "\uf0cb"   # 
BRANCH = "\ue0a0"         #  (powerline branch)
LIGHTNING = "\uf0e7"      # 
PENCIL = "\uf303"         # 
EYE = "\uf06e"            # 
CLOCK = "\uf017"          # 
PLUG = "\uf1e6"           #  (extensions)


def icon_for_path(name: str, is_dir: bool, expanded: bool = False) -> str:
    """Return the appropriate glyph for a tree entry."""
    if is_dir:
        return FOLDER_OPEN if expanded else FOLDER
    suffix = name.rsplit(".", 1)[-1].lower() if "." in name else name.lower()
    return FILE_ICONS.get(suffix, FILE_TEXT)
