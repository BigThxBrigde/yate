; yate bundled tree-sitter highlights for Markdown (tree-sitter-markdown).
; Captures are mapped to SYNTAX_KINDS via DEFAULT_CAPTURE_MAP.
; Known limitation: the shipped grammar is block-level only -- the (inline)
; node is a single catchall, so emphasis / code spans inside a paragraph
; cannot be captured here (the regex fallback covers those better).

; --- headings -------------------------------------------------------------
[
  (atx_h1_marker) (atx_h2_marker) (atx_h3_marker)
  (atx_h4_marker) (atx_h5_marker) (atx_h6_marker)
] @heading
(setext_h1_underline) @heading
(setext_h2_underline) @heading

; --- code -----------------------------------------------------------------
(fenced_code_block (fenced_code_block_delimiter) @keyword)
(fenced_code_block (info_string) @builtin)
(code_fence_content) @string
(indented_code_block) @string

; --- links ----------------------------------------------------------------
(link_destination) @string
(link_label) @property
(link_title) @string
(link_reference_definition) @property

; --- misc block structure -------------------------------------------------
(block_quote (block_quote_marker) @operator)
(thematic_break) @operator
(list_marker_dot) @operator
(list_marker_parenthesis) @operator
(list_marker_star) @operator
(list_marker_plus) @operator
(list_marker_minus) @operator
(html_block) @comment
(backslash_escape) @string
(entity_reference) @constant
(numeric_character_reference) @constant
