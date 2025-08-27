import sys
import os
from fastapi import Request
import uvicorn
from fastapi import FastAPI
from api_send import EvolutionAPI 
import unicodedata
import datetime
import pytz
import re
# Get the path to the project's root directory
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
# Add the project's root directory to the system path
sys.path.append(project_root)

from google_api.google_api import GoogleCalendar
from llm_integration.chatbot import GeminiChatbot, get_current_saopaulo_date
try:
    from python_integration.src.utils.config import load_config

    config = load_config()
except ImportError:
    config = {}
DEFAULT_CALENDAR_NAME = config.get("DEFAULT_CALENDAR_NAME", "wpp-llm")
# Create FastAPI app
app = FastAPI()

# Initialize the sending class
evo = EvolutionAPI()

# Initialize the Google Calendar and Gemini Chatbot clients once
API_NAME = "calendar"
API_VERSION = "v3"
SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Construct the absolute path to the client secret file
client_secret_path = os.path.join(project_root, "google_api", "client_secret.json")

print("Iniciando a conexão com o Google Calendar...")
print(f"Tentando carregar o arquivo de credenciais de: {client_secret_path}")
try:
    calendar_client = GoogleCalendar(
        client_secret_path, API_NAME, API_VERSION, SCOPES
    )
    print("Conexão com o Google Calendar inicializada com sucesso.")
except FileNotFoundError:
    print(f"ERRO: O arquivo 'client_secret.json' não foi encontrado em: {client_secret_path}")
    print("Por favor, verifique se o arquivo existe e se o caminho está correto na sua configuração do Docker.")
    sys.exit(1) # Exit with an error code to make the problem obvious

print("\n" + "=" * 30 + "\n")

print("Iniciando o chatbot Gemini...")
chatbot = GeminiChatbot(model_name="gemini-2.0-flash")
print("\n" + "=" * 30 + "\n")


def normalize_text(text: str) -> str:
    """
    Normaliza o texto removendo acentos e convertendo para minúsculas.
    """
    # Se o texto não for uma string, retorne uma string vazia para evitar erros
    if not isinstance(text, str):
        return ""
    
    # Normaliza a string para a forma NFKD, que separa os caracteres de seus acentos
    normalized = unicodedata.normalize('NFKD', text)
    
    # Filtra e decodifica a string para remover os acentos
    return "".join([
        c for c in normalized if not unicodedata.combining(c)
    ]).lower()
@app.post("/")
async def webhook(request: Request):
    """
    Handles incoming webhook requests from the WhatsApp API.
    """
    data = await request.json()
    print("📩 Received webhook:", data)

    telephone = data["data"]["key"]["remoteJid"]
    message_text = data["data"]["message"].get("conversation")

    if telephone and message_text:
        print(f"Processando a solicitação do usuário: {message_text}")
        action_request = chatbot.ask_question(message_text)
        print(f"LLM action_request: {action_request}")

        if not action_request or "action" not in action_request:
            reply_text = "Não consegui entender sua solicitação de calendário. Por favor, tente novamente."
            evo.send_message(telephone, reply_text)
            return {"status": "ok"}

        action = action_request.get("action")
        target = action_request.get("target")
        reply_text = "Ação de calendário executada com sucesso!"

        # Execute the action based on the LLM's intent
        if action == "create" and target == "calendar":
            calendar_name = action_request.get("calendar_name", DEFAULT_CALENDAR_NAME)
            if calendar_name:
                existing_id = calendar_client.get_calendar_id_by_name(calendar_name)
                if not existing_id:
                    print(f"Criando o calendário '{calendar_name}'...")
                    calendar_client.create_new_calendar(calendar_name)
                    reply_text = f"Calendário '{calendar_name}' criado com sucesso."
                else:
                    reply_text = f"O calendário '{calendar_name}' já existe. Não foi criado novamente."
            else:
                reply_text = "Nome do calendário não fornecido. Ação de criação cancelada."

        if action == "create" and target == "event":
            event_data = action_request.get("event_details")
            calendar_name = action_request.get("calendar_name", DEFAULT_CALENDAR_NAME)
            
            # 1. Obter o ID do calendário
            calendar_id = calendar_client.get_calendar_id_by_name(calendar_name)
            if not calendar_id:
                reply_text = f"Erro: Não foi possível encontrar o calendário '{calendar_name}'."
            else:
                try:
                    # 2. Lógica para definir o horário de término padrão (se não fornecido)
                    if 'start_time' in event_data and 'end_time' not in event_data:
                        start_datetime_str = f"{event_data['start_date']}T{event_data['start_time']}"
                        start_datetime_obj = datetime.datetime.strptime(start_datetime_str, "%Y-%m-%dT%H:%M:%S")
                        end_datetime_obj = start_datetime_obj + datetime.timedelta(hours=1)
                        event_data['end_time'] = end_datetime_obj.strftime("%H:%M:%S")

                    # 3. Chamar a API de criação de evento
                    # Essa é a parte que estava faltando.
                    created_event = calendar_client.create_event(calendar_id, event_data)
                    
                    if created_event:
                        reply_text = f"Evento '{created_event.get('summary')}' criado com sucesso."
                    else:
                        reply_text = "O evento não pôde ser criado. Verifique os logs para mais detalhes."
                except Exception as e:
                    reply_text = f"Ocorreu um erro ao criar o evento: {e}"

        elif action == "delete" and target == "event":
            event_summary_or_id = action_request.get("event_summary_or_id")
            calendar_name = action_request.get("calendar_name", DEFAULT_CALENDAR_NAME)

            if not event_summary_or_id:
                reply_text = "Por favor, especifique o nome do evento que deseja excluir."
                evo.send_message(telephone, reply_text)
                return {"status": "ok"}
            
            calendar_id = calendar_client.get_calendar_id_by_name(calendar_name)
            if not calendar_id:
                reply_text = f"Erro: Não foi possível encontrar o calendário '{calendar_name}'."
            else:
                try:
                    # Busque eventos específicos
                    events = calendar_client.get_all_events(
                        calendar_id=calendar_id,
                        start_date=datetime.datetime.now(pytz.timezone("America/Sao_Paulo")).isoformat()
                    )
                    
                    events_to_delete = []
                    normalized_summary = normalize_text(event_summary_or_id)
                    
                    for event in events:
                        normalized_event_summary = normalize_text(event.get('summary', ''))
                        if normalized_summary in normalized_event_summary:
                            events_to_delete.append(event)
                    
                    if events_to_delete:
                        deleted_count = 0
                        for event in events_to_delete:
                            try:
                                calendar_client.delete_event(calendar_id, event['id'])
                                deleted_count += 1
                            except Exception as e:
                                print(f"Erro ao deletar o evento {event.get('summary', 'sem título')}: {e}", file=sys.stderr)
                        
                        if deleted_count > 0:
                            reply_text = f"{deleted_count} evento(s) com o título '{event_summary_or_id}' foram excluídos com sucesso."
                        else:
                            reply_text = "Nenhum evento foi excluído."
                    else:
                        reply_text = f"Nenhum evento com o título '{event_summary_or_id}' foi encontrado."
                except Exception as e:
                    reply_text = f"Ocorreu um erro ao buscar e excluir os eventos: {e}"


        elif action == "delete_all_events" and target == "event":
            calendar_name = action_request.get("calendar_name", DEFAULT_CALENDAR_NAME)

            calendar_id = calendar_client.get_calendar_id_by_name(calendar_name)
            if not calendar_id:
                reply_text = f"Erro: Não foi possível encontrar o calendário '{calendar_name}'."
            else:
                try:
                    now = datetime.datetime.now(pytz.timezone("America/Sao_Paulo"))
                    end_of_year = datetime.datetime(now.year, 12, 31, 23, 59, 59, tzinfo=now.tzinfo)
                    
                    events = calendar_client.get_all_events(
                        calendar_id=calendar_id,
                        start_date=now.isoformat(),
                        end_date=end_of_year.isoformat()
                    )

                    if events:
                        deleted_count = 0
                        for event in events:
                            try:
                                calendar_client.delete_event(calendar_id, event['id'])
                                deleted_count += 1
                            except Exception as e:
                                print(f"Erro ao deletar o evento {event.get('summary', 'sem título')}: {e}", file=sys.stderr)
                        
                        if deleted_count > 0:
                            reply_text = f"{deleted_count} evento(s) foram excluído(s) com sucesso até o fim do ano."
                        else:
                            reply_text = "Nenhum evento foi excluído. Por favor, verifique os logs."
                    else:
                        reply_text = "Não há eventos para excluir no período solicitado."
                except Exception as e:
                    reply_text = f"Ocorreu um erro ao buscar e excluir os eventos: {e}"



        # Ação de atualização para eventos
        elif action == "update" and target == "event":
            event_summary_or_id = action_request.get("event_summary_or_id")
            update_data = action_request.get("update_data")
            calendar_name = action_request.get("calendar_name", DEFAULT_CALENDAR_NAME)

            if not event_summary_or_id or not update_data:
                reply_text = "Por favor, especifique qual evento e o que deseja atualizar."
                evo.send_message(telephone, reply_text)
                return {"status": "ok"}

            calendar_id = calendar_client.get_calendar_id_by_name(calendar_name)
            if not calendar_id:
                reply_text = f"Erro: Não foi possível encontrar o calendário '{calendar_name}'."
            else:
                try:
                    # 1. Busca todos os eventos para encontrar o(s) evento(s) correto(s)
                    all_events = calendar_client.get_all_events(calendar_id)
                    events_to_update = []

                    # 2. Filtra os eventos com base no resumo/título
                    normalized_search_term = normalize_text(event_summary_or_id)
                    for event in all_events:
                        if 'summary' in event and normalized_search_term in normalize_text(event['summary']):
                            events_to_update.append(event)

                    if not events_to_update:
                        reply_text = f"Nenhum evento com o título '{event_summary_or_id}' foi encontrado."
                    else:
                        updated_count = 0
                        for event in events_to_update:
                            # 3. Aplica as modificações de offset de data
                            if 'start_date_offset' in update_data:
                                offset_str = update_data['start_date_offset']
                                match = re.match(r"([+-])(\d+)\s*(day|week|month|year)s?", offset_str, re.IGNORECASE)

                                if match:
                                    sign = match.group(1)
                                    value = int(match.group(2))
                                    unit = match.group(3).lower()

                                    if sign == '-':
                                        value = -value

                                    delta_kwargs = {}
                                    if unit == 'day':
                                        delta_kwargs['days'] = value
                                    elif unit == 'week':
                                        delta_kwargs['weeks'] = value
                                    elif unit == 'month':
                                        delta_kwargs['days'] = value * 30
                                    elif unit == 'year':
                                        delta_kwargs['days'] = value * 365

                                    if delta_kwargs:
                                        original_start_time = datetime.datetime.fromisoformat(event['start']['dateTime'])
                                        new_start_time = original_start_time + datetime.timedelta(**delta_kwargs)

                                        event['start']['dateTime'] = new_start_time.isoformat()
                                        event['end']['dateTime'] = (new_start_time + (datetime.datetime.fromisoformat(event['end']['dateTime']) - original_start_time)).isoformat()
                                        calendar_client.update_event(calendar_id, event['id'], event)
                                        updated_count += 1

                            # 4. Aplica as modificações de horário
                            if 'start_time' in update_data:
                                new_time_str = update_data['start_time']
                                new_time = datetime.datetime.strptime(new_time_str, '%H:%M:%S').time()
                                
                                original_start_time = datetime.datetime.fromisoformat(event['start']['dateTime'])
                                original_end_time = datetime.datetime.fromisoformat(event['end']['dateTime'])
                                duration = original_end_time - original_start_time
                                
                                new_start_time = original_start_time.replace(hour=new_time.hour, minute=new_time.minute, second=new_time.second)
                                new_end_time = new_start_time + duration
                                
                                event['start']['dateTime'] = new_start_time.isoformat()
                                event['end']['dateTime'] = new_end_time.isoformat()
                                
                                calendar_client.update_event(calendar_id, event['id'], event)
                                updated_count += 1

                        if updated_count > 0:
                            reply_text = f"{updated_count} evento(s) com o título '{event_summary_or_id}' foram atualizados com sucesso."
                        else:
                            reply_text = "Nenhum evento foi atualizado. Verifique se os dados de atualização estão corretos."

                except Exception as e:
                    reply_text = f"Ocorreu um erro ao atualizar os eventos: {e}"

            evo.send_message(telephone, reply_text)
            return {"status": "ok"}


        elif action == "list" and target == "event":
            calendar_name = action_request.get("calendar_name", DEFAULT_CALENDAR_NAME)
            
            # Adicionando a lógica para capturar a duração da solicitação, se disponível
            duration_months = action_request.get('duration_months', 12)
            # Por padrão, se a LLM não especificar, assumiremos 12 meses.
            
            calendar_id = calendar_client.get_calendar_id_by_name(calendar_name)
            if not calendar_id:
                reply_text = f"Erro: Não foi possível encontrar o calendário '{calendar_name}'."
            else:
                try:
                    now = datetime.datetime.now(pytz.timezone("America/Sao_Paulo"))
                    # Definir a data de início como a data e hora atuais
                    start_date = now.isoformat()
                    
                    # Calcular a data de término com base no número de meses
                    end_date = (now + datetime.timedelta(days=30 * duration_months)).isoformat()
                    
                    events = calendar_client.get_all_events(
                        calendar_id=calendar_id,
                        start_date=start_date,
                        end_date=end_date
                    )
                    
                    if events:
                        event_list_str = []
                        for event in events:
                            start_data = event.get('start', {})
                            start_time = start_data.get('dateTime')
                            start_date_only = start_data.get('date')

                            if start_time:
                                start_time_obj = datetime.datetime.fromisoformat(start_time)
                                start_time_str = start_time_obj.strftime('%d/%m/%Y %H:%M')
                            elif start_date_only:
                                start_date_obj = datetime.datetime.strptime(start_date_only, '%Y-%m-%d')
                                start_time_str = f"Dia inteiro em {start_date_obj.strftime('%d/%m/%Y')}"
                            else:
                                start_time_str = "Data/Hora não informada"
                            
                            event_list_str.append(f"- **{event.get('summary', 'Evento sem título')}** ({start_time_str})")
                        
                        reply_text = f"Seus próximos eventos para os próximos {duration_months} meses são:\n" + "\n".join(event_list_str)
                    else:
                        reply_text = f"Não há eventos para os próximos {duration_months} meses."
                except Exception as e:
                    reply_text = f"Ocorreu um erro ao listar os eventos: {e}"


    
        # Send the final response back to WhatsApp
        evo.send_message(telephone, reply_text)
        print(f"📤 Sent reply to {telephone}: {reply_text}")

    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=9421, reload=True)
