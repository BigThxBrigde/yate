; yate bundled tree-sitter highlights for XAML (reuses tree-sitter-xml).
; Same node shapes as xml.scm: elements are colored as types, attribute
; names as properties and attribute values as strings.
; NOTE: the body below is intentionally identical to xml.scm -- both names
; resolve to the same grammar, so keep the two files in sync.

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
