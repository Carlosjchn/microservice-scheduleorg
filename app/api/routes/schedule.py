from fastapi import APIRouter, Depends, HTTPException
from app.models.schedule import ScheduleRequest, ScheduleResponse
from app.services.ai_service import AIService
from app.utils.validators import validate_schedule_data
import structlog
import traceback

logger = structlog.get_logger()

router = APIRouter(prefix="/schedule", tags=["schedule"])

@router.post("/generate", response_model=ScheduleResponse)
async def generate_schedule(
    request: ScheduleRequest,
    ai_service: AIService = Depends(lambda: AIService())
) -> ScheduleResponse:
    """
    Generate a work schedule for a team based on worker preferences and restrictions.
    """
    try:
        # Validate request data
        validate_schedule_data(request)
        
        # Generate schedule using AI service
        schedule = await ai_service.generate_schedule(request)
        
        if "error" in schedule:
            raise HTTPException(status_code=400, detail=schedule["error"])
            
        return ScheduleResponse(**schedule)
        
    except Exception as e:
        logger.error(
            "Error in generate_schedule",
            error=str(e),
            traceback=traceback.format_exc()
        )
        raise HTTPException(status_code=500, detail=str(e)) 