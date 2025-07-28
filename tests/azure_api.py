import os

import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.append(str(Path(__file__).parent.parent / 'src'))


from data_processor.content_retriever import ContentRetriever
from data_processor.narrative_builder import NarrativeBuilder
from data_processor.text_optimizer import TextOptimizer
from video_pipeline.voice_synthesizer import VoiceSynthesizer

def test_voice_synthesis():
    load_dotenv()
    
    print("🎤 Iniciando prueba de VoiceSynthesizer...")
    
    azure_config = {
        'SPEECH_KEY': os.getenv('AZURE_SPEECH_KEY'),
        'SPEECH_REGION': os.getenv('AZURE_SPEECH_REGION', 'uksouth'),
        'SPEECH_VOICE': os.getenv('AZURE_VOICE_NAME', 'en-US-JennyNeural')
    }
    
    print(f"✅ Azure configurado - Región: {azure_config['SPEECH_REGION']}")
    print(f"🎭 Voz seleccionada: {azure_config['SPEECH_VOICE']}")
    
    # Configuración BD
    db_config = {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'user': os.getenv('POSTGRES_USER', 'scraper'),
        'password': os.getenv('POSTGRES_PASSWORD', 'scraper_pass'),
        'port': int(os.getenv('POSTGRES_PORT', '5432')),
    }
    
    try:
        print("\n📊 Conectando a base de datos...")
        
        # 1. Obtener contenido procesado
        retriever = ContentRetriever(db_config)
        posts = retriever.get_unprocessed_posts('aita', limit=1)
        
        if not posts:
            print("❌ No hay posts para procesar")
            return
        
        post = posts[0]
        print(f"📝 Post seleccionado: {post.title[:60]}...")
        
        # 2. Procesar contenido
        print("\n🔄 Procesando contenido...")
        
        builder = NarrativeBuilder()
        content = builder.build_narrative(post, 'aita')
        
        if not content:
            print("❌ Error: No se pudo generar contenido narrativo")
            return
        
        optimizer = TextOptimizer()
        content = optimizer.optimize_content(content)
        
        print(f"✅ Contenido procesado: {len(content.segments)} segmentos")
        
        # 3. Sintetizar voz
        print(f"\n🎤 Iniciando síntesis de voz...")
        
        synthesizer = VoiceSynthesizer(azure_config)
        
        output_dir = f"test_audio/{post.post_id}"
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        audio_data = synthesizer.synthesize_content(content, output_dir)
        
        if audio_data:
            print(f"🎵 Audio generado: {audio_data['audio_file']}")
            print(f"⏱️ Duración: {audio_data['total_duration']:.1f}s")
        else:
            print("❌ Error generando audio")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_voice_synthesis()