; yate bundled tree-sitter highlights for Go (tree-sitter-go).
; Captures are mapped to SYNTAX_KINDS via DEFAULT_CAPTURE_MAP; unmapped
; captures (variables, punctuation) inherit the default foreground.

; --- comments -------------------------------------------------------------
(comment) @comment

; --- strings & numbers ----------------------------------------------------
(interpreted_string_literal) @string
(raw_string_literal) @string
(escape_sequence) @string
(rune_literal) @string
(int_literal) @number
(float_literal) @number
(imaginary_literal) @number

; --- constants ------------------------------------------------------------
[
  (true)
  (false)
  (nil)
  (iota)
] @constant

; --- keywords -------------------------------------------------------------
[
  "break" "case" "chan" "const" "continue" "default" "defer" "else"
  "fallthrough" "for" "func" "go" "goto" "if" "import" "interface" "map"
  "package" "range" "return" "select" "struct" "switch" "type" "var"
] @keyword

; --- types ----------------------------------------------------------------
(type_identifier) @type

; --- definitions & calls --------------------------------------------------
(function_declaration name: (identifier) @function)
(method_declaration name: (field_identifier) @function)
(type_spec name: (type_identifier) @type)
(call_expression function: (identifier) @function.call)
(call_expression function: (selector_expression field: (field_identifier) @function.method))
(field_identifier) @property
(package_identifier) @property
