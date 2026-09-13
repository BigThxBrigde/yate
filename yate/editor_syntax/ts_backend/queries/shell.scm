; yate bundled tree-sitter highlights for Shell (tree-sitter-bash).
; Captures are mapped to SYNTAX_KINDS via DEFAULT_CAPTURE_MAP; unmapped
; captures (punctuation, file descriptors, ...) inherit the default
; foreground.

; --- comments -------------------------------------------------------------
(comment) @comment

; --- strings --------------------------------------------------------------
(string) @string
(raw_string) @string
(ansi_c_string) @string
(heredoc_start) @string
(heredoc_body) @string
(heredoc_end) @string

; --- keywords -------------------------------------------------------------
; note: tree-sitter-bash has no keyword tokens for time/return/break/
; continue/source -- they parse as plain words
[
  "if" "then" "else" "elif" "fi"
  "for" "while" "until" "in" "do" "done"
  "case" "esac" "function" "select"
  "export" "local" "readonly" "unset" "declare"
] @keyword

; --- variables ------------------------------------------------------------
(variable_name) @property
(special_variable_name) @property

; --- definitions and commands ----------------------------------------------
(function_definition name: (word) @function)

(command name: (command_name (word) @function.call))
