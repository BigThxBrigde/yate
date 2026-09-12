# yate Language Server (LSP) Configuration

**English** · [中文](lsp.zh.md)

yate ships a small built-in
[LSP](https://microsoft.github.io/language-server-protocol/) client (no extra
dependencies): it spawns language server processes over stdio, speaks JSON-RPC
itself, and provides **autocompletion** and **diagnostics**. Language servers
themselves must be installed by the user; yate does not bundle any.

Client capabilities:

- **Autocomplete**: the popup appears automatically while typing (after the
  server's trigger characters, e.g. `.` in Python), or manually with
  `Ctrl+Space` at any time. Navigate with `↑`/`↓`, accept with `Tab` or
  `Enter`, close with `Esc`.
- **Diagnostics**: errors/warnings are underlined in the editor, the gutter
  shows `✖`/`▲` and tints line numbers; the diagnostic on the cursor line is
  echoed in the message bar and the status bar shows counts. `:diagnostics`
  lists all diagnostics of the current file.
- **Buffer completion fallback**: when the current file has no usable language
  server, completion falls back to words collected from all open buffers (and
  completes file paths when the prefix contains `/` or `~`).

Documents synchronize whole-text: on open, on save, and after an idle debounce
(0.25s) while typing. A server starts **lazily** when the first matching file
opens, one process per (server × project root). The status bar shows server
state: the server name when ready, `LSP…` while starting, `LSP ✖` on failure.

This file is a configuration cookbook for mainstream language servers;
section 16 of the manual is a short introduction.

---

## 1. How a language server is registered

Language servers register through **extensions**. Inside any extension's
`setup(api)` call:

```python
api.lsp.register_server(
    name="rust-analyzer",                       # name shown in the status bar
    command="rust-analyzer",                    # executable; "" means known-missing, fails lazily
    args=[],                                    # command-line arguments
    filetypes=["rs"],                           # list of extensions without the leading dot
    language_ids={"rs": "rust"},                # filetype -> LSP languageId (defaults to the filetype)
    root_markers=["Cargo.toml", ".git"],        # project-root probe files
    initialization_options=None,                # raw initializeOptions
    settings=None,                              # sent with didChangeConfiguration
    env=None,                                   # extra environment variables
)
```

Put the registration in `~/.yate/extensions/lsp.py` (or any `.py` referenced by
the yaterc `extensions` option); it takes effect at the next startup.
Registering the same name again replaces the old config and discards its cached
process and diagnostics.

Use `api.lsp.statuses()` to inspect `{name: state}`, and
`api.lsp.has_state(name, "ready")` to check whether a server is ready.

**Project root**: the open workspace root takes precedence; otherwise yate
walks up from the document's directory looking for the first existing file in
`root_markers`; if none is found, the document directory itself is used.

### 1.1 The simpler way: declare it in yaterc (auto-activation)

If you would rather not write an extension, declare servers directly in yaterc
(`~/.yate/yaterc` or a project-root `yaterc`) with the `language_servers`
option. It is a list of dictionaries with the same field names as the
`register_server` arguments above; once configured, **no manual command is
needed** -- the server starts automatically when a matching file opens:

```python
language_servers = [
    {
        "name": "rust-analyzer",
        "command": "rust-analyzer",
        "filetypes": ["rs"],                 # no leading dot; ".rs" is accepted too
        "language_ids": {"rs": "rust"},
        "root_markers": ["Cargo.toml", ".git"],
        # "args": [], "env": {...},
        # "initialization_options": {...}, "settings": {...},
    },
]
```

- `name` / `command` / `filetypes` are required and `command` must be
  non-empty; malformed entries are skipped and reported in the startup message
  bar while the remaining entries still register.
- The option registers **after** extensions load, so same-named entries replace
  extension registrations -- including the built-in Python server (use
  `"name": "python"` to customize its command).
- Configuration alone spawns nothing: unnamed buffers and non-matching files
  are completely unaffected; a later yaterc replaces the whole list.

Each `api.lsp.register_server(...)` call in the language recipes below can be
rewritten equivalently as such a dictionary.

---

## 2. Python (built-in)

`yate/extensions/python_lsp.py` ships with yate and auto-loads at startup
(regardless of the working directory); it registers a Python language server
for `.py` / `.pyi`. To skip it, set
`disabled_extensions = ["python_lsp"]` in yaterc (you can then declare your
own `"name": "python"` entry via `language_servers`). Install the server
yourself:

```powershell
pip install python-lsp-server     # provides pylsp
# or
npm install -g pyright            # provides pyright-langserver
pip install pyright               # alternative
```

Server discovery order:

1. The `YATE_PYTHON_LSP` environment variable: a full command line with
   shell-style quoting, e.g.
   `set YATE_PYTHON_LSP=C:\tools\pyright-langserver.cmd --stdio`.
   Set it to `0`/`off`/`false`/`none`/`no` to disable completely (registration
   stays but nothing ever starts).
2. `pyright-langserver` on `PATH` (started with `--stdio` appended).
3. `pylsp` on `PATH`.

When none of the three is available, no process starts and no error pops up;
opening a Python file shows `LSP ✖` in the status bar.

---

## 3. Rust

Install:

```bash
rustup component add rust-analyzer
# or download from https://github.com/rust-lang/rust-analyzer/releases
```

Register:

```python
api.lsp.register_server(
    name="rust-analyzer",
    command="rust-analyzer",
    filetypes=["rs"],
    language_ids={"rs": "rust"},
    root_markers=["Cargo.toml", ".git"],
)
```

---

## 4. TypeScript / JavaScript

Install:

```bash
npm install -g typescript typescript-language-server
```

Register:

```python
api.lsp.register_server(
    name="typescript",
    command="typescript-language-server",
    args=["--stdio"],
    filetypes=["ts", "tsx", "js", "jsx", "mjs", "cjs"],
    language_ids={
        "ts": "typescript",
        "tsx": "typescriptreact",
        "js": "javascript",
        "jsx": "javascriptreact",
        "mjs": "javascript",
        "cjs": "javascript",
    },
    root_markers=["package.json", "tsconfig.json", ".git"],
)
```

---

## 5. Go

Install:

```bash
go install golang.org/x/tools/gopls@latest
```

Register:

```python
api.lsp.register_server(
    name="gopls",
    command="gopls",
    args=["serve"],
    filetypes=["go"],
    language_ids={"go": "go"},
    root_markers=["go.mod", ".git"],
)
```

---

## 6. C / C++

Install:

```bash
# via your system package manager or download from
# https://github.com/clangd/clangd/releases
# Debian/Ubuntu: sudo apt install clangd
# macOS: brew install llvm
```

Register:

```python
api.lsp.register_server(
    name="clangd",
    command="clangd",
    args=["--background-index"],
    filetypes=["c", "cc", "cpp", "cxx", "h", "hh", "hpp", "hxx"],
    language_ids={
        "c": "c", "cc": "c",
        "cpp": "cpp", "cxx": "cpp",
        "h": "c", "hh": "c",
        "hpp": "cpp", "hxx": "cpp",
    },
    root_markers=["compile_commands.json", "compile_flags.txt", ".git"],
)
```

---

## 7. Bash / Shell

Install:

```bash
npm install -g bash-language-server
```

Register:

```python
api.lsp.register_server(
    name="bash-language-server",
    command="bash-language-server",
    args=["start"],
    filetypes=["sh", "bash", "zsh"],
    language_ids={"sh": "shellscript", "bash": "shellscript", "zsh": "shellscript"},
    root_markers=[".git"],
)
```

---

## 8. JSON

Install:

```bash
npm install -g vscode-langservers-extracted
# provides vscode-json-languageserver (plus html/css/eslint)
```

Register:

```python
api.lsp.register_server(
    name="json",
    command="vscode-json-language-server",
    args=["--stdio"],
    filetypes=["json", "jsonc"],
    language_ids={"json": "json", "jsonc": "json"},
    root_markers=["package.json", ".git"],
)
```

---

## 9. HTML / CSS

`vscode-langservers-extracted` also provides the HTML and CSS servers:

```python
api.lsp.register_server(
    name="html",
    command="vscode-html-language-server",
    args=["--stdio"],
    filetypes=["html", "htm"],
    language_ids={"html": "html", "htm": "html"},
    root_markers=["package.json", ".git"],
)

api.lsp.register_server(
    name="css",
    command="vscode-css-language-server",
    args=["--stdio"],
    filetypes=["css", "scss", "less"],
    language_ids={"css": "css", "scss": "scss", "less": "less"},
    root_markers=["package.json", ".git"],
)
```

---

## 10. Lua

Install:

```bash
# download from https://github.com/LuaLS/lua-language-server/releases
# or: brew install lua-language-server
```

Register:

```python
api.lsp.register_server(
    name="lua-language-server",
    command="lua-language-server",
    filetypes=["lua"],
    language_ids={"lua": "lua"},
    root_markers=[".luarc.json", ".git"],
)
```

---

## 11. One-shot script example

Save the following as `~/.yate/extensions/lsp.py` and comment out languages
you do not need:

```python
import shutil


def _has(cmd):
    return shutil.which(cmd) is not None


def setup(api):
    if _has("rust-analyzer"):
        api.lsp.register_server("rust-analyzer", command="rust-analyzer",
                                filetypes=["rs"], language_ids={"rs": "rust"},
                                root_markers=["Cargo.toml", ".git"])

    if _has("typescript-language-server"):
        api.lsp.register_server(
            "typescript", command="typescript-language-server",
            args=["--stdio"],
            filetypes=["ts", "tsx", "js", "jsx"],
            language_ids={"ts": "typescript", "tsx": "typescriptreact",
                          "js": "javascript", "jsx": "javascriptreact"},
            root_markers=["package.json", "tsconfig.json", ".git"],
        )

    if _has("gopls"):
        api.lsp.register_server("gopls", command="gopls", args=["serve"],
                                filetypes=["go"], language_ids={"go": "go"},
                                root_markers=["go.mod", ".git"])

    if _has("clangd"):
        api.lsp.register_server("clangd", command="clangd",
                                args=["--background-index"],
                                filetypes=["c", "cc", "cpp", "h", "hpp"],
                                language_ids={"c": "c", "cc": "c",
                                              "cpp": "cpp", "h": "c", "hpp": "cpp"},
                                root_markers=["compile_commands.json", ".git"])

    if _has("bash-language-server"):
        api.lsp.register_server("bash-language-server",
                                command="bash-language-server", args=["start"],
                                filetypes=["sh", "bash"],
                                language_ids={"sh": "shellscript",
                                              "bash": "shellscript"},
                                root_markers=[".git"])
```

`shutil.which` probes for executables, so missing servers are not registered
and the status bar never shows `LSP ✖`. If you prefer "known-missing but still
registered" (an explicit hint in the status bar), set `command` to `""`.

> Rather than writing an extension script, the servers above can also be
> declared directly with yaterc's `language_servers` list (see section 1.1):
> rewrite each `api.lsp.register_server(...)` call into a dictionary with the
> same field names; servers auto-activate when a matching file opens.

---

## 12. Troubleshooting

- **Status bar shows `LSP ✖`**: a server is registered for the file type but
  failed to start. Common causes: the executable is not on `PATH`, wrong
  command arguments, or initialization timed out (default 20 seconds).
- **No LSP text at all**: no server is registered for this file type, so
  completion falls back to buffer completion. Register one using the recipes
  above.
- **The popup never appears**: make sure the server has reached `ready`; some
  servers require configuration files at the project root (e.g.
  `tsconfig.json`, `pyproject.toml`) before offering full capabilities.
- **Disabling a language**: guard the registration with `shutil.which`, or
  simply do not register that language. To turn off the bundled Python server,
  use `disabled_extensions = ["python_lsp"]` in yaterc.
