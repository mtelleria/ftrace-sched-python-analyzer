#!/usr/bin/python
# -*- coding: utf-8 -*-

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
    report_filename = 'report.txt'
    first_record = -1
    last_record = -1


class Timestamp:

    def __init__(self):
        self.sg = 0
        self.us = 0
        
    def from_sg_us(self, sg, us):
        self.sg = sg
        self.us = us
        return self

    def from_string(self, cadena):
        [sg, us] = cadena.split('.')
        self.sg = int(sg)
        self.us = int(us)
        return self

    def stcopy(self, uno):
        otro = Timestamp()
        otro.sg = uno.sg
        otro.us = uno.us
        return otro

    def to_msg(self):
        return int(self.sg * 1000 + self.us/1000)

    def __cmp__(self, other):
        sg_cmp = cmp(self.sg, other.sg)
        if sg_cmp != 0:
            return sg_cmp
        else:
            return cmp(self.us, other.us)

    def __add__(self, other):
        us = self.us + other.us
        sg = self.sg + other.sg

        if (us > 1000000):
            us -= 1000000
            sg += 1

        res = Timestamp()
        res.sg = sg
        res.us = us
        return res

    def __sub__(self, other):
        sg = self.sg - other.sg
        us = self.us - other.us
        if us < 0 :
            us += 1000000
            sg -= 1

        res = Timestamp()
        res.sg = sg
        res.us = us
        return res

        
class result:
    pid_data = {}
    cpus = []
    ts_first = Timestamp()

class Muestra:
    nr_linea = 0
    linea = ""
    ts_str = ""
    evento = ""
    subsys = ""
    ts = Timestamp()
    basecmd = ""
    pid_= -1
    cpu = -1
    param = []

    def escribe(self):
        print ("nr_linea: " + str(self.nr_linea) + " evento: " + self.evento + " subsys: " + self.subsys,
               " ts: " + str(self.ts.sg) + "." + str(self.ts.us) + " basecmd: " + self.basecmd,
               " pid: " + str(self.pid) + " CPU " + str(self.cpu) + " param: " + str(self.param) )
    


class Fragmento:
    comienzo_ms = 0
    duracion_ms = 0
    cpus = [ ]
    hueco = 0
    separacion = 0
    latency = 0
    pid = 0


# Eventos aceptados

# Eventos que no pertenezcan a estos subsistemas son filtrados
accepted_subsystems = ['sched']

# Dentro de los no filtrados eventos que no esten aqui provocan un warning
processed_events = ['sched_switch', 'sched_wakeup', 'sched_migrate_task']
#discarded_events = ['sched_stat_runtime']
discarded_events = ['sched_runtime']

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
        nr_linea += 1
        
        # Metaformato de la linea
        # <Proceso_ejecutando> <cpu_ejecutando> <timestamp> <event_name> <params-eventname>
        #  BLOQUE-PROCESO-EJECUTANDO  [CPU] TIMESTAMP:  EVENTO: PAR1=VAL1 PAR2=VAL2 PAR3=VAL3 ...

        bloques = linea.split()

        bloque_ts = bloques[2]
        ts_str = bloque_ts[0:-1]
        
        if result.ts_first.sg == 0:
            result.ts_first.from_string(ts_str)

        # El 4o bloque es el evento que ademas tiene un : al final
        bloque_evento = bloques[3]

        # Con esto quitamos el ultimo caracter que es un ':'
        evento = bloque_evento[0:-1]

        # Eventos de subsistemas no buscados son ignorados

        [subsys, separador, resto] = evento.partition('_')
        if separador == '':
            exit_error_linea(nr_linea, ts_str, "Evento " + evento + " sin separador de subsystema")


        if not subsys in accepted_subsystems: continue

        # Eventos que estan en discarded tambien son ignorados
        if evento in discarded_events: continue

        # Eventos del subsistema que no son conocidos generan un warning
        if not evento in processed_events:
            
            print ("WARNING: Linea " + str(nr_linea) + " Timestamp = " + ts_str,
                   " evento " + evento + " no esperado pero ignorado")
            continue


        # Realizamos la parte comun
        muestra = Muestra()

        muestra.nr_linea = nr_linea
        muestra.linea = linea
        muestra.ts_str = ts_str
        muestra.evento = evento
        muestra.subsys = subsys
        muestra.ts = Timestamp()
        muestra.ts = muestra.ts.from_string(ts_str) - result.ts_first

        # Bloque PID  ej:  trace-cmd-20674
        [muestra.basecmd, separador, muestra.pid] = bloques[0].rpartition('-')
        if separador == "":
            exit_error_linea(nr_linea, ts_str, "Imposible separar basecmdline y PID")

        # Bloque CPU  ej: [001]
        cpu_str = bloques[1]
        muestra.cpu = int(cpu_str[1:-1])
        muestra.param = equal_asignments_to_dico(bloques[4:])
        
        muestra.escribe()
        


        if evento == 'sched_switch':
            procesa_sched_switch(nr_linea, ts_str, bloques, linea)
        elif evento == 'sched_wakeup':
            procesa_sched_wakeup(nr_linea, ts_str, bloques, linea)
        elif evento == 'sched_migrate_task':
            procesa_sched_migrate_task(nr_linea, ts_str, bloques, linea)
        else:
            exit_error_linea(nr_linea, ts_str, "Error evento " + evento + " no soportado")

    # PRINT RESULT

# -------------------------------------

    
def procesa_sched_switch(nr_linea, ts_str, bloques, linea):
    print "Procesando sched_switch con",
    print "nr_linea: " + str(nr_linea) + " ts_str " + ts_str + " linea: " + linea

def procesa_sched_wakeup(nr_linea, ts_str, bloques, linea):
    print "Procesando sched_wakeup con",
    print "nr_linea: " + str(nr_linea) + " ts_str " + ts_str + " linea: " + linea

def procesa_sched_migrate_task(nr_linea, ts_str, bloques, linea):
    print "Procesando sched_migrate_task con",
    print "nr_linea: " + str(nr_linea) + " ts_str " + ts_str + " linea: " + linea


# ----------------------------------------

def equal_asignments_to_dico(props):
    res = {}
    for prop in props:
        [key, val] = prop.split('=')
        res[key] = val

    return res


def exit_error_linea(nr_linea, ts_str, mensaje):
    print "Linea " + str(nr_linea) + " TS " + ts_str + ": " + mensaje
    exit(-1)



if __name__ == '__main__':
    main()
