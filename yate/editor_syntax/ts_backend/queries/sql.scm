; yate bundled tree-sitter highlights for SQL (tree-sitter-sql).
; Captures are mapped to SYNTAX_KINDS via DEFAULT_CAPTURE_MAP; unmapped
; captures (identifiers, punctuation) inherit the default foreground.

; --- comments -------------------------------------------------------------
(comment) @comment
(marginalia) @comment

; --- literals -------------------------------------------------------------
(literal) @string
(dollar_quote) @string

; --- keywords -------------------------------------------------------------
[
  (keyword_select) (keyword_from) (keyword_where) (keyword_insert)
  (keyword_into) (keyword_values) (keyword_update) (keyword_delete)
  (keyword_set) (keyword_create) (keyword_table) (keyword_drop)
  (keyword_alter) (keyword_add) (keyword_index) (keyword_view)
  (keyword_join) (keyword_inner) (keyword_left) (keyword_right)
  (keyword_outer) (keyword_full) (keyword_cross) (keyword_on)
  (keyword_group) (keyword_by) (keyword_order) (keyword_having)
  (keyword_limit) (keyword_offset) (keyword_union) (keyword_all)
  (keyword_distinct) (keyword_as) (keyword_and) (keyword_or) (keyword_not)
  (keyword_in) (keyword_between) (keyword_like) (keyword_exists)
  (keyword_case) (keyword_when) (keyword_then) (keyword_else) (keyword_end)
  (keyword_primary) (keyword_key) (keyword_foreign) (keyword_references)
  (keyword_default) (keyword_check) (keyword_unique) (keyword_constraint)
  (keyword_begin) (keyword_commit) (keyword_rollback) (keyword_desc)
  (keyword_asc) (keyword_is) (keyword_null)
] @keyword

; --- types ----------------------------------------------------------------
[
  (bigint) (int) (smallint) (tinyint) (mediumint) (char) (varchar)
  (nchar) (nvarchar) (float) (double) (decimal) (numeric)
  (binary) (bit) (varbinary) (time) (timestamp) (datetimeoffset)
  (interval) (enum)
] @type.builtin
