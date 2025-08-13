import azure.cognitiveservices.speech as speechsdk
import json
import librosa

from utils import ProcessedContent, StructuredLogger
from pathlib import Path
from typing import List, Dict

class VoiceSynthesizer:   
    def __init__(self, azure_config: Dict):
        self.logger = StructuredLogger('VoiceSynthesizer')
      
        # Configuración Azure
        self.speech_config = speechsdk.SpeechConfig(
            subscription=azure_config['SPEECH_KEY'],
            region=azure_config['SPEECH_REGION'],
        )
        
        self.speech_config.speech_synthesis_voice_name = azure_config["SPEECH_VOICE"]
        self.speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Riff24Khz16BitMonoPcm
        )

        self.speech_config.set_property(
            property_id=speechsdk.PropertyId.SpeechServiceResponse_RequestWordLevelTimestamps,
            value="true"
        )
        
        self.logger.info("VoiceSynthesizer inicializado", extra={
            'voice': azure_config["SPEECH_VOICE"],
            'region': azure_config['SPEECH_REGION']
        })
    
    def synthesize_content(self, processed_content: ProcessedContent, output_dir: str) -> Dict:
        try:
            self.logger.info("Iniciando síntesis de audio", extra={
                'segments_count': len(processed_content.segments),
                'output_dir': output_dir
            })
            
            output_path = Path(output_dir)
            output_path.mkdir(exist_ok=True)
            
            # 1. Crear SSML
            full_ssml = self._create_simple_ssml(processed_content.segments)
            if not full_ssml:
                self.logger.error("No se pudo crear SSML válido")
                return {}
            
            # 2. Generar audio
            audio_file = output_path / "full_audio.wav"
            word_timings = self._generate_audio(full_ssml, str(audio_file))

            # 3. Verificar archivo
            if not audio_file.exists() or audio_file.stat().st_size == 0:
                self.logger.error("Archivo de audio no válido", extra={
                    'file_exists': audio_file.exists(),
                    'file_size': audio_file.stat().st_size if audio_file.exists() else 0
                })
                return {}
            
            # 4. Obtener duración
            total_duration = librosa.get_duration(path=str(audio_file))
            
            # 5. Resultado
            result = {
                'audio_file': str(audio_file),
                'total_duration': total_duration,
                'segment_count': len(processed_content.segments),
                'segments': processed_content.segments,
                'word_timings': word_timings
            }
            
            # Guardar metadata
            with open(output_path / "audio_metadata.json", 'w') as f:
                json.dump(result, f, indent=2, default=str)  

            
            self.logger.info("Audio generado exitosamente", extra={
                'total_duration': f"{total_duration:.2f}s",
                'word_count': len(word_timings),
                'file_size_mb': f"{audio_file.stat().st_size / (1024*1024):.2f}"
            })
            
            return result
            
        except Exception as e:
            self.logger.error("Error en synthesize_content", extra={
                'error': str(e),
                'error_type': type(e).__name__
            })
            return {}
        
    def _create_simple_ssml(self, segments: List[str]) -> str:
        full_text = " ".join([segment for segment in segments if segment.strip()])
        
        if not full_text.strip():
            self.logger.warning("Texto final está vacío")
            return ""
        
        escaped_text = self._escape_xml_only(full_text)
        
        # SSML básico
        ssml = f"""
        <speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'>
            <voice name='{self.speech_config.speech_synthesis_voice_name}'>
                <prosody rate="1.1">
                    {escaped_text}
                </prosody>
            </voice>
        </speak>"""
        
        return ssml

    def _escape_xml_only(self, text: str) -> str:
        if not text:
            return ""
        
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&apos;')
        
        return text

    def _generate_audio(self, ssml: str, output_file: str) -> List[Dict]:
        try:
            self.logger.info("Iniciando síntesis Azure TTS")
            
            # Lista para guardar word timings
            word_timings = []

            def word_callback(evt: speechsdk.SpeechSynthesisWordBoundaryEventArgs):
                start_seconds = float(evt.audio_offset) / 10000000.0
                duration_seconds = float(evt.duration.total_seconds())
                end_seconds = start_seconds + duration_seconds
                
                timing = {
                    'word': evt.text.strip(),
                    'start': round(start_seconds, 3),
                    'end': round(end_seconds, 3),
                    'duration': round(duration_seconds, 3)
                }
                word_timings.append(timing)
                    
                
            # Configurar salida de audio
            audio_config = speechsdk.audio.AudioOutputConfig(filename=output_file)
            synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=self.speech_config,
                audio_config=audio_config
            )
            
            synthesizer.synthesis_word_boundary.connect(word_callback)

            # Sintetizar
            result = synthesizer.speak_ssml_async(ssml).get()
            
            if result is None:
                self.logger.error("Resultado de síntesis es None")
                return []

            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                self.logger.info("Síntesis Azure completada exitosamente", extra={
                    'word_timings_count': len(word_timings)
                })
                return word_timings
                
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation = result.cancellation_details
                self.logger.error("Síntesis cancelada por Azure", extra={
                    'error_code': str(cancellation.error_code),
                    'error_details': cancellation.error_details
                })
                return []
                
            else:
                self.logger.error("Síntesis falló", extra={
                    'reason': str(result.reason)
                })
                return []

        except Exception as e:
            self.logger.error("Error en _generate_audio", extra={
                'error': str(e),
                'error_type': type(e).__name__
            })
            return []
