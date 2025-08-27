import os
import datetime
import sys
import pytz
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.pydantic_v1 import BaseModel, Field, validator
from typing import Optional, Literal, List

# Get the path to the project's root directory
project_root = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)
# Add the project's root directory to the system path
sys.path.append(project_root)


try:
    from python_integration.src.utils.config import load_config

    config = load_config()
except ImportError:
    config = {}

# Define o nome do calendário padrão. Isso pode ser movido para um arquivo de configuração.
DEFAULT_CALENDAR_NAME = config.get("DEFAULT_CALENDAR_NAME", "wpp-llm")

def get_current_saopaulo_date() -> str:
    """
    Returns the current date and time in the America/Sao_Paulo timezone.
    """
    try:
        saopaulo_tz = pytz.timezone("America/Sao_Paulo")
        now_in_saopaulo = datetime.datetime.now(saopaulo_tz)
        return now_in_saopaulo.strftime("%Y-%m-%d %H:%M:%S %Z")
    except Exception as e:
        print(f"Error getting São Paulo date: {e}")
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# --- NOVOS MODELOS PYDANTIC PARA UMA SAÍDA MAIS FLEXÍVEL ---
class RecurrenceDetails(BaseModel):
    """Detalhes para a recorrência de um evento."""
    rule: Literal["DAILY", "WEEKLY", "MONTHLY", "YEARLY"] = Field(..., description="A regra de recorrência: 'DAILY', 'WEEKLY', 'MONTHLY', ou 'YEARLY'.")
    until_date: Optional[str] = Field(None, description="A data final da recorrência no formato 'YYYY-MM-DD'.")
    count: Optional[int] = Field(None, description="O número de vezes que o evento deve se repetir.")
    byweekday: Optional[List[Literal["MO", "TU", "WE", "TH", "FR", "SA", "SU"]]] = Field(None, description="Lista de dias da semana (ex: 'MO', 'TU', 'WE').")
    interval: Optional[int] = Field(1, description="A frequência com que a regra se repete (ex: 2 para 'a cada duas semanas'). Padrão é 1.")


class EventData(BaseModel):
    """Dados de um evento para o Google Calendar API, incluindo recorrência."""
    summary: Optional[str] = Field(None, description="O título ou resumo do evento.")
    start_date: Optional[str] = Field(None, description="A data de início do evento no formato 'YYYY-MM-DD'.")
    end_date: Optional[str] = Field(None, description="A data de fim do evento no formato 'YYYY-MM-DD'.")
    start_time: Optional[str] = Field(None, description="O horário de início do evento no formato 'HH:MM:SS'.")
    end_time: Optional[str] = Field(None, description="O horário de fim do evento no formato 'HH:MM:SS'.")
    location: Optional[str] = Field(None, description="O local do evento.")
    description: Optional[str] = Field(None, description="Uma breve descrição do evento.")
    recurrence_details: Optional[RecurrenceDetails] = Field(None, description="Detalhes da recorrência para eventos repetitivos.")

class GoogleCalendarAction(BaseModel):
    """Ação a ser executada no Google Calendar."""
    action: Literal["create", "delete", "list", "update", "delete_all_events"] = Field(
        description="A ação a ser executada. Deve ser 'create', 'delete', 'list', 'update' ou 'delete_all_events'."
    )
    target: Literal["event", "calendar"] = Field(
        description="O alvo da ação. Deve ser 'event' ou 'calendar'."
    )
    calendar_name: Optional[str] = Field(
        None, description="O nome do calendário para a ação."
    )
    event_details: Optional[EventData] = Field(
        None, description="Detalhes do evento a ser criado ou atualizado."
    )
    event_summary_or_id: Optional[str] = Field(
        None, description="O resumo ou ID de um evento a ser excluído ou atualizado."
    )
    update_data: Optional[dict] = Field(
        None, description="Um dicionário contendo as chaves e valores a serem atualizados. Ex: {'start_date': '2025-08-30'}"
    )


    @validator('event_details', always=True)
    def validate_event_details(cls, v, values):
        if values.get('action') == 'create' and values.get('target') == 'event' and v is None:
            raise ValueError('event_details must be provided for creating an event')
        return v


class GeminiChatbot:
    """
    Uma classe de chatbot que interage com a API do Google Gemini via LangChain.
    """
    def __init__(self, model_name: str = "gemini-2.0-flash"):
        try:
            if "GOOGLE_API_KEY" not in os.environ:
                os.environ["GOOGLE_API_KEY"] = config.get("GOOGLE_API_KEY")
            self.llm = ChatGoogleGenerativeAI(model=model_name, temperature=0.7)
        except ValueError as e:
            print(f"Error initializing the GeminiChatbot: {e}")
            self.llm = None
        except Exception as e:
            print(f"An unexpected error occurred during initialization: {e}")
            self.llm = None

    def ask_question(self, user_question: str) -> dict:
        """
        Envia uma pergunta ao modelo Gemini para extrair informações da ação de calendário.
        """
        if not self.llm:
            return {"error": "Chatbot is not initialized. Please check the API key."}

        parser = JsonOutputParser(pydantic_object=GoogleCalendarAction)

        # Prompt estruturado para guiar o LLM a gerar o JSON correto para todas as ações.
        prompt = ChatPromptTemplate.from_template(
            """
        Você é um assistente de calendário inteligente que extrai intenções de usuário para um formato JSON.
        Sua tarefa é analisar a mensagem do usuário e determinar a ação, o alvo e os dados relevantes para o Google Calendar.

        Data de referência atual: {current_date}

        Instruções detalhadas para cada tipo de ação:
        1.  **CRIAR CALENDÁRIO**: Se o usuário pedir para criar um novo calendário, use `action: "create"` e `target: "calendar"`. Defina `calendar_name` com o nome fornecido.
            Exemplo: "Crie um novo calendário chamado 'Viagens'" -> {{"action": "create", "target": "calendar", "calendar_name": "Viagens"}}
            
        2.  **CRIAR EVENTO**: Se o usuário pedir para agendar um evento, use `action: "create"` e `target: "event"`.
            -   **summary**: O título do evento (obrigatório).
            -   **start_date**, **start_time**, **end_date**, **end_time**: Calcule as datas e horários exatos. Se o usuário usar termos como "amanhã" ou "na próxima sexta-feira", use a data de referência para calcular a data correta. Se o horário não for especificado, use "00:00:00". Se o evento for de um dia, a data de início e de fim devem ser as mesmas.
            -   **location**: Onde o evento acontecerá. Se não for especificado, use uma string descritiva como "To be determined".
            -   **description**: Uma breve descrição do evento.
            -   **IMPORTANTE**: Para eventos recorrentes, use o novo campo `recurrence_details` dentro de `event_details`.
            Exemplo: "Agende um almoço amanhã às 13h no restaurante de sempre" -> {{"action": "create", "target": "event", "event_details": {{"summary": "Almoço", "start_date": "2025-08-29", "end_date": "2025-08-29", "start_time": "13:00:00", "end_time": "14:00:00", "location": "Restaurante de sempre", "description": "Almoço com a equipe."}}}}
                    
        2.a. **CRIAR EVENTO RECORRENTE**: Se o usuário pedir para um evento se repetir.
            - Se o usuário especificar um número de semanas (ex: '3 semanas') e também dias da semana (ex: 'quartas, quintas e sextas'), o campo 'count' deve ser a multiplicação do número de semanas pelo número de dias da semana.
            Exemplo: "Agendar uma investigação pessoal às quartas, quintas e sextas pelas próximas 3 semanas." -> O 'count' deve ser 9 (3 semanas * 3 dias/semana).
        Exemplo: "marcar investigação pessoal de segunda a sexta das 21:30 ate o fim da semana que vem" -> {{"action": "create", "target": "event", "event_details": {{"summary": "investigação pessoal", "start_date": "2025-09-01", "end_date": "2025-09-01", "start_time": "21:30:00", "end_time": "23:59:00", "recurrence_details": {{"rule": "WEEKLY", "byweekday": ["MO", "TU", "WE", "TH", "FR"], "until_date": "2025-09-12"}}}}}}
        3.  **LISTAR**: Se o usuário pedir para ver eventos ou calendários, use `action: "list"`. Use `target: "event"` ou `target: "calendar"`.
            -   Para listar eventos, use `target: "event"` e defina `calendar_name` para o nome do calendário (ex: "Trabalho", "Pessoal").
            -   Para listar calendários, use `target: "calendar"`.
            Exemplo: "Mostre meus eventos" -> {{"action": "list", "target": "event", "calendar_name": "{default_calendar_name}"}}
            Exemplo: "Quais são meus calendários?" -> {{"action": "list", "target": "calendar"}}
            
        4.  **DELETAR/EXCLUIR EVENTO**:
            - **Excluir um evento específico**: Se o usuário pedir para apagar um evento pelo nome, use `action: "delete"` e `target: "event"`. Use `event_summary_or_id` para identificar o evento.
            - **Excluir todos os eventos**: Se o usuário usar uma frase como "apagar todos os eventos", "deletar tudo" ou "limpar o calendário", use a ação `action: "delete_all_events"`. Esta é uma ação especial que não precisa de outros detalhes.
            
            Exemplo: "Delete a reunião de hoje" -> {{"action": "delete", "target": "event", "event_summary_or_id": "Reunião de hoje"}}
            Exemplo: "Delete todos os eventos até o fim do ano" -> {{"action": "delete_all_events", "target": "event"}}


       5.  **ATUALIZAR/EDITAR/ADIAR EVENTO**:
            - Use `action: "update"` e `target: "event"`.
            - A informação do evento (como o nome) deve ir em `event_summary_or_id`.
            - Use o campo `update_data` para fornecer os dados que devem ser alterados.
            - Para adiar ou alterar a data, use `start_date` e `end_date` em `update_data`.
            - Se a intenção for adiar por um período (ex: "uma semana"), o valor em `update_data` deve ser um "offset" que o seu código interpretará, como `start_date_offset`.

            Exemplo: "Mude a reunião com o cliente para amanhã" -> {{"action": "update", "target": "event", "event_summary_or_id": "Reunião com o cliente", "update_data": {{"start_date": "2025-08-27", "end_date": "2025-08-27"}}}}
            
            Exemplo: "Adie todos os eventos teste em uma semana" -> {{"action": "update", "target": "event", "event_summary_or_id": "teste", "update_data": {{"start_date_offset": "+7 days"}} }}
        
        
        Regras para o JSON de saída:
        - O retorno deve ser SOMENTE um objeto JSON válido, sem texto adicional.
        - Os nomes das chaves devem ser exatamente como definidos no esquema.
        - Use "{default_calendar_name}" como `calendar_name` padrão para eventos, a menos que o usuário especifique outro.
        - Se a mensagem não se relaciona a um calendário, retorne um objeto JSON vazio: {{}}.

        Aqui está o esquema JSON que você deve seguir:
            {format_instructions}

        Mensagem do usuário: {question}
        """
        ).partial(format_instructions=parser.get_format_instructions())

        try:
            current_date_str = get_current_saopaulo_date()
            chain = prompt | self.llm | parser
            response = chain.invoke(
                {
                    "question": user_question,
                    "current_date": current_date_str,
                    "default_calendar_name": DEFAULT_CALENDAR_NAME,
                }
            )
            return response
        except Exception as e:
            print(f"Erro ao obter a resposta do LLM: {e}")
            return {}