import pdfplumber
from PyPDF2 import PdfReader
import re
from typing import List, Dict
from io import BytesIO
import logging

logger = logging.getLogger(__name__)

class PDFProcessor:
    def __init__(self):
        self.legal_patterns = {
            'case_citation': r'\b\d+\s+\w+\.\s*\d+\w*\b',
            'statute': r'(?:Mass\.|M\.G\.L\.|G\.L\.)\s*c\.\s*\d+\w*,?\s*§\s*\d+\w*',
            'section_header': r'^(?:Rule|Section|Chapter|Part|Article|§)\s*\d+',
        }
    
    def extract_text(self, pdf_content: bytes) -> str:
        """Extract text using pdfplumber with fallback to PyPDF2"""
        try:
            with pdfplumber.open(BytesIO(pdf_content)) as pdf:
                text = ""
                for page in pdf.pages:
                    # Extract with layout preservation
                    page_text = page.extract_text(
                        x_tolerance=3,
                        y_tolerance=3,
                        layout=True
                    )
                    if page_text:
                        text += page_text + "\n\n"
                
                return text
        except Exception as e:
            logger.warning(f"pdfplumber failed, trying PyPDF2: {e}")
            
            # Fallback to PyPDF2
            try:
                reader = PdfReader(BytesIO(pdf_content))
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n\n"
                return text
            except Exception as e2:
                logger.error(f"All PDF extraction methods failed: {e2}")
                raise
    
    def chunk_legal_text(
        self, 
        text: str, 
        max_size: int = 1500,
        preserve_citations: bool = True
    ) -> List[Dict]:
        """Smart chunking for legal documents"""
        chunks = []
        
        # Split by major sections
        sections = re.split(
            r'(?=^(?:Rule|RULE|Section|SECTION|Chapter|CHAPTER|§)\s*\d+)',
            text,
            flags=re.MULTILINE
        )
        
        for section_idx, section in enumerate(sections):
            if not section.strip():
                continue
            
            # Extract section header if present
            header_match = re.match(self.legal_patterns['section_header'], section)
            section_header = header_match.group(0) if header_match else None
            
            if len(section) <= max_size:
                chunks.append({
                    'content': section.strip(),
                    'metadata': {
                        'section_index': section_idx,
                        'section_header': section_header,
                        'type': 'legal_section'
                    }
                })
            else:
                # Split large sections by paragraphs
                paragraphs = section.split('\n\n')
                current_chunk = ""
                
                for para in paragraphs:
                    # Check if adding this paragraph would break a citation
                    if preserve_citations and self._contains_partial_citation(
                        current_chunk, para, max_size
                    ):
                        # Include the full paragraph to preserve citation
                        chunks.append({
                            'content': current_chunk.strip(),
                            'metadata': {
                                'section_index': section_idx,
                                'section_header': section_header,
                                'type': 'legal_paragraph'
                            }
                        })
                        current_chunk = para
                    elif len(current_chunk) + len(para) > max_size and current_chunk:
                        chunks.append({
                            'content': current_chunk.strip(),
                            'metadata': {
                                'section_index': section_idx,
                                'section_header': section_header,
                                'type': 'legal_paragraph'
                            }
                        })
                        current_chunk = para
                    else:
                        current_chunk += "\n\n" + para if current_chunk else para
                
                if current_chunk.strip():
                    chunks.append({
                        'content': current_chunk.strip(),
                        'metadata': {
                            'section_index': section_idx,
                            'section_header': section_header,
                            'type': 'legal_paragraph'
                        }
                    })
        
        return chunks
    
    def _contains_partial_citation(
        self, 
        current_chunk: str, 
        next_para: str, 
        max_size: int
    ) -> bool:
        """Check if splitting would break a legal citation"""
        combined = current_chunk + "\n\n" + next_para
        if len(combined) <= max_size:
            return False
        
        # Check if we would split in the middle of a citation
        split_point = max_size - len(current_chunk)
        text_around_split = next_para[max(0, split_point-50):split_point+50]
        
        for pattern in self.legal_patterns.values():
            if re.search(pattern, text_around_split):
                return True
        
        return False