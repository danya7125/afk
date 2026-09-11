import psycopg2

conn = psycopg2.connect(
    host="127.0.0.1",
    port=5432,
    database="mfc_data",
    user="postgres",
    password="psg_123"
)

print("PostgreSQL подключен!")

conn.close()