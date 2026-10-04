; yate bundled tree-sitter highlights for Rust (tree-sitter-rust).
; Captures are mapped to SYNTAX_KINDS via DEFAULT_CAPTURE_MAP; unmapped
; captures (variables, punctuation) inherit the default foreground.

; --- comments -------------------------------------------------------------
(line_comment) @comment
(block_comment) @comment

; --- strings & numbers ----------------------------------------------------
(string_literal) @string
(raw_string_literal) @string
(char_literal) @string
(escape_sequence) @string
(integer_literal) @number
(float_literal) @number

; --- constants ------------------------------------------------------------
(boolean_literal) @constant

; --- lifetimes & attributes ----------------------------------------------
(lifetime) @decorator
(attribute_item) @decorator

; --- keywords -------------------------------------------------------------
[
  "as" "async" "await" "break" "const" "continue" "dyn" "else"
  "enum" "extern" "fn" "for" "if" "impl" "in" "let" "loop" "match" "mod"
  "move" "pub" "ref" "return" "static" "struct"
  "trait" "type" "unsafe" "use" "where" "while"
] @keyword
(crate) @keyword
(self) @keyword
(mutable_specifier) @keyword

; --- types ----------------------------------------------------------------
(primitive_type) @type.builtin
(type_identifier) @type

; --- definitions & calls --------------------------------------------------
(function_item name: (identifier) @function)
(struct_item name: (type_identifier) @type)
(enum_item name: (type_identifier) @type)
(trait_item name: (type_identifier) @type)
(type_item name: (type_identifier) @type)
(call_expression function: (identifier) @function.call)
(call_expression function: (field_expression field: (field_identifier) @function.method))
(field_identifier) @property
(macro_invocation macro: (identifier) @function.call)
