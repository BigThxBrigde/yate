; yate bundled tree-sitter highlights for Java (tree-sitter-java).
; Captures are mapped to SYNTAX_KINDS via DEFAULT_CAPTURE_MAP; unmapped
; captures (variables, punctuation) inherit the default foreground.

; --- comments -------------------------------------------------------------
(line_comment) @comment
(block_comment) @comment

; --- strings & numbers ----------------------------------------------------
(string_literal) @string
(character_literal) @string
(escape_sequence) @string
(decimal_integer_literal) @number
(octal_integer_literal) @number
(hex_integer_literal) @number
(decimal_floating_point_literal) @number
(hex_floating_point_literal) @number

; --- constants ------------------------------------------------------------
[
  (true)
  (false)
  (null_literal)
] @constant

; --- keywords -------------------------------------------------------------
[
  "abstract" "assert" "break" "case" "catch" "class" "continue"
  "default" "do" "else" "enum" "extends" "final" "finally" "for"
  "if" "implements" "import" "instanceof" "interface" "native" "new"
  "package" "private" "protected" "public" "record" "return" "sealed"
  "permits" "static" "strictfp" "switch" "synchronized"
  "throw" "throws" "transient" "try" "volatile" "while" "yield"
] @keyword
(this) @keyword
(super) @keyword

; --- types ----------------------------------------------------------------
(void_type) @type.builtin
(boolean_type) @type.builtin
(integral_type) @type.builtin
(floating_point_type) @type.builtin
(type_identifier) @type

; --- definitions & calls --------------------------------------------------
(class_declaration name: (identifier) @type)
(interface_declaration name: (identifier) @type)
(enum_declaration name: (identifier) @type)
(record_declaration name: (identifier) @type)
(method_declaration name: (identifier) @function)
(constructor_declaration name: (identifier) @function)
(method_invocation name: (identifier) @function.call)
(object_creation_expression type: (type_identifier) @type)
(field_access field: (identifier) @property)
