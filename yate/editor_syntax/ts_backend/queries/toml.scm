; yate bundled tree-sitter highlights for TOML (tree-sitter-toml).
; Captures are mapped to SYNTAX_KINDS via DEFAULT_CAPTURE_MAP; unmapped
; captures (punctuation) inherit the default foreground.

; --- comments -------------------------------------------------------------
(comment) @comment

; --- strings & numbers ----------------------------------------------------
(string) @string
(escape_sequence) @string
(integer) @number
(float) @number
(offset_date_time) @number
(local_date_time) @number
(local_date) @number
(local_time) @number

; --- constants ------------------------------------------------------------
(boolean) @constant

; --- keys -----------------------------------------------------------------
(bare_key) @property
(quoted_key) @property
(dotted_key) @property
