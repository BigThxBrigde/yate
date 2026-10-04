; yate bundled tree-sitter highlights for XAML (reuses tree-sitter-xml).
; Same node shapes as xml.scm: elements are colored as types, attribute
; names as properties and attribute values as strings.

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
