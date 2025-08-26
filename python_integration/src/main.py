import sys
import os
from fastapi import Request
import uvicorn
from fastapi import FastAPI
from api_send import EvolutionAPI 

# Get the path to the project's root directory
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
# Add the project's root directory to the system path
sys.path.append(project_root)

from google_api.google_api import GoogleCalendar
from llm_integration.chatbot import GeminiChatbot, get_current_saopaulo_date

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
        # Use the LLM to extract the intent from the user's message
        print(f"Processando a solicitação do usuário: {message_text}")
        action_request = chatbot.ask_question(message_text)

        # Check if the LLM returned a valid, non-empty JSON
        if not action_request or "action" not in action_request:
            reply_text = "Não consegui entender sua solicitação de calendário. Por favor, tente novamente."
            evo.send_message(telephone, reply_text)
            return {"status": "ok"}

        action = action_request.get("action")
        target = action_request.get("target")
        reply_text = "Ação de calendário executada com sucesso!"

        # Execute the action based on the LLM's intent
        if action == "create" and target == "calendar":
            calendar_name = action_request.get("calendar_name")
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

        elif action == "create" and target == "event":
            event_data_dict = action_request.get("event_details")
            calendar_name = action_request.get("calendar_name", "primary")
            calendar_id = calendar_client.get_calendar_id_by_name(calendar_name)
            if not calendar_id:
                reply_text = f"Erro: Não foi possível encontrar o calendário '{calendar_name}'. Ação de criação de evento cancelada."
            elif event_data_dict:
                event_body = {
                    'summary': event_data_dict.get('summary'),
                    'location': event_data_dict.get('location'),
                    'description': event_data_dict.get('description'),
                    'start': {
                        'dateTime': f"{event_data_dict['start_date']}T{event_data_dict['start_time']}-03:00",
                        'timeZone': 'America/Sao_Paulo',
                    },
                    'end': {
                        'dateTime': f"{event_data_dict['end_date']}T{event_data_dict['end_time']}-03:00",
                        'timeZone': 'America/Sao_Paulo',
                    },
                }

                # NEW: Check for recurrence details and add the RRULE to the event body
                recurrence_details = event_data_dict.get("recurrence_details")
                if recurrence_details:
                    # Construct the RRULE string based on the rule and end condition
                    if recurrence_details.get('until_date'):
                        until_date_str = recurrence_details['until_date'].replace('-', '')
                        recurrence_rule = f"RRULE:FREQ={recurrence_details['rule'].upper()};UNTIL={until_date_str}T235959Z"
                    elif recurrence_details.get('count'):
                        recurrence_rule = f"RRULE:FREQ={recurrence_details['rule'].upper()};COUNT={recurrence_details['count']}"
                    else:
                        recurrence_rule = f"RRULE:FREQ={recurrence_details['rule'].upper()}"
                    
                    event_body['recurrence'] = [recurrence_rule]
                
                event = calendar_client.create_event(calendar_id, event_body)
                reply_text = f"Evento '{event_body.get('summary')}' criado com sucesso."
            else:
                reply_text = "Detalhes do evento não foram extraídos corretamente. Ação de criação cancelada."

        elif action == "delete" and target == "event":
            event_summary_or_id = action_request.get("event_summary_or_id")
            calendar_name = action_request.get("calendar_name", "primary")
            calendar_id = calendar_client.get_calendar_id_by_name(calendar_name)
            
            if not calendar_id:
                reply_text = f"Erro: Não foi possível encontrar o calendário '{calendar_name}'."
            else:
                events = calendar_client.get_all_events(calendar_id)
                event_to_delete_id = None
                for event in events:
                    if event_summary_or_id in event.get('summary', ''):
                        event_to_delete_id = event['id']
                        break
                
                if event_to_delete_id:
                    calendar_client.delete_event(calendar_id, event_to_delete_id)
                    reply_text = f"Evento com o resumo '{event_summary_or_id}' foi excluído."
                else:
                    reply_text = f"Evento com o resumo '{event_summary_or_id}' não encontrado para exclusão."
        
        elif action == "list" and target == "calendar":
            calendars = calendar_client.get_all_calendars()
            if calendars:
                reply_text = "Seus calendários:\n" + "\n".join([f"- {cal.get('summary')} (ID: {cal.get('id')})" for cal in calendars])
            else:
                reply_text = "Nenhum calendário encontrado."
        
        elif action == "list" and target == "event":
            calendar_name = action_request.get("calendar_name", "primary")
            calendar_id = calendar_client.get_calendar_id_by_name(calendar_name)
            if calendar_id:
                events = calendar_client.get_all_events(calendar_id)
                if events:
                    reply_text = f"Eventos em '{calendar_name}':\n" + "\n".join([f"- {e.get('summary')} ({e.get('start_time')})" for e in events])
                else:
                    reply_text = f"Nenhum evento encontrado no calendário '{calendar_name}'."
            else:
                reply_text = f"Não foi possível encontrar o calendário '{calendar_name}'."

        elif action == "update" and target == "event":
            event_summary_or_id = action_request.get("event_summary_or_id")
            event_data_dict = action_request.get("event_details")
            calendar_name = action_request.get("calendar_name", "primary")

            calendar_id = calendar_client.get_calendar_id_by_name(calendar_name)
            if not calendar_id:
                reply_text = f"Erro: Não foi possível encontrar o calendário '{calendar_name}'. Ação de atualização cancelada."
            else:
                events = calendar_client.get_all_events(calendar_id)
                event_to_update_id = None
                for event in events:
                    if event_summary_or_id in event.get('summary', ''):
                        event_to_update_id = event['id']
                        break
                
                if event_to_update_id and event_data_dict:
                    updated_body = {}
                    if 'summary' in event_data_dict: updated_body['summary'] = event_data_dict['summary']
                    if 'location' in event_data_dict: updated_body['location'] = event_data_dict['location']
                    if 'description' in event_data_dict: updated_body['description'] = event_data_dict['description']
                    
                    start_time_str = f"{event_data_dict['start_date']}T{event_data_dict['start_time']}-03:00" if 'start_date' in event_data_dict and 'start_time' in event_data_dict else None
                    end_time_str = f"{event_data_dict['end_date']}T{event_data_dict['end_time']}-03:00" if 'end_date' in event_data_dict and 'end_time' in event_data_dict else None

                    if start_time_str: updated_body['start'] = {'dateTime': start_time_str, 'timeZone': 'America/Sao_Paulo'}
                    if end_time_str: updated_body['end'] = {'dateTime': end_time_str, 'timeZone': 'America/Sao_Paulo'}

                    calendar_client.update_event(calendar_id, event_to_update_id, updated_body)
                    reply_text = f"Evento '{event_summary_or_id}' atualizado com sucesso."
                else:
                    reply_text = f"Evento '{event_summary_or_id}' não encontrado ou dados de atualização inválidos."
        
        else:
            reply_text = "Solicitação não reconhecida. As ações suportadas são: criar, deletar, listar, atualizar."
        
        # Send the final response back to WhatsApp
        evo.send_message(telephone, reply_text)
        print(f"📤 Sent reply to {telephone}: {reply_text}")

    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=9421, reload=True)
