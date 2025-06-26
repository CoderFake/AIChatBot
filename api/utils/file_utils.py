import os
import tempfile
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from langchain_community.document_loaders import (
    UnstructuredExcelLoader,
    UnstructuredHTMLLoader,
    UnstructuredMarkdownLoader,
    UnstructuredPowerPointLoader,
    UnstructuredWordDocumentLoader,
    UnstructuredPDFLoader,
    UnstructuredCSVLoader,
    UnstructuredFileLoader  # Generic loader cho các file types khác
)

from langchain_core.documents import Document

from common.types import Department, FileType
from services.dataclasses.milvus import ChunkingConfig
from utils.logging import get_logger
from utils.datetime_utils import CustomDateTime
from config.settings import get_settings

logger = get_logger(__name__)


class UnstructuredFileProcessor:
    
    def __init__(self):
        self.settings = get_settings()
        
        self.department_collections = {
            Department.HR: "hr_documents",
            Department.IT: "it_documents", 
            Department.FINANCE: "finance_documents",
            Department.ADMIN: "general_documents",
            Department.GENERAL: "general_documents"
        }
        
        self.loader_mapping = {
            '.pdf': UnstructuredPDFLoader,
            '.docx': UnstructuredWordDocumentLoader,
            '.doc': UnstructuredWordDocumentLoader,
            '.xlsx': UnstructuredExcelLoader,
            '.xls': UnstructuredExcelLoader,
            '.pptx': UnstructuredPowerPointLoader,
            '.ppt': UnstructuredPowerPointLoader,
            '.html': UnstructuredHTMLLoader,
            '.htm': UnstructuredHTMLLoader,
            '.md': UnstructuredMarkdownLoader,
            '.csv': UnstructuredCSVLoader,
            '.txt': UnstructuredFileLoader,  
            '.rtf': UnstructuredFileLoader,
            '.xml': UnstructuredFileLoader,
            '.json': UnstructuredFileLoader
        }
        
        self.supported_extensions = set(self.loader_mapping.keys())
    
    def get_collection_name(self, department: Department) -> str:
        """Get Milvus collection name từ Department"""
        return self.department_collections.get(department, "general_documents")
    
    def is_supported_file(self, filename: str) -> bool:
        """Check xem file có được support bởi Unstructured không"""
        extension = Path(filename).suffix.lower()
        return extension in self.supported_extensions
    
    def get_file_type(self, filename: str) -> FileType:
        """Determine FileType từ filename"""
        extension = Path(filename).suffix.lower()
        
        mapping = {
            '.pdf': FileType.PDF,
            '.docx': FileType.DOCX,
            '.doc': FileType.DOC,
            '.txt': FileType.TXT,
            '.md': FileType.MD,
            '.xlsx': FileType.XLSX,
            '.pptx': FileType.PPTX
        }
        
        return mapping.get(extension, FileType.TXT)
    
    def _get_loader_class(self, filename: str):
        """Get appropriate Unstructured loader class cho file type"""
        extension = Path(filename).suffix.lower()
        return self.loader_mapping.get(extension, UnstructuredFileLoader)
    
    def calculate_chunking_config(self, file_size: int, estimated_text_length: int = None) -> ChunkingConfig:
        """
        Calculate optimal chunking configuration dựa trên file size
        
        Args:
            file_size: Size của file trong bytes
            estimated_text_length: Estimated text length (optional)
            
        Returns:
            ChunkingConfig object
        """
        config = ChunkingConfig()
        
        if file_size < 10 * 1024:  # < 10KB - small files
            config.size_multiplier = 0.3
            config.base_chunk_size = 200
            config.base_overlap = 20
            
        elif file_size < 50 * 1024:  # < 50KB - small files  
            config.size_multiplier = 0.5
            config.base_chunk_size = 400
            config.base_overlap = 50
            
        elif file_size < 200 * 1024:  # < 200KB - medium files
            config.size_multiplier = 0.8
            config.base_chunk_size = 800
            config.base_overlap = 100
            
        elif file_size < 1 * 1024 * 1024:  # < 1MB - medium-large files
            config.size_multiplier = 1.0
            config.base_chunk_size = 1000
            config.base_overlap = 150
            
        elif file_size < 5 * 1024 * 1024:  # < 5MB - large files
            config.size_multiplier = 1.2
            config.base_chunk_size = 1200
            config.base_overlap = 200
            
        elif file_size < 10 * 1024 * 1024:  # < 10MB - very large files
            config.size_multiplier = 1.5
            config.base_chunk_size = 1500
            config.base_overlap = 250
            
        else:  # >= 10MB - huge files
            config.size_multiplier = 2.0
            config.base_chunk_size = 2000
            config.base_overlap = 400
        
        # Apply multiplier
        config.base_chunk_size = int(config.base_chunk_size * config.size_multiplier)
        config.base_overlap = int(config.base_overlap * config.size_multiplier)
        
        # Ensure within bounds
        config.base_chunk_size = max(config.min_chunk_size, 
                                   min(config.max_chunk_size, config.base_chunk_size))
        config.base_overlap = min(config.base_chunk_size // 4, config.base_overlap)
        
        # Adjust based on estimated text length if provided
        if estimated_text_length:
            if estimated_text_length < config.base_chunk_size:
                # File nhỏ, giảm chunk size
                config.base_chunk_size = max(config.min_chunk_size, estimated_text_length // 2)
                config.base_overlap = config.base_chunk_size // 10
        
        logger.info(
            f"Calculated chunking config for file_size={file_size}: "
            f"chunk_size={config.base_chunk_size}, overlap={config.base_overlap}, "
            f"multiplier={config.size_multiplier}"
        )
        
        return config
    
    async def extract_text_with_unstructured(
        self, 
        file_content: bytes, 
        filename: str,
        **kwargs
    ) -> Tuple[str, List[Document]]:
        """
        Extract text sử dụng appropriate Unstructured loader
        
        Args:
            file_content: Raw file content
            filename: Original filename
            **kwargs: Additional parameters for Unstructured
            
        Returns:
            Tuple of (full_text, documents_list)
        """
     
        if not self.is_supported_file(filename):
            raise ValueError(f"File type not supported: {filename}")
        
        temp_file_path = None
        
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(
                delete=False, 
                suffix=Path(filename).suffix
            ) as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name
            
            # Get appropriate loader class
            LoaderClass = self._get_loader_class(filename)
            
            # Configure loader parameters
            loader_kwargs = {
                "mode": kwargs.get("mode", "elements"),  # Default to elements mode
                "strategy": kwargs.get("strategy", "auto"),  # Auto-detect best strategy
                **{k: v for k, v in kwargs.items() if k not in ["mode", "strategy"]}
            }
            
            # Local processing
            logger.info(f"Using Unstructured local processing for {filename}")
            
            # Create loader instance
            loader = LoaderClass(temp_file_path, **loader_kwargs)
            
            # Load documents
            documents = loader.load()
            
            # Extract full text
            full_text = "\n".join(doc.page_content for doc in documents)
            
            logger.info(
                f"Extracted {len(documents)} elements, {len(full_text)} chars from {filename} "
                f"using {LoaderClass.__name__}"
            )
            
            return full_text, documents
            
        except Exception as e:
            logger.error(f"Unstructured extraction failed for {filename}: {e}")
            # Fallback to simple text extraction
            return await self._fallback_text_extraction(file_content, filename), []
            
        finally:
            # Cleanup temp file
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file {temp_file_path}: {e}")
    
    async def _fallback_text_extraction(self, file_content: bytes, filename: str) -> str:
        """Fallback text extraction cho khi Unstructured fails"""
        extension = Path(filename).suffix.lower()
        
        try:
            if extension == '.txt' or extension == '.md':
                return file_content.decode('utf-8', errors='ignore')
            elif extension == '.pdf':
                return await self._extract_pdf_fallback(file_content)
            elif extension in ['.docx', '.doc']:
                return await self._extract_docx_fallback(file_content)
            else:
                return file_content.decode('utf-8', errors='ignore')
                
        except Exception as e:
            logger.error(f"Fallback extraction failed for {filename}: {e}")
            return ""
    
    async def _extract_pdf_fallback(self, file_content: bytes) -> str:
        """Fallback PDF extraction"""
        try:
            import PyPDF2
            import io
            
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text.strip()
        except Exception:
            return ""
    
    async def _extract_docx_fallback(self, file_content: bytes) -> str:
        """Fallback DOCX extraction"""
        try:
            import docx
            import io
            
            doc = docx.Document(io.BytesIO(file_content))
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text.strip()
        except Exception:
            return ""
    
    def create_smart_chunks(
        self, 
        text: str, 
        documents: List[Document],
        config: ChunkingConfig,
        preserve_structure: bool = True
    ) -> List[Dict[str, Any]]:
       
        chunks = []
        
        if preserve_structure and documents:
            chunks = self._create_structured_chunks(documents, config)
        else:
            chunks = self._create_text_chunks(text, config)
        
        for i, chunk in enumerate(chunks):
            chunk.update({
                "chunk_index": i,
                "total_chunks": len(chunks),
                "chunking_method": "structured" if preserve_structure and documents else "text_based",
                "chunk_size": len(chunk["content"]),
                "config_used": config.__dict__
            })
        
        logger.info(f"Created {len(chunks)} chunks using {chunks[0]['chunking_method'] if chunks else 'unknown'} method")
        
        return chunks
    
    def _create_structured_chunks(self, documents: List[Document], config: ChunkingConfig) -> List[Dict[str, Any]]:
        """Create chunks preserve structure từ Unstructured documents"""
        chunks = []
        current_chunk = ""
        current_metadata = {}
        
        for doc in documents:
            element_text = doc.page_content.strip()
            element_metadata = doc.metadata
            
            if not element_text:
                continue
            
            potential_chunk = current_chunk + "\n" + element_text if current_chunk else element_text
            
            if len(potential_chunk) <= config.base_chunk_size:
                current_chunk = potential_chunk
                current_metadata.update(element_metadata)
            else:
                if current_chunk:
                    chunks.append({
                        "content": current_chunk.strip(),
                        "metadata": current_metadata.copy(),
                        "source_elements": len(current_metadata)
                    })
                
                if config.base_overlap > 0 and current_chunk:
                    overlap_text = current_chunk[-config.base_overlap:]
                    current_chunk = overlap_text + "\n" + element_text
                else:
                    current_chunk = element_text
                
                current_metadata = element_metadata.copy()
        
        if current_chunk:
            chunks.append({
                "content": current_chunk.strip(),
                "metadata": current_metadata.copy(),
                "source_elements": len(current_metadata)
            })
        
        return chunks
    
    def _create_text_chunks(self, text: str, config: ChunkingConfig) -> List[Dict[str, Any]]:
        """Create simple text-based chunks"""
        chunks = []
        
        sentences = text.split('. ')
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            sentence_with_period = sentence + ". " if not sentence.endswith('.') else sentence + " "
            
            potential_chunk = current_chunk + sentence_with_period
            
            if len(potential_chunk) <= config.base_chunk_size:
                current_chunk = potential_chunk
            else:
                if current_chunk.strip():
                    chunks.append({
                        "content": current_chunk.strip(),
                        "metadata": {},
                        "sentences": current_chunk.count('. ') + 1
                    })
                
                if config.base_overlap > 0 and current_chunk:
                    overlap_text = current_chunk[-config.base_overlap:]
                    current_chunk = overlap_text + sentence_with_period
                else:
                    current_chunk = sentence_with_period
        
        if current_chunk.strip():
            chunks.append({
                "content": current_chunk.strip(),
                "metadata": {},
                "sentences": current_chunk.count('. ') + 1
            })
        
        return chunks
    
    def generate_document_hash(self, file_content: bytes) -> str:
        """Generate unique hash cho document content"""
        return hashlib.sha256(file_content).hexdigest()
    
    async def process_document_for_milvus(
        self,
        file_content: bytes,
        filename: str,
        department: Department,
        metadata: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Complete pipeline để process document cho Milvus
        
        Args:
            file_content: Raw file content
            filename: Original filename  
            department: Department enum cho collection mapping
            metadata: Additional metadata
            **kwargs: Additional parameters
            
        Returns:
            Processing result dictionary
        """
        try:
            collection_name = self.get_collection_name(department)
            
            file_size = len(file_content)
            file_hash = self.generate_document_hash(file_content)
            file_type = self.get_file_type(filename)
            
            extracted_text, documents = await self.extract_text_with_unstructured(
                file_content, filename, **kwargs
            )
            
            if not extracted_text.strip():
                raise ValueError("No text content extracted from file")
            
            chunking_config = self.calculate_chunking_config(file_size, len(extracted_text))
            
            chunks = self.create_smart_chunks(
                extracted_text, 
                documents, 
                chunking_config,
                preserve_structure=kwargs.get('preserve_structure', True)
            )
            
            if not chunks:
                raise ValueError("No chunks created from document")
            
            enhanced_metadata = {
                **metadata,
                "filename": filename,
                "file_size": file_size,
                "file_hash": file_hash,
                "file_type": file_type.value,
                "department": department.value,
                "text_length": len(extracted_text),
                "extraction_method": "unstructured",
                "processing_timestamp": CustomDateTime.now().isoformat(),
                "total_chunks": len(chunks),
                "chunking_config": chunking_config.__dict__
            }
            
            return {
                "success": True,
                "collection_name": collection_name,
                "file_hash": file_hash,
                "extracted_text": extracted_text,
                "chunks": chunks,
                "metadata": enhanced_metadata,
                "chunking_config": chunking_config,
                "processing_stats": {
                    "file_size": file_size,
                    "text_length": len(extracted_text),
                    "chunks_created": len(chunks),
                    "avg_chunk_size": sum(len(c["content"]) for c in chunks) // len(chunks),
                    "structured_elements": len(documents) if documents else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Document processing failed for {filename}: {e}")
            return {
                "success": False,
                "error": str(e),
                "filename": filename,
                "file_size": len(file_content) if file_content else 0
            }


unstructured_processor = UnstructuredFileProcessor()
