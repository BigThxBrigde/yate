; yate bundled tree-sitter highlights for CSS (tree-sitter-css).
; Captures are mapped to SYNTAX_KINDS via DEFAULT_CAPTURE_MAP; unmapped
; captures (plain values) inherit the default foreground.

; --- comments -------------------------------------------------------------
(comment) @comment

; --- strings & numbers ----------------------------------------------------
(string_value) @string
(integer_value) @number
(float_value) @number
(color_value) @constant

; --- at-rules -------------------------------------------------------------
(at_keyword) @keyword

; --- selectors ------------------------------------------------------------
(tag_name) @type
(class_name) @type
(id_name) @constant
(attribute_name) @property
(pseudo_class_selector (class_name) @property)
(pseudo_element_selector (tag_name) @property)
(nesting_selector) @keyword

; --- declarations ---------------------------------------------------------
(property_name) @property
