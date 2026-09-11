import os
import json
import psycopg
from dotenv import load_dotenv

load_dotenv()

PG_HOST = os.getenv("PG_HOST", "127.0.0.1")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_DATABASE = os.getenv("PG_DATABASE", "mfc_data")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD")

def sync_data_elt(json_filepath):
    with open(json_filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    with psycopg.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DATABASE,
        user=PG_USER, password=PG_PASSWORD
    ) as conn:
        
        conn.execute("""
            CREATE TEMPORARY TABLE staging_services (
                id TEXT PRIMARY KEY,
                service_title_text TEXT,
                documents_text TEXT,
                payment_info_text TEXT,
                time_term_text TEXT,
                service_result_text TEXT,
                reject_reasons_text TEXT
            ) ON COMMIT DROP;
        """)
        
        conn.cursor().executemany("""
            INSERT INTO staging_services (
                id, service_title_text, documents_text, 
                payment_info_text, time_term_text, 
                service_result_text, reject_reasons_text
            ) VALUES (
                %(id)s, %(service_title_text)s, %(documents_text)s, 
                %(payment_info_text)s, %(time_term_text)s, 
                %(service_result_text)s, %(reject_reasons_text)s
            )
        """, data)

        result = conn.execute("""
            INSERT INTO services (
                id, 
                service_title_text, 
                documents_text, 
                payment_info_text, 
                time_term_text, 
                service_result_text, 
                reject_reasons_text,
                life_situation_ids_json,
                mfc_ids_json,
                recipient_ids_json,
                department_id,
                service_ordering_text,
                service_recipients,
                applicant_categories_json,
                description_text
            )
            SELECT 
                id, 
                service_title_text, 
                documents_text, 
                payment_info_text, 
                time_term_text, 
                service_result_text, 
                reject_reasons_text,
                '[]', -- life_situation_ids_json
                '[]', -- mfc_ids_json
                '[]', -- recipient_ids_json
                '',   -- department_id
                '',   -- service_ordering_text
                '',   -- service_recipients
                '[]', -- applicant_categories_json
                ''    -- description_text
            FROM staging_services
            
            ON CONFLICT (id) DO UPDATE SET 
                service_title_text = EXCLUDED.service_title_text,
                documents_text = EXCLUDED.documents_text,
                payment_info_text = EXCLUDED.payment_info_text,
                time_term_text = EXCLUDED.time_term_text,
                service_result_text = EXCLUDED.service_result_text,
                reject_reasons_text = EXCLUDED.reject_reasons_text
            WHERE 
                services.service_title_text IS DISTINCT FROM EXCLUDED.service_title_text OR
                services.documents_text IS DISTINCT FROM EXCLUDED.documents_text OR
                services.payment_info_text IS DISTINCT FROM EXCLUDED.payment_info_text OR
                services.time_term_text IS DISTINCT FROM EXCLUDED.time_term_text OR
                services.service_result_text IS DISTINCT FROM EXCLUDED.service_result_text OR
                services.reject_reasons_text IS DISTINCT FROM EXCLUDED.reject_reasons_text;
        """)

        

if __name__ == "__main__":
    sync_data_elt("test.json")
