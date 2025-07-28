import azure.cognitiveservices.speech as speechsdk
from pathlib import Path
from typing import List, Dict, Optional
import json
import librosa
import re

from data_models.video_models import ProcessedContent
from utils.logger import StructuredLogger

class VoiceSynthesizer:   
    def __init__(self, azure_config: Dict):
        self.logger = StructuredLogger('VoiceSynthesizer')
        
        print(f"🔧 DEBUG: Inicializando VoiceSynthesizer")
        print(f"   Key: {azure_config['SPEECH_KEY'][:10]}...")
        print(f"   Region: {azure_config['SPEECH_REGION']}")
        print(f"   Voice: {azure_config['SPEECH_VOICE']}")
        
        # Configuración Azure SIMPLE
        self.speech_config = speechsdk.SpeechConfig(
            subscription=azure_config['SPEECH_KEY'],
            region=azure_config['SPEECH_REGION'],
        )
        
        self.speech_config.speech_synthesis_voice_name = azure_config["SPEECH_VOICE"]
        self.speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm
        )
        
        print(f"✅ VoiceSynthesizer inicializado correctamente")
    
    def synthesize_content(self, processed_content: ProcessedContent, output_dir: str) -> Dict:
        try:
            print(f"🔧 DEBUG: Iniciando síntesis SIMPLE")
            print(f"   Segmentos: {len(processed_content.segments)}")
            print(f"   Output dir: {output_dir}")
            
            output_path = Path(output_dir)
            output_path.mkdir(exist_ok=True)
            
            # 1. Crear SSML
            print(f"🔧 DEBUG: Creando SSML...")
            full_ssml = self._create_simple_ssml(processed_content.segments)
            
            if not full_ssml:
                print("❌ DEBUG: No se pudo crear SSML")
                return {}
            
            # 2. Generar audio
            audio_file = output_path / "full_audio.wav"
            print(f"🔧 DEBUG: Generando audio en: {audio_file}")
            
            success = self._generate_audio(full_ssml, str(audio_file))
            
            if not success:
                print("❌ DEBUG: Error generando audio")
                return {}
            
            # 3. Verificar archivo
            if not audio_file.exists() or audio_file.stat().st_size == 0:
                print("❌ DEBUG: Archivo de audio no válido")
                return {}
            
            # 4. Obtener duración
            total_duration = librosa.get_duration(path=str(audio_file))
            print(f"✅ DEBUG: Audio generado - Duración: {total_duration:.1f}s")
            
            
            # 6. Resultado
            result = {
                'audio_file': str(audio_file),
                'total_duration': total_duration,
                'segment_count': len(processed_content.segments)
            }
            
            # Guardar metadata
            with open(output_path / "audio_metadata.json", 'w') as f:
                json.dump(result, f, indent=2, default=str)
            
            print(f"🎉 ¡Audio generado exitosamente!")
            return result
            
        except Exception as e:
            print(f"❌ DEBUG: Error en synthesize_content: {e}")
            import traceback
            traceback.print_exc()
            return {}
        
    def _create_simple_ssml(self, segments: List[str]) -> str:
        print(f"🔧 DEBUG: Procesando {len(segments)} segmentos")
        
        # ✅ CAMBIAR: NO llamar _clean_text(), el texto YA está optimizado
        full_text = " ".join([segment for segment in segments if segment.strip()])
        
        if not full_text.strip():
            print("❌ DEBUG: Texto final está vacío")
            return ""
        
        # ✅ SOLO escapar caracteres XML (mínimo procesamiento)
        full_text = self._escape_xml_only(full_text)
        print(full_text)
        
        # SSML básico
        ssml = f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'>
        <voice name='{self.speech_config.speech_synthesis_voice_name}'>
            <prosody rate="1.1">
                {full_text}
            </prosody>
        </voice>
    </speak>"""
        
        print(f"✅ DEBUG: SSML creado ({len(ssml)} caracteres)")
        return ssml

    def _escape_xml_only(self, text: str) -> str:
        """SOLO escapa caracteres XML, sin modificar el contenido."""
        if not text:
            return ""
        
        # SOLO escapar XML - NO tocar el contenido optimizado
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&apos;')
        
        return text

    def _generate_audio(self, ssml: str, output_file: str) -> bool:
        """Genera el archivo de audio SIN word timings."""
        try:
            print(f"🔧 DEBUG: Iniciando síntesis Azure")
            
            # Configurar salida de audio
            audio_config = speechsdk.audio.AudioOutputConfig(filename=output_file)
            synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=self.speech_config,
                audio_config=audio_config
            )
            
            # Sintetizar (SIMPLE)
            result = synthesizer.speak_ssml_async(ssml).get()
            
            print(f"🔧 DEBUG: Síntesis completada")
            
            if result is None:
                print(f"❌ DEBUG: Resultado de síntesis es None")
                return False
            
            print(f"   Reason: {result.reason}")
            
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                print(f"✅ DEBUG: Audio generado exitosamente")
                return True
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation = result.cancellation_details
                print(f"❌ DEBUG: Síntesis cancelada")
                print(f"   Error: {cancellation.error_details}")
                return False
            else:
                print(f"❌ DEBUG: Síntesis falló: {result.reason}")
                return False
                
        except Exception as e:
            print(f"❌ DEBUG: Error en _generate_audio: {e}")
            return False
    