import sys

# El fichero de texto se ha de generar de la forma
#
#      trace-cmd report -r -i <fichero.dat> > report.txt
#
# La opción -r deshabilita los "plugins" que por defecto formatean 
# algunos eventos (ver el output de trace-cmd report -V).
#
# De esta forma todas las lineas tienen el mismo output
# independientemente del tipo de evento que sea.  Separando por
# espacios se obtiene:
#
#   BLOQUE-PROCESO-EJECUTANDO  [CPU] TIMESTAMP:  EVENTO:  PAR1=VAL1 PAR2=VAL2 PAR3=VAL3 ...
#
class glb:
    report_filename = 'trace_cte_report_small.txt'
    first_record = -1
    last_record = -1

class out:
    pid_data = {}
    cpus = []

# Eventos aceptados

# Eventos que no pertenezcan a estos subsistemas son filtrados
accepted_subsystems = ['sched']

# Dentro de los no filtrados eventos que no esten aqui provocan un warning
processed_events = ['sched_switch', 'sched_wakeup', 'sched_migrate_task']
discarded_events = ['sched_stat_runtime']

def main():
    
    report_file = open(glb.report_filename)
    
    # First contains C
    report_file.readline()
    
    # Second line contains CPU=N
    linea_cpu = report_file.readline()

    [token, nr_cpus] = linea_cpu.split('=')

    nr_linea = 2
    # Bucle de lineas generales
    for linea in report_file:
        nr_linea++
        linea = report_file.readline()
        
        # Metaformato de la linea
        # <Proceso_ejecutando> <cpu_ejecutando> <timestamp> <event_name> <params-eventname>
        #  BLOQUE-PROCESO-EJECUTANDO  [CPU] TIMESTAMP:  EVENTO: PAR1=VAL1 PAR2=VAL2 PAR3=VAL3 ...

        bloques = linea.split()

        bloque_timestamp = bloques[2]
        timestamp = bloque_timestamp[0:-1]

        # El 4o bloque es el evento que ademas tiene un : al final
        bloque_evento = bloques[3]

        # Con esto quitamos el ultimo caracter que es un ':'
        evento = bloque_evento[0:-1]

        # Eventos de subsistemas no buscados son ignorados
        [subsys, subevento] = evento.split('_')
        if ! subsys in accepted_subsystems: continue

        # Eventos que estan en discarded tambien son ignorados
        if evento in discarded_events: continue

        # Eventos del subsistema que no son conocidos generan un warning
        if ! evento in processed_events:
            
            print "WARNING: Linea " + nr_linea + " Timestamp = " +
                  timestamp + " evento " + evento + 
                  " no esperado pero ignorado"
            continue

        if (evento == '
           
        
    


if __name__ == '__main__':
    main()
