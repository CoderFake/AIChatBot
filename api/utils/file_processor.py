import os
import platform
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from langchain_core.documents import Document
from transformers import AutoTokenizer

is_arm = platform.machine() in ["arm64", "aarch64"]
cpu_count = os.cpu_count() or 4

thread_count = min(cpu_count // 2 if is_arm else cpu_count, 8)
os.environ["OMP_NUM_THREADS"] = str(thread_count)
os.environ["MKL_NUM_THREADS"] = str(thread_count)
os.environ["OPENBLAS_NUM_THREADS"] = str(thread_count)

try:
    import docling
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.chunking import HybridChunker
    from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False

try:
    from unstructured.partition.auto import partition
    UNSTRUCTURED_AVAILABLE = True
except ImportError:
    UNSTRUCTURED_AVAILABLE = False

from langchain_community.document_loaders import (
    PyPDFLoader, 
    Docx2txtLoader,
    TextLoader,
    UnstructuredHTMLLoader,
    UnstructuredPowerPointLoader,
    UnstructuredExcelLoader,
    CSVLoader
)
from langchain_text_splitters import RecursiveCharacterTextSplitter

try:
    import fitz
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

from utils.logging import get_logger

logger = get_logger(__name__)

class FileProcessor:
    """
    Advanced document processor with HybridChunker for automatic token-aware chunking.
    
    Supports Docling formats: PDF, DOCX, PPTX, XLSX, HTML, CSV, PNG, JPEG, TIFF, BMP,
    Markdown, AsciiDoc, and text files with intelligent fallback strategies.
    """
    
    DOCLING_FORMATS = {
        '.pdf', '.docx', '.pptx', '.xlsx', '.html', '.htm', '.csv',
        '.png', '.jpeg', '.jpg', '.tiff', '.tif', '.bmp', '.md', '.txt'
    }
    
    LANGCHAIN_FORMATS = {
        '.pdf', '.docx', '.doc', '.txt', '.md', '.html', '.htm', 
        '.pptx', '.ppt', '.xlsx', '.xls', '.csv'
    }
    
    SUPPORTED_EXTENSIONS = DOCLING_FORMATS.union(LANGCHAIN_FORMATS)
    
    def __init__(self, 
                 tokenizer_name: str = "BAAI/bge-m3",
                 max_tokens: int = 1500,
                 enable_hybrid_chunking: bool = True):
        """
        Initialize FileProcessor with AutoTokenizer and HybridChunker.
        
        Args:
            tokenizer_name: HuggingFace tokenizer model name
            max_tokens: Maximum tokens per chunk for automatic calculation
            enable_hybrid_chunking: Enable HybridChunker for structure-aware chunking
        """
        self.tokenizer_name = tokenizer_name
        self.max_tokens = max_tokens
        self.enable_hybrid_chunking = enable_hybrid_chunking
        
        self._initialize_tokenizer()
        self._initialize_chunkers()
        self._check_dependencies()
        self._setup_docling_converter()
        
        logger.info(f"FileProcessor initialized - Tokenizer: {tokenizer_name} | Max tokens: {max_tokens} | Hybrid chunking: {enable_hybrid_chunking} | Threads: {thread_count}")
    
    def _initialize_tokenizer(self):
        """Load AutoTokenizer from HuggingFace for token-based chunking."""
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.tokenizer_name,
                trust_remote_code=True
            )
            logger.info(f"Successfully initialized tokenizer: {self.tokenizer_name}")
        except Exception as e:
            logger.error(f"Failed to initialize tokenizer {self.tokenizer_name}: {e}")
            self.tokenizer = None
    
    def _initialize_chunkers(self):
        """Initialize HybridChunker with AutoTokenizer for automatic token calculation."""
        self.hybrid_chunker = None
        
        if DOCLING_AVAILABLE and self.enable_hybrid_chunking and self.tokenizer:
            try:
                hf_tokenizer = HuggingFaceTokenizer(
                    tokenizer=self.tokenizer,
                    max_tokens=self.max_tokens
                )
                
                self.hybrid_chunker = HybridChunker(
                    tokenizer=hf_tokenizer,
                    merge_peers=True
                )
                logger.info(f"HybridChunker initialized with max_tokens: {self.max_tokens}")
                
            except Exception as e:
                logger.error(f"Failed to initialize HybridChunker: {e}")
        
        self._initialize_fallback_text_splitter()
    
    def _initialize_fallback_text_splitter(self):
        """Initialize fallback RecursiveCharacterTextSplitter with token-based length function."""
        try:
            if self.tokenizer:
                def token_length_function(text: str) -> int:
                    """Calculate exact token count using AutoTokenizer."""
                    try:
                        return len(self.tokenizer.encode(text))
                    except Exception:
                        return len(text.split())
                
                self.text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=self.max_tokens,
                    chunk_overlap=200,
                    length_function=token_length_function,
                    separators=["\n\n", "\n", ". ", " ", ""],
                    add_start_index=True
                )
                logger.info("RecursiveCharacterTextSplitter with AutoTokenizer-based length function")
            else:
                self.text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=1500,
                    chunk_overlap=200,
                    separators=["\n\n", "\n", ". ", " ", ""],
                    add_start_index=True
                )
                logger.warning("Using character-based RecursiveCharacterTextSplitter")
                
        except Exception as e:
            logger.error(f"Failed to initialize text splitter: {e}")
            self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)
    
    def _setup_docling_converter(self):
        """Setup Docling DocumentConverter for advanced document processing."""
        if DOCLING_AVAILABLE:
            try:
                pipeline_options = PdfPipelineOptions()
                
                if is_arm:
                    pipeline_options.generate_page_images = False
                    pipeline_options.images_scale = 0.5
                else:
                    pipeline_options.generate_page_images = True
                    pipeline_options.images_scale = 1.0
                    
                pipeline_options.do_table_structure = True
                pipeline_options.table_structure_options.do_cell_matching = True
                
                self.docling_converter = DocumentConverter(
                    format_options={
                        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                    }
                )
                logger.info("Docling DocumentConverter initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Docling converter: {e}")
                self.docling_converter = None
        else:
            self.docling_converter = None
    
    def _check_dependencies(self):
        """Check and log available document processing dependencies."""
        if DOCLING_AVAILABLE:
            logger.info("Docling available - advanced document processing enabled")
        elif UNSTRUCTURED_AVAILABLE:
            logger.warning("Docling not available, using Unstructured as fallback")
        else:
            logger.warning("Neither Docling nor Unstructured available, basic loaders only")
    
    def _chunk_with_hybrid_chunker(self, docling_document) -> List[Document]:
        """
        Chunk DoclingDocument using HybridChunker for structure-aware, token-optimal chunking.
        
        - Automatically calculates optimal chunk sizes based on tokenizer
        - Preserves document structure and context
        - Merges undersized chunks and splits oversized ones
        """
        try:
            chunks = []
            chunk_iter = self.hybrid_chunker.chunk(dl_doc=docling_document)
            
            for i, chunk in enumerate(chunk_iter):
                serialized_text = self.hybrid_chunker.serialize(chunk=chunk)
                
                token_count = self._count_tokens(chunk.text) if self.tokenizer else len(chunk.text.split())
                
                doc = Document(
                    page_content=serialized_text,
                    metadata={
                        "chunk_index": i,
                        "token_count": token_count,
                        "chunk_type": "hybrid",
                        "raw_text_length": len(chunk.text),
                        "serialized_text_length": len(serialized_text),
                        "chunk_meta": chunk.meta.model_dump() if hasattr(chunk.meta, 'model_dump') else str(chunk.meta)
                    }
                )
                chunks.append(doc)
            
            logger.info(f"HybridChunker created {len(chunks)} structure-aware chunks")
            return chunks
            
        except Exception as e:
            logger.error(f"HybridChunker error: {e}")
            raise
    
    def _chunk_with_text_splitter(self, text: str) -> List[Document]:
        """
        Fallback chunking using RecursiveCharacterTextSplitter with token-based calculation.
        
        - Uses AutoTokenizer for accurate token counting
        - Respects max_tokens limit automatically
        """
        try:
            initial_doc = Document(page_content=text)
            chunks = self.text_splitter.split_documents([initial_doc])
            
            for i, chunk in enumerate(chunks):
                token_count = self._count_tokens(chunk.page_content) if self.tokenizer else len(chunk.page_content.split())
                chunk.metadata.update({
                    "chunk_index": i,
                    "token_count": token_count,
                    "chunk_type": "recursive_splitter"
                })
            
            logger.info(f"RecursiveCharacterTextSplitter created {len(chunks)} token-aware chunks")
            return chunks
            
        except Exception as e:
            logger.error(f"Text splitter error: {e}")
            raise
    
    def _count_tokens(self, text: str) -> int:
        """Calculate exact token count using AutoTokenizer."""
        try:
            if self.tokenizer:
                return len(self.tokenizer.encode(text))
            else:
                return len(text.split())
        except Exception:
            return len(text.split())
    
    async def process_file(
        self,
        file_path: str,
        file_name: str,
        doc_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Process file with intelligent strategy selection for optimal chunking.
        
        Strategy 1: Docling + HybridChunker (for supported formats)
        Strategy 2: Text extraction + token-based RecursiveCharacterTextSplitter
        """
        try:
            file_extension = Path(file_name).suffix.lower()
            
            if file_extension not in self.SUPPORTED_EXTENSIONS:
                raise ValueError(f"Unsupported file type: {file_extension}")
            
            base_metadata = {
                "doc_id": doc_id,
                "source": file_name,
                "file_type": file_extension,
                "tokenizer_name": self.tokenizer_name,
                "max_tokens": self.max_tokens
            }
            
            if metadata:
                base_metadata.update(metadata)
            
            chunks = await self._extract_and_chunk_with_strategy(file_path, file_extension, base_metadata)
            
            for i, chunk in enumerate(chunks):
                chunk.metadata.update({
                    "chunk_id": f"{doc_id}_chunk_{i}",
                    "total_chunks": len(chunks),
                    "chunk_length": len(chunk.page_content),
                    "processed_with": self._get_processor_used()
                })
                chunk.metadata.update(base_metadata)
            
            total_tokens = sum(chunk.metadata.get("token_count", 0) for chunk in chunks)
            logger.info(f"Processed {file_name}: {len(chunks)} chunks, {total_tokens} total tokens")
            return chunks
            
        except Exception as e:
            logger.error(f"Error processing file {file_name}: {e}")
            raise
    
    async def _extract_and_chunk_with_strategy(
        self, 
        file_path: str, 
        file_extension: str, 
        base_metadata: Dict[str, Any]
    ) -> List[Document]:
        """
        Intelligent document processing with strategy selection.
        
        Priority: Docling + HybridChunker > Text extraction + RecursiveCharacterTextSplitter
        """
        
        if (self.docling_converter and self.hybrid_chunker and 
            file_extension in self.DOCLING_FORMATS):
            try:
                logger.debug(f"Strategy 1: Docling + HybridChunker for {file_path}")
                result = self.docling_converter.convert(file_path)
                docling_document = result.document
                
                chunks = self._chunk_with_hybrid_chunker(docling_document)
                logger.info("Successfully used Docling + HybridChunker")
                return chunks
                
            except Exception as e:
                logger.warning(f"Docling + HybridChunker failed: {e}, falling back to text extraction")
        
        extracted_text = await self._extract_text_with_fallback_chain(file_path, file_extension)
        
        if not extracted_text or not extracted_text.strip():
            raise ValueError("No text content extracted from file")
        
        chunks = self._chunk_with_text_splitter(extracted_text)
        return chunks
    
    async def _extract_text_with_fallback_chain(self, file_path: str, file_extension: str) -> str:
        """
        Multi-strategy text extraction with intelligent fallbacks.
        
        Chain: Docling markdown export > Unstructured > Enhanced LangChain loaders
        """
        extraction_methods = []
        
        if self.docling_converter and file_extension in self.DOCLING_FORMATS:
            extraction_methods.append(("Docling", self._extract_with_docling))
        
        if UNSTRUCTURED_AVAILABLE:
            extraction_methods.append(("Unstructured", self._extract_with_unstructured))
        
        extraction_methods.append(("LangChain", lambda fp: self._extract_with_langchain(fp, file_extension)))
        
        for method_name, method_func in extraction_methods:
            try:
                logger.debug(f"Attempting extraction with {method_name} for {file_path}")
                text_content = await method_func(file_path)
                
                if text_content and text_content.strip():
                    logger.info(f"Successfully extracted text using {method_name}")
                    return text_content
                else:
                    logger.warning(f"{method_name} returned empty content, trying next method")
                    
            except Exception as e:
                logger.warning(f"{method_name} extraction failed: {e}, trying next method")
                continue
        
        raise ValueError("All extraction methods failed to produce valid text content")
    
    async def _extract_with_docling(self, file_path: str) -> str:
        """Extract text using Docling DocumentConverter with markdown export."""
        try:
            result = self.docling_converter.convert(file_path)
            text_content = result.document.export_to_markdown()
            
            logger.debug(f"Docling extracted {len(text_content)} characters")
            return text_content
            
        except Exception as e:
            logger.error(f"Docling extraction error: {e}")
            raise
    
    async def _extract_with_unstructured(self, file_path: str) -> str:
        """Extract text using Unstructured with automatic format detection."""
        try:
            elements = partition(filename=file_path)
            
            text_content = "\n\n".join([
                element.text for element in elements 
                if hasattr(element, 'text') and element.text.strip()
            ])
            
            logger.debug(f"Unstructured extracted {len(text_content)} characters")
            return text_content
            
        except Exception as e:
            logger.error(f"Unstructured extraction error: {e}")
            raise
    
    async def _extract_with_langchain(self, file_path: str, file_extension: str) -> str:
        """
        Enhanced LangChain loaders with multiple PDF strategies and format-specific optimization.
        
        PDF: PDFPlumber > PyMuPDF > PyPDF fallback chain
        Others: Format-specific optimized loaders
        """
        try:
            documents = []
            
            if file_extension == '.pdf':
                if PDFPLUMBER_AVAILABLE:
                    try:
                        import pdfplumber
                        with pdfplumber.open(file_path) as pdf:
                            text_content = ""
                            for page in pdf.pages:
                                page_text = page.extract_text()
                                if page_text:
                                    text_content += page_text + "\n"
                        if text_content.strip():
                            logger.debug(f"PDFPlumber extracted {len(text_content)} characters")
                            return text_content
                    except Exception as e:
                        logger.warning(f"PDFPlumber failed: {e}")
                
                if PYMUPDF_AVAILABLE:
                    try:
                        import fitz
                        doc = fitz.open(file_path)
                        text_content = ""
                        for page in doc:
                            text_content += page.get_text() + "\n"
                        doc.close()
                        if text_content.strip():
                            logger.debug(f"PyMuPDF extracted {len(text_content)} characters")
                            return text_content
                    except Exception as e:
                        logger.warning(f"PyMuPDF failed: {e}")
                
                loader = PyPDFLoader(file_path)
                
            elif file_extension in {'.docx', '.doc'}:
                loader = Docx2txtLoader(file_path)
            elif file_extension in {'.pptx', '.ppt'}:
                loader = UnstructuredPowerPointLoader(file_path)
            elif file_extension in {'.xlsx', '.xls'}:
                loader = UnstructuredExcelLoader(file_path)
            elif file_extension == '.csv':
                try:
                    import pandas as pd
                    df = pd.read_csv(file_path)
                    text_content = df.to_string(index=False)
                    logger.debug(f"Pandas CSV extracted {len(text_content)} characters")
                    return text_content
                except Exception as e:
                    logger.warning(f"Pandas CSV failed: {e}")
                    loader = CSVLoader(file_path)
            elif file_extension in {'.txt', '.md'}:
                loader = TextLoader(file_path, encoding='utf-8')
            elif file_extension in {'.html', '.htm'}:
                loader = UnstructuredHTMLLoader(file_path)
            else:
                loader = TextLoader(file_path, encoding='utf-8')
            
            documents = loader.load()
            text_content = "\n\n".join([doc.page_content for doc in documents])
            
            logger.debug(f"LangChain loader extracted {len(text_content)} characters")
            return text_content
            
        except Exception as e:
            logger.error(f"LangChain loader extraction error: {e}")
            raise
    
    def _get_processor_used(self) -> str:
        """Get the primary processor that was successfully used."""
        if self.hybrid_chunker:
            return "docling_hybrid_chunker"
        elif self.docling_converter:
            return "docling_text_splitter"
        elif UNSTRUCTURED_AVAILABLE:
            return "unstructured"
        else:
            return "langchain_basic"
    
    def get_chunker_info(self) -> Dict[str, Any]:
        """Get comprehensive information about current chunker configuration."""
        return {
            "tokenizer_name": self.tokenizer_name,
            "max_tokens": self.max_tokens,
            "hybrid_chunking_enabled": self.enable_hybrid_chunking,
            "hybrid_chunker_available": self.hybrid_chunker is not None,
            "docling_available": DOCLING_AVAILABLE,
            "tokenizer_available": self.tokenizer is not None,
            "supported_docling_formats": sorted(list(self.DOCLING_FORMATS)),
            "supported_langchain_formats": sorted(list(self.LANGCHAIN_FORMATS)),
            "total_supported_formats": len(self.SUPPORTED_EXTENSIONS)
        }
    
    def get_supported_extensions(self) -> List[str]:
        """Get list of all supported file extensions."""
        return sorted(list(self.SUPPORTED_EXTENSIONS))
    
    def is_supported_file(self, file_name: str) -> bool:
        """Check if file type is supported by any available processor."""
        extension = Path(file_name).suffix.lower()
        return extension in self.SUPPORTED_EXTENSIONS
    
    def is_docling_supported(self, file_name: str) -> bool:
        """Check if file is supported by Docling for advanced processing."""
        extension = Path(file_name).suffix.lower()
        return extension in self.DOCLING_FORMATS and DOCLING_AVAILABLE
    
    async def batch_process_files(
        self,
        file_infos: List[Dict[str, Any]],
        batch_size: int = 10
    ) -> List[Document]:
        """
        Process multiple files in batches with async support and error handling.
        
        - Processes files in parallel batches
        - Individual file error handling
        - Progress tracking and logging
        """
        import asyncio
        
        all_documents = []
        
        for i in range(0, len(file_infos), batch_size):
            batch = file_infos[i:i + batch_size]
            
            batch_tasks = [
                self.process_file(
                    file_info['file_path'],
                    file_info['file_name'],
                    file_info['doc_id'],
                    file_info.get('metadata')
                )
                for file_info in batch
            ]
            
            try:
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                for j, result in enumerate(batch_results):
                    if isinstance(result, Exception):
                        logger.error(f"Failed to process file {batch[j]['file_name']}: {result}")
                    else:
                        all_documents.extend(result)
                        
            except Exception as e:
                logger.error(f"Batch processing error: {e}")
        
        logger.info(f"Batch processed {len(file_infos)} files -> {len(all_documents)} document chunks")
        return all_documents