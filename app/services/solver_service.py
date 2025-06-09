from ortools.sat.python import cp_model
from typing import Dict, Any, List
import structlog
from app.models.schedule import WorkerShift

logger = structlog.get_logger()

class SolverService:
    DAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    
    @staticmethod
    def time_str_to_minutes(t_str: str) -> int:
        h, m, s = map(int, t_str.split(':'))
        return h * 60 + m

    @staticmethod
    def minutes_to_time_str(m: int) -> str:
        h = m // 60
        mm = m % 60
        return f"{h:02d}:{mm:02d}:00"

    def solve_schedule(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            logger.info("Iniciando proceso de resolución de horario")
            equipo = input_data["equipo"]
            trabajadores = input_data["scheduleTrabajadores"]

            dias_actividad = equipo["diasActividad"]
            hora_inicio_act = self.time_str_to_minutes(equipo["horaInicioActividad"])
            hora_fin_act = self.time_str_to_minutes(equipo["horaFinActividad"])
            horas_min_diaria = equipo["horasMinDiaria"] * 60
            horas_max_diaria = equipo["horasMaxDiaria"] * 60

            logger.info("Configuración inicial", 
                       hora_inicio=equipo["horaInicioActividad"],
                       hora_fin=equipo["horaFinActividad"],
                       horas_min=equipo["horasMinDiaria"],
                       horas_max=equipo["horasMaxDiaria"])

            # Modelo
            model = cp_model.CpModel()

            # Variables
            interval_length = 15  # bloques de 15 minutos
            num_slots = (hora_fin_act - hora_inicio_act) // interval_length
            logger.info(f"Número de slots calculados: {num_slots}")

            # Map para buscar índice día según nombre
            day_to_idx = {d: i for i, d in enumerate(self.DAYS)}

            # Filtrar días activos
            active_days_idx = [i for i, val in enumerate(dias_actividad) if val == '1']
            logger.info(f"Días activos: {[self.DAYS[i] for i in active_days_idx]}")

            # Variables por trabajador, día y slot
            work = {}
            for t_idx, t in enumerate(trabajadores):
                for d_idx in active_days_idx:
                    for s in range(num_slots):
                        work[(t_idx, d_idx, s)] = model.NewBoolVar(f"work_t{t_idx}_d{d_idx}_s{s}")

            # Variables auxiliares para detectar inicios y finales de turnos
            shift_start = {}
            shift_end = {}
            for t_idx, t in enumerate(trabajadores):
                for d_idx in active_days_idx:
                    for s in range(num_slots):
                        shift_start[(t_idx, d_idx, s)] = model.NewBoolVar(f"start_t{t_idx}_d{d_idx}_s{s}")
                        shift_end[(t_idx, d_idx, s)] = model.NewBoolVar(f"end_t{t_idx}_d{d_idx}_s{s}")

            # Variables para contar número de turnos por día (para minimizar fragmentación)
            num_shifts_per_day = {}
            for t_idx, t in enumerate(trabajadores):
                for d_idx in active_days_idx:
                    num_shifts_per_day[(t_idx, d_idx)] = model.NewIntVar(0, num_slots, f"num_shifts_t{t_idx}_d{d_idx}")

            # Variables para desviación de horas semanales (solo por debajo)
            weekly_deviations = []
            weekly_hours_vars = []

            # Restricciones diarias con flexibilidad de ±1 hora
            for t_idx, t in enumerate(trabajadores):
                for d_idx in active_days_idx:
                    slots_vars = [work[(t_idx, d_idx, s)] for s in range(num_slots)]
                    total_minutes = model.NewIntVar(0, horas_max_diaria + 60, f"total_minutes_t{t_idx}_d{d_idx}")
                    model.Add(total_minutes == sum(slots_vars) * interval_length)
                    
                    # Variable para la desviación diaria
                    daily_deviation_up = model.NewIntVar(0, 60, f"daily_deviation_up_t{t_idx}_d{d_idx}")  # Máximo 1 hora arriba
                    daily_deviation_down = model.NewIntVar(0, 60, f"daily_deviation_down_t{t_idx}_d{d_idx}")  # Máximo 1 hora abajo
                    
                    # Si hay horas trabajadas ese día (total_minutes > 0), aplicar límites con flexibilidad
                    has_work = model.NewBoolVar(f"has_work_t{t_idx}_d{d_idx}")
                    model.Add(total_minutes > 0).OnlyEnforceIf(has_work)
                    model.Add(total_minutes == 0).OnlyEnforceIf(has_work.Not())
                    
                    # Restricción de máximo diario con flexibilidad hacia arriba
                    model.Add(total_minutes <= horas_max_diaria + daily_deviation_up).OnlyEnforceIf(has_work)
                    
                    # Restricción de mínimo diario con flexibilidad hacia abajo
                    model.Add(total_minutes >= horas_min_diaria - daily_deviation_down).OnlyEnforceIf(has_work)
                    
                    # Logging de las desviaciones diarias
                    logger.info(f"Configurando límites diarios flexibles para trabajador {t['id']} en {self.DAYS[d_idx]}", 
                               min_diario=(horas_min_diaria - 60)/60,
                               max_diario=(horas_max_diaria + 60)/60)

            # Restricciones semanales con desviación permitida solo por debajo
            for t_idx, t in enumerate(trabajadores):
                slots_vars = []
                for d_idx in active_days_idx:
                    slots_vars.extend([work[(t_idx, d_idx, s)] for s in range(num_slots)])
                
                horas_semanales = t["horarioGeneral"]["horasSemanales"] * 60
                total_week_minutes = model.NewIntVar(0, horas_semanales, f"total_week_minutes_t{t_idx}")  # Limitado a horas semanales
                model.Add(total_week_minutes == sum(slots_vars) * interval_length)
                weekly_hours_vars.append(total_week_minutes)
                
                min_semanal = int(horas_semanales * 0.7)  # Reducimos el mínimo al 70%
                
                logger.info(f"Configurando restricciones semanales para trabajador {t['id']}", 
                           horas_semanales=horas_semanales,
                           min_semanal=min_semanal)
                
                # Variable para la desviación (solo por debajo)
                deviation = model.NewIntVar(0, horas_semanales - min_semanal, f"deviation_t{t_idx}")
                weekly_deviations.append(deviation)
                
                # La desviación ahora solo mide cuánto falta para llegar al objetivo
                model.Add(total_week_minutes + deviation == horas_semanales)
                
                # Asegurar un mínimo de horas
                model.Add(total_week_minutes >= min_semanal)

            # Restricciones para detectar inicios y finales de turnos
            for t_idx, t in enumerate(trabajadores):
                for d_idx in active_days_idx:
                    for s in range(num_slots):
                        # Detectar inicio de turno
                        if s == 0:
                            # Primer slot del día
                            model.Add(shift_start[(t_idx, d_idx, s)] == work[(t_idx, d_idx, s)])
                        else:
                            # Un turno empieza si este slot está trabajando pero el anterior no
                            model.AddBoolOr([
                                shift_start[(t_idx, d_idx, s)].Not(),
                                work[(t_idx, d_idx, s)]
                            ])
                            model.AddBoolOr([
                                shift_start[(t_idx, d_idx, s)].Not(),
                                work[(t_idx, d_idx, s-1)].Not()
                            ])
                            model.AddBoolAnd([
                                work[(t_idx, d_idx, s)],
                                work[(t_idx, d_idx, s-1)].Not()
                            ]).OnlyEnforceIf(shift_start[(t_idx, d_idx, s)])
                        
                        # Detectar final de turno
                        if s == num_slots - 1:
                            # Último slot del día
                            model.Add(shift_end[(t_idx, d_idx, s)] == work[(t_idx, d_idx, s)])
                        else:
                            # Un turno termina si este slot está trabajando pero el siguiente no
                            model.AddBoolOr([
                                shift_end[(t_idx, d_idx, s)].Not(),
                                work[(t_idx, d_idx, s)]
                            ])
                            model.AddBoolOr([
                                shift_end[(t_idx, d_idx, s)].Not(),
                                work[(t_idx, d_idx, s+1)].Not()
                            ])
                            model.AddBoolAnd([
                                work[(t_idx, d_idx, s)],
                                work[(t_idx, d_idx, s+1)].Not()
                            ]).OnlyEnforceIf(shift_end[(t_idx, d_idx, s)])
                    
                    # Contar número de turnos por día (número de inicios)
                    model.Add(num_shifts_per_day[(t_idx, d_idx)] == sum(shift_start[(t_idx, d_idx, s)] for s in range(num_slots)))

            # Restricciones para turnos mínimos de 1 hora (4 bloques de 15 min)
            min_shift_blocks = 4  # 1 hora = 4 bloques de 15 minutos
            for t_idx, t in enumerate(trabajadores):
                for d_idx in active_days_idx:
                    # Para cada posible inicio de turno, si empieza debe durar al menos min_shift_blocks
                    for s in range(num_slots - min_shift_blocks + 1):
                        # Si hay un inicio en s, debe haber trabajo en los siguientes min_shift_blocks-1 slots
                        for offset in range(1, min_shift_blocks):
                            if s + offset < num_slots:
                                model.Add(work[(t_idx, d_idx, s + offset)] == 1).OnlyEnforceIf(shift_start[(t_idx, d_idx, s)])
                    
                    # Para turnos que empiezan muy cerca del final del día, aplicar restricción más flexible
                    for s in range(max(0, num_slots - min_shift_blocks + 1), num_slots):
                        # Si hay un inicio muy cerca del final, debe trabajar hasta el final del día disponible
                        remaining_slots = num_slots - s
                        for offset in range(1, remaining_slots):
                            model.Add(work[(t_idx, d_idx, s + offset)] == 1).OnlyEnforceIf(shift_start[(t_idx, d_idx, s)])

            # Días obligatorios con ventanas de tiempo
            for t_idx, t in enumerate(trabajadores):
                dias_obligatorios = t["horarioGeneral"]["diasObligatorios"]
                for dia_str, horario in dias_obligatorios.items():
                    if dia_str in day_to_idx and day_to_idx[dia_str] in active_days_idx:
                        d_idx = day_to_idx[dia_str]
                        hora_inicio_obl = self.time_str_to_minutes(horario["horaInicio"])
                        hora_fin_obl = self.time_str_to_minutes(horario["horaFin"])
                        
                        logger.info(f"Procesando día obligatorio para trabajador {t['id']}", 
                                   dia=dia_str,
                                   hora_inicio=horario["horaInicio"],
                                   hora_fin=horario["horaFin"])
                        
                        # Variables para los slots dentro de la ventana obligatoria
                        mandatory_slots = []
                        for s in range(num_slots):
                            slot_start = hora_inicio_act + s * interval_length
                            slot_end = slot_start + interval_length
                            if slot_start >= hora_inicio_obl and slot_end <= hora_fin_obl:
                                mandatory_slots.append(work[(t_idx, d_idx, s)])
                        
                        if mandatory_slots:
                            # Asegurar mínimo de horas en días obligatorios
                            total_minutes = model.NewIntVar(0, hora_fin_obl - hora_inicio_obl, 
                                                         f"total_minutes_mandatory_t{t_idx}_d{d_idx}")
                            model.Add(total_minutes == sum(mandatory_slots) * interval_length)
                            min_required = min(horas_min_diaria, hora_fin_obl - hora_inicio_obl)
                            model.Add(total_minutes >= min_required)
                            
                            logger.info(f"Configurando mínimo para día obligatorio", 
                                       trabajador=t['id'],
                                       dia=dia_str,
                                       min_required=min_required)
                            
                        # Prohibir trabajo fuera de la ventana obligatoria en días obligatorios
                        for s in range(num_slots):
                            slot_start = hora_inicio_act + s * interval_length
                            slot_end = slot_start + interval_length
                            if slot_end <= hora_inicio_obl or slot_start >= hora_fin_obl:
                                model.Add(work[(t_idx, d_idx, s)] == 0)

            # Restricciones horarias
            for t_idx, t in enumerate(trabajadores):
                restricciones = t["restricciones"]["dias"]
                for dia_str, horas in restricciones.items():
                    if dia_str in day_to_idx and day_to_idx[dia_str] in active_days_idx:
                        d_idx = day_to_idx[dia_str]
                        restr_inicio = self.time_str_to_minutes(horas["horaInicio"])
                        restr_fin = self.time_str_to_minutes(horas["horaFin"])
                        
                        logger.info(f"Aplicando restricción horaria", 
                                   trabajador=t['id'],
                                   dia=dia_str,
                                   inicio=horas["horaInicio"],
                                   fin=horas["horaFin"])
                        
                        for s in range(num_slots):
                            slot_start = hora_inicio_act + s * interval_length
                            slot_end = slot_start + interval_length
                            if not (slot_end <= restr_inicio or slot_start >= restr_fin):
                                model.Add(work[(t_idx, d_idx, s)] == 0)

            # Preferencias
            preference_literals = []
            for t_idx, t in enumerate(trabajadores):
                preferencias = t["preferencias"]["dias"]
                for dia_str, horas in preferencias.items():
                    if dia_str in day_to_idx and day_to_idx[dia_str] in active_days_idx:
                        d_idx = day_to_idx[dia_str]
                        pref_inicio = self.time_str_to_minutes(horas["horaInicio"])
                        pref_fin = self.time_str_to_minutes(horas["horaFin"])
                        
                        logger.info(f"Procesando preferencia", 
                                   trabajador=t['id'],
                                   dia=dia_str,
                                   inicio=horas["horaInicio"],
                                   fin=horas["horaFin"])
                        
                        for s in range(num_slots):
                            slot_start = hora_inicio_act + s * interval_length
                            slot_end = slot_start + interval_length
                            if slot_start >= pref_inicio and slot_end <= pref_fin:
                                preference_literals.append(work[(t_idx, d_idx, s)])

            # Función objetivo: minimizar desviaciones, maximizar preferencias y minimizar fragmentación
            logger.info(f"Número de preferencias a optimizar: {len(preference_literals) if preference_literals else 0}")
            
            # Pesos para diferentes objetivos
            preference_weight = 1
            deviation_weight = 10  # Mayor peso para minimizar desviaciones
            fragmentation_weight = 15  # Penalizar mucho la fragmentación
            
            objective_terms = []
            
            # Añadir términos de preferencia (positivos)
            if preference_literals:
                for pref in preference_literals:
                    objective_terms.append(preference_weight * pref)
            
            # Añadir términos de desviación (negativos)
            for dev in weekly_deviations:
                objective_terms.append(-deviation_weight * dev)
            
            # Añadir términos de anti-fragmentación (negativos - penalizar múltiples turnos por día)
            for t_idx, t in enumerate(trabajadores):
                for d_idx in active_days_idx:
                    # Penalizar cada turno adicional después del primero
                    # Si hay 1 turno = 0 penalización, 2 turnos = -15, 3 turnos = -30, etc.
                    penalty_var = model.NewIntVar(0, num_slots * fragmentation_weight, f"frag_penalty_t{t_idx}_d{d_idx}")
                    # penalty = max(0, (num_shifts - 1) * fragmentation_weight)
                    shifts_minus_one = model.NewIntVar(-1, num_slots - 1, f"shifts_minus_one_t{t_idx}_d{d_idx}")
                    model.Add(shifts_minus_one == num_shifts_per_day[(t_idx, d_idx)] - 1)
                    model.AddMaxEquality(penalty_var, [0, shifts_minus_one * fragmentation_weight])
                    objective_terms.append(-penalty_var)
            
            logger.info(f"Configurando función objetivo con {len(objective_terms)} términos")
            model.Maximize(sum(objective_terms))

            # Resolver
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = 60.0  # Límite de tiempo de 60 segundos para mejores soluciones
            solver.parameters.num_search_workers = 4  # Usar múltiples hilos para acelerar la búsqueda
            logger.info("Iniciando resolución del modelo")
            status = solver.Solve(model)
            logger.info(f"Estado de la resolución: {status}")

            if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                logger.info("Solución encontrada, procesando resultados")
                
                # Logging de las horas asignadas y fragmentación
                for t_idx, t in enumerate(trabajadores):
                    total_assigned = solver.Value(weekly_hours_vars[t_idx])
                    deviation = solver.Value(weekly_deviations[t_idx])
                    target_hours = t["horarioGeneral"]["horasSemanales"] * 60
                    
                    # Calcular fragmentación total
                    total_shifts = sum(solver.Value(num_shifts_per_day[(t_idx, d_idx)]) for d_idx in active_days_idx)
                    days_working = sum(1 for d_idx in active_days_idx if solver.Value(num_shifts_per_day[(t_idx, d_idx)]) > 0)
                    
                    logger.info(f"Resumen para trabajador {t['id']}", 
                               horas_objetivo=target_hours/60,
                               horas_asignadas=total_assigned/60,
                               horas_faltantes=deviation/60,
                               dias_trabajando=days_working,
                               turnos_totales=total_shifts,
                               promedio_turnos_por_dia=round(total_shifts/max(days_working, 1), 2))
                
                # Initialize response structure
                common_schedule: Dict[str, List[WorkerShift]] = {}
                
                # Process results for each active day
                for d_idx in active_days_idx:
                    dia_nombre = self.DAYS[d_idx]
                    day_shifts: List[WorkerShift] = []
                    
                    # Process each worker's schedule for this day
                    for t_idx, t in enumerate(trabajadores):
                        bloques_trabajados = []
                        for s in range(num_slots):
                            if solver.Value(work[(t_idx, d_idx, s)]) == 1:
                                bloques_trabajados.append(s)
                                
                        if bloques_trabajados:
                            # Group consecutive blocks
                            bloques_trabajados.sort()
                            intervals = []
                            start = bloques_trabajados[0]
                            prev = start
                            
                            for b in bloques_trabajados[1:]:
                                if b == prev + 1:
                                    prev = b
                                else:
                                    intervals.append((start, prev))
                                    start = b
                                    prev = b
                            intervals.append((start, prev))
                            
                            # Convert blocks to time intervals
                            for (inicio, fin) in intervals:
                                start_time = self.minutes_to_time_str(hora_inicio_act + inicio * interval_length)
                                end_time = self.minutes_to_time_str(hora_inicio_act + (fin + 1) * interval_length)
                                
                                day_shifts.append(WorkerShift(
                                    workerId=t["id"],
                                    startTime=start_time,
                                    endTime=end_time
                                ))
                                
                            logger.info(f"Turnos generados para trabajador", 
                                       trabajador=t['id'],
                                       dia=dia_nombre,
                                       num_turnos=len(intervals))
                    
                    if day_shifts:  # Only add days with shifts
                        common_schedule[dia_nombre] = day_shifts
                
                logger.info("Proceso completado exitosamente")
                return {"commonSchedule": common_schedule}
            else:
                logger.error("No se pudo encontrar una solución factible", status=status)
                return {"error": "No se pudo encontrar una solución factible."}
                
        except Exception as e:
            logger.error("Error al resolver el horario", error=str(e))
            return {"error": f"Error al resolver el horario: {str(e)}"} 