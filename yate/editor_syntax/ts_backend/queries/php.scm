; yate bundled tree-sitter highlights for PHP (tree-sitter-php).
; Captures are mapped to SYNTAX_KINDS via DEFAULT_CAPTURE_MAP; unmapped
; captures (variables, punctuation) inherit the default foreground.

; --- comments -------------------------------------------------------------
(comment) @comment

; --- strings & numbers ----------------------------------------------------
; (string) covers single-quoted and heredoc bodies; a double-quoted string with
; interpolation is an (encapsed_string) holding (string_content) fragments and
; (variable_name) holes, so it needs its own pattern or it stays unpainted.
(string) @string
(encapsed_string) @string
(heredoc_body) @string
(escape_sequence) @string
(integer) @number
(float) @number

; --- constants ------------------------------------------------------------
(boolean) @constant
(null) @constant

; --- keywords -------------------------------------------------------------
[
  "abstract" "and" "array" "as" "break" "case" "catch" "class"
  "clone" "const" "continue" "declare" "default" "do" "echo" "else" "elseif"
  "enddeclare" "endfor" "endforeach" "endif" "endswitch"
  "endwhile" "enum" "extends" "final" "finally" "fn" "for" "foreach"
  "function" "global" "goto" "if" "implements" "include" "include_once"
  "instanceof" "insteadof" "interface" "list" "match" "namespace"
  "new" "or" "print" "private" "protected" "public" "readonly" "require"
  "require_once" "return" "static" "switch" "throw" "trait" "try" "unset"
  "use" "while" "xor" "yield"
] @keyword

; --- types ----------------------------------------------------------------
(primitive_type) @type.builtin
(cast_type) @type.builtin
(named_type (name) @type)

; --- definitions & calls --------------------------------------------------
(function_definition name: (name) @function)
(method_declaration name: (name) @function)
(class_declaration name: (name) @type)
(interface_declaration name: (name) @type)
(trait_declaration name: (name) @type)
(enum_declaration name: (name) @type)
(function_call_expression function: (name) @function.call)
(scoped_call_expression name: (name) @function.method)
(member_call_expression name: (name) @function.method)
(member_access_expression name: (name) @property)
