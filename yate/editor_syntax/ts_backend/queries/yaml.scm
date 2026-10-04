; yate bundled tree-sitter highlights for YAML (tree-sitter-yaml).
; Captures are mapped to SYNTAX_KINDS via DEFAULT_CAPTURE_MAP; unmapped
; captures (plain scalars, punctuation) inherit the default foreground.

; --- comments -------------------------------------------------------------
(comment) @comment

; --- strings & numbers ----------------------------------------------------
(double_quote_scalar) @string
(single_quote_scalar) @string
(block_scalar) @string
(escape_sequence) @string
(integer_scalar) @number
(float_scalar) @number

; --- constants ------------------------------------------------------------
(boolean_scalar) @constant
(null_scalar) @constant

; --- keys & anchors -------------------------------------------------------
(block_mapping_pair key: (flow_node (plain_scalar (string_scalar) @property)))
(anchor) @decorator
(alias) @decorator
(tag) @decorator
(yaml_directive) @decorator
(tag_directive) @decorator
