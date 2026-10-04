; yate bundled tree-sitter highlights for Ruby (tree-sitter-ruby).
; Captures are mapped to SYNTAX_KINDS via DEFAULT_CAPTURE_MAP; unmapped
; captures (variables, punctuation) inherit the default foreground.

; --- comments -------------------------------------------------------------
(comment) @comment

; --- strings & numbers ----------------------------------------------------
(string) @string
(heredoc_body) @string
(regex) @string
(escape_sequence) @string
(integer) @number
(float) @number

; --- constants ------------------------------------------------------------
[
  (true)
  (false)
  (nil)
] @constant
(simple_symbol) @constant
(delimited_symbol) @constant

; --- keywords -------------------------------------------------------------
[
  "alias" "and" "begin" "break" "case" "class" "def" "do" "else" "elsif"
  "end" "ensure" "for" "if" "in" "module" "next" "not" "or" "redo" "rescue"
  "retry" "return" "then" "undef" "unless" "until" "when" "while" "yield"
] @keyword
(self) @keyword
(super) @keyword

; --- definitions & calls --------------------------------------------------
(method name: (identifier) @function)
(singleton_method name: (identifier) @function)
(class name: (constant) @type)
(module name: (constant) @type)
(call method: (identifier) @function.call)
(call method: (constant) @function.call)
(constant) @type
