; yate bundled tree-sitter highlights for PowerShell (tree-sitter-powershell).
; Captures are mapped to SYNTAX_KINDS via DEFAULT_CAPTURE_MAP; unmapped
; captures (variables, punctuation) inherit the default foreground.

; --- comments -------------------------------------------------------------
(comment) @comment

; --- strings & numbers ----------------------------------------------------
(string_literal) @string
(expandable_string_literal) @string
(expandable_here_string_literal) @string
(integer_literal) @number
(real_literal) @number
(hexadecimal_integer_literal) @number
(decimal_integer_literal) @number

; --- keywords -------------------------------------------------------------
[
  "if" "elseif" "else" "switch" "for" "foreach" "while" "do" "until"
  "break" "continue" "return" "throw" "try" "catch" "finally" "trap"
  "function" "filter" "param" "in" "begin" "process" "end" "exit" "data"
  "workflow" "dynamicparam"
] @keyword

; --- commands & parameters ------------------------------------------------
(command_name) @function
(command_parameter) @property
