from supabase import create_client, Client
import os
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_SERVICE_KEY')
        
        if not url or not key:
            raise ValueError("Supabase credentials not set")
        
        self.client: Client = create_client(url, key)
    
    async def update_document_status(
        self, 
        document_id: str, 
        status: str,
        chunk_count: Optional[int] = None,
        error_message: Optional[str] = None
    ):
        """Update document processing status"""
        data = {
            'ingestion_status': status,
            'updated_at': 'now()'
        }
        
        if chunk_count is not None:
            data['chunk_count'] = chunk_count
            data['chunked'] = True
        
        if error_message:
            data['error_message'] = error_message
        
        self.client.table('documents').update(data).eq('id', document_id).execute()
    
    async def store_chunks(
        self,
        document_id: str,
        chunks: List[Dict],
        embeddings: List[List[float]],
        metadata: Dict
    ):
        """Store document chunks with embeddings"""
        # Delete existing chunks
        self.client.table('chunks').delete().eq('document_id', document_id).execute()
        
        # Prepare chunk records
        chunk_records = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_records.append({
                'document_id': document_id,
                'content': chunk['content'],
                'embedding': embedding,
                'chunk_index': i,
                'metadata': {
                    **chunk['metadata'],
                    **metadata
                }
            })
        
        # Insert in batches
        batch_size = 50
        for i in range(0, len(chunk_records), batch_size):
            batch = chunk_records[i:i + batch_size]
            self.client.table('chunks').insert(batch).execute()
    
    async def vector_search(
        self,
        query_embedding: List[float],
        max_results: int = 5,
        threshold: float = 0.7
    ) -> List[Dict]:
        """Perform vector similarity search"""
        response = self.client.rpc(
            'match_chunks',
            {
                'query_embedding': query_embedding,
                'match_threshold': threshold,
                'match_count': max_results
            }
        ).execute()
        
        return response.data
    
    async def get_document_status(self, document_id: str) -> Optional[Dict]:
        """Get document processing status"""
        response = self.client.table('documents').select(
            'id, ingestion_status, chunk_count, error_message, updated_at'
        ).eq('id', document_id).single().execute()
        
        return response.data
    
    async def delete_document_completely(self, document_id: str):
        """Delete document and all associated data"""
        # Chunks will be deleted by cascade
        self.client.table('documents').delete().eq('id', document_id).execute()