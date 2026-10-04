; yate bundled tree-sitter highlights for JavaScript (tree-sitter-javascript).
; Captures are mapped to SYNTAX_KINDS via DEFAULT_CAPTURE_MAP; unmapped
; captures (variables, punctuation) inherit the default foreground.

; --- comments -------------------------------------------------------------
(comment) @comment

; --- strings & numbers ----------------------------------------------------
(string) @string
(template_string) @string
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
  "delete" "do" "else" "export" "extends" "finally" "for" "function" "if"
  "import" "in" "instanceof" "let" "new" "return" "static" "switch"
  "throw" "try" "typeof" "var" "void" "while" "with" "yield" "async"
  "await" "of" "as" "from" "get" "set"
] @keyword

; --- types ----------------------------------------------------------------
(class_declaration name: (identifier) @type)

; --- definitions & calls --------------------------------------------------
(function_declaration name: (identifier) @function)
(generator_function_declaration name: (identifier) @function)
(method_definition name: (property_identifier) @function)
(call_expression function: (identifier) @function.call)
(call_expression function: (member_expression property: (property_identifier) @function.method))
(property_identifier) @property
