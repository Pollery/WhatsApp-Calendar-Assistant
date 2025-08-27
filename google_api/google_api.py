import os
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import pytz
import datetime

class GoogleCalendar:
    def __init__(self, client_secret_file, api_name, api_version, *scopes):
        self.client_secret_file = client_secret_file
        self.api_name = api_name
        self.api_version = api_version
        self.scopes = [scope for scope in scopes[0]]
        self.service = self._create_service()

    def _create_service(self):
        creds = None
        working_dir = os.getcwd()
        token_dir = "token_files"
        token_file = f"token_{self.api_name}_{self.api_version}.json"

        if not os.path.exists(os.path.join(working_dir, token_dir)):
            os.mkdir(os.path.join(working_dir, token_dir))

        if os.path.exists(os.path.join(working_dir, token_dir, token_file)):
            creds = Credentials.from_authorized_user_file(
                os.path.join(working_dir, token_dir, token_file), self.scopes
            )

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secret_file, self.scopes
                )
                creds = flow.run_local_server(port=0)

            with open(
                os.path.join(working_dir, token_dir, token_file), "w"
            ) as token:
                token.write(creds.to_json())
        
        try:
            service = build(
                self.api_name, self.api_version, credentials=creds
            )
            print(f"{self.api_name} service created successfully")
            return service
        except Exception as e:
            print(f"Unable to connect to {self.api_name}.")
            print(e)
            return None

    def create_event(self, calendar_id, event_data_from_llm):
        """
        Creates an event from raw LLM data, handling date changes for overnight events.
        """
        try:
            start_datetime_str = f"{event_data_from_llm['start_date']}T{event_data_from_llm['start_time']}"
            end_datetime_str = f"{event_data_from_llm['end_date']}T{event_data_from_llm['end_time']}"

            start_dt = datetime.datetime.fromisoformat(start_datetime_str)
            end_dt = datetime.datetime.fromisoformat(end_datetime_str)

            # Check if the end time is before the start time, implying an overnight event
            if end_dt < start_dt:
                end_dt += datetime.timedelta(days=1)
                event_data_from_llm['end_date'] = end_dt.strftime('%Y-%m-%d')
                end_datetime_str = f"{event_data_from_llm['end_date']}T{event_data_from_llm['end_time']}"

            # Construct the event body
            event_body = {
                'summary': event_data_from_llm.get('summary'),
                'location': event_data_from_llm.get('location'),
                'description': event_data_from_llm.get('description'),
                'start': {
                    'dateTime': f"{start_datetime_str}-03:00",
                    'timeZone': 'America/Sao_Paulo',
                },
                'end': {
                    'dateTime': f"{end_datetime_str}-03:00",
                    'timeZone': 'America/Sao_Paulo',
                },
            }

            # Handle recurrence details if they exist
            recurrence_details = event_data_from_llm.get("recurrence_details")
            if recurrence_details:
                rrule_parts = [f"FREQ={recurrence_details['rule'].upper()}"]
                if recurrence_details.get('byweekday'):
                    byweekday_str = ','.join(recurrence_details['byweekday'])
                    rrule_parts.append(f"BYDAY={byweekday_str}")
                if recurrence_details.get('until_date'):
                    until_date_str = recurrence_details['until_date'].replace('-', '')
                    until_dt = datetime.datetime.strptime(until_date_str, "%Y%m%d").replace(
                        hour=23, minute=59, second=59, tzinfo=pytz.timezone('America/Sao_Paulo')
                    ).astimezone(pytz.utc)
                    rrule_parts.append(f"UNTIL={until_dt.strftime('%Y%m%dT%H%M%SZ')}")
                elif recurrence_details.get('count'):
                    rrule_parts.append(f"COUNT={recurrence_details['count']}")

                event_body['recurrence'] = [f"RRULE:{';'.join(rrule_parts)}"]

            # Insert the event into the calendar
            event = self.service.events().insert(
                calendarId=calendar_id,
                body=event_body
            ).execute()
            print(f"Event created: {event.get('htmlLink')}")
            return event

        except Exception as e:
            print(f"Failed to create event: {e}")
            return None

    def create_new_calendar(self, calendar_name):
        try:
            new_calendar = {
                'summary': calendar_name,
                'timeZone': 'America/Sao_Paulo'
            }
            created_calendar = self.service.calendars().insert(body=new_calendar).execute()
            print(f"Calendar created: {created_calendar.get('htmlLink')}")
            return created_calendar
        except Exception as e:
            print(f"Failed to create calendar: {e}")
            return None

    def update_event(self, calendar_id, event_id, updated_event_data):
        """
        Updates an existing calendar event with new data, handling overnight events and recurrence.
        """
        try:
            # Step 1: Get the current event data from the API
            event_body = self.service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()

            # Step 2: Update the event_body with new data from LLM
            if 'summary' in updated_event_data:
                event_body['summary'] = updated_event_data['summary']
            if 'location' in updated_event_data:
                event_body['location'] = updated_event_data['location']
            if 'description' in updated_event_data:
                event_body['description'] = updated_event_data['description']
            if 'attendees' in updated_event_data:
                event_body['attendees'] = [{'email': email} for email in updated_event_data['attendees']]

            # Step 3: Handle date and time updates, including overnight events
            if 'start_date' in updated_event_data and 'start_time' in updated_event_data:
                start_datetime_str = f"{updated_event_data['start_date']}T{updated_event_data['start_time']}"
                start_dt = datetime.datetime.fromisoformat(start_datetime_str)
                event_body['start']['dateTime'] = f"{start_dt.isoformat()}-03:00"

            if 'end_date' in updated_event_data and 'end_time' in updated_event_data:
                end_datetime_str = f"{updated_event_data['end_date']}T{updated_event_data['end_time']}"
                end_dt = datetime.datetime.fromisoformat(end_datetime_str)

                # Check if it's an overnight event and adjust the end date
                if 'start' in event_body and event_body['start']['dateTime'] and end_dt < datetime.datetime.fromisoformat(event_body['start']['dateTime'].split('-')[0]):
                    end_dt += timedelta(days=1)
                event_body['end']['dateTime'] = f"{end_dt.isoformat()}-03:00"

            # Step 4: Handle recurrence updates
            recurrence_details = updated_event_data.get("recurrence_details")
            if recurrence_details:
                rrule_parts = [f"FREQ={recurrence_details['rule'].upper()}"]
                if recurrence_details.get('byweekday'):
                    byweekday_str = ','.join(recurrence_details['byweekday'])
                    rrule_parts.append(f"BYDAY={byweekday_str}")
                if recurrence_details.get('until_date'):
                    until_date_str = recurrence_details['until_date'].replace('-', '')
                    until_dt = datetime.datetime.strptime(until_date_str, "%Y%m%d").replace(
                        hour=23, minute=59, second=59, tzinfo=pytz.timezone('America/Sao_Paulo')
                    ).astimezone(pytz.utc)
                    rrule_parts.append(f"UNTIL={until_dt.strftime('%Y%m%dT%H%M%SZ')}")
                elif recurrence_details.get('count'):
                    rrule_parts.append(f"COUNT={recurrence_details['count']}")
                event_body['recurrence'] = [f"RRULE:{';'.join(rrule_parts)}"]
            elif 'recurrence' in event_body:
                del event_body['recurrence']

            # Step 5: Perform the update API call
            updated_event = self.service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event_body
            ).execute()

            print(f"Event updated: {updated_event.get('htmlLink')}")
            return updated_event

        except Exception as e:
            print(f"Failed to update event: {e}")
            return None

    def delete_event(self, calendar_id, event_id):
        """
        Deletes a single event by its ID.
        """
        try:
            self.service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            print(f"Event {event_id} deleted successfully.")
            return True
        except Exception as e:
            print(f"Failed to delete event {event_id}: {e}")
            return False


    def get_calendar_id_by_name(self, calendar_name):
        try:
            page_token = None
            while True:
                calendar_list = self.service.calendarList().list(pageToken=page_token).execute()
                for calendar_list_entry in calendar_list['items']:
                    if calendar_list_entry['summary'] == calendar_name:
                        print(f"Found calendar '{calendar_name}' with ID: {calendar_list_entry['id']}")
                        return calendar_list_entry['id']
                page_token = calendar_list.get('nextPageToken')
                if not page_token:
                    break
            print(f"Calendar with name '{calendar_name}' not found.")
            return None
        except Exception as e:
            print(f"Failed to retrieve calendar ID: {e}")
            return None
        
    def get_all_events(self, calendar_id, start_date=None, end_date=None, summary=None):
        try:
            # Pega a data e hora atual no fuso horário de São Paulo como padrão
            saopaulo_tz = pytz.timezone("America/Sao_Paulo")
            now = datetime.datetime.now(saopaulo_tz)

            # Se start_date não for fornecido, usa a data e hora atual
            if not start_date:
                start_date = now.isoformat()

            # Se end_date não for fornecido, usa 30 dias a partir de agora
            if not end_date:
                end_date = (now + datetime.timedelta(days=30)).isoformat()

            # Formata as datas para o Google Calendar
            start_datetime = start_date + 'Z' if 'T' not in start_date else start_date
            end_datetime = end_date + 'Z' if 'T' not in end_date else end_date

            events_result = self.service.events().list(
                calendarId=calendar_id,
                timeMin=start_datetime,
                timeMax=end_datetime,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])
            
            # Filtra por resumo se um for fornecido
            if summary:
                normalized_summary = normalize_text(summary)
                filtered_events = [
                    event for event in events
                    if 'summary' in event and normalized_summary in normalize_text(event['summary'])
                ]
                return filtered_events

            return events
        except Exception as e:
            print(f"Failed to retrieve events: {e}")
            return None

        
    def get_all_calendars(self):
        try:
            page_token = None
            all_calendars = []
            while True:
                calendar_list = self.service.calendarList().list(pageToken=page_token).execute()
                all_calendars.extend(calendar_list.get('items', []))
                page_token = calendar_list.get('nextPageToken')
                if not page_token:
                    break
            
            print("Your calendars:")
            for calendar in all_calendars:
                print(f"  - {calendar.get('summary')} (ID: {calendar.get('id')})")
            
            return all_calendars
        except Exception as e:
            print(f"Failed to retrieve calendars: {e}")
            return None

# --- Example Usage with the new class ---
API_NAME = "calendar"
API_VERSION = "v3"
SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Instantiate the class, which handles authentication and service creation
calendar_client = GoogleCalendar(
    "google_api/client_secret.json", API_NAME, API_VERSION, SCOPES
)



if calendar_client.service:
    all_my_calendars = calendar_client.get_all_calendars()
    calendar_name = "wpp-llm"
    wpp_calendar_id = calendar_client.get_calendar_id_by_name(calendar_name)
    
    # 1. Create the calendar only if it doesn't already exist
    if not wpp_calendar_id:
        print(f"Calendar '{calendar_name}' not found. Creating a new one...")
        new_calendar = calendar_client.create_new_calendar(calendar_name)
        if new_calendar:
            wpp_calendar_id = new_calendar.get('id')
    
    if wpp_calendar_id:
        # 2. Add an event to the specific calendar (if we found its ID)
        event_details = {
            'summary': 'Refactoring complete!',
            'start': {'dateTime': '2025-08-28T10:00:00-03:00', 'timeZone': 'America/Sao_Paulo'},
            'end': {'dateTime': '2025-08-28T11:00:00-03:00', 'timeZone': 'America/Sao_Paulo'},
        }
        calendar_client.create_event(wpp_calendar_id, event_details)
        
        # 3. Get all events from that specific calendar
        calendar_client.get_all_events(wpp_calendar_id)
    else:
        print(f"Could not find or create calendar '{calendar_name}'. Event creation skipped.")

