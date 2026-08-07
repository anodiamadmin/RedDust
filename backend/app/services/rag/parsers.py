# services/rag/parsers.py — File parser layer
# Parses .xlsx and .docx files into plain text chunks with metadata.

from pathlib import Path
from typing import TypedDict

import openpyxl
from docx import Document


class Chunk(TypedDict):
    text: str
    metadata: dict  # filename, source (sheet name or section heading)


def parse_xlsx(path: str | Path) -> list[Chunk]:
    """
    Reads every sheet in the workbook.
    Each non-empty row becomes one chunk.
    Metadata includes filename and sheet name.
    """
    path = Path(path)
    wb = openpyxl.load_workbook(path, data_only=True)
    chunks: list[Chunk] = []

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        for row in ws.iter_rows(values_only=True):
            text = " | ".join(str(cell) for cell in row if cell is not None)
            if text.strip():
                chunks.append(
                    Chunk(
                        text=text.strip(),
                        metadata={"filename": path.name, "source": sheet_name},
                    )
                )
    return chunks


def parse_docx(path: str | Path) -> list[Chunk]:
    """
    Reads all paragraphs in the document.
    Each non-empty paragraph becomes one chunk.
    Heading paragraphs are tagged as section in metadata.
    """
    path = Path(path)
    doc = Document(str(path))
    chunks: list[Chunk] = []
    current_section = "root"

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        if para.style.name.startswith("Heading"):
            current_section = text
        chunks.append(
            Chunk(
                text=text,
                metadata={"filename": path.name, "source": current_section},
            )
        )
    return chunks