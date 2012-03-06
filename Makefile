
##
## Makefile
##  
## Made by Ismael Ripoll
## Login   <iripollfredes.disca.upv.es>
##
## Started on  Fri Jun 23 13:24:07 2006 Ismael Ripoll
## Last update Sun Nov  8 19:35:00 2009 Miguel Telleria de Esteban
## 
##############################
# Complete this to make it ! #
##############################
NAME 	= caracterizacion_workload_cpu.pdf
CLEANUP = *.log *.toc *.dvi *.aux *. *.out *.idx *~ *.revt *.dist *.bbl *.blg *.lot *.lof *.ilg *.ind *.bak
TODOS   = $(wildcard *.tex) $(wildcard *.bib) $(wildcard *.sty) $(wildcard *.cls)

.SUFFIXES: .pdf .tex

##############################
# Basic Compile Instructions #
##############################

all:	$(NAME)

$(NAME): $(TODOS)
	pdflatex  $$(basename $(NAME) .pdf) &&  	\
	pdflatex  $$(basename $(NAME) .pdf) \
	pdflatex  $$(basename $(NAME) .pdf) 


# 	pdflatex  $$(basename $(NAME) .pdf) &&  	\

# 	pdflatex  $$(basename $(NAME) .pdf) \
# 	bibtex $$(basename $(NAME) .pdf) && \
# 	pdflatex  $$(basename $(NAME) .pdf) 



clean:
	@exec echo -e "\n>> Cleaning... ";
	@find \( -name '*.[oa]' -or -name '*~' -or -name '*.log' -or -name '*.toc' \
            -or -name '*.dvi' -or -name '*.aux' -or -name '*.out' -or -name '*.idx' \
	        -or -name '*.revt' -or -name '*.dist' -or -name '*.bbl' -or -name '*.blg' \
            -or -name '*.lot' -or -name '*.lof' -or -name '*.ilg' -or -name '*.ind' \
	        -or -name '*.bak' -or -name '*.backup' \) -print -delete
	@exec echo ">> [OK]"


distclean: clean
	rm -f $(NAME)

################
# Dependencies #
################
