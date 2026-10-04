; yate bundled tree-sitter highlights for Lua (tree-sitter-lua).
; Captures are mapped to SYNTAX_KINDS via DEFAULT_CAPTURE_MAP; unmapped
; captures (variables, punctuation) inherit the default foreground.

; --- comments -------------------------------------------------------------
(comment) @comment

; --- strings & numbers ----------------------------------------------------
(string) @string
(escape_sequence) @string
(number) @number

; --- constants ------------------------------------------------------------
[
  (true)
  (false)
  (nil)
] @constant

; --- keywords -------------------------------------------------------------
[
  "and" "do" "else" "elseif" "end" "for" "function" "goto" "if"
  "in" "local" "not" "or" "repeat" "return" "then" "until" "while"
] @keyword

; --- definitions & calls --------------------------------------------------
(function_declaration name: (identifier) @function)
(function_declaration name: (dot_index_expression field: (identifier) @function.method))
(function_declaration name: (method_index_expression method: (identifier) @function.method))
(function_call name: (identifier) @function.call)
(function_call name: (dot_index_expression field: (identifier) @function.method))
(function_call name: (method_index_expression method: (identifier) @function.method))
