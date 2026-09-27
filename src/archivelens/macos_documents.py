"""Finder metadata for supported read-only document sources."""

DOCUMENT_EXTENSIONS = ("cbz", "cbr", "zip", "rar", "7z", "pdf")


def document_types() -> list[dict]:
    """Register as an alternate viewer without claiming default ownership."""
    return [
        {
            "CFBundleTypeName": f"ArchiveLens {extension.upper()} document",
            "CFBundleTypeExtensions": [extension],
            "CFBundleTypeRole": "Viewer",
            "LSHandlerRank": "Alternate",
        }
        for extension in DOCUMENT_EXTENSIONS
    ]


def verify_document_types(plist: dict) -> None:
    if plist.get("CFBundleDocumentTypes") != document_types():
        raise ValueError("Finder document declarations must match the approved six-type allowlist")
    if "UTExportedTypeDeclarations" in plist or "UTImportedTypeDeclarations" in plist:
        raise ValueError("Unexpected Finder type declarations")
