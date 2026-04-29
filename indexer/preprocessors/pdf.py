import logging
from pathlib import Path
from typing import Set, List
from pypdf import PdfReader
from .base import BasePreprocessor

logger = logging.getLogger(__name__)

class PdfPreprocessor(BasePreprocessor):
    """
    Advanced PDF pre-processor that extracts text, identifies sections,
    and handles graphics with placeholders.
    """
    
    @property
    def supported_extensions(self) -> Set[str]:
        return {'.pdf'}

    def preprocess(self, filepath: Path) -> str:
        """
        Process a PDF file and return a structured Markdown representation.
        """
        try:
            reader = PdfReader(filepath)
            
            # 1. Extract Metadata
            metadata = reader.metadata
            title = metadata.title if metadata and metadata.title else filepath.name
            author = metadata.author if metadata and metadata.author else "Unknown"
            subject = metadata.subject if metadata and metadata.subject else ""
            
            md_output = []
            
            # Frontmatter / Metadata
            md_output.append("---")
            md_output.append(f"title: \"{title}\"")
            md_output.append(f"author: \"{author}\"")
            if subject:
                md_output.append(f"subtitle: \"{subject}\"")
            md_output.append(f"source: \"{filepath}\"")
            md_output.append("---\n")
            
            md_output.append(f"# {title}\n")
            if subject:
                md_output.append(f"## {subject}\n")

            # 2. Process Pages
            for page_idx, page in enumerate(reader.pages):
                md_output.append(f"### Page {page_idx + 1}\n")
                
                # Check for images/graphics in resources
                if "/Resources" in page and "/XObject" in page["/Resources"]:
                    xobjects = page["/Resources"]["/XObject"]
                    for obj_name in xobjects:
                        if xobjects[obj_name]["/Subtype"] == "/Image":
                            md_output.append(f"\n> [!NOTE]\n> **Graphic Placeholder**: {obj_name} detected on page {page_idx + 1}. Artifacts such as graphics are excluded from text indexing.\n")

                # Extract and clean text
                text = page.extract_text()
                if text:
                    # Basic heuristic: identify potential headers (short lines with no period at end)
                    lines = text.split('\n')
                    cleaned_lines = []
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                            
                        # If line is short and looks like a header (heuristic)
                        if 3 < len(line) < 60 and not line.endswith('.') and not line[0].islower():
                            cleaned_lines.append(f"#### {line}")
                        else:
                            cleaned_lines.append(line)
                    
                    md_output.append("\n".join(cleaned_lines))
                    md_output.append("\n")

            return "\n".join(md_output)

        except Exception as e:
            logger.error(f"Failed to process PDF {filepath}: {e}")
            return f"# Error processing PDF: {filepath.name}\n\n{str(e)}"
