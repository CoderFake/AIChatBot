"""
Summary Tool implementation
"""
import re
from typing import Dict, Any, Optional, Type, List
from langchain_core.tools import BaseTool
from langchain_core.callbacks import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun
from langchain_core.prompts import PromptTemplate
from langchain_core.language_models import BaseLanguageModel
from langchain_core.documents import Document
from pydantic import BaseModel, Field
from api.models.models import SummaryInput
from utils.logging import get_logger

logger = get_logger(__name__)


class SummaryTool(BaseTool):
    """
    Summary tool for text summarization
    Provides various types of text summarization including concise, bullet points, detailed summaries
    """
    name = "summary"
    description = "Summarizes text content in various formats including concise summaries, bullet points, and detailed analysis."
    args_schema: Type[BaseModel] = SummaryInput
    
    def __init__(self, llm: Optional[BaseLanguageModel] = None, **kwargs):
        super().__init__(**kwargs)
        self.llm = llm
        logger.info("Initialized summary tool")

    def _create_summary_prompt(self, summary_type: str, max_length: Optional[int] = None, 
                              focus_areas: Optional[str] = None, language: str = "english") -> PromptTemplate:
        """Create appropriate prompt based on summary type"""
        
        base_instruction = f"Please provide a summary in {language}."
        
        if max_length:
            length_instruction = f" Keep the summary under {max_length} words."
        else:
            length_instruction = ""
        
        if focus_areas:
            focus_instruction = f" Focus specifically on these areas: {focus_areas}."
        else:
            focus_instruction = ""
        
        if summary_type == "concise":
            template = f"""
{base_instruction} Create a concise, clear summary that captures the main points and key information.{length_instruction}{focus_instruction}

Text to summarize:
{{text}}

Concise Summary:
"""
        
        elif summary_type == "bullet_points":
            template = f"""
{base_instruction} Create a summary using bullet points that highlight the key information and main points.{length_instruction}{focus_instruction}

Text to summarize:
{{text}}

Bullet Point Summary:
"""
        
        elif summary_type == "detailed":
            template = f"""
{base_instruction} Create a detailed summary that covers all important aspects, key arguments, and supporting details.{length_instruction}{focus_instruction}

Text to summarize:
{{text}}

Detailed Summary:
"""
        
        elif summary_type == "executive":
            template = f"""
{base_instruction} Create an executive summary suitable for decision-makers, focusing on key insights, recommendations, and actionable information.{length_instruction}{focus_instruction}

Text to summarize:
{{text}}

Executive Summary:
"""
        
        elif summary_type == "key_points":
            template = f"""
{base_instruction} Extract and summarize the key points, main arguments, and essential information.{length_instruction}{focus_instruction}

Text to summarize:
{{text}}

Key Points Summary:
"""
        
        else:  
            template = f"""
{base_instruction} Create a clear and informative summary.{length_instruction}{focus_instruction}

Text to summarize:
{{text}}

Summary:
"""
        
        return PromptTemplate(input_variables=["text"], template=template)

    def _clean_text(self, text: str) -> str:
        """Clean and preprocess text for summarization"""
        text = re.sub(r'\s+', ' ', text)
        
        lines = text.split('\n')
        cleaned_lines = [line.strip() for line in lines if len(line.strip()) > 10]
        
        text = ' '.join(cleaned_lines)

        return text.strip()

    def _extract_text_statistics(self, text: str) -> Dict[str, int]:
        """Extract basic statistics about the text"""
        words = text.split()
        sentences = text.split('.')
        paragraphs = text.split('\n\n')
        
        return {
            "word_count": len(words),
            "sentence_count": len([s for s in sentences if s.strip()]),
            "paragraph_count": len([p for p in paragraphs if p.strip()]),
            "character_count": len(text)
        }

    def _create_fallback_summary(self, text: str, summary_type: str, max_length: Optional[int] = None) -> str:
        """Create a basic summary without LLM (fallback method)"""
        
        cleaned_text = self._clean_text(text)
        
        sentences = [s.strip() for s in cleaned_text.split('.') if s.strip()]
        
        if not sentences:
            return self._create_fallback_summary(cleaned_text, summary_type, max_length)

    def _run(
        self,
        text: str,
        summary_type: str = "concise",
        max_length: Optional[int] = None,
        focus_areas: Optional[str] = None,
        language: str = "english",
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """
        Execute text summarization synchronously
        
        Args:
            text: Text content to summarize
            summary_type: Type of summary to generate
            max_length: Maximum length in words
            focus_areas: Specific areas to focus on
            language: Output language
            run_manager: Optional callback manager for tool run
            
        Returns:
            Generated summary
        """
        logger.info(f"Generating {summary_type} summary")
        
        result = self._perform_summarization(
            text=text,
            summary_type=summary_type,
            max_length=max_length,
            focus_areas=focus_areas,
            language=language
        )
        
        logger.info(f"Summary generation completed")
        return result

    async def _arun(
        self,
        text: str,
        summary_type: str = "concise",
        max_length: Optional[int] = None,
        focus_areas: Optional[str] = None,
        language: str = "english",
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """
        Execute text summarization asynchronously
        
        Args:
            text: Text content to summarize
            summary_type: Type of summary to generate
            max_length: Maximum length in words
            focus_areas: Specific areas to focus on
            language: Output language
            run_manager: Optional async callback manager for tool run
            
        Returns:
            Generated summary
        """
        logger.info(f"Generating {summary_type} summary async")
        
        
        try:
            if self.llm and hasattr(self.llm, 'ainvoke'):
                cleaned_text = self._clean_text(text)
                
                if not cleaned_text.strip():
                    return "Error: No text provided for summarization"
                
                if len(cleaned_text) < 50:
                    return "Error: Text too short for meaningful summarization"
                
                try:
                    prompt = self._create_summary_prompt(summary_type, max_length, focus_areas, language)
                    formatted_prompt = prompt.format(text=cleaned_text)
                    response = await self.llm.ainvoke(formatted_prompt)
                    
                    if hasattr(response, 'content'):
                        summary = response.content
                    elif isinstance(response, str):
                        summary = response
                    else:
                        summary = str(response)
                    
                    summary = summary.strip()
                    
                    if summary_type == "detailed":
                        stats = self._extract_text_statistics(cleaned_text)
                        summary += f"\n\nOriginal text statistics: {stats['word_count']} words, {stats['sentence_count']} sentences, {stats['paragraph_count']} paragraphs."
                    
                    return summary
                    
                except Exception as e:
                    logger.error(f"Async LLM summarization failed: {e}")
                    return self._create_fallback_summary(cleaned_text, summary_type, max_length)
            else:
                return self._run(
                    text=text,
                    summary_type=summary_type,
                    max_length=max_length,
                    focus_areas=focus_areas,
                    language=language,
                    run_manager=None
                )
                
        except Exception as e:
            logger.error(f"Async summary error: {e}")
            return f"Error during async summarization: {str(e)}" "Unable to generate summary: No valid sentences found."
        

    def _perform_summarization(
        self,
        text: str,
        summary_type: str,
        max_length: Optional[int],
        focus_areas: Optional[str],
        language: str
    ) -> str:
        """Perform the actual summarization"""
        
        if not text.strip():
            return "Error: No text provided for summarization"
        
        cleaned_text = self._clean_text(text)
        
        if len(cleaned_text) < 50:
            return "Error: Text too short for meaningful summarization"
        
        stats = self._extract_text_statistics(cleaned_text)
        logger.info(f"Text statistics: {stats}")
        
        if not self.llm:
            logger.info("Using fallback summarization method")
            return self._create_fallback_summary(cleaned_text, summary_type, max_length)
        
        try:
            prompt = self._create_summary_prompt(summary_type, max_length, focus_areas, language)
            
            formatted_prompt = prompt.format(text=cleaned_text)
            response = self.llm.invoke(formatted_prompt)
            
            if hasattr(response, 'content'):
                summary = response.content
            elif isinstance(response, str):
                summary = response
            else:
                summary = str(response)
            
            summary = summary.strip()
            
            if summary_type == "detailed":
                summary += f"\n\nOriginal text statistics: {stats['word_count']} words, {stats['sentence_count']} sentences, {stats['paragraph_count']} paragraphs."
            
            return summary
            
        except Exception as e:
            logger.error(f"LLM summarization failed: {e}")
            logger.info("Falling back to basic summarization")
            return