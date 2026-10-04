; yate bundled tree-sitter highlights for XML (tree-sitter-xml, language_xml).
; Captures are mapped to SYNTAX_KINDS via DEFAULT_CAPTURE_MAP; unmapped
; captures (text content) inherit the default foreground.

; --- tags -----------------------------------------------------------------
(element (STag (Name) @type))
(element (ETag (Name) @type))
(element (EmptyElemTag (Name) @type))

; --- attributes -----------------------------------------------------------
(Attribute (Name) @property)
(Attribute (AttValue) @string)

; --- processing & misc ----------------------------------------------------
(XMLDecl) @decorator
(PI) @decorator
(Comment) @comment
(CDSect) @string
(CharRef) @constant
(EntityRef) @constant
(doctypedecl) @decorator
