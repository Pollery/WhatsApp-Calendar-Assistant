# WhatsApp Calendar Assistant

---

## Project Overview

The **WhatsApp Calendar Assistant** is an intelligent bot designed to manage your Google Calendar directly through WhatsApp. By leveraging the power of conversational AI, this bot allows you to schedule, list, update, and delete calendar events using simple, natural language commands.

Built to integrate seamlessly with the Evolution API for WhatsApp and the Google Calendar API, the assistant translates your messages into structured actions, making calendar management faster and more intuitive than ever. Whether you need to schedule a meeting, postpone an appointment, or simply check your agenda, this bot is a powerful tool to streamline your daily routine.

---

## Key Features

The bot currently supports the following core functionalities:

- **Event Creation**: Create new calendar events by providing details such as the summary, date, time, and location. The bot intelligently understands relative dates (e.g., "tomorrow," "next week") and handles recurring events with specific rules (e.g., "every Monday for 3 weeks").
- **Event Management**: Update existing events by changing their date, time, or location. This includes advanced commands like postponing events by a specific period (e.g., "postpone by one week").
- **Event Deletion**: Delete individual events or clear an entire calendar with simple commands like "delete this event" or "clear my agenda."
- **Calendar and Event Listing**: Get a quick overview of your upcoming events or a list of all your calendars.

---

## Getting Started

To run this project, you will need to set up credentials for the following services:

1.  **Evolution API**: For WhatsApp integration.
2.  **Google Calendar API**: To manage your calendars.
3.  **LLM Provider**: An API key for a large language model (LLM) to parse user messages (e.g., Gemini, OpenAI).

---

## Known Issues and Future Enhancements

The following is a list of known issues and planned enhancements to improve the bot's functionality and user experience.

### Known Issues

-   **Generic Event Search**: The current method for finding events by title is not optimized. It searches all calendar events, which can be inefficient for calendars with a large number of entries. This may lead to slower response times.

### Future Enhancements

-   **Expand Update Functionality**: The bot can currently change an event's time and postpone it. Future updates will allow for modifying other event details, such as the **summary (title)**, **description**, and **location**.
-   **User Confirmation Flow**: To prevent accidental changes, especially for commands affecting multiple events, the bot will be enhanced to ask for user confirmation before executing potentially destructive actions.
-   **Advanced Recurrence Handling**: While the bot can create recurring events, it currently lacks the ability to modify or delete a **single occurrence** within a recurring series. This feature will be added to give users more granular control over their schedules.