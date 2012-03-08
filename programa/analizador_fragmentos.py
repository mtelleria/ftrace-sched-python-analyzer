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
class inp:
    report_filename = 'report.txt'
    first_record = -1
    last_record = -1
    granularity = 30

class Timestamp:

    def __init__(self, sg=0, us=0, string=""):
        if string != "":
            [self.sg, self.us] = string.split('.')
        else:
            self.sg = sg
            self.us = us
        

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

        
class res:
    lwp_dico = {}
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
    comienzo = Timestamp()
    duracion = Timestamp()
    cpus = [ ]
    hueco = 0
    separacion = 0
    latency = 0
    pid = 0

class Lwp_data:
    # Estaticos
    basecmd = ""
    pid = 0

    # Dinamicos

    # as reported by trace.dat
    state = "S"
    
    # As infered by us
    active = False
    en_hueco = False
    
    last_wakeup = Timestamp()
    last_sched_in = Timestamp()
    last_sched_out = Timestamp()
    total_exec = Timestamp()
    total_hueco = Timestamp()
    fragmentos = []
    
    
    
    def new_sched_switch_out(self, muestra):
        self.pid = muestra.param.prev_pid
        self.basecmd = muestra.param.prev_comm
        self.state = glb.state_num_to_char{muestra.param.prev_state}
        self.active = False
        
        self.last_wakeup = new Timestamp()
        self.last_sched_in = new Timestamp()
        self.last_sched_out = muestra.ts
        self.total_exec = new Timestamp()
        self.total_hueco = new Timestamp()

    def new_sched_switch_in(self, muestra):
        self.pid = muestra.param.next_pid
        self.basecmd = muestra.param.next_comm
        self.active = True

        self.last_wakeup = new Timestamp()
        self.last_sched_in = muestra.ts
        self.last_sched_out = Timestamp()
        self.total_exec = new Timestamp()
        self.total_hueco = new Timestamp()



class glb:
    # Eventos que no pertenezcan a estos subsistemas son filtrados
    accepted_subsystems = ['sched']

    # Dentro de los aceptados, estos eventos son tambien ignorados
    discarded_events = ['sched_stat_runtime']

    # Estos son los eventos procesados
    processed_events = ['sched_switch', 'sched_wakeup', 'sched_migrate_task']

    # Eventos dentro de los subsistemas que no son ni ignorados ni procesados 
    # provocan un warning

    # Obtenido de trace-cmd --events | less (y buscando sched_switch)
    state_num_to_char = {"0x0":'R', "0x1":'S', "0x2":"D", "0x4":"T", "0x8":"t", "0x10":"Z", 
                         "0x20":"X", "0x40":"x", "0x80":"W"}

def main():
    
    inp.granularity = Timestamp(0, inp.granularity)
    report_file = open(inp.report_filename)
    
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
            result.ts_first = Timestamp(string=ts_str)

        # El 4o bloque es el evento que ademas tiene un : al final
        bloque_evento = bloques[3]

        # Con esto quitamos el ultimo caracter que es un ':'
        evento = bloque_evento[0:-1]

        # Eventos de subsistemas no buscados son ignorados

        [subsys, separador, resto] = evento.partition('_')
        if separador == '':
            exit_error_linea(nr_linea, ts_str, "Evento " + evento + " sin separador de subsystema")


        if not subsys in glb.accepted_subsystems: continue

        # Eventos que estan en discarded tambien son ignorados
        if evento in glb.discarded_events: continue

        # Eventos del subsistema que no son conocidos generan un warning
        if not evento in glb.processed_events:
            
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
        muestra.ts = Timestamp(string=ts_str) - result.ts_first

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
            procesa_sched_switch(muestra)
        elif evento == 'sched_wakeup':
            procesa_sched_wakeup(muestra)
        elif evento == 'sched_migrate_task':
            procesa_sched_migrate_task(muestra)
        else:
            exit_error_linea(nr_linea, ts_str, "Error evento " + evento + " no soportado")

    # PRINT RESULT

# -------------------------------------

    
def procesa_sched_switch(muestra):
    
    pid_saliente = muestra.param.prev_pid
    pid_entrante = muestra.param.next_pid

    # Tratamiento del PID saliente #
    # -----------------------------#
    if not pid_saliente in res.lwp_dico:
        # Nuevo PID saliente
        lwp_data = Lwp_data()
        lwp_data.new_sched_switch_out(muestra)
        res.lwp_dico{pid_saliente} = lwp_data
    else:
        lwp_saliente = res.lwp_dico{pid_saliente}

        # Sanity check
        if lwp_saliente.last_sched_in == Timestamp(0,0):
            exit_error_logico(muestra.linea, muestra_ts_str, 
                              " PID " + str(pid_saliente) + " tiene 2 sched_out sin ningun sched_in")

        if not lwp_saliente.active:
            exit_error_logico(muestra.linea, muestra_ts_str, " PID " + str(pid_saliente) " sale del scheduler estando inactivo")

        if not lwp_saliente.en_hueco:
            # Tenemos un nuevo fragmento !!
            fragmento = Fragmento()
            fragmento.comienzo = lwp_saliente.last_sched_in
            fragmento.latency = fragmento.comienzo - lwp_saliente.last_wakeup

            if len(lwp_saliente.fragmentos) > 0:
                fragmento_previo = lwp_saliente.fragmentos[-1]
                fragmento.separacion = fragmento.comienzo - fragmento_previo.comienzo

            fragmento.cpus.append(muestra.cpu)

            # Actualizamos datos en el lwp
            lwp.last_wakeup = Timestamp(0,0)

        else:
            # Estamos en hueco, sacamos el fragmento de la lista
            # de fragmentos para actualizarlo
            fragmento = lwp_saliente.fragmentos.pop(-1)

            if not muestra.cpu in fragmento.cpus:
                fragmento.cpus.append(muestra.cpu)

        # Comun (para actualizacion y para nuevo)
        fragmento.duracion = muestra.ts - fragmento_comienzo
        
        # Agnadimos el fragmento a la lista del LWP
        lwp_saliente.fragmentos.append(fragmento)

        # Actualizamos datos del LWP
        lwp_saliente.total_exec += (muestra.ts - lwp_saliente.last_sched_in)
        lwp_saliente.last_sched_out = muestra.ts
        lwp_saliente.last_sched_in = Timestamp(0,0)
        lwp_saliente.active = False
        lwp_saliente.state = glb.state_num_to_char{muestra.param.prev_state}

    # Tratamiento del PID entrante #
    # -----------------------------#

    # Podemos estar en 3 estados:
    # -  Primer fragmento:  No hay last_sched_out, puede haber (o no) last_wakeup
    # -  Hueco:  Hay sched_out y el espacio_vacio < granularity
    # -  Nuevo fragmento:  Se termino el "estado hueco" si lo habia y empezamos un nuevo fragmento


    if not pid_entrante in res.lwp_dico:
        # Nuevo pid entrante.  Estado nuevo
        lwp_data = Lwp_data()
        lwp_data.new_sched_switch_in(muestra)
        res.lwp_dico{next_pid} = lwp_data
    else:
        lwp_entrante = res.lwp_dico{pid_entrante}

        # Sanity checks
        if lwp_entrante.active :
            exit_error_logico(muestra.linea, muestra_ts_str, 
                              " PID " + str(pid_entrante) + " tiene 1 sched_in estando ya activo")
        
        if ( not lwp_entrante.last_sched_out == Timestamp(0,0) ) and (lwp_entrante.last_wakeup == Timestamp(0,0) ):
            exit_error_logico(muestra.linea, muestra_ts_str, 
                              " PID " + str(pid_entrante) + " tiene un periodo sched_out y sched_in sin wakeup en medio")


        # Vemos la distancia respecto al ultimo sched_out y 
        # definimos si estamos en hueco o no
        if  muestra.ts - lwp_entrante.last_sched_out > inp.granularity :
            # El espacio vacio es mayor que el hueco, luego empezamos
            # un nuevo fragmento.
            lwp_entrante.en_hueco = False
            lwp_entrante.latency = muestra.ts - lwp_entrante.last_wakeup
        else:
            # Estamos en hueco
            lwp_entrante.en_hueco = True
            fragmento = lwp_saliente.fragmentos.pop(-1)
            fragmento.hueco += (muestra.ts - lwp_entrante.last_sched_out)

            
            

    

       trace-cmd-20674 [002] 1031300.401990: sched_switch:          prev_comm=trace-cmd prev_pid=20674 prev_prio=120 prev_state=0x1 next_comm=trace-cmd next_pid=20679 next_prio=120
    
#    if ( not muestra.param.prev_pid



    print "Procesando sched_switch con",
    print "nr_linea: " + str(muestra.nr_linea) + " ts_str " + muestra.ts_str + " linea: " + muestra.linea

def procesa_sched_wakeup(muestra):
    print "Procesando sched_wakeup con",
    print "nr_linea: " + str(muestra.nr_linea) + " ts_str " + muestra.ts_str + " linea: " + muestra.linea

def procesa_sched_migrate_task(muestra):
    print "Procesando sched_migrate_task con",
    print "nr_linea: " + str(muestra.nr_linea) + " ts_str " + muestra.ts_str + " linea: " + muestra.linea


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

def statenum2statechar(state_num):
    
             
def exit_error_logico(nr_linea, ts_str, mensaje):
    print "Linea " + str(nr_linea) + " TS " + ts_str + ": " + mensaje



if __name__ == '__main__':
    main()
