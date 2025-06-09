from datetime import datetime
from fastapi import HTTPException
from app.models.schedule import ScheduleRequest

def validate_time_format(time_str: str) -> bool:
    try:
        datetime.strptime(time_str, '%H:%M:%S')
        return True
    except ValueError:
        return False

def validate_schedule_data(request: ScheduleRequest) -> None:
    # Validate time formats
    if not validate_time_format(request.equipo.horaInicioActividad) or \
       not validate_time_format(request.equipo.horaFinActividad):
        raise HTTPException(status_code=400, detail="Invalid time format in team schedule")
    
    # Validate diasActividad format (should be 7 digits of 0/1)
    if not request.equipo.diasActividad.isdigit() or len(request.equipo.diasActividad) != 7:
        raise HTTPException(status_code=400, detail="diasActividad must be 7 digits of 0/1")
    
    # Validate minimum and maximum hours
    if request.equipo.horasMinDiaria >= request.equipo.horasMaxDiaria:
        raise HTTPException(status_code=400, 
                          detail="Minimum daily hours must be less than maximum daily hours")
    
    # Process and validate worker schedules
    for worker in request.scheduleTrabajadores:
        # Validate worker's required hours
        if worker.horarioGeneral.horasSemanales <= 0:
            raise HTTPException(status_code=400,
                              detail=f"Invalid weekly hours for worker {worker.id}")
        
        # Validate time formats in worker's schedule
        for dia_slot in worker.horarioGeneral.diasObligatorios.values():
            if not validate_time_format(dia_slot.horaInicio) or \
               not validate_time_format(dia_slot.horaFin):
                raise HTTPException(status_code=400,
                                  detail=f"Invalid time format in worker {worker.id}'s required days")
        
        for dia_slot in worker.preferencias.dias.values():
            if not validate_time_format(dia_slot.horaInicio) or \
               not validate_time_format(dia_slot.horaFin):
                raise HTTPException(status_code=400,
                                  detail=f"Invalid time format in worker {worker.id}'s preferences")
        
        for dia_slot in worker.restricciones.dias.values():
            if not validate_time_format(dia_slot.horaInicio) or \
               not validate_time_format(dia_slot.horaFin):
                raise HTTPException(status_code=400,
                                  detail=f"Invalid time format in worker {worker.id}'s restrictions") 