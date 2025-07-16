from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from typing import Optional, List
import uuid
from datetime import datetime
import logging
from io import BytesIO

# Import our processing modules
from pdf_processor import PDFProcessor
from embeddings_generator import EmbeddingsGenerator
from database import DatabaseManager
from llama_processor import LlamaCloudProcessor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Criminal Law Document Processor")

# Configure CORS for Lovable frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure with your Lovable app URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
db = DatabaseManager()
pdf_processor = PDFProcessor()
llama_processor = LlamaCloudProcessor()
embeddings_gen = EmbeddingsGenerator()

class ProcessingResponse(BaseModel):
    document_id: str
    status: str
    message: str

class SearchRequest(BaseModel):
    query: str
    max_results: Optional[int] = 5
    threshold: Optional[float] = 0.7

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "Criminal Law Document Processor"}

@app.post("/process-document", response_model=ProcessingResponse)
async def process_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    use_llama_cloud: bool = True,
    document_id: Optional[str] = None
):
    """
    Process a legal document with optional LlamaCloud extraction
    """
    try:
        # Generate document ID if not provided
        if not document_id:
            document_id = str(uuid.uuid4())
        
        logger.info(f"Processing document: {file.filename} (ID: {document_id})")
        
        # Read file content
        content = await file.read()
        
        # Update document status to processing
        await db.update_document_status(document_id, "processing")
        
        # Queue background processing
        background_tasks.add_task(
            process_document_background,
            content,
            document_id,
            file.filename,
            use_llama_cloud
        )
        
        return ProcessingResponse(
            document_id=document_id,
            status="processing",
            message=f"Document {file.filename} queued for processing"
        )
        
    except Exception as e:
        logger.error(f"Error processing document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_document_background(
    pdf_content: bytes,
    document_id: str,
    filename: str,
    use_llama_cloud: bool
):
    """
    Background task for document processing
    """
    try:
        logger.info(f"Starting background processing for {document_id}")
        
        # Extract text based on method
        if use_llama_cloud:
            logger.info("Using LlamaCloud for advanced extraction")
            extracted_data = await llama_processor.extract_with_llama_cloud(
                pdf_content, 
                filename
            )
            text_content = extracted_data.get('text', '')
            tables = extracted_data.get('tables', [])
            metadata = extracted_data.get('metadata', {})
        else:
            logger.info("Using pdfplumber for basic extraction")
            text_content = pdf_processor.extract_text(pdf_content)
            tables = []
            metadata = {}
        
        if not text_content:
            raise ValueError("No text content extracted from PDF")
        
        logger.info(f"Extracted {len(text_content)} characters")
        
        # Smart legal document chunking
        chunks = pdf_processor.chunk_legal_text(
            text_content,
            max_size=1500,
            preserve_citations=True
        )
        
        logger.info(f"Created {len(chunks)} chunks")
        
        # Generate embeddings
        embeddings = embeddings_gen.generate_embeddings(
            [chunk['content'] for chunk in chunks]
        )
        
        # Store in database
        await db.store_chunks(
            document_id=document_id,
            chunks=chunks,
            embeddings=embeddings,
            metadata={
                'filename': filename,
                'tables_count': len(tables),
                'extraction_method': 'llama_cloud' if use_llama_cloud else 'pdfplumber',
                **metadata
            }
        )
        
        # Update document status
        await db.update_document_status(
            document_id, 
            "completed",
            chunk_count=len(chunks)
        )
        
        logger.info(f"Successfully processed document {document_id}")
        
    except Exception as e:
        logger.error(f"Error in background processing: {str(e)}")
        await db.update_document_status(
            document_id, 
            "failed",
            error_message=str(e)
        )

@app.post("/search")
async def search_documents(request: SearchRequest):
    """
    Search across all processed legal documents
    """
    try:
        # Generate embedding for query
        query_embedding = embeddings_gen.generate_embedding(request.query)
        
        # Search in database
        results = await db.vector_search(
            query_embedding,
            max_results=request.max_results,
            threshold=request.threshold
        )
        
        return {
            "query": request.query,
            "results": results,
            "count": len(results)
        }
        
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/document/{document_id}/status")
async def get_document_status(document_id: str):
    """
    Get processing status for a document
    """
    status = await db.get_document_status(document_id)
    if not status:
        raise HTTPException(status_code=404, detail="Document not found")
    return status

@app.delete("/document/{document_id}")
async def delete_document(document_id: str):
    """
    Delete a document and all its chunks
    """
    try:
        await db.delete_document_completely(document_id)
        return {"message": f"Document {document_id} deleted successfully"}
    except Exception as e:
        logger.error(f"Delete error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))