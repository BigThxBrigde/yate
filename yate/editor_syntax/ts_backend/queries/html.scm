; yate bundled tree-sitter highlights for HTML (tree-sitter-html).
; Captures are mapped to SYNTAX_KINDS via DEFAULT_CAPTURE_MAP; unmapped
; captures (text content) inherit the default foreground.
; Note: embedded <script>/<style> content is not re-highlighted (no
; injection support in the backend).

; --- comments -------------------------------------------------------------
(comment) @comment

; --- doctype & processing -------------------------------------------------
(doctype) @decorator

; --- tags -----------------------------------------------------------------
; (start_tag) / (self_closing_tag) nest inside (element), so a bare
; (element (start_tag (tag_name) @type)) pattern would only duplicate the span
; already claimed above -- children of start_tag match on their own.
(start_tag (tag_name) @type)
(end_tag (tag_name) @type)
(self_closing_tag (tag_name) @type)

; --- attributes -----------------------------------------------------------
(attribute (attribute_name) @property)
(quoted_attribute_value) @string
(attribute_value) @string
