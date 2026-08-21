import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Apenas escopo de leitura do calendário
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def obter_credenciais():
    creds = None
    # O arquivo token.json armazena os tokens de acesso e de atualização do usuário, e é criado automaticamente quando o fluxo de autorização é concluído pela primeira vez.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # Se não houver credenciais válidas disponíveis, faz o fluxo de login do usuário
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Passo 156 e 157: Usa o arquivo baixado do Google Cloud
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Salva as credenciais/refresh token localmente para os próximos acessos
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return creds

if __name__ == '__main__':
    creds = obter_credenciais()
    print("Autorização concluída com sucesso! Arquivo 'token.json' gerado.")