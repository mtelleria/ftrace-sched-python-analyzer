#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import argparse
from timestamp import *

# TODO:
#
# - Implementar el filtrado de PIDs
# - Implementar el filtrado de CPUs
# - Implementar el filtrado de tiempo (rel y abs)
# - Implementar el filtrado de linea
#
# - Implementar funcionalidad info
#
# - Implementar autolanzado de trace-cmd report


# Analizador de fragmentos de trace-cmd
#
# Opciones:
#
# --info               Da solo datos generales del fichero (inicio, final, duracion,
#                      nr_pids, nr_cpus)
#
# --info_pids          Lista los pids y basecmds
#
# --file               Fichero de entrada.  Por defecto trace.dat
# --nobinfile          El fichero de entrada ya es de texto
#                      -  Incluye keep-text = True
# --keep-text          Mantiene el fichero de texto generado
#
#
# --pids=pid1,pid2,..  Procesa únicamente estos PIDs (por defecto todos)
#                      Si se da un PID por defecto process_idle is false
# --process_idle       Procesa también las idle-task (swapper)
# --cpus=cpu0, cpu1... Procesa únicamente estas CPU's
#
# --from_rel_ts_ms     Tiempo de inicio relativo en milisg
# --to_rel_ts_ms       Tiempo de final relativo en milisg
# --from_abs_ts_str    Tiempo inicial en timestamps_str
# --to_abs_ts_str      Tiempo_final en timestamps_str
# --from_linenr        Desde el numero de linea
# --to_linenr          Hasta el numero de linea
#
# --granularity_us     Granularidad



class res:
    lwp_dico = {}
    cpu_dico = {}
    ts_first = None # Timestamp absoluto
    ts_first_str = ""
    ts_last = None # Timestamp absoluto
    ts_last_str = ""

class glb:
    # Eventos que no pertenezcan a estos subsistemas son filtrados
    accepted_subsystems = ['sched']

    # Dentro de los aceptados, estos eventos son tambien ignorados
    discarded_events = ['sched_stat_runtime']
    discarded_events += ['sched_kthread_stop', 'sched_process_exit', 'sched_process_free',
                         'sched_process_fork', 'sched_wakeup_new', 'sched_wait_task',
                         'sched_process_wait', 'sched_kthread_stop_ret', 'sched_stat_wait',
                         'sched_stat_sleep', 'sched_stat_iowait']

    # Estos son los eventos procesados
    processed_events = ['sched_switch', 'sched_wakeup', 'sched_migrate_task', ]

    # Eventos dentro de los subsistemas que no son ni ignorados ni procesados 
    # provocan un warning

    # Obtenido de trace-cmd --events | less (y buscando sched_switch)
    state_num_to_char = {"0x0":'R', "0x1":'S', "0x2":"D", "0x4":"T", "0x8":"t", "0x10":"Z", 
                         "0x20":"X", "0x40":"x", "0x80":"W"}

    # From cmdline
    report_filename = 'trace_cte_report.txt'
    report_file = None
    keep_text_file = True
    granularity = None
    filtros = {}
    granularity = None
    mode = "p" # p for process, i for info
    info_pids = False
    info_cpus = False
    nr_linea_inicial = 0

class opt:
    filename = ""
    keep_text_file = True
    from_abs = ""
    to_abs = ""



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
        self.comienzo = Timestamp()       # Instante de comienzo   
        self.duracion = Timestamp()       # Duracion (ejecucion + hueco interno de granularidad)
        self.cpus = [ ]                   # CPU's en las que ejecuta
        self.hueco = Timestamp()          # Tiempo interno no ejecutado
        self.max_hueco = Timestamp()      # Maxima separacion interna (max granularidad)
        self.periodo = Timestamp()        # Entre el inicio del anterior y el inicio actual
        self.separacion = Timestamp()     # Entre el final del anterior y el final actual
        self.latencia = Timestamp()       # Entre el wakeup y el comienzo
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
        self.latencia = Timestamp(0, 0)
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


# Aqui se lleva todo


def main():

    # Parseamos los argumentos
    parsea_argv()

    # Abrimos el fichero y lo convertimos a texto si hace falta
    open_trace_file()

    if glb.mode == "p" :
        procesa_fichero()
        report_proceso()
    elif glb.mode == "i" :
        info_fichero()
        report_info()


# ---------------------------------------------------------------

#
# parsea argv
#
#--------------------------------------------------------------
def parsea_argv() :

    parser = argparse.ArgumentParser(description='Analiza trazas de trace-cmd/kernelshark.',
                                     epilog = 'cualquier opcion --info anula el modo procesamiento')

    parser.add_argument('--gran',
                        default = 30,
                        type = int,
                        help = 'Granularidad en usec para unir bloques de ejecucion')

    parser.add_argument('--file',
                        default = 'trace.dat',
                        help = 'Fichero a examinar.  Puede ser binario o texto, por defecto trace.dat')
    parser.add_argument('--keep-text',
                        action = 'store_true',
                        help = 'Mantener el fichero de texto autogenerado')

    parser.add_argument('--pids',
                        help = 'pid1,pid2,...,pidN:  Procesar unicamente los PIDs de la lista')
    parser.add_argument('--process-idle',
                        action='store_true',
                        help = 'Procesa ademas las tareas swapper (idle) de cada CPU')

    parser.add_argument('--cpus',
                        help = 'cpuid0,cpuid1,cpuid2...:  Procesar unicamente los eventos que ocurren en las CPUs de la lista')

    parser.add_argument('--from',
                        dest = 'from_rel',
                        help = 'Tiempo de comienzo relativo en milisegundos')
    parser.add_argument('--to',
                        dest = 'to_rel',
                        help = 'Tiempo de final relativo en milisegundos')
    parser.add_argument('--from-line',
                        help = 'Linea de fichero a partir de la cual se empieza a procesar')
    parser.add_argument('--to-line',
                        help = 'Linea de fichero hasta la cual se sigue procesando')
    parser.add_argument('--from-abs',
                        help = 'Tiempo de comienzo absoluto <segundos>.<usec>')
    parser.add_argument('--to-abs',
                        help = 'Tiempo de final absoluto <segundos>.<usec>')


    parser.add_argument('--info',
                        action = 'store_true',
                        help = 'Da datos globales del fichero:  inicio, final, duracion, nr_pids, nr_cpus, nr_lineas')

    parser.add_argument('--info-pids',
                        action = 'store_true',
                        help = 'Lista los PIDs con sus basecmd de los threads que tiene la traza')
    parser.add_argument('--info-cpus',
                        action = 'store_true',
                        help = 'Lista las CPUs que intervienen en la traza')


    args = parser.parse_args()

    opt.filename = args.file

    # temporal fix until trace-cmd report is added
    if opt.filename == "trace.dat" :
        opt.filename = 'trace_cte_report.txt'


    opt.keep_text_file = args.keep_text

    if args.info or args.info_pids or args.info_cpus :
        glb.mode = "i"
        glb.info_pids = args.info_pids
        glb.info_cpus = args.info_cpus
    else:
        glb.mode = "p"
        glb.granularity = Timestamp(0, args.gran)
        if (args.pids) :
            glb.filtros['pids'] = map( int, args.pids.split(',') )
            if (args.process_idle) :
                glb.filtros['idle'] = True

        if (args.cpus) :
            glb.filtros['cpus'] = map( int, args.cpus.split(',') )

    if (args.from_rel) :
        glb.filtros['from_rel'] = Timestamp(string_ms=args.from_rel)

    if (args.to_rel) :
        glb.filtros['to_rel'] = Timestamp(string_ms=args.to_rel)

    if (args.from_abs) :
        opt.from_abs = Timestamp(string=args.from_abs)

    if (args.to_abs) :
        opt.to_abs = Timestamp(string=args.to_abs)

    if args.from_line :
        glb.filtros['from_line'] = int(args.from_line)
        glb.filtros['from_line_ts'] = Timestamp(0, -1)

    if args.to_line :
        glb.filtros['to_line'] = int(args.to_line)
        glb.filtros['to_line_ts'] = Timestamp(0, -1)


#
# open_trace_file()
#
# Esta funcion tiene la mision siguiente:
# *  Mirar si el fichero de entrada es binario y si es asi llamar a lanza_trace_cmd_report()
#    para generar el fichero de texto.
#
# *  Dejar el fichero de texto abierto y preparado para procesar lineas,
#
# *  Si el fichero de entrada ya es de texto pone glb.keep_text_file a true
#
# *  Al final de la funcion se ha de cumplir:
#    -  glb.report_filename contiene el nombre del fichero de traceado de TEXTO
#    -  glb.report_file contiene el file del fichero de traceado
#    -  El glb.report_file esta abierto y apuntando a la primera linea
#    -  glb.nr_linea_inicial contiene la ultima linea procesada
# --------------------------------------------------------------------------
def open_trace_file() :

    report_file = open(opt.filename, "rb")
    # investigate if it is a binary or text file
    first_twenty_bytes = report_file.read(20)
    report_file.close()

    first_three_bytes = first_twenty_bytes[0:3]
    first_seven_bytes = first_twenty_bytes[0:7]
    
    
    if first_three_bytes == '\x17\x08\x044' :
        # magic value of trace.dat file (see man trace-cmd-dat)
        glb.keep_text_file = opt.keep_text_file
        lanza_trace_cmd_report()
        abre_y_consume_header()
    elif first_seven_bytes == 'version' :
        glb.report_filename = opt.filename
        glb.keep_text_file = True
        abre_y_consume_header()
    else :
        # Se supone que el fichero se compone de lineas con el header
        # eliminado (ej copia directa de tracing/trace
        binario = False
        for michar in first_twenty_bytes :
            if ord(michar) < 0x20 :
                if ord(michar) != 0x0a and ord(michar) != 0x09 and ord(michar) != 0x0d :
                    binario = True
            elif ord(michar) > 127 :
                binario = True
            
            if binario :
                print "Fichero binario incompatible"
                exit(-1)

        # Vistos los primeros 20 bytes concluimos que es un fichero de texto
        # y por tanto parseable
        glb.report_filename = opt.filename
        glb.keep_text_file = True
        glb.report_file = open(glb.report_filename, "r")
        glb.nr_linea_inicial = 0


def abre_y_consume_header() :

    glb.report_file = open(glb.report_filename, "r")
    # First contains version = 6
    glb.report_file.readline()
    
    # Second line contains CPU=N
    linea_cpu = glb.report_file.readline()
    glb.nr_linea_inicial = 2


#
# lanza_trace_cmd_report()
#
# El fichero de texto se ha de generar de la forma
#
#      trace-cmd report -r -i <fichero.dat> > report.txt
#
# La opción -r deshabilita los "plugins" que por defecto formatean 
# algunos eventos (ver el output de trace-cmd report -V).
#
# De esta forma todas las lineas tienen el mismo output
# independientemente del tipo de evento que sea.
# --------------------------------------------------------------
def lanza_trace_cmd_report():
    
    print ('La conversion de trace.dat binario a trace_report texto no esta implementada todavia')
    print ('Lance trace-cmd report -r <fichero.dat> para hacerlo usted mismo')
    exit(-1)
    
    # TBC


#
# parsea_fichero()
#
# Esta funcion abre el fichero de texto report ya generado y parsea
# las lineas llamando a diferentes funciones por cada evento
#
# Separando por espacios se obtiene:
#
#   BLOQUE-PROCESO-EJECUTANDO  [CPU] TIMESTAMP:  EVENTO:  PAR1=VAL1 PAR2=VAL2 PAR3=VAL3 ...

# -----------------------------------------------------------------
def procesa_fichero():

    nr_linea = glb.nr_linea_inicial

    # Bucle de lineas generales
    for linea in glb.report_file:
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
            res.ts_first_str = ts_str
            res.ts_last = ts
            res.ts_last_str = ts_str

            if opt.from_abs :
                glb.filtros['from_abs'] = opt.from_abs - res.ts_first

            if opt.to_abs :
                glb.filtros['to_abs'] = opt.to_abs - res.ts_first

        else :
            if ts < res.ts_last :
                exit_error_linea(nr_linea, ts_str, "Timestamp decreciente respecto a linea anterior")
            res.ts_last = ts

        # Pasamos ts a valor RELATIVO
        ts = ts - res.ts_first

        # Filtramos por tiempo
        if 'from_rel' in glb.filtros :
            if ts < glb.filtros['from_rel'] : continue

        if 'to_rel' in glb.filtros :
            if ts > glb.filtros['to_rel'] : continue

        if 'from_abs' in glb.filtros :
            if ts < glb.filtros['from_abs'] : continue

        if 'to_abs' in glb.filtros :
            if ts > glb.filtros['to_abs'] : continue

        # Filtramos por nr_linea
        if 'from_line' in glb.filtros :
            if nr_linea < glb.filtros['from_line'] : continue
            if nr_linea == glb.filtros['from_line'] : glb.filtros['from_line_ts'] = ts
                
        if 'to_line' in glb.filtros :
            if nr_linea > glb.filtros['to_line'] : continue
            if nr_linea == glb.filtros['to_line'] : glb.filtros['to_line_ts'] = ts


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
        muestra.ts = ts

        # Bloque PID  ej:  trace-cmd-20674
        [muestra.basecmd, separador, muestra.pid] = bloques[0].rpartition('-')
        if separador == "":
            exit_error_linea(nr_linea, ts_str, "Imposible separar basecmdline y PID")
        muestra.pid = int(muestra.pid)
        
        # Bloque CPU  ej: [001]
        cpu_str = bloques[1]
        muestra.cpu = int(cpu_str[1:-1])

        if 'cpus' in glb.filtros and muestra.cpu not in glb.filtros['cpus'] :
            # Filtramos por CPU
            continue

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
        if 'idle' in glb.filtros :
            if pid_saliente not in glb.filtros['pids'] :
                glb.filtros['pids'].append(pid_saliente)

    pid_entrante = int(muestra.param["next_pid"])
    if pid_entrante == 0 :
        pid_entrante = -1*muestra.cpu
        if 'idle' in glb.filtros :
            if pid_entrante not in glb.filtros['pids'] :
                glb.filtros['pids'].append(pid_entrante)

    procesa_saliente = False
    procesa_entrante = False
    if 'pids' in glb.filtros :
        if pid_saliente in glb.filtros['pids'] :
            procesa_saliente = True
        if pid_entrante in glb.filtros['pids'] :
            procesa_entrante = True
    else :
        procesa_saliente = True
        procesa_entrante = True

    if procesa_saliente :
        procesa_sched_out(pid_saliente, muestra)
    
    if procesa_entrante :
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
            fragmento.latencia = lwp_saliente.latencia
            lwp_saliente.latencia = Timestamp(0, 0)

            if len(lwp_saliente.fragmentos) > 0:
                fragmento_previo = lwp_saliente.fragmentos[-1]
                fragmento.periodo = fragmento.comienzo - fragmento_previo.comienzo
                fragmento.separacion = fragmento.periodo - fragmento_previo.duracion
                
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
#        lwp_saliente.last_wakeup = Timestamp(0,0)
        
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
            lwp_entrante.last_wakeup = Timestamp(0,0)
        else:
            # Nota:  Esto tambien incluye los idle/swapper
            lwp_entrante.latencia = Timestamp(0,-1) # Signalling that first latency is missing

    else:
        # Ya no es el primer arranque
        tiempo_vacio = muestra.ts - lwp_entrante.last_sched_out

        if (tiempo_vacio < glb.granularity):
            # Estamos en hueco
            lwp_entrante.en_hueco = True
            fragmento = lwp_entrante.fragmentos.pop(-1)
            fragmento.hueco += tiempo_vacio
            if tiempo_vacio > fragmento.max_hueco :
                fragmento.max_hueco = tiempo_vacio
            lwp_entrante.fragmentos.append(fragmento)

            if lwp_entrante.last_wakeup != Timestamp(0,0) :
                warning_error_logico(muestra, pid_entrante, "se ha ignorado un wakeup previo en hueco")
                lwp_entrante.last_wakeup = Timestamp(0,0)
        else:
            # Una entrada normal ya no estamos en hueco
            lwp_entrante.en_hueco = False
            # Los PIDs de idle no tienen sched_wakeup
            if lwp_entrante.last_wakeup != Timestamp(0,0) :
                # El sched_in es debido a un desbloqueo
                lwp_entrante.latencia = muestra.ts - lwp_entrante.last_wakeup
                lwp_entrante.last_wakeup = Timestamp(0, 0)
            else:
                # El sched in es debido a una vuelta de preemption
                # el proceso no se bloqueo por lo que no consideramos la latencia
                lwp_entrante.latencia = Timestamp(0, -1)
                
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

    if 'pids' in glb.filtros and not pid_wakeup in glb.filtros['pids'] :
        # Filtramos por pid
        return

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

def report_proceso():

    # Resultados globales de la traza
    # -------------------------------
    duracion_total = res.ts_last - res.ts_first
    print
    print "Fichero: %s   ts_init: %s,  ts_last: %s,  duracion (ms): %s" % (
          opt.filename, res.ts_first_str, res.ts_last_str, duracion_total.to_msg() )

    print "CPUs totales: %d   PID totales: %d" % ( len(res.cpu_dico), len(res.lwp_dico) )

    
    # Datos de entrada
    # ----------------
    print "Granularidad us: %d " % (glb.granularity.us )

    if len(glb.filtros) > 0 :
        print "FILTRANDO: ",
        if 'pids' in glb.filtros :
            print " PIDs: ",
            print glb.filtros['pids'],

        if 'cpus' in glb.filtros :
            print " CPUs: ",
            print glb.filtros['cpus'],

        if 'from_rel' in glb.filtros :
            print " From_rel: %s " % (glb.filtros['from_rel'].to_msg() ),
        
        if 'to_rel' in glb.filtros :
            print " To_rel:  %s " % (glb.filtros['to_rel'].to_msg() ),

        if 'from_abs' in glb.filtros :
            print " From_abs: %s (%s) " % (opt.from_abs, glb.filtros['from_abs'].to_msg() ),
        
        if 'to_abs' in glb.filtros :
            print " To_abs:  %s (%s)" % (opt.to_abs, glb.filtros['to_rel'].to_msg() ),

        if 'from_line' in glb.filtros :
            print " From_line: %d (%s)" % (glb.filtros['from_line'], glb.filtros['from_line_ts'].to_msg()),
        
        if 'to_line' in glb.filtros :
            print "To line: %d (%s)" % (glb.filtros['to_line'], glb.filtros['to_line_ts'].to_msg()),

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
        print "%10s %10s %10s %10s %10s %10s %10s %10s %10s" % ("N Frag", "Start_ms", "Durac_ms", "CPUs", 
                                                           "Hueco_ms", "Periodo_ms", "Separ_ms", "Max_Hueco_ms", "Laten_ms")

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
            hueco_ms = fragmento.hueco.to_msg()
            periodo_ms = fragmento.periodo.to_msg()
            separacion_ms = fragmento.separacion.to_msg()
            max_hueco_ms = fragmento.max_hueco.to_msg()
            latencia_ms = fragmento.latencia.to_msg()
            
            print "%10s %10s %10s %10s %10s %10s %10s %10s %10s" % (contador, comienzo_ms, duracion_ms, CPUs,
                                                               hueco_ms, periodo_ms, separacion_ms, 
                                                               max_hueco_ms, latencia_ms)

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

        # Puede haber CPU's que no tengan ningun fragmento
        if duracion == Timestamp(0,0):
            continue

        pcrg_ocupado = 100.0*cpu.total_exec.to_us()/duracion.to_us()

        print "CPU %d:  Total exec:  %s    Total_idle:  %s   Duraction %s   Pctg_ocupado: %f" % (cpu.cpuid,
            cpu.total_exec.to_msg(), cpu.total_idle.to_msg(), duracion.to_msg(), pcrg_ocupado)

        print

# ----------------------------------------------------

def info_fichero() :
    print "Funcionalidad de info aun no implementada"
    
def report_info() :
    print "Reporte de info aun no implementado"

# ----------------------------------------------------


def equal_asignments_to_dico(props):
    res = {}

    # detectamos strings sin '=' que significa que son apendices de la
    # anterior.
    #
    # ej: ['comm=dconf', 'worker', 'pid=4704', 'prio=120', 'success=1', 'target_cpu=0']
    #
    # tiene que pasar a
    # ej: ['comm=dconf worker', 'pid=4704', 'prio=120', 'success=1', 'target_cpu=0']

    props_con_espacios = []
    for prop in props :
        if prop.find('=') >= 0 :
            props_con_espacios.append(prop)
        else :
            previous_prop = props_con_espacios.pop(-1)
            previous_prop += (' ' + prop)
            props_con_espacios.append(previous_prop)

    for prop in props_con_espacios:
        [key, val] = prop.split('=')
        res[key] = val

    return res


def exit_error_linea(nr_linea, ts_str, mensaje):
    print "Linea " + str(nr_linea) + " TS " + ts_str + ": " + mensaje
    exit(-1)


    
             
def warning_error_logico(muestra, pid, mensaje):
    print "WARNING:  Linea: %d  TS_ABS: %s  TS_REL: %s  PID: %d  : %s" % (muestra.nr_linea,
                                                                          muestra.ts_str,
                                                                          muestra.ts.to_msg(),
                                                                          pid,
                                                                          mensaje)
    


if __name__ == '__main__':
    main()
