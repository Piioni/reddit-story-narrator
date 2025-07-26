import re
from typing import Dict, List
from data_models.video_models import ProcessedContent
from utils.logger import StructuredLogger

class TextOptimizer: 
    def __init__(self):
        self.logger = StructuredLogger('TextOptimizer')
        
        # Common Reddit abbreviations and replacements
        self.abbreviations = {
            'AITA': 'Am I The A-hole',
            'NTA': 'Not The A-hole',
            'YTA': 'You\'re The A-hole',
            'ESH': 'Everyone Sucks Here',
            'NAH': 'No A-holes Here',
            'SO': 'significant other',
            'BF': 'boyfriend',
            'GF': 'girlfriend',
            'BFF': 'best friend',
            'MIL': 'mother in law',
            'FIL': 'father in law',
            'SIL': 'sister in law',
            'BIL': 'brother in law',
            'TL;DR': 'Too long, didn\'t read',
            'TLDR': 'Too long, didn\'t read',
            'IMO': 'In my opinion',
            'IMHO': 'In my humble opinion',
            'BTW': 'By the way',
            'FYI': 'For your information',
            'TBH': 'To be honest',
            'OP': 'Original Poster',
            'DH': 'Dear Husband',
            'DW': 'Dear Wife',
            'LTR': 'Long Term Relationship'
        }
        
        # Number to word conversions for better TTS
        self.number_words = {
            '1': 'one', '2': 'two', '3': 'three', '4': 'four', '5': 'five',
            '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine', '10': 'ten'
        }
    
    def optimize_content(self, content: ProcessedContent) -> ProcessedContent:
        """
        Optimize processed content for TTS synthesis.
        
        Args:
            content: ProcessedContent with narrative text
            
        Returns:
            ProcessedContent with optimized text for TTS
        """
        try:
            # Optimize main narrative
            optimized_narrative = self._optimize_text(content.narrative_text)
            
            # Optimize individual segments
            optimized_segments = [
                self._optimize_text(segment) for segment in content.segments
            ]
            
            # Update content with optimized text
            content.optimized_text = optimized_narrative
            content.segments = optimized_segments
            
            # Recalculate word count after optimization
            new_word_count = len(optimized_narrative.split())
            content.word_count = new_word_count
            
            # Recalculate duration (assuming 150 WPM)
            content.estimated_duration = (new_word_count / 150) * 60
            
            self.logger.info("Text optimization completed", 
                           post_id=content.post_id,
                           original_words=len(content.narrative_text.split()),
                           optimized_words=new_word_count)
            
            return content
            
        except Exception as e:
            self.logger.error("Error optimizing text", 
                            post_id=content.post_id, error=str(e))
            return content
    
    def _optimize_text(self, text: str) -> str:
        """Core text optimization for TTS."""
        if not text:
            return ""
        
        # 1. Replace abbreviations first
        text = self._replace_abbreviations(text)
        
        # 2. Normalize numbers and ages
        text = self._normalize_numbers(text)
        
        # 3. Fix contractions that TTS struggles with
        text = self._fix_contractions(text)
        
        # 4. Fix pronunciation issues
        text = self._fix_pronunciation(text)
        
        # 5. Add natural pauses where needed
        text = self._add_natural_pauses(text)
        
        # 6. Final cleanup
        text = self._final_cleanup(text)
        
        return text.strip()
    
    def _replace_abbreviations(self, text: str) -> str:
        """Replace Reddit abbreviations with full forms."""
        for abbrev, full_form in self.abbreviations.items():
            # Use word boundaries to avoid partial replacements
            pattern = r'\b' + re.escape(abbrev) + r'\b'
            text = re.sub(pattern, full_form, text, flags=re.IGNORECASE)
        
        return text
    
    def _normalize_numbers(self, text: str) -> str:
        """Normalize numbers for better TTS pronunciation."""
        # Replace standalone single digits with words
        for digit, word in self.number_words.items():
            pattern = r'\b' + digit + r'\b'
            text = re.sub(pattern, word, text)
        
        # Handle ages more naturally (25M -> 25 year old male)
        text = re.sub(r'\b(\d{1,2})[Mm]\b', r'\1 year old male', text)
        text = re.sub(r'\b(\d{1,2})[Ff]\b', r'\1 year old female', text)
        
        # Handle money amounts
        text = re.sub(r'\$(\d+)k\b', r'\1 thousand dollars', text, flags=re.IGNORECASE)
        text = re.sub(r'\$(\d+)K\b', r'\1 thousand dollars', text)
        text = re.sub(r'\$(\d+)\b', r'\1 dollars', text)
        
        # Handle time formats (24/7 -> twenty four seven)
        text = re.sub(r'\b24/7\b', 'twenty four seven', text)
        text = re.sub(r'\b(\d{1,2})/(\d{1,2})\b', r'\1 out of \2', text)
        
        return text
    
    def _fix_contractions(self, text: str) -> str:
        """Fix contractions that cause TTS issues."""
        contractions = {
            "won't": "will not",
            "can't": "cannot",
            "shouldn't": "should not",
            "wouldn't": "would not",
            "couldn't": "could not",
            "mustn't": "must not",
            "don't": "do not",
            "doesn't": "does not",
            "didn't": "did not",
            "isn't": "is not",
            "aren't": "are not",
            "wasn't": "was not",
            "weren't": "were not",
            "haven't": "have not",
            "hasn't": "has not",
            "hadn't": "had not"
        }
        
        for contraction, expansion in contractions.items():
            text = re.sub(r'\b' + re.escape(contraction) + r'\b', 
                         expansion, text, flags=re.IGNORECASE)
        
        return text
    
    def _fix_pronunciation(self, text: str) -> str:
        """Fix common pronunciation issues for TTS."""
        # Common internet slang and abbreviations
        replacements = {
            r'\bOMG\b': 'Oh my god',
            r'\bWTF\b': 'What the heck',
            r'\bLOL\b': 'Laughing out loud',
            r'\bLMAO\b': 'Laughing my butt off',
            r'\bROFL\b': 'Rolling on the floor laughing',
            r'\bIKR\b': 'I know right',
            r'\bTBF\b': 'To be fair',
            r'\bTBH\b': 'To be honest',
            r'\bIRL\b': 'In real life',
            r'\bAFK\b': 'Away from keyboard',
            r'\bFML\b': 'F my life',
            r'\bSMH\b': 'Shaking my head'
        }
        
        for pattern, replacement in replacements.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        # Fix common typing errors that affect pronunciation
        text = re.sub(r'\bthru\b', 'through', text, flags=re.IGNORECASE)
        text = re.sub(r'\bu\b', 'you', text, flags=re.IGNORECASE)
        text = re.sub(r'\bur\b', 'your', text, flags=re.IGNORECASE)
        text = re.sub(r'\br\b', 'are', text, flags=re.IGNORECASE)
        
        # Fix all caps words (except known abbreviations) - TTS often mispronounces them
        def fix_caps(match):
            word = match.group(0)
            # Keep known abbreviations in caps
            if word in self.abbreviations or len(word) <= 3:
                return word
            return word.lower()
        
        text = re.sub(r'\b[A-Z]{4,}\b', fix_caps, text)
        
        return text
    
    def _add_natural_pauses(self, text: str) -> str:
        """Add natural pauses for better TTS flow."""
        # Add comma after introductory phrases if not already present
        intro_phrases = [
            'So basically', 'Long story short', 'To make things worse',
            'Here\'s the thing', 'The problem is', 'What happened was',
            'To be honest', 'To be fair', 'At the end of the day',
            'All things considered', 'On the other hand'
        ]
        
        for phrase in intro_phrases:
            # Only add comma if there isn't already punctuation
            pattern = f'{re.escape(phrase)}(?![,.:;!?])'
            text = re.sub(pattern, f'{phrase},', text, flags=re.IGNORECASE)
        
        # Ensure commas after transition words
        transitions = ['However', 'Meanwhile', 'Subsequently', 'Nevertheless', 
                      'Furthermore', 'Additionally', 'Moreover', 'Therefore']
        for word in transitions:
            pattern = f'{re.escape(word)} (?![,.:;!?])'
            text = re.sub(pattern, f'{word}, ', text, flags=re.IGNORECASE)
        
        return text
    
    def _final_cleanup(self, text: str) -> str:
        """Final cleanup and normalization."""
        # Fix multiple punctuation
        text = re.sub(r'[.]{2,}', '.', text)
        text = re.sub(r'[!]{2,}', '!', text)
        text = re.sub(r'[?]{2,}', '?', text)
        
        # Fix spacing around punctuation
        text = re.sub(r'\s+([.!?])', r'\1', text)
        text = re.sub(r'([.!?])\s+', r'\1 ', text)
        
        # Clean up extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Ensure sentences end with proper punctuation for TTS pauses
        # Add period if sentence doesn't end with punctuation
        if text and not text[-1] in '.!?':
            text += '.'
        
        return text.strip()
    
    def get_optimization_stats(self, original_text: str, optimized_text: str) -> Dict[str, int]:
        """Get statistics about the optimization process."""
        return {
            'original_words': len(original_text.split()) if original_text else 0,
            'optimized_words': len(optimized_text.split()) if optimized_text else 0,
            'original_chars': len(original_text) if original_text else 0,
            'optimized_chars': len(optimized_text) if optimized_text else 0,
            'abbreviations_replaced': len([abbr for abbr in self.abbreviations.keys() 
                                         if abbr.lower() in original_text.lower()]) if original_text else 0
        }