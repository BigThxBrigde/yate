; yate bundled tree-sitter highlights for C# (tree-sitter-c-sharp).
; Captures are mapped to SYNTAX_KINDS via DEFAULT_CAPTURE_MAP; unmapped
; captures (variables, punctuation) inherit the default foreground.

; --- comments -------------------------------------------------------------
(comment) @comment

; --- strings & numbers ----------------------------------------------------
(string_literal) @string
(verbatim_string_literal) @string
(raw_string_literal) @string
(character_literal) @string
(escape_sequence) @string
(integer_literal) @number
(real_literal) @number

; --- constants ------------------------------------------------------------
(boolean_literal) @constant
(null_literal) @constant

; --- keywords -------------------------------------------------------------
[
  "abstract" "as" "base" "break" "case" "catch" "checked" "class" "const"
  "continue" "default" "delegate" "do" "else" "enum" "event" "explicit"
  "extern" "finally" "fixed" "for" "foreach" "goto" "if" "implicit" "in"
  "interface" "internal" "is" "lock" "namespace" "new" "operator" "out"
  "override" "params" "private" "protected" "public" "readonly" "ref"
  "return" "sealed" "sizeof" "stackalloc" "static" "struct" "switch" "this"
  "throw" "try" "typeof" "unchecked" "unsafe" "using" "virtual" "volatile"
  "while" "async" "await" "var" "get" "set" "when" "where" "yield"
  "partial" "record" "global" "init" "with"
] @keyword

; --- types ----------------------------------------------------------------
(predefined_type) @type.builtin

; --- definitions & calls --------------------------------------------------
(class_declaration name: (identifier) @type)
(interface_declaration name: (identifier) @type)
(struct_declaration name: (identifier) @type)
(enum_declaration name: (identifier) @type)
(record_declaration name: (identifier) @type)
(method_declaration name: (identifier) @function)
(local_function_statement name: (identifier) @function)
(property_declaration name: (identifier) @property)
(invocation_expression function: (identifier) @function.call)
(invocation_expression function: (member_access_expression name: (identifier) @function.method))
