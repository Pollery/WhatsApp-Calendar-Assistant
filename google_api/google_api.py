import os
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request


def create_service(client_secret_file, api_name, api_version, *scopes):
    CLIENT_SECRET_FILE = client_secret_file
    API_SERVICE_NAME = api_name
    API_VERSION = api_version
    SCOPES = [scope for scope in scopes[0]]

    creds = None
    working_dir = os.getcwd()
    token_dir = "token_files"
    token_file = f"token_{API_SERVICE_NAME}_{API_VERSION}.json"

    if not os.path.exists(os.path.join(working_dir, token_dir)):
        os.mkdir(os.path.join(working_dir, token_dir))

    if os.path.exists(os.path.join(working_dir, token_dir, token_file)):
        creds = Credentials.from_authorized_user_file(
            os.path.join(working_dir, token_dir, token_file), SCOPES
        )

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRET_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(
            os.path.join(working_dir, token_dir, token_file), "w"
        ) as token:
            token.write(creds.to_json())

    try:
        service = build(
            API_SERVICE_NAME, API_VERSION, credentials=creds
        )
        print(f"{API_SERVICE_NAME} service created successfully")
        return service
    except Exception as e:
        print(f"Unable to connect to {API_SERVICE_NAME}.")
        print(e)
        return None

def create_event(service, calendar_id, event_data):
    try:
        event = service.events().insert(
            calendarId=calendar_id,
            body=event_data
        ).execute()
        print(f"Event created: {event.get('htmlLink')}")
        return event
    except Exception as e:
        print(f"Failed to create event: {e}")
        return None

# Example usage
# event_details = {
#     'summary': 'Meeting with team',
#     'location': 'Online',
#     'description': 'Discuss Q3 goals.',
#     'start': {
#         'dateTime': '2025-08-26T09:00:00-07:00',
#         'timeZone': 'America/Los_Angeles',
#     },
#     'end': {
#         'dateTime': '2025-08-26T10:00:00-07:00',
#         'timeZone': 'America/Los_Angeles',
#     },
# }
# create_event(service, 'primary', event_details)

def create_new_calendar(service, calendar_name):
    try:
        new_calendar = {
            'summary': calendar_name,
            'timeZone': 'America/Los_Angeles'
        }
        created_calendar = service.calendars().insert(body=new_calendar).execute()
        print(f"Calendar created: {created_calendar.get('htmlLink')}")
        return created_calendar
    except Exception as e:
        print(f"Failed to create calendar: {e}")
        return None

# Example usage
# create_new_calendar(service, 'Project X Team')

def update_event(service, calendar_id, event_id, updated_event_data):
    try:
        updated_event = service.events().update(
            calendarId=calendar_id,
            eventId=event_id,
            body=updated_event_data
        ).execute()
        print(f"Event updated: {updated_event.get('htmlLink')}")
        return updated_event
    except Exception as e:
        print(f"Failed to update event: {e}")
        return None

# Example usage (moving an event)
# updated_details = {
#     'start': {
#         'dateTime': '2025-08-27T14:00:00-07:00',
#         'timeZone': 'America/Los_Angeles',
#     },
#     'end': {
#         'dateTime': '2025-08-27T15:00:00-07:00',
#         'timeZone': 'America/Los_Angeles',
#     },
# }
# update_event(service, 'primary', 'your_event_id_here', updated_details)
def delete_event(service, calendar_id, event_id):
    try:
        service.events().delete(
            calendarId=calendar_id,
            eventId=event_id
        ).execute()
        print(f"Event {event_id} deleted successfully.")
        return True
    except Exception as e:
        print(f"Failed to delete event: {e}")
        return False

# Example usage
# delete_event(service, 'primary', 'your_event_id_here')

def get_calendar_id_by_name(service, calendar_name):
    """
    Finds and returns the ID of a calendar based on its name.
    """
    try:
        page_token = None
        while True:
            calendar_list = service.calendarList().list(pageToken=page_token).execute()
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
    
def get_all_events(service, calendar_id):
    """
    Gets all events from a specified calendar and prints their details.
    """
    try:
        events_result = service.events().list(
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

API_NAME = "calendar"
API_VERSION = "v3"
SCOPES = ["https://www.googleapis.com/auth/calendar"]
service = create_service(
    "google_api/client_secret.json", API_NAME, API_VERSION, SCOPES
)
