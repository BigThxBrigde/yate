; yate bundled tree-sitter highlights for Python (tree-sitter-python).
; Captures are mapped to SYNTAX_KINDS via DEFAULT_CAPTURE_MAP; unmapped
; captures (variables, punctuation) inherit the default foreground.

; --- comments -------------------------------------------------------------
(comment) @comment

; --- strings --------------------------------------------------------------
(string) @string
(escape_sequence) @string

; --- numbers --------------------------------------------------------------
(integer) @number
(float) @number

; --- constants ------------------------------------------------------------
[
  (true)
  (false)
  (none)
] @constant

; --- decorators -----------------------------------------------------------
(decorator) @decorator

; --- keywords -------------------------------------------------------------
[
  "if" "elif" "else" "for" "while" "break" "continue" "return"
  "def" "class" "import" "from" "as" "with" "try" "except" "finally"
  "raise" "pass" "global" "nonlocal" "lambda" "yield" "assert" "del"
  "and" "or" "not" "in" "is" "async" "await" "match" "case"
] @keyword

; --- definitions ----------------------------------------------------------
(function_definition name: (identifier) @function)
(class_definition name: (identifier) @type)

; --- calls ----------------------------------------------------------------
(call function: (identifier) @function.call)
(call function: (attribute attribute: (identifier) @function.method))
