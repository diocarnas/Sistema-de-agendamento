import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

class Config:
    # Chave secreta para sessões e cookies
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'chave-padrao-de-desenvolvimento'
    
    # Configuração do Banco de Dados
    DB_USER = os.environ.get('DB_USER') or 'root'
    DB_PASS = os.environ.get('DB_PASS') or 'senha_padrao'  # <-- Removida a sua senha real daqui
    DB_HOST = os.environ.get('DB_HOST') or 'localhost'
    DB_NAME = os.environ.get('DB_NAME') or 'sistema_quadras'

    SQLALCHEMY_DATABASE_URI = f'mysql+mysqlconnector://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False