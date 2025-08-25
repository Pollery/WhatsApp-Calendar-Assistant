import os
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request


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

    def create_event(self, calendar_id, event_data):
        try:
            event = self.service.events().insert(
                calendarId=calendar_id,
                body=event_data
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
        try:
            updated_event = self.service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=updated_event_data
            ).execute()
            print(f"Event updated: {updated_event.get('htmlLink')}")
            return updated_event
        except Exception as e:
            print(f"Failed to update event: {e}")
            return None

    def delete_event(self, calendar_id, event_id):
        try:
            self.service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            print(f"Event {event_id} deleted successfully.")
            return True
        except Exception as e:
            print(f"Failed to delete event: {e}")
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
        
    def get_all_events(self, calendar_id):
        try:
            events_result = self.service.events().list(
                calendarId=calendar_id,
                maxResults=100,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])
            if not events:
                print('No upcoming events found.')
                return []

            print(f"Upcoming events for calendar ID: {calendar_id}")
            event_list = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                event_info = {
                    'id': event['id'],
                    'summary': event['summary'],
                    'start_time': start
                }
                event_list.append(event_info)
                print(f"  - Event: {event_info['summary']} (ID: {event_info['id']})")
            return event_list
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

