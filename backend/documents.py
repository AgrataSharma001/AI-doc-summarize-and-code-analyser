"""Read-only PDF/DOCX intake with bounded text and structural source locations."""

import io
import zipfile
from xml.etree import ElementTree

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from fastapi import HTTPException
from pypdf import PdfReader, apply_configuration
from pypdf.errors import LimitReachedError

from backend.models import SourceFile
from backend.sources import MAX_SOURCE_CHARS, extract_text

MAX_PDF_PAGES = 200
MAX_PDF_PAGE_STREAM = 4 * 1024 * 1024
MAX_EXPANDED_BYTES = 20 * 1024 * 1024
MAX_DOCX_BLOCKS = 10_000


def _validate_docx(content: bytes) -> None:
    """Check the package before python-docx loads any XML parts."""
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if (len(entries) > 1000 or len(names) != len(set(names))
                or sum(entry.file_size for entry in entries) > MAX_EXPANDED_BYTES
                or any(entry.flag_bits & 1 for entry in entries)):
            raise HTTPException(413, "DOCX archive exceeds safe package limits or is encrypted.")
        for entry in entries:
            if entry.filename.lower().endswith((".xml", ".rels")):
                # Also catches UTF-16/32 declarations. No DTD/entity definitions
                # are needed for ordinary OOXML; reject before library parsing.
                xml = archive.read(entry).replace(b"\x00", b"").upper()
                if b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:
                    raise ValueError("Unsupported XML declarations")
        types = ElementTree.fromstring(archive.read("[Content_Types].xml"))
        expected = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
        if not any(e.attrib.get("PartName") == "/word/document.xml"
                   and e.attrib.get("ContentType") == expected for e in types):
            raise ValueError("Not a DOCX document")
        if ElementTree.fromstring(archive.read("word/document.xml")).tag != (
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}document"):
            raise ValueError("Invalid document XML")


def extract_document(source: SourceFile, content: bytes, extension: str) -> list[str]:
    """Append all spans only after successful extraction; return coverage warnings."""
    pending = SourceFile(id=source.id)
    total = 0
    warnings = []

    def add(text: str, location: str):
        nonlocal total
        total += len(text)
        if total > MAX_SOURCE_CHARS:
            raise HTTPException(413, "Extracted document exceeds 200,000 characters. Split it into smaller files.")
        if text.strip():
            extract_text(pending, text, location)

    try:
        if extension == ".pdf":
            with apply_configuration(
                maximum_declared_stream_length=MAX_EXPANDED_BYTES,
                array_based_stream_maximum_output_length=MAX_PDF_PAGE_STREAM,
                zlib_maximum_output_length=MAX_PDF_PAGE_STREAM,
                lzw_maximum_output_length=MAX_PDF_PAGE_STREAM,
                run_length_maximum_output_length=MAX_PDF_PAGE_STREAM,
                page_tree_maximum_entries=2000, page_tree_maximum_depth=32,
                xform_maximum_invocations_per_extraction=500, jbig2dec_binary=None,
            ):
                reader = PdfReader(io.BytesIO(content), strict=True)
                if reader.is_encrypted:
                    raise HTTPException(422, "PDF is encrypted. Upload an unencrypted copy.")
                if not reader.pages:
                    raise HTTPException(422, "PDF has no pages.")
                if len(reader.pages) > MAX_PDF_PAGES:
                    raise HTTPException(413, "PDF exceeds the 200-page limit. Split it into smaller files.")
                empty_pages = 0
                stream_bytes = 0
                for number, page in enumerate(reader.pages, 1):
                    stream = page.get_contents()
                    size = len(stream.get_data()) if stream is not None else 0
                    stream_bytes += size
                    if size > MAX_PDF_PAGE_STREAM or stream_bytes > MAX_EXPANDED_BYTES:
                        raise HTTPException(413, "PDF content streams are too large. Upload a simpler PDF.")
                    text = page.extract_text() or ""
                    if not text.strip():
                        empty_pages += 1
                    add(text, f"page {number}, ")
                if empty_pages:
                    warnings.append(f"{source.filename}: {empty_pages} PDF page(s) had no extractable text; "
                                    "blank pages or scanned images may be omitted. OCR is not supported.")
        elif extension == ".docx":
            _validate_docx(content)
            document = Document(io.BytesIO(content))
            heading = ""
            section = 0
            blocks = 0

            def walk(container, prefix="", depth=0):
                nonlocal heading, section, blocks
                if depth > 8:
                    raise HTTPException(413, "DOCX tables are nested too deeply.")
                paragraph_number = table_number = 0
                for block in container.iter_inner_content():
                    blocks += 1
                    if blocks > MAX_DOCX_BLOCKS:
                        raise HTTPException(413, "DOCX contains too many paragraphs or table cells.")
                    if isinstance(block, Paragraph):
                        paragraph_number += 1
                        if not prefix and block.style and block.style.name.startswith("Heading"):
                            section += 1
                            heading = f"section {section} ({' '.join(block.text.split())[:32]}), "
                        add(block.text, f"{heading}{prefix}paragraph {paragraph_number}, ")
                    elif isinstance(block, Table):
                        table_number += 1
                        seen_cells = set()
                        for row_number, row in enumerate(block.rows, 1):
                            for cell_number, cell in enumerate(row.cells, 1):
                                # Merged cells can appear repeatedly in rows/columns.
                                if cell._tc in seen_cells:
                                    continue
                                seen_cells.add(cell._tc)
                                walk(cell, f"{prefix}table {table_number} row {row_number} cell {cell_number}, ", depth + 1)
            walk(document)
            warnings.append(f"{source.filename}: DOCX extraction covers body paragraphs and tables; "
                            "images, text boxes, headers/footers, and tracked changes may be omitted.")
        else:
            raise ValueError("Unsupported document type")
    except LimitReachedError as exc:
        raise HTTPException(413, "PDF exceeds parser resource limits. Upload a simpler or smaller PDF.") from exc
    except HTTPException:
        raise
    except Exception as exc:
        kind = "PDF" if extension == ".pdf" else "DOCX"
        raise HTTPException(422, f"{kind} is corrupt or unsupported. Try exporting a fresh copy or paste its text.") from exc
    if not pending.spans:
        raise HTTPException(422, "No extractable document text. Scanned/image-only files need OCR; "
                            "upload a text-based file or paste its text.")
    # Keep the database location contract, including unusually nested tables.
    for span in pending.spans:
        if len(span.location) > 100:
            raise HTTPException(413, "Document structure produces overly long source locations. Simplify its tables/headings.")
    source.spans.extend(pending.spans)
    return warnings
