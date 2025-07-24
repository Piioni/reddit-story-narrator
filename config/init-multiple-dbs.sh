#!/bin/bash
set -e  # Detener si hay error
echo "🚀 Creando múltiples bases de datos para Reddit Scraper..."

# Definir categorías y sus subreddits
declare -A DATABASES=(
    ["aita_stories"]="AmItheAsshole AITAH"
    ["relationship_stories"]="relationship_advice relationships"
    ["legal_stories"]="legaladvice bestoflegaladvice"
    ["work_stories"]="antiwork MaliciousCompliance pettyrevenge"
)

# Base de datos administrativa
echo "📊 Creando base de datos administrativa..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "postgres" <<-EOSQL
    CREATE DATABASE reddit_admin;
    GRANT ALL PRIVILEGES ON DATABASE reddit_admin TO $POSTGRES_USER;
EOSQL

# Crear schema administrativo COMPLETO
echo "📋 Creando schema administrativo..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "reddit_admin" <<-EOSQL
    -- Configuración de categorías
    CREATE TABLE IF NOT EXISTS categories (
        id SERIAL PRIMARY KEY,
        category_name TEXT UNIQUE NOT NULL,
        database_name TEXT UNIQUE NOT NULL,
        subreddits TEXT[] NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active BOOLEAN DEFAULT TRUE
    );

    -- Estadísticas por categoría
    CREATE TABLE IF NOT EXISTS category_stats (
        id SERIAL PRIMARY KEY,
        category_name TEXT UNIQUE NOT NULL,
        last_scrape TIMESTAMP,
        total_posts INTEGER DEFAULT 0,
        total_updates INTEGER DEFAULT 0,
        total_comments INTEGER DEFAULT 0,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Logs de scraping
    CREATE TABLE IF NOT EXISTS scraping_logs (
        id SERIAL PRIMARY KEY,
        category TEXT NOT NULL,
        database_name TEXT NOT NULL,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ended_at TIMESTAMP,
        posts_scraped INTEGER DEFAULT 0,
        errors_count INTEGER DEFAULT 0,
        status TEXT DEFAULT 'running'
    );
EOSQL

# Crear bases de datos de contenido
echo "📁 Creando bases de datos de contenido..."
for db_name in "${!DATABASES[@]}"; do
    subreddits=${DATABASES[$db_name]}
    echo "🔨 Creando base de datos: $db_name"
    
    # Crear la base de datos
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "postgres" <<-EOSQL
        CREATE DATABASE $db_name;
        GRANT ALL PRIVILEGES ON DATABASE $db_name TO $POSTGRES_USER;
EOSQL

    # Aplicar schema a la nueva DB
    echo "📋 Aplicando schema a: $db_name"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$db_name" < /tmp/schema.sql
    # Registrar en la DB administrativa
    category_name=${db_name%_stories}
    subreddits_array="{$(echo $subreddits | sed 's/ /,/g')}"
    
    echo "📊 Registrando categoría: $category_name"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "reddit_admin" <<-EOSQL
        INSERT INTO categories (category_name, database_name, subreddits, description) 
        VALUES ('$category_name', '$db_name', '$subreddits_array', 'Database for $subreddits stories')
        ON CONFLICT (category_name) DO UPDATE SET 
            subreddits = EXCLUDED.subreddits,
            description = EXCLUDED.description;
            
        INSERT INTO category_stats (category_name) 
        VALUES ('$category_name')
        ON CONFLICT (category_name) DO NOTHING;
EOSQL

    echo "✅ Base de datos $db_name configurada correctamente"
done

echo "🎉 Todas las bases de datos han sido creadas exitosamente!"
echo "📊 Base de datos administrativa: reddit_admin"
echo "📁 Bases de datos de contenido: ${!DATABASES[*]}"