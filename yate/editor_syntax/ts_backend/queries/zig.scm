; yate bundled tree-sitter highlights for Zig (tree-sitter-zig).
; Captures are mapped to SYNTAX_KINDS via DEFAULT_CAPTURE_MAP; unmapped
; captures (variables, punctuation) inherit the default foreground.
; Builtin functions (@import, @as, ...) land on the decorator capture via
; the leading @ and are recolored there.

; --- comments -------------------------------------------------------------
(comment) @comment

; --- strings & numbers ----------------------------------------------------
(string) @string
(escape_sequence) @string
(character) @string
(integer) @number
(float) @number

; --- constants ------------------------------------------------------------
[
  "true"
  "false"
  "null"
  "undefined"
] @constant

; --- keywords -------------------------------------------------------------
[
  "align" "allowzero" "and" "anyframe" "anytype" "asm" "async" "await"
  "break" "callconv" "catch" "comptime" "const" "continue" "defer" "else"
  "enum" "errdefer" "error" "export" "extern" "fn" "for" "if" "inline"
  "nosuspend" "opaque" "or" "orelse" "packed" "pub" "resume"
  "return" "linksection" "struct" "suspend" "switch" "test" "threadlocal"
  "try" "union" "usingnamespace" "var" "volatile" "while"
] @keyword

; --- types ----------------------------------------------------------------
(builtin_type) @type.builtin

; --- definitions & calls --------------------------------------------------
(function_declaration name: (identifier) @function)
(builtin_function) @function.builtin
