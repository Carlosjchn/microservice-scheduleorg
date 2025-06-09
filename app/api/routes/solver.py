from fastapi import APIRouter, HTTPException, Depends
from app.models.schedule import ScheduleRequest, ScheduleResponse
from app.services.solver_service import SolverService
from app.utils.validators import validate_schedule_data

router = APIRouter(prefix="/solver", tags=["solver"])

@router.post("/optimize", response_model=ScheduleResponse)
async def optimize_schedule(
    request: ScheduleRequest,
    solver_service: SolverService = Depends(lambda: SolverService())
) -> ScheduleResponse:
    """
    Optimiza el horario usando OR-Tools constraint programming solver.
    
    Este endpoint utiliza programación con restricciones para generar un horario
    optimizado que:
    - Respeta las restricciones de cada trabajador
    - Maximiza el cumplimiento de las preferencias
    - Cumple con las horas mínimas y máximas diarias
    - Cumple con las horas semanales requeridas
    """
    try:
        # Validate request data
        validate_schedule_data(request)
        
        # Convert Pydantic model to dict and solve
        result = solver_service.solve_schedule(request.model_dump())
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
            
        return ScheduleResponse(**result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 