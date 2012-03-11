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


class Timestamp:

    def __init__(self, sg=0, us=0, string=""):
        if string != "":
            [sg_str, us_str] = string.split('.')
            self.sg = int(sg_str)
            self.us = int(us_str)
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

    def __init__(self):
        # Estaticos
        basecmd = ""
        pid = 0

        # Dinamicos
        state = "S"
    
        # As infered by us
        active = False
        en_hueco = False
    
        last_wakeup = Timestamp(0, 0)
        last_sched_in = Timestamp(0, 0)
        last_sched_out = Timestamp(0, 0)

        fragmentos = []

        total_exec = Timestamp(0, 0)
        total_hueco = Timestamp(0, 0)
    


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
        
        if res.ts_first.sg == 0:
            res.ts_first = Timestamp(string=ts_str)

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
        muestra.ts = Timestamp(string=ts_str) - res.ts_first

        # Bloque PID  ej:  trace-cmd-20674
        [muestra.basecmd, separador, muestra.pid] = bloques[0].rpartition('-')
        if separador == "":
            exit_error_linea(nr_linea, ts_str, "Imposible separar basecmdline y PID")

        # Bloque CPU  ej: [001]
        cpu_str = bloques[1]
        muestra.cpu = int(cpu_str[1:-1])
        muestra.param = equal_asignments_to_dico(bloques[4:])
        
        # Problema con la IDLE-task (swapper).  Es una tarea especial ya que:
        #
        # -  Tiene 2 basecmd:  <idle> y swapper/0, swapper/1, swapper/2
        # -  Puede ejecutar en varias CPU's A LA VEZ (ya que no ejecuta nada)
        # -  Las swapper de todos los cores comparten el mismo PID
        #
        # DECISION:  Cambiar el PID a:
        # -  swapper/0 --> 0
        # -  swapper/1 --> -1
        # -  swapper/2 --> -2
        #
        # En nuestro programa, swapper es el único lwp que cambia de PID cuando
        # pasa a otra CPU.

        if muestra.pid == 0 :
            muestra.pid = -1 * muestra.cpu
            muestra.basecmd = "swapper/" + str(muestra.cpu)
        
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

# sched_switch tiene los siguientes params:
#
# -  prev_comm
# -  prev_pid
# -  prev_prio
# -  prev_state
# -  next_comm
# -  next_pid
# -  next_prio
# ------------------------------------------    
def procesa_sched_switch(muestra):
    
    pid_saliente = muestra.param["prev_pid"]
    if pid_saliente == 0 :
        pid_saliente = -1*muestra.cpu

    pid_entrante = muestra.param["next_pid"]
    if pid_entrante == 0 :
        pid_entrante = -1*muestra.cpu


    # Hacemos la conversion de PID de swapper/idle


    # Tratamiento del PID saliente #
    # -----------------------------#
    if not pid_saliente in res.lwp_dico:
        # Nuevo PID saliente
        lwp_saliente = Lwp_data() # Esto pone por defecto todo a 0

        lwp_saliente.pid = pid_saliente
        lwp_saliente.basecmd = muestra.param["prev_comm"]

        lwp_saliente.state = glb.state_num_to_char[muestra.param["prev_state"]]
        lwp_saliente.active = False
        
        lwp_saliente.last_sched_out = muestra.ts
        lwp_saliente.last_wakeup = Timestamp()
        lwp_saliente.last_sched_in = Timestamp()
        lwp_saliente.last_sched_out = muestra.ts
        lwp_saliente.total_exec = Timestamp()
        lwp_saliente.total_hueco = Timestamp()

        res.lwp_dico[pid_saliente] = lwp_saliente

    else:
        lwp_saliente = res.lwp_dico[pid_saliente]

        # Sanity checks
        # -------------
        if lwp_saliente.basecmd != muestra.param["prev_comm"]:
            exit_error_logico(muestra, pid_saliente, "nuevo basecmdline, anterior: " 
                              + lwp_saliente.basecmd + " nuevo: " + muestra.param["prev_comm"])

        if lwp_saliente.last_sched_in == Timestamp(0,0):
            exit_error_logico(muestra, pid_saliente, "tiene 2 sched_out sin ningun sched_in")

        if not lwp_saliente.active:
            exit_error_logico(muestra, pid_saliente, "sale del scheduler estando inactivo")

        if lwp_saliente.last_wakeup != Timestamp(0,0) and lwp_saliente.last_sched_in == Timestamp(0,0):
            exit_error_logico(muestra, pid_saliente, "wakeup y sched_out sin sched_in en medio")

        if pid_saliente != muestra.pid:
            exit_error_logico(muestra, pid_saliente, 
                              "el PID saliente no se corresponde con el PID de la muestra: " + muestra.pid)

        
            
        # Vemos si estamos en hueco o no (detectado por sched_in)
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
        lwp_saliente.state = glb.state_num_to_char[muestra.param["prev_state"]]

    # Tratamiento del PID entrante #
    # -----------------------------#

    # Podemos estar en 3 estados:
    # -  Primer fragmento:  No hay last_sched_out, puede haber (o no) last_wakeup
    # -  Hueco:  Hay sched_out y el espacio_vacio < granularity
    # -  Nuevo fragmento:  Se termino el "estado hueco" si lo habia y empezamos un nuevo fragmento
    if not pid_entrante in res.lwp_dico:
        # Nuevo pid entrante.  Estado nuevo
        lwp_entrante = Lwp_data()
        lwp_entrante.pid = pid_entrante
        lwp_entrante.basecmd = muestra.param["next_comm"]

        lwp_entrante.active = True
        lwp_entrante.last_sched_in = muestra.ts

        res.lwp_dico[pid_entrante] = lwp_entrante
    else:
        lwp_entrante = res.lwp_dico[pid_entrante]

        # Sanity checks
        if lwp_entrante.active :
            exit_error_logico(muestra, pid_entrante, " tiene 1 sched_in estando ya activo")
        
        
        if lwp_entrante.last_sched_out != Timestamp(0,0) and lwp_entrante.last_wakeup == Timestamp(0,0):
            exit_error_logico(muestra, pid_entrante, "tiene un periodo sched_out y sched_in sin wakeup en medio")

        if  lwp_entrante.last_sched_in == Timestamp(0,0):
            exit_error_logico(muestra, pid_entrante, "tiene un dos sched_in seguidos sin sched_out en medio")

        # NOTA:  Este check es mas de la propia script que de
        #        los datos.
        if lwp_entrante.last_sched_out == Timestamp(0, 0) and len(lwp_entrante.fragmentos) > 0:
            exit_error_logico(muestra, pid_entrante, "sched_out es nulo pero tiene un fragmento anterior")


        # Miramos si estamos somos los primeros y si estamos en hueco
        # -----------------------------------------------------------
        if lwp_entrante.last_sched_out == Timestamp(0,0):
            # Primer arranque
            if lwp_entrante.last_wakeup != Timestamp(0,0):
                lwp_entrante.latency = muestra.ts - lwp_entrante.last_wakeup
            else:
                lwp_entrante.latency = -1 # Signalling that first latency is missing

        else:
            tiempo_vacio = timestamp.ts - lwp_entrante.last_sched_out

            if (tiempo_vacio < inp.granularity):
                # Estamos en hueco
                lwp_entrante.en_hueco = True
                fragmento = lwp_entrante.fragmentos.pop(-1)
                fragmento.hueco += tiempo_vacio
                lwp_entrante.total_hueco += tiempo_vacio
                lwp_entrante.fragmentos.append(fragmento)
            else:
                # Una entrada normal ya no estamos en hueco
                lwp_entrante.en_hueco = False
                lwp_entrante.latency = muestra.ts - lwp_entrante.last_wakeup
                
        # Actualizamos campos comunes
        lwp_entrante.last_sched_in = timestamp.ts
        lwp_entrante.activo = True
        lwp_entrante.last_sched_out = Timestamp(0,0)
    

# sched_wakeup tiene los siguientes params:
#
# -  comm
# -  pid
# -  prio
# -  success
# -  target_cpu

def procesa_sched_wakeup(muestra):

    if not muestra.param["pid"] in res.lwp_dico:
        # Nuevo PID que se despierta
        lwp_wakeup = Lwp_data()
        lwp_wakeup.pid = muestra.param["pid"]
        lwp_wakeup.basecmd = muestra.param["conn"]

        res.lwp.dico[muestra.param["pid"]] = lwp_wakeup
    else:
        lwp_wakeup = res.lwp_dico[muestra.param["pid"]]
        
        # Sanity check
        if lwp_wakeup.basecmd != muestra.param["comm"] :
            exit_error_logico(muestra, muestra.param["pid"], "sched_wakeup shows a different basecmd")

        if lwp_wakeup.last_sched_in != Timestamp(0,0):
            exit_error_logico

    lwp_wakeup.last_wakeup = muestra.ts

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


    
             
def exit_error_logico(muestra, pid, mensaje):
    print "Linea " + str(muestra.nr_linea) + " TS: " + muestra.ts_str + "PID: " + pid + ": " + mensaje



if __name__ == '__main__':
    main()
