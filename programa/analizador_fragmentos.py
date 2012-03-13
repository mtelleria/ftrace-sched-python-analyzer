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
#    report_filename = 'report.txt'
    report_filename = 'trace_cte_report.txt'
    first_record = -1
    last_record = -1
#    granularity = 5
    granularity = 30

class res:
    lwp_dico = {}
    cpu_dico = {}
    ts_first = None # Timestamp absoluto
    ts_last = None # Timestamp absoluto


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
        ms_int = self.sg*1000 + self.us/1000
        ms_frac = self.us % 1000
        res = "%d.%03d" % (ms_int, ms_frac)
        return res

    def to_us(self):
        return self.us + self.sg*1000000

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

        

class Muestra:
    def __init__(self):
        self.nr_linea = 0
        self.linea = ""
        self.ts_str = ""
        self.evento = ""
        self.subsys = ""
        self.ts = Timestamp()
        self.basecmd = ""
        self.pid = -1
        self.cpu = -1
        self.param = []

    def escribe(self):
        print ("nr_linea: " + str(self.nr_linea) + " evento: " + self.evento + " subsys: " + self.subsys,
               " ts: " + str(self.ts.sg) + "." + str(self.ts.us) + " basecmd: " + self.basecmd,
               " pid: " + str(self.pid) + " CPU " + str(self.cpu) + " param: " + str(self.param) )
    
class Fragmento:
    def __init__(self):
        self.comienzo = Timestamp()
        self.duracion = Timestamp()
        self.cpus = [ ]
        self.hueco = Timestamp()
        self.max_hueco = Timestamp()
        self.separacion = Timestamp()
        self.latencia = Timestamp()
        self.pid = 0

class Lwp_data:

    def __init__(self):
        # Estaticos
        self.basecmd = ""
        self.pid = 0
        # Dinamicos
        self.state = "S"
    
        # As infered by us
        self.activo = False
        self.en_hueco = False
    
        self.last_wakeup = Timestamp(0, 0)
        self.last_sched_in = Timestamp(0, 0)
        self.last_sched_out = Timestamp(0, 0)

        self.fragmentos = []
        self.total_exec = {} # Index by CPU

        for cpuid in res.cpu_dico.keys() :
            self.total_exec[cpuid] = Timestamp(0, 0)
    
class Cpu_data:
    def __init__(self, cpuid = 0) :
        self.cpuid = cpuid
        self.total_exec = Timestamp(0, 0)
        self.total_idle = Timestamp(0, 0)
        self.nr_sched_switch = 0

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
        ts = Timestamp(string=ts_str)

        if type(res.ts_first) == type(None) :
            res.ts_first = ts
            res.ts_last = ts
        else :
            if ts < res.ts_last :
                exit_error_linea(nr_linea, ts_str, "Timestamp decreciente respecto a linea anterior")
            res.ts_last = ts


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
            
            print "%s%s" % ("WARNING: Linea " + str(nr_linea) + " Timestamp = " + ts_str,
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
        muestra.pid = int(muestra.pid)
        
        # Bloque CPU  ej: [001]
        cpu_str = bloques[1]
        muestra.cpu = int(cpu_str[1:-1])
        if not muestra.cpu in res.cpu_dico :
            nueva_cpu(muestra.cpu)

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
        
        #muestra.escribe()

        if evento == 'sched_switch':
            procesa_sched_switch(muestra)
        elif evento == 'sched_wakeup':
            procesa_sched_wakeup(muestra)
        elif evento == 'sched_migrate_task':
            procesa_sched_migrate_task(muestra)
        else:
            exit_error_linea(nr_linea, ts_str, "Error evento " + evento + " no soportado")

    # PRINT RESULT
    imprime_resultados()
            
# Esta funcion se llama en cuanto se descubre una nueva CPU en
# la traza.  En concreto se llama antes de procesar esa linea de
# la traza.
def nueva_cpu(cpuid) :
    # Cuando vemos una nueva CPU hacemos 2 cosas:
    # -  Una:  Agnadirla a res.cpu_dico
    # -  Dos:  A cada lwp agandir un indice a total_exec
    cpu_data = Cpu_data(cpuid)
    res.cpu_dico[cpuid] = cpu_data

    # Agnadimos una nueva clave en la total_exec de los lwp
    for lwp in res.lwp_dico.values():
        lwp.total_exec[cpuid] = Timestamp(0,0)
    



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
    
    # Hacemos la conversion de PID de swapper/idle
    pid_saliente = int(muestra.param["prev_pid"])
    if pid_saliente == 0 :
        pid_saliente = -1*muestra.cpu

    pid_entrante = int(muestra.param["next_pid"])
    if pid_entrante == 0 :
        pid_entrante = -1*muestra.cpu

    procesa_sched_out(pid_saliente, muestra)
    procesa_sched_in(pid_entrante, muestra)
    res.cpu_dico[muestra.cpu].nr_sched_switch += 1

# -----------------------------------------------------------

def procesa_sched_out(pid_saliente, muestra):

    # Tratamiento del PID saliente #
    # -----------------------------#
    if not pid_saliente in res.lwp_dico:
        # Nuevo PID saliente.  Esto sólo puede pasar al principio, con los threads
        # que se ejecutan en las CPU's en el momento de activar la traza.

        lwp_saliente = Lwp_data() # Esto pone por defecto todo a 0

        lwp_saliente.pid = pid_saliente
        lwp_saliente.basecmd = muestra.param["prev_comm"]
        res.lwp_dico[pid_saliente] = lwp_saliente

    else:
        lwp_saliente = res.lwp_dico[pid_saliente]

        # Sanity checks
        # -------------
        if lwp_saliente.basecmd != muestra.param["prev_comm"]:
            warning_error_logico(muestra, pid_saliente, "nuevo basecmdline, anterior: " 
                              + lwp_saliente.basecmd + " nuevo: " + muestra.param["prev_comm"])

        if lwp_saliente.last_sched_in == Timestamp(0,0):
            warning_error_logico(muestra, pid_saliente, "tiene 2 sched_out sin ningun sched_in")

        if not lwp_saliente.activo:
            warning_error_logico(muestra, pid_saliente, "sale del scheduler estando inactivo")

        if lwp_saliente.last_wakeup != Timestamp(0,0) and lwp_saliente.last_sched_in == Timestamp(0,0):
            warning_error_logico(muestra, pid_saliente, "wakeup y sched_out sin sched_in en medio")

        if pid_saliente != muestra.pid:
            warning_error_logico(muestra, pid_saliente, 
                              "el PID saliente no se corresponde con el PID de la muestra: " + muestra.pid)
            
        # Vemos si estamos en hueco o no (detectado por sched_in)
        if not lwp_saliente.en_hueco:
            # Tenemos un nuevo fragmento !!
            fragmento = Fragmento()
            fragmento.comienzo = lwp_saliente.last_sched_in
            if pid_saliente > 0 :
                fragmento.latencia = fragmento.comienzo - lwp_saliente.last_wakeup

            if len(lwp_saliente.fragmentos) > 0:
                fragmento_previo = lwp_saliente.fragmentos[-1]
                fragmento.separacion = fragmento.comienzo - fragmento_previo.comienzo
                
            fragmento.cpus.append(muestra.cpu)

        else:
            # Estamos en hueco, sacamos el fragmento de la lista
            # de fragmentos para actualizarlo
            fragmento = lwp_saliente.fragmentos.pop(-1)

            if not muestra.cpu in fragmento.cpus:
                fragmento.cpus.append(muestra.cpu)

        # Comun (para actualizacion y para nuevo)
        fragmento.duracion = muestra.ts - fragmento.comienzo
        
        # Agnadimos el fragmento a la lista del LWP
        lwp_saliente.fragmentos.append(fragmento)

        # Actualizamos datos del LWP
        chunk_exec = muestra.ts - lwp_saliente.last_sched_in
        lwp_saliente.total_exec[muestra.cpu] += chunk_exec
        lwp_saliente.last_sched_in = Timestamp(0,0)
        lwp_saliente.last_wakeup = Timestamp(0,0)
        
        if pid_saliente > 0 :
            res.cpu_dico[muestra.cpu].total_exec += chunk_exec
        else:
            res.cpu_dico[muestra.cpu].total_idle += chunk_exec


    # Acciones comunes para LWP nuevos y los conocidos
    lwp_saliente.last_sched_out = muestra.ts
    lwp_saliente.activo = False
    lwp_saliente.state = glb.state_num_to_char[muestra.param["prev_state"]]


# ------------------------------------------------------------

def procesa_sched_in(pid_entrante, muestra):

    # Podemos estar en 3 estados:
    # -  Primer fragmento:  No hay last_sched_out, puede haber (o no) last_wakeup
    # -  Hueco:  Hay sched_out y el espacio_vacio < granularity
    # -  Nuevo fragmento:  Se termino el "estado hueco" si lo habia y empezamos un nuevo fragmento
    if not pid_entrante in res.lwp_dico:
        # Nuevo pid entrante.  Estado nuevo
        lwp_entrante = Lwp_data()
        lwp_entrante.pid = pid_entrante
        lwp_entrante.basecmd = muestra.param["next_comm"]

        res.lwp_dico[pid_entrante] = lwp_entrante
    else:
        lwp_entrante = res.lwp_dico[pid_entrante]

        # Sanity checks
        if lwp_entrante.activo :
            warning_error_logico(muestra, pid_entrante, " tiene 1 sched_in estando ya activo")
        
        # Por alguna razon los procesos idle/swapper no tienen eventos wakeup
        if lwp_entrante > 0:
            if lwp_entrante.last_sched_out != Timestamp(0,0) and lwp_entrante.last_wakeup == Timestamp(0,0):
                warning_error_logico(muestra, pid_entrante, 
                                     "tiene un periodo sched_out y sched_in sin wakeup en medio")

        if  lwp_entrante.last_sched_in != Timestamp(0,0):
            warning_error_logico(muestra, pid_entrante, "tiene un dos sched_in seguidos sin sched_out en medio")

        # NOTA:  Este check es mas de la propia script que de
        #        los datos.
        if lwp_entrante.last_sched_out == Timestamp(0, 0) and len(lwp_entrante.fragmentos) > 0:
            warning_error_logico(muestra, pid_entrante, "sched_out es nulo pero tiene un fragmento anterior")


    # Miramos si somos los primeros y si estamos en hueco
    # ---------------------------------------------------
    if lwp_entrante.last_sched_out == Timestamp(0,0):
        # Primer arranque
        if lwp_entrante.last_wakeup != Timestamp(0,0):
            lwp_entrante.latencia = muestra.ts - lwp_entrante.last_wakeup
        else:
            # Nota:  Esto tambien incluye los idle/swapper
            lwp_entrante.latencia = Timestamp(0, 0) # Signalling that first latency is missing

    else:
        # Ya no es el primer arranque
        tiempo_vacio = muestra.ts - lwp_entrante.last_sched_out

        if (tiempo_vacio < inp.granularity):
            # Estamos en hueco
            lwp_entrante.en_hueco = True
            fragmento = lwp_entrante.fragmentos.pop(-1)
            fragmento.hueco += tiempo_vacio
            if tiempo_vacio > fragmento.max_hueco :
                fragmento.max_hueco = tiempo_vacio
            lwp_entrante.fragmentos.append(fragmento)
        else:
            # Una entrada normal ya no estamos en hueco
            lwp_entrante.en_hueco = False

            # Los PIDs de idle no tienen sched_wakeup
            if pid_entrante > 0 :
                lwp_entrante.latencia = muestra.ts - lwp_entrante.last_wakeup
                
    # Actualizamos campos comunes
    lwp_entrante.last_sched_in = muestra.ts
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

    pid_wakeup = int(muestra.param["pid"])

    if not pid_wakeup in res.lwp_dico:
        # Nuevo PID que se despierta
        lwp_wakeup = Lwp_data()
        lwp_wakeup.pid = pid_wakeup
        lwp_wakeup.basecmd = muestra.param["comm"]

        res.lwp_dico[pid_wakeup] = lwp_wakeup
    else:
        lwp_wakeup = res.lwp_dico[pid_wakeup]
        
        # Sanity check
        if lwp_wakeup.basecmd != muestra.param["comm"] :
            warning_error_logico(muestra, pid_wakeup, "sched_wakeup shows a different basecmd")

        if lwp_wakeup.last_sched_in != Timestamp(0,0):
            warning_error_logico(muestra, pid_wakeup, "sched_in y sched_wakeup sin sched_out en medio")

    lwp_wakeup.last_wakeup = muestra.ts

def procesa_sched_migrate_task(muestra):
    pass
#    print "Procesando sched_migrate_task con",
#    print "nr_linea: " + str(muestra.nr_linea) + " ts_str " + muestra.ts_str + " linea: " + muestra.linea




# -------------------------------------------------------------------------------------

def imprime_resultados():

    # Resultados globales
    # -------------------
    duracion_total = res.ts_last - res.ts_first
    print
    print "Fichero: %s   ts_init: %s,  ts_last: %s,  duracion (ms): %s" % (
          inp.report_filename, res.ts_first.to_msg(), res.ts_last.to_msg(), duracion_total.to_msg() )

    print "CPUs totales: %d   PID totales: %d" % ( len(res.cpu_dico), len(res.lwp_dico) )
    print
    print
    
    # Resultados por LWP
    # ------------------
    for pid in sorted (res.lwp_dico.keys()) :
        lwp = res.lwp_dico[pid]


        # Listado de fragmentos
        print "Estadisticas de PID %d basename %s" % (lwp.pid, lwp.basecmd)
        print "-----------------------------------------"
        print
        print "%10s %10s %10s %10s %10s %10s %10s %10s" % ("N Frag", "Start_ms", "Durac_ms", "CPUs", 
                                                           "Hueco_us", "Separ_ms", "Max_Hueco_us", "Laten_ms")

        # LWP que no han completado un fragmento son ignorados
        if len(lwp.fragmentos) == 0 :
            print "PID sin fragmentos completados"
            continue

        contador = 0
        for fragmento in lwp.fragmentos:
            contador += 1
            comienzo_ms = fragmento.comienzo.to_msg()
            duracion_ms = fragmento.duracion.to_msg()
            CPUs = ' '.join( map(str, fragmento.cpus))
            hueco_us = fragmento.hueco.us
            separacion_ms = fragmento.separacion.to_msg()
            max_hueco_us = fragmento.max_hueco.us
            latencia_ms = fragmento.latencia.to_msg()
            
            print "%10s %10s %10s %10s %10s %10s %10s %10s" % (contador, comienzo_ms, duracion_ms, CPUs,
                                                               hueco_us, separacion_ms, max_hueco_us, latencia_ms)

        # Datos del LWP por CPU
        for cpuid in res.cpu_dico.keys() :

            print "CPU %d:" % cpuid,
            fragmentos_cpu = filter( lambda frg : cpuid in frg.cpus, lwp.fragmentos)

            # Si no se ha usado se pone a 0 y se sigue
            if len(fragmentos_cpu) == 0 :
                print "Exec: 0  Pctg 0%"
                continue

            ts_first_cpu = fragmentos_cpu[0].comienzo
            ts_last_cpu = fragmentos_cpu[-1].comienzo + fragmentos_cpu[-1].duracion
            ts_duracion = ts_last_cpu - ts_first_cpu
            pcrg_cpu = 100.0*lwp.total_exec[cpuid].to_us()/ts_duracion.to_us()

            print "Exec: %s  Duracion: %s  Pct: %f" % (lwp.total_exec[cpuid].to_msg(), ts_duracion.to_msg(),
                                                       pcrg_cpu)
        
        # Dejamos una linea de separacion
        print

        
    # Dejamos 2 lineas de separacion
    print
    print

    # Resultados por CPU
    for cpu in res.cpu_dico.values() :
        duracion = cpu.total_exec + cpu.total_idle
        pcrg_ocupado = 100.0*cpu.total_exec.to_us()/duracion.to_us()

        print "CPU %d:  Total exec:  %s    Total_idle:  %s   Duraction %s   Pctg_ocupado: %f" % (cpu.cpuid,
            cpu.total_exec.to_msg(), cpu.total_idle.to_msg(), duracion.to_msg(), pcrg_ocupado)

        print



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


    
             
def warning_error_logico(muestra, pid, mensaje):
    print "WARNING: Linea " + str(muestra.nr_linea) + " TS: " + muestra.ts_str + " PID: " + str(pid) + ": " + mensaje
    


if __name__ == '__main__':
    main()
