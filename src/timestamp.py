# -*- coding: utf-8 -*-
class Timestamp:

    def __init__(self, sg=0, us=0, string="", string_ms=""):
        if string != "":
            [sg_str, us_str] = string.split('.')
            self.sg = int(sg_str)
            self.us = int(us_str)
            
        elif string_ms != "":
            self.sg = 0
            self.us = 0
            if string_ms.find('.') >= 0 :
                [ms_str, us_str] = string_ms.split('.')
                if ms_str:
                    self.sg = int(ms_str) / 1000
                    self.us = (int(ms_str) % 1000) * 1000
                if us_str:
                    self.us += int(us_str)
            else :
                # No hay . entonces son todo msg
                self.sg = int(string_ms) / 1000
                self.us = (int(string_ms) % 1000) * 1000
        else:
            self.sg = sg
            self.us = us
        

    def stcopy(self, uno):
        otro = Timestamp()
        otro.sg = uno.sg
        otro.us = uno.us
        return otro

    def to_msg(self):
        if self.sg < 0 or self.us < 0 :
            signo = -1
        else :
            signo = 1

        ms_int = abs(self.sg)*1000 + abs(self.us)/1000
        ms_frac = abs(self.us) % 1000
        if (signo == -1) :
            res = "-%d.%03d" % (ms_int, ms_frac)
        else :
            res = "%d.%03d" % (ms_int, ms_frac)
        return res

    def to_sg_us_str(self) :
        res = "%d.%d" % (self.sg, self.us)
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
