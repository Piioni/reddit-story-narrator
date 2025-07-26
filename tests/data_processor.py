import os
import sys
from dotenv import load_dotenv
from data_processor import ContentRetriever, NarrativeBuilder, TextOptimizer
from utils import StructuredLogger

class DataProcessorTester:   
    def __init__(self):
        load_dotenv()
        self.logger = StructuredLogger('DataProcessorTester')
        
        # Configuración de BD (igual que en main.py)
        self.db_config = {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'user': os.getenv('POSTGRES_USER', 'scraper'),
            'password': os.getenv('POSTGRES_PASSWORD', 'scraper_pass'),
            'port': int(os.getenv('POSTGRES_PORT', '5432'))
        }
        
        # Inicializar componentes
        self.content_retriever = ContentRetriever(self.db_config)
        self.narrative_builder = NarrativeBuilder()
        self.text_optimizer = TextOptimizer()
        
        print("🧪 DataProcessor Tester inicializado")
    
    def test_single_post(self, category: str):
        print(f"\n{'='*80}")
        print(f"🔍 PROBANDO CATEGORÍA: {category.upper()}")
        print(f"{'='*80}")
        
        try:
            # 1. Obtener un post no procesado
            print("\n📡 1. Obteniendo posts no procesados...")
            posts = self.content_retriever.get_unprocessed_posts(category, limit=1)
            
            if not posts:
                print(f"❌ No se encontraron posts no procesados en '{category}'")
                return False
            
            post = posts[0]
            print(f"✅ Post obtenido: {post.post_id}")
            print(f"   📝 Título: {post.title[:100]}...")
            print(f"   👤 Autor: {post.author}")
            print(f"   📊 Upvotes: {post.upvotes}")
            print(f"   🔄 Updates: {len(post.updates)}")
            print(f"   💬 Comentarios: {len(post.comments)}")
            
            # 2. Construir narrativa
            print(f"\n🏗️  2. Construyendo narrativa...")
            processed_content = self.narrative_builder.build_narrative(post, category)
            
            if not processed_content:
                print("❌ Error construyendo narrativa")
                return False
            
            print(f"✅ Narrativa construida")
            print(f"   📊 Palabras: {processed_content.word_count}")
            print(f"   ⏱️  Duración estimada: {processed_content.estimated_duration/60:.1f} minutos")
            print(f"   🧩 Segmentos: {len(processed_content.segments)}")
            
            # 3. Optimizar texto
            print(f"\n⚡ 3. Optimizando texto para TTS...")
            optimized_content = self.text_optimizer.optimize_content(processed_content)
            
            print(f"✅ Texto optimizado")
            print(f"   📊 Palabras después de optimización: {optimized_content.word_count}")
            print(f"   ⏱️  Duración final: {optimized_content.estimated_duration/60:.1f} minutos")
            
            # 4. Mostrar resultados
            self._show_detailed_results(post, optimized_content)
            
            return True
            
        except Exception as e:
            self.logger.error("Error en test", category=category, error=str(e))
            print(f"❌ Error: {e}")
            return False
    
# ...código existente...

    def _show_detailed_results(self, original_post, processed_content):
        print(f"\n{'='*80}")
        print("📋 RESULTADOS DETALLADOS")
        print(f"{'='*80}")
        
        # Información del post original
        print(f"\n📄 POST ORIGINAL:")
        print(f"   ID: {original_post.post_id}")
        print(f"   Título: {original_post.title}")
        print(f"   Texto original: {len(original_post.text)} caracteres")
        print(f"   Updates: {len(original_post.updates)}")
        print(f"   Comentarios: {len(original_post.comments)}")
        
        # Narrativa construida
        print(f"\n📝 NARRATIVA CONSTRUIDA:")
        print(f"   Palabras: {processed_content.word_count}")
        print(f"   Caracteres: {len(processed_content.narrative_text)}")
        print(f"   Segmentos: {len(processed_content.segments)}")
        
        print(f"\n📖 TEXTO NARRATIVA COMPLETO:")
        print(f"{'─'*80}")
        print(processed_content.narrative_text)
        
        # Texto optimizado COMPLETO
        print(f"\n⚡ TEXTO OPTIMIZADO COMPLETO PARA TTS:")
        print(f"{'─'*80}")
        print(processed_content.optimized_text)
        
        # TODOS los segmentos
        print(f"\n🧩 TODOS LOS SEGMENTOS PARA TTS ({len(processed_content.segments)} total):")
        print(f"{'─'*80}")
        for i, segment in enumerate(processed_content.segments, 1):
            print(f"\n[SEGMENTO {i:02d}] ({len(segment.split())} palabras)")
            print(f"{'▸'*40}")
            print(segment)
        
        # Estadísticas de optimización
        stats = self.text_optimizer.get_optimization_stats(
            processed_content.narrative_text, 
            processed_content.optimized_text
        )
        
        print(f"\n📊 ESTADÍSTICAS DE OPTIMIZACIÓN:")
        print(f"{'─'*80}")
        for key, value in stats.items():
            print(f"   {key}: {value}")
        
        # Análisis adicional
        print(f"\n🔍 ANÁLISIS ADICIONAL:")
        print(f"{'─'*80}")
        print(f"   Duración promedio por segmento: {processed_content.estimated_duration/len(processed_content.segments):.1f} segundos")
        print(f"   Palabras promedio por segmento: {processed_content.word_count/len(processed_content.segments):.1f}")
        print(f"   Segmento más largo: {max(len(seg.split()) for seg in processed_content.segments)} palabras")
        print(f"   Segmento más corto: {min(len(seg.split()) for seg in processed_content.segments)} palabras")
    
    def test_multiple_categories(self, categories: list):
        """Prueba múltiples categorías."""
        results = {}
        
        for category in categories:
            print(f"\n{'🔄'*20}")
            success = self.test_single_post(category)
            results[category] = success
            
            if success:
                print(f"✅ {category}: ÉXITO")
            else:
                print(f"❌ {category}: FALLÓ")
        
        # Resumen final
        print(f"\n{'='*80}")
        print("📊 RESUMEN DE PRUEBAS")
        print(f"{'='*80}")
        
        successful = sum(results.values())
        total = len(results)
        
        print(f"Categorías probadas: {total}")
        print(f"Exitosas: {successful}")
        print(f"Fallidas: {total - successful}")
        
        for category, success in results.items():
            status = "✅" if success else "❌"
            print(f"   {status} {category}")
    
    def list_available_categories(self):
        """Lista las categorías disponibles en la BD."""
        print("\n📂 CATEGORÍAS DISPONIBLES:")
        print("─"*50)
        
        # Estas deberían coincidir con las de tu main.py
        categories = [
            'aita',
            'relationship',
            'tifu',
            'legal',
            'work'
        ]
        
        for i, category in enumerate(categories, 1):
            print(f"{i}. {category}")
        
        return categories

def main():
    """Función principal del tester."""
    print("🧪 REDDIT DATA PROCESSOR TESTER")
    print("="*50)
    
    try:
        tester = DataProcessorTester()
        categories = tester.list_available_categories()
        
        print(f"\nSelecciona una opción:")
        print(f"1-{len(categories)}. Probar categoría específica")
        print(f"{len(categories) + 1}. Probar todas las categorías")
        print("0. Salir")
        
        while True:
            try:
                choice = input(f"\nOpción (0-{len(categories) + 1}): ").strip()
                choice_num = int(choice)
                
                if choice_num == 0:
                    print("👋 ¡Hasta luego!")
                    break
                elif 1 <= choice_num <= len(categories):
                    category = categories[choice_num - 1]
                    tester.test_single_post(category)
                elif choice_num == len(categories) + 1:
                    tester.test_multiple_categories(categories)
                else:
                    print("❌ Opción inválida")
                
                input("\n⏸️  Presiona Enter para continuar...")
                
            except ValueError:
                print("❌ Por favor ingresa un número válido")
            except KeyboardInterrupt:
                print("\n👋 ¡Hasta luego!")
                break
                
    except Exception as e:
        print(f"❌ Error crítico: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()