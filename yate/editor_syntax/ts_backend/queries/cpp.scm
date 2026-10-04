; yate bundled tree-sitter highlights for C++ (tree-sitter-cpp).
; Captures are mapped to SYNTAX_KINDS via DEFAULT_CAPTURE_MAP; unmapped
; captures (variables, punctuation) inherit the default foreground.

; --- comments -------------------------------------------------------------
(comment) @comment

; --- strings & numbers ----------------------------------------------------
(string_literal) @string
(raw_string_literal) @string
(char_literal) @string
(escape_sequence) @string
(number_literal) @number

; --- constants ------------------------------------------------------------
[
  (true)
  (false)
  (null)
  "nullptr"
] @constant

; --- keywords -------------------------------------------------------------
[
  "if" "else" "for" "while" "do" "switch" "case" "default" "break"
  "continue" "return" "goto" "sizeof" "static" "struct" "union" "enum"
  "typedef" "const" "extern" "volatile" "inline" "constexpr" "consteval"
  "constinit" "mutable" "signed" "unsigned" "class" "namespace"
  "template" "typename" "using" "public" "private" "protected" "virtual"
  "override" "final" "new" "delete" "try" "catch" "throw" "operator"
  "explicit" "friend" "noexcept" "concept" "requires" "co_await"
  "co_return" "co_yield" "decltype"
] @keyword
(this) @keyword

; --- types ----------------------------------------------------------------
(primitive_type) @type.builtin
(type_identifier) @type

; --- definitions & calls --------------------------------------------------
(function_declarator declarator: (identifier) @function)
(function_declarator declarator: (field_identifier) @function)
(call_expression function: (identifier) @function.call)
(call_expression function: (field_expression field: (field_identifier) @function.method))
(field_identifier) @property
