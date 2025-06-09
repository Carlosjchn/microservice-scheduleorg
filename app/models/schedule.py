from pydantic import BaseModel, Field
from typing import Dict, List, Optional

class TimeSlot(BaseModel):
    horaInicio: str = Field(..., description="Start time in HH:MM:SS format")
    horaFin: str = Field(..., description="End time in HH:MM:SS format")

class DayPreference(BaseModel):
    dias: Dict[str, TimeSlot] = Field(..., description="Day preferences with time slots")

class GeneralSchedule(BaseModel):
    diasObligatorios: Dict[str, TimeSlot] = Field(..., description="Required working days with their time slots")
    horasSemanales: int = Field(..., description="Required weekly hours")

class WorkerSchedule(BaseModel):
    id: str = Field(..., description="Worker ID")
    nombre: str = Field(..., description="Worker name")
    preferencias: DayPreference = Field(..., description="Worker's schedule preferences")
    restricciones: DayPreference = Field(..., description="Worker's schedule restrictions")
    horarioGeneral: GeneralSchedule = Field(..., description="General schedule requirements")

class Team(BaseModel):
    idEquipo: int = Field(..., description="Team ID")
    tipo: str = Field(..., description="Team type")
    nombre: str = Field(..., description="Team name")
    diasActividad: str = Field(..., pattern="^[01]{7}$", description="Activity days in binary format (7 digits)")
    horaInicioActividad: str = Field(..., description="Activity start time in HH:MM:SS format")
    horaFinActividad: str = Field(..., description="Activity end time in HH:MM:SS format")
    horasMinDiaria: int = Field(..., ge=0, description="Minimum daily hours")
    horasMaxDiaria: int = Field(..., gt=0, description="Maximum daily hours")

class ScheduleRequest(BaseModel):
    equipo: Team = Field(..., description="Team information")
    scheduleTrabajadores: List[WorkerSchedule] = Field(..., description="List of workers with their schedules")

    class Config:
        json_schema_extra = {
            "example": {
                "equipo": {
                    "idEquipo": 12345,
                    "tipo": "Comercial",
                    "nombre": "Mi Negocio",
                    "diasActividad": "1111100",
                    "horaInicioActividad": "08:00:00",
                    "horaFinActividad": "17:00:00",
                    "horasMinDiaria": 4,
                    "horasMaxDiaria": 8
                },
                "scheduleTrabajadores": [
                    {
                        "id": "T001",
                        "nombre": "Juan Pérez",
                        "preferencias": {
                            "dias": {
                                "Lunes": {
                                    "horaInicio": "09:00:00",
                                    "horaFin": "15:00:00"
                                },
                                "Martes": {
                                    "horaInicio": "09:00:00",
                                    "horaFin": "15:00:00"
                                }
                            }
                        },
                        "restricciones": {
                            "dias": {
                                "Miércoles": {
                                    "horaInicio": "13:00:00",
                                    "horaFin": "18:00:00"
                                }
                            }
                        },
                        "horarioGeneral": {
                            "diasObligatorios": {
                                "Lunes": {
                                    "horaInicio": "08:00:00",
                                    "horaFin": "17:00:00"
                                },
                                "Martes": {
                                    "horaInicio": "08:00:00",
                                    "horaFin": "17:00:00"
                                },
                                "Miércoles": {
                                    "horaInicio": "08:00:00",
                                    "horaFin": "17:00:00"
                                },
                                "Jueves": {
                                    "horaInicio": "08:00:00",
                                    "horaFin": "17:00:00"
                                },
                                "Viernes": {
                                    "horaInicio": "08:00:00",
                                    "horaFin": "17:00:00"
                                }
                            },
                            "horasSemanales": 40
                        }
                    }
                ]
            }
        }

class WorkerShift(BaseModel):
    workerId: str = Field(..., description="Worker ID")
    startTime: str = Field(..., description="Shift start time in HH:MM:SS format")
    endTime: str = Field(..., description="Shift end time in HH:MM:SS format")

class ScheduleResponse(BaseModel):
    commonSchedule: Dict[str, List[WorkerShift]] = Field(
        ..., 
        description="Schedule organized by day, with list of worker shifts"
    ) 