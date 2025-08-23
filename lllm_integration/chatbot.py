import os
import datetime
import sys
import pytz
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.pydantic_v1 import BaseModel, Field


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


def get_current_saopaulo_date() -> str:
    """
    Returns the current date and time in the America/Sao_Paulo timezone.

    The format is 'YYYY-MM-DD HH:MM:SS TZ'. This is crucial for the LLM
    to have an accurate reference point for relative date calculations.
    """
    try:
        saopaulo_tz = pytz.timezone("America/Sao_Paulo")
        now_in_saopaulo = datetime.datetime.now(saopaulo_tz)
        return now_in_saopaulo.strftime("%Y-%m-%d %H:%M:%S %Z")
    except Exception as e:
        print(f"Error getting São Paulo date: {e}")
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# Define the Pydantic model for the event JSON.
# This schema is compatible with the Google Calendar API "Events" resource.
class Event(BaseModel):
    """Event information to be used for Google Calendar."""

    summary: str = Field(description="The event's title or summary.")
    start_date: str = Field(
        description="The start date of the event in 'YYYY-MM-DD' format."
    )
    end_date: str = Field(
        description="The end date of the event in 'YYYY-MM-DD' format. If it is a one day event, it should be the same as the start_date."
    )
    start_time: str = Field(
        description="The start time of the event in 'HH:MM:SS' format."
    )
    end_time: str = Field(
        description="The end time of the event in 'HH:MM:SS' format."
    )
    location: str = Field(description="The location of the event.")
    description: str = Field(
        description="A brief description of the event."
    )


class GeminiChatbot:
    """
    A chatbot class that interacts with the Google Gemini API via LangChain.
    """

    def __init__(self, model_name: str = "gemini-2.0.flash"):
        """
        Initializes the chatbot with a specified Gemini model.
        """
        try:
            if "GOOGLE_API_KEY" not in os.environ:
                os.environ["GOOGLE_API_KEY"] = config.get(
                    "GOOGLE_API_KEY"
                )

            self.llm = ChatGoogleGenerativeAI(
                model=model_name,
                temperature=0.7,
            )
        except ValueError as e:
            print(f"Error initializing the GeminiChatbot: {e}")
            self.llm = None
        except Exception as e:
            print(
                f"An unexpected error occurred during initialization: {e}"
            )
            self.llm = None

    def ask_question(self, user_question: str) -> dict:
        """
        Sends a question to the Gemini model to extract event information.

        Args:
            user_question (str): The user's message.

        Returns:
            dict: The extracted event information as a dictionary, or an
                  error message if an issue occurred.
        """
        if not self.llm:
            return {
                "error": "Chatbot is not initialized. Please check the API key."
            }

        # Define the parser and instructions based on the Pydantic model.
        parser = JsonOutputParser(pydantic_object=Event)

        # Create a structured prompt that instructs the model to act as a parser.
        prompt = ChatPromptTemplate.from_template(
            """
        You are an expert event and reminder extractor. Your task is to extract information from a user's message and format it into a valid JSON object.

        Current date for reference: {current_date}
        
        If the message contains a reminder or an event, generate a JSON object with the following fields:
        - summary: The title of the event.
        - start_date: The start date in 'YYYY-MM-DD' format. If the user mentions a day like "tomorrow" or "next Friday," calculate the correct date.
        - end_date: The end date in 'YYYY-MM-DD' format. If it's a single-day event, use the same date as start_date.
        - location: The location of the event. If not specified, user a descriptive string like "To be determined".
        - description: A brief description of the event.

        You MUST adhere to the following rules:
        1. The response MUST be a valid JSON object.
        2. You MUST use the exact field names specified.
        3. Do not include any additional text or expanations outside the JSON.
        4. If a piece of information is not present, use a sensible default (e.g., 'To be determined', '00:00:00', or the same start/end date)
        5. If its not something that should go on a calendar like a question or a description of an object, etc. you should return an empty json.
        6. All text that can be in portugues brasileiro should be unless is the name of the place os brandname.
        
        Here is the JSON schema you must follow:
            {format_instructions}

            User message: {question}
        """
        ).partial(format_instructions=parser.get_format_instructions())

        try:
            # Create a chain to parse the output.
            current_date_str = get_current_saopaulo_date()
            chain = prompt | self.llm | parser
            response = chain.invoke(
                {
                    "question": user_question,
                    "current_date": current_date_str,
                }
            )
            return response
        except Exception as e:
            return {
                "error": f"An error occured while getting a response: {e}"
            }


# Example Usage
if __name__ == "__main__":
    # 1. Instatiate the chatbot.
    chatbot = GeminiChatbot(model_name="gemini-2.0-flash")

    # 2. Test a simple reminder.
    question_1 = "Me lembre de tomar remédio amanha as 14h"
    answer_1 = chatbot.ask_question(question_1)
    print(f"User Message: {question_1}")
    print("Generated JSON:")
    print(answer_1)
    print("\n" + "=" * 30 + "\n")

    # 3. Test an event with more details.
    question_2 = (
        "Maruqe uma reunião sexta feira as 15h na sala de conferencia"
    )
    answer_2 = chatbot.ask_question(question_2)
    print(f"User Message: {question_2}")
    print("Generated JSON:")
    print(answer_2)
    print("\n" + "=" * 30 + "\n")

    # 4. Test a message that is not a reminder or event.
    question_4 = "What is the capital of France?"
    answer_4 = chatbot.ask_question(question_4)
    print(f"User Message: {question_4}")
    print("Generated JSON:")
    print(answer_4)
    print("\n" + "=" * 30 + "\n")
