import httpx
import base64
import logging
from typing import Dict, Any
import asyncio
import os

logger = logging.getLogger(__name__)

class LlamaCloudProcessor:
    def __init__(self):
        self.api_key = os.getenv('LLAMA_CLOUD_API_KEY')
        self.api_url = "https://api.cloud.llamaindex.ai/api/v1/parsing/upload"
        self.client = httpx.AsyncClient(timeout=300.0)  # 5 minute timeout
    
    async def extract_with_llama_cloud(
        self, 
        pdf_content: bytes, 
        filename: str
    ) -> Dict[str, Any]:
        """Extract text, tables, and metadata using LlamaCloud"""
        try:
            if not self.api_key:
                raise ValueError("LLAMA_CLOUD_API_KEY not set")
            
            logger.info(f"Uploading {filename} to LlamaCloud")
            
            # Upload file
            files = {
                'file': (filename, pdf_content, 'application/pdf')
            }
            headers = {
                'Authorization': f'Bearer {self.api_key}'
            }
            
            response = await self.client.post(
                self.api_url,
                files=files,
                headers=headers
            )
            
            if response.status_code != 200:
                raise Exception(f"LlamaCloud API error: {response.text}")
            
            job_data = response.json()
            job_id = job_data['job_id']
            
            # Poll for results
            result = await self._poll_for_results(job_id)
            
            # Extract structured data
            return {
                'text': result.get('text', ''),
                'tables': result.get('tables', []),
                'metadata': {
                    'page_count': result.get('page_count', 0),
                    'has_tables': len(result.get('tables', [])) > 0,
                    'document_type': result.get('document_type', 'legal'),
                    'extraction_method': 'llama_cloud'
                }
            }
            
        except Exception as e:
            logger.error(f"LlamaCloud extraction failed: {e}")
            raise
    
    async def _poll_for_results(
        self, 
        job_id: str, 
        max_attempts: int = 60
    ) -> Dict:
        """Poll LlamaCloud for processing results"""
        check_url = f"https://api.cloud.llamaindex.ai/api/v1/parsing/jobs/{job_id}"
        headers = {'Authorization': f'Bearer {self.api_key}'}
        
        for attempt in range(max_attempts):
            response = await self.client.get(check_url, headers=headers)
            
            if response.status_code != 200:
                raise Exception(f"Failed to check job status: {response.text}")
            
            job_status = response.json()
            
            if job_status['status'] == 'completed':
                return job_status['result']
            elif job_status['status'] == 'failed':
                raise Exception(f"LlamaCloud processing failed: {job_status.get('error')}")
            
            # Wait before next attempt
            await asyncio.sleep(5)
        
        raise Exception("LlamaCloud processing timeout")