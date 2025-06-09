from pydantic import BaseModel
from typing import Dict, List, Optional

class TimeInterval(BaseModel):
    horaInicio: str
    horaFin: str

class WorkerScheduleResult(BaseModel):
    id: str
    nombre: str
    horariosAsignados: Dict[str, List[TimeInterval]]

class SolverResponse(BaseModel):
    equipo: Dict
    scheduleTrabajadores: List[WorkerScheduleResult]
    error: Optional[str] = None 