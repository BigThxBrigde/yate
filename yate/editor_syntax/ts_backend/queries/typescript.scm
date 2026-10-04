; yate bundled tree-sitter highlights for TypeScript (tree-sitter-typescript).
; Captures are mapped to SYNTAX_KINDS via DEFAULT_CAPTURE_MAP; unmapped
; captures (variables, punctuation) inherit the default foreground.
; Note: .tsx files resolve to this same grammar (jsx-specific nodes are not
; specially highlighted).

; --- comments -------------------------------------------------------------
(comment) @comment

; --- strings & numbers ----------------------------------------------------
(string) @string
(template_string) @string
(template_literal_type) @string
(regex) @string
(escape_sequence) @string
(number) @number

; --- constants ------------------------------------------------------------
[
  (true)
  (false)
  (null)
  (undefined)
] @constant

; --- keywords -------------------------------------------------------------
[
  "break" "case" "catch" "class" "const" "continue" "debugger" "default"
  "delete" "do" "else" "enum" "export" "extends" "finally" "for" "function"
  "if" "import" "in" "instanceof" "interface" "let" "new" "return" "static"
  "switch" "throw" "try" "typeof" "var" "void" "while"
  "with" "yield" "async" "await" "of" "as" "from" "get" "set" "implements"
  "private" "protected" "public" "readonly" "declare" "abstract" "keyof"
  "infer" "is" "namespace" "type" "satisfies"
] @keyword

; --- types ----------------------------------------------------------------
(predefined_type) @type.builtin
(type_identifier) @type

; --- definitions & calls --------------------------------------------------
(class_declaration name: (type_identifier) @type)
(interface_declaration name: (type_identifier) @type)
(abstract_class_declaration name: (type_identifier) @type)
(type_alias_declaration name: (type_identifier) @type)
(enum_declaration name: (identifier) @type)
(function_declaration name: (identifier) @function)
(generator_function_declaration name: (identifier) @function)
(call_expression function: (identifier) @function.call)
(call_expression function: (member_expression property: (property_identifier) @function.method))
(property_identifier) @property
