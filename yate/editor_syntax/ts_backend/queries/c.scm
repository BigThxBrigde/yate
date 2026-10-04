; yate bundled tree-sitter highlights for C (tree-sitter-c).
; Captures are mapped to SYNTAX_KINDS via DEFAULT_CAPTURE_MAP; unmapped
; captures (variables, punctuation) inherit the default foreground.

; --- comments -------------------------------------------------------------
(comment) @comment

; --- strings & numbers ----------------------------------------------------
(string_literal) @string
(char_literal) @string
(escape_sequence) @string
(number_literal) @number

; --- constants ------------------------------------------------------------
[
  (true)
  (false)
  (null)
  "NULL"
  "nullptr"
] @constant

; --- preprocessor ---------------------------------------------------------
[
  "#include"
  "#define"
  "#if"
  "#ifdef"
  "#ifndef"
  "#elif"
  "#else"
  "#endif"
] @keyword

; --- keywords -------------------------------------------------------------
[
  "if" "else" "for" "while" "do" "switch" "case" "default" "break"
  "continue" "return" "goto" "sizeof" "static" "struct" "union" "enum"
  "typedef" "const" "extern" "volatile" "inline" "register" "restrict"
  "auto" "signed" "unsigned"
] @keyword

; --- types ----------------------------------------------------------------
(primitive_type) @type.builtin
(type_identifier) @type

; --- definitions & calls --------------------------------------------------
(function_declarator declarator: (identifier) @function)
(call_expression function: (identifier) @function.call)
(call_expression function: (field_expression field: (field_identifier) @function.method))
(field_identifier) @property
