import google.generativeai as genai
import json
from typing import Dict, Any
import structlog
import traceback
from app.config import get_settings
from app.models.schedule import ScheduleRequest
from fastapi import HTTPException

logger = structlog.get_logger()

class AIService:
    def __init__(self):
        settings = get_settings()
        if not settings.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel(settings.MODEL_NAME)

    def _create_prompt(self, request: ScheduleRequest) -> str:
        system_prompt = """You are an expert assistant in generating work schedules for teams. You must respond ONLY with a JSON object containing the schedule, no explanations or additional text."""
        
        task_instructions = """
Given the team and worker data below, generate an optimized weekly schedule that:

1. Respects each worker's restrictions (never assign work during restricted hours)
2. Maximizes alignment with worker preferences when possible
3. Fulfills each worker's weekly hours requirement
4. Stays within the team's activity days (diasActividad where 1=active, 0=inactive)
5. Stays within the team's activity hours (horaInicioActividad to horaFinActividad)
6. Assigns at least horasMinDiaria and at most horasMaxDiaria hours per day per worker
7. Ensures all workers are included in the schedule
8. Assigns work only on days marked as "diasObligatorios" for each worker

Remember:
- Time slots must be in HH:MM:SS format
- Days must be in Spanish (Lunes, Martes, etc.)
- Each day's schedule must be a list of shifts with workerId, startTime, and endTime
- Only include days that have assigned shifts
- Ensure shifts don't overlap for the same worker"""

        output_format = """
The response must be EXACTLY in this format (only the JSON, no other text):
{
  "commonSchedule": {
    "Lunes": [
      {
        "workerId": "T001",
        "startTime": "09:00:00",
        "endTime": "13:00:00"
      }
    ],
    "Martes": [
      {
        "workerId": "T001",
        "startTime": "09:00:00",
        "endTime": "17:00:00"
      }
    ]
  }
}

IMPORTANT RULES FOR THE OUTPUT:
1. The response MUST contain ONLY the "commonSchedule" field at the root level
2. Each day MUST be in Spanish: "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"
3. Each shift MUST have exactly these fields: "workerId", "startTime", "endTime"
4. All times MUST be in "HH:MM:SS" format
5. Only include days that have shifts assigned
6. Each day MUST have a non-empty array of shifts
7. DO NOT include any additional fields or properties"""
        
        try:
            input_data = json.dumps(request.model_dump(), ensure_ascii=False, indent=2)
            prompt = f"{system_prompt}\n\n{task_instructions}\n\nRequired Output Format:\n{output_format}\n\nInput Data:\n{input_data}"
            
            # Log the complete prompt
            logger.info(
                "Generated prompt for AI model",
                system_prompt=system_prompt,
                task_instructions=task_instructions,
                output_format=output_format,
                input_data=input_data
            )
            
            return prompt
            
        except Exception as e:
            logger.error("Error creating prompt", error=str(e), traceback=traceback.format_exc())
            raise

    async def generate_schedule(self, request: ScheduleRequest) -> Dict[str, Any]:
        try:
            prompt = self._create_prompt(request)
            
            # Log the exact prompt being sent
            print("\n=== PROMPT ENVIADO AL MODELO ===")
            print(prompt)
            print("\n=== FIN DEL PROMPT ===\n")
            
            response = self.model.generate_content(prompt)
            
            if not response.text:
                logger.error("Empty response from AI model")
                return {"error": "No se pudo generar el horario: respuesta vacía del modelo"}
            
            # Log the AI response
            print("\n=== RESPUESTA DEL MODELO ===")
            print(response.text)
            print("\n=== FIN DE LA RESPUESTA ===\n")
            
            try:
                logger.info("AI response received", response_text=response.text)
                # Clean the response text by removing markdown code block markers
                cleaned_response = response.text.replace("```json", "").replace("```", "").strip()
                schedule_data = json.loads(cleaned_response)
                
                if "commonSchedule" not in schedule_data:
                    logger.error("Invalid response format", response=response.text)
                    return {"error": "Formato de respuesta inválido del modelo"}
                
                # Validate the schedule structure
                common_schedule = schedule_data["commonSchedule"]
                if not isinstance(common_schedule, dict):
                    logger.error("Invalid schedule format", schedule=common_schedule)
                    return {"error": "Formato de horario inválido"}
                
                # Convert day names to Spanish if needed
                day_mapping = {
                    "Monday": "Lunes",
                    "Tuesday": "Martes",
                    "Wednesday": "Miércoles",
                    "Thursday": "Jueves",
                    "Friday": "Viernes",
                    "Saturday": "Sábado",
                    "Sunday": "Domingo"
                }
                
                formatted_schedule = {}
                for day, shifts in common_schedule.items():
                    spanish_day = day_mapping.get(day, day)
                    formatted_schedule[spanish_day] = shifts
                
                return {"commonSchedule": formatted_schedule}
                
            except json.JSONDecodeError as e:
                logger.error("Failed to parse AI response", error=str(e), response=response.text)
                return {"error": "Error al procesar la respuesta del modelo"}
                
        except Exception as e:
            logger.error(
                "Error generating schedule",
                error=str(e),
                traceback=traceback.format_exc()
            )
            return {"error": f"Error al generar el horario: {str(e)}"} 