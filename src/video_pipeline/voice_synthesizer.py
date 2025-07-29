import azure.cognitiveservices.speech as speechsdk
from pathlib import Path
from typing import List, Dict
import json
import librosa

from data_models.video_models import ProcessedContent
from utils.logger import StructuredLogger

class VoiceSynthesizer:   
    def __init__(self, azure_config: Dict):
        self.logger = StructuredLogger('VoiceSynthesizer')
      
        # Configuración Azure SIMPLE
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

        print(f"VoiceSynthesizer inicializado correctamente")
    
    def synthesize_content(self, processed_content: ProcessedContent, output_dir: str) -> Dict:
        try:
            print(f"Iniciando síntesis")
            
            output_path = Path(output_dir)
            output_path.mkdir(exist_ok=True)
            
            # 1. Crear SSML
            full_ssml = self._create_simple_ssml(processed_content.segments)
            if not full_ssml:
                return {}
            
            # 2. Generar audio
            audio_file = output_path / "full_audio.wav"
            word_timings = self._generate_audio(full_ssml, str(audio_file))

            # 3. Verificar archivo
            if not audio_file.exists() or audio_file.stat().st_size == 0:
                print("Error: Archivo de audio no válido")
                return {}
            
            # 4. Obtener duración
            total_duration = librosa.get_duration(path=str(audio_file))
            
            # 6. Resultado
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
        
            if word_timings:
                with open(output_path / "word_timings.json", 'w') as f:
                    json.dump(word_timings, f, indent=2)
            
            print(f"🎉 ¡Audio generado exitosamente!")
            return result
            
        except Exception as e:
            print(f"Error en synthesize_content: {e}")
            import traceback
            traceback.print_exc()
            return {}
        
    def _create_simple_ssml(self, segments: List[str]) -> str:
        full_text = " ".join([segment for segment in segments if segment.strip()])
        
        if not full_text.strip():
            print("Texto final está vacío")
            return ""
        
        print(full_text)
        
        escaped_text = self._escape_xml_only(full_text)
        
        # SSML básico
        ssml = f"""
        <speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'>
            <voice name='{self.speech_config.speech_synthesis_voice_name}'>
                <prosody rate="1.1">
                    {escaped_text}
                </prosody>
            </voice>
        </speak>
        """
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
            print(f"Iniciando síntesis Azure")
        
            # Lista para guardar word timings
            word_timings = []

            def word_callback(evt: speechsdk.SpeechSynthesisWordBoundaryEventArgs):
                start_seconds = evt.audio_offset / 10000000.0

                timing = {
                    'word': evt.text.strip(),
                    'start': start_seconds,
                    'end': None,  
                    'duration': None  
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
            
            print(f"Síntesis completada")
            print(f"Word timings capturados: {len(word_timings)}")
            
            if result is None:
                print(f"Error: Resultado de síntesis es None")
                return []

            print(f"Reason: {result.reason}")

            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                print(f"Audio generado exitosamente")
                return word_timings
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation = result.cancellation_details
                print(f"Síntesis cancelada")
                print(f"Error: {cancellation.error_details}")
                return []
            else:
                print(f"Error: Síntesis falló: {result.reason}")
                return []

        except Exception as e:
            print(f"Error en _generate_audio: {e}")
            return []


    def _calculate_end_times(self, word_timings: List[Dict]) -> List[Dict]:
        if not word_timings:
            return []
        
        print(f"🔧 Calculando end times para {len(word_timings)} palabras...")
        
        for i, timing in enumerate(word_timings):
            if i < len(word_timings) - 1:
                # End = start de la siguiente palabra
                timing['end'] = word_timings[i + 1]['start']
            else:
                # Última palabra - estimar duración
                char_count = len(timing['word'])
                estimated_duration = max(0.15, char_count * 0.07)
                timing['end'] = timing['start'] + estimated_duration
            
            # Calcular duración
            timing['duration'] = timing['end'] - timing['start']
        
        return word_timings
