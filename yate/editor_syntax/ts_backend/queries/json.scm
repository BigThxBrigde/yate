; yate bundled tree-sitter highlights for JSON (tree-sitter-json).
; Captures are mapped to SYNTAX_KINDS via DEFAULT_CAPTURE_MAP; unmapped
; captures (punctuation) inherit the default foreground.

; --- strings & numbers ----------------------------------------------------
(pair key: (string) @property)
(string) @string
(escape_sequence) @string
(number) @number

; --- constants ------------------------------------------------------------
[
  (true)
  (false)
  (null)
] @constant
