# ProjetoAutomacao

# 📅 FETT — Sincronização Google Calendar & Automação de Mensageria

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supabase-316192?style=flat&logo=postgresql&logoColor=white)
![GCP](https://img.shields.io/badge/Google_Cloud-4285F4?style=flat&logo=google-cloud&logoColor=white)

Microsserviço orientado a eventos desenvolvido para automatizar réguas de comunicação e sincronizar compromissos da agenda corporativa via **Google Calendar API** com disparos automáticos de lembretes pela **WhatsApp Cloud API (Meta)**.

---

## 📌 Funcionalidades Principais

* **Sincronização em Tempo Real:** Criação e renovação periódica de canais de *watch* (webhooks) integrados ao Google Calendar.
* **Worker & Agendamento Assíncrono:** Execução em segundo plano via **APScheduler** para processamento de filas e cálculo dinâmico de *offsets* de notificação.
* **Validação Estrita & ORM:** Modelagem de dados com **Pydantic** e persistência relacional com **SQLAlchemy**.
* **Tratamento de Leads:** Rota de recepção de webhooks de parceiros/CRM com limpeza e formatação de contatos.
* **Containerização Cloud:** Ambiente isolado via **Docker** preparado para deploy em Google Cloud com persistência no Supabase.

---

## 🛠️ Stack Tecnológica

| Componente | Tecnologia |
| :--- | :--- |
| **Linguagem & Framework** | Python 3.11+, FastAPI |
| **Banco de Dados & ORM** | PostgreSQL (Supabase), SQLAlchemy |
| **Manipulação de Dados** | Pandas, Pydantic |
| **Agendador de Tarefas** | APScheduler |
| **Mensageria & APIs** | Google Calendar API, Meta for Developers (WhatsApp API) |
| **Container & Deploy** | Docker, Google Cloud Platform |
| **Qualidade & Linting** | Ruff |

---

## 📂 Estrutura do Projeto

```text
FETT/
├── app/
│   ├── config.py            # Carregamento de variáveis de ambiente
│   ├── crm_client_real.py   # Integração com API de CRM externo
│   ├── crm_service.py       # Lógica de resolução de contatos
│   ├── database.py          # Sessão e engine do SQLAlchemy
│   ├── main.py              # Aplicação FastAPI e rotas de webhook
│   ├── models.py            # Tabelas do banco (CalendarEvent, Contact, etc.)
│   ├── parser.py            # Tratamento e normalização de payloads
│   ├── services.py          # Lógica de sincronização e controle de canais
│   ├── webhook.py           # Processamento de retornos e logs da Meta
│   ├── whatsapp.py          # Cliente HTTP para envio de mensagens
│   └── worker.py            # Loop assíncrono de consumo de jobs
├── google/
│   └── criar_watch.py       # Script de registro do canal Google Watch
├── tests/
│   └── test_concorrencia.py # Testes de integridade e concorrência
├── Dockerfile
├── requirements.txt
└── README.md