; yate bundled tree-sitter highlights for Makefiles (tree-sitter-make).
; Captures are mapped to SYNTAX_KINDS via DEFAULT_CAPTURE_MAP; unmapped
; captures (recipe lines) inherit the default foreground.

; --- comments -------------------------------------------------------------
(comment) @comment

; --- rule targets ---------------------------------------------------------
(rule (targets (word) @function))

; --- variables ------------------------------------------------------------
(variable_assignment (word) @property)
(variable_reference (word) @property)

; --- directives -----------------------------------------------------------
[
  "ifeq" "ifneq" "ifdef" "ifndef" "else" "endif" "include" "-include"
  "define" "endef" "export" "unexport" "override" "undefine" "private"
  "vpath"
] @keyword
